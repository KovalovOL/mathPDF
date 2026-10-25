"""Short owner-scoped HTTP requests around a bounded in-process generator."""

import asyncio
import logging
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from .study import GenerateRequest, GenerationError, StudyProvider, StudySet, generate_study
from .workspace import Workspace


class GenerationBusy(Exception):
    pass


@dataclass
class GenerationJob:
    owner_id: str
    requested_count: int
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "running"
    phase: str = "preparing"
    accepted_count: int = 0
    attempt: int = 0
    result: StudySet | None = None
    error: str | None = None
    finished_at: float | None = None
    task: asyncio.Task | None = None

    def progress(self, values: dict):
        for key in ("phase", "accepted_count", "attempt"):
            if key in values:
                setattr(self, key, values[key])

    def snapshot(self):
        return {"id": self.id, "status": self.status, "phase": self.phase,
                "accepted_count": self.accepted_count, "requested_count": self.requested_count,
                "attempt": self.attempt, "error": self.error,
                "result": self.result if self.status == "completed" else None}


class GenerationJobs:
    retention_seconds = 900
    max_finished = 20

    def __init__(self, workspace: Workspace, lock: asyncio.Lock):
        self.workspace, self.lock = workspace, lock
        self.jobs: dict[str, GenerationJob] = {}

    def prune(self):
        finished = sorted((job for job in self.jobs.values() if job.finished_at is not None),
                          key=lambda job: job.finished_at)
        for index, job in enumerate(finished):
            if monotonic() - job.finished_at > self.retention_seconds or index < len(finished) - self.max_finished:
                self.jobs.pop(job.id, None)

    async def start(self, owner_id: str, selection: GenerateRequest, provider: StudyProvider) -> GenerationJob:
        self.prune()
        if self.lock.locked():
            raise GenerationBusy("A generation request is already running. Wait for it to finish or cancel it.")
        await self.lock.acquire()
        job = GenerationJob(owner_id, selection.count)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self.run(job, selection, provider))
        return job

    def get(self, job_id: str, owner_id: str) -> GenerationJob:
        self.prune()
        job = self.jobs.get(job_id)
        if job is None or job.owner_id != owner_id:
            raise KeyError("Generation was interrupted or has expired. Start a new generation.")
        return job

    async def run(self, job: GenerationJob, selection: GenerateRequest, provider: StudyProvider):
        logger = logging.getLogger(__name__)
        try:
            job.result = await generate_study(self.workspace, job.owner_id, selection, provider, job.progress)
            job.status = "completed"
            logger.info("Study job completed requested=%s accepted=%s", job.requested_count, job.accepted_count)
        except asyncio.CancelledError:
            job.status = "cancelled"
        except (GenerationError, ValueError) as error:
            job.status, job.error = "failed", str(error)
            logger.warning("Study job failed requested=%s accepted=%s error_type=%s",
                           job.requested_count, job.accepted_count, type(error).__name__)
        except KeyError:
            job.status, job.error = "failed", "A selected file is no longer available. Reopen your library and try again."
        except Exception as error:
            job.status, job.error = "failed", "Generation failed unexpectedly. Please try again."
            logger.error("Study job failed exception_type=%s", type(error).__name__)
        finally:
            job.finished_at = monotonic()
            self.lock.release()
            self.prune()

    async def cancel(self, job_id: str, owner_id: str) -> GenerationJob:
        job = self.get(job_id, owner_id)
        if job.status == "running":
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
            # A task cancelled before its first instruction never enters run's finally.
            if job.finished_at is None:
                job.status, job.finished_at = "cancelled", monotonic()
                self.lock.release()
        return job

    async def close(self):
        for job in list(self.jobs.values()):
            if job.status == "running":
                await self.cancel(job.id, job.owner_id)
