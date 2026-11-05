from app.core.observability.context import CorrelationScope

"Short owner-scoped HTTP requests around a bounded in-process generator."
import asyncio
import logging
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4
from app.generation.models import GenerateRequest, GenerationError, StudyProvider
from app.study.contract import StudySet
from app.usage.quotas import QuotaExceeded
from app.core.observability.diagnostics import (
    job_context,
    log_exception,
    exception_summary,
    request_context,
    error_identity,
)


class GenerationBusy(Exception):
    pass


@dataclass
class GenerationJob:
    owner_id: str
    requested_count: int
    id: str = field(default_factory=lambda: uuid4().hex)
    request_id: str = field(default_factory=request_context.get)
    status: str = "running"
    phase: str = "preparing"
    accepted_count: int = 0
    attempt: int = 0
    result: StudySet | None = None
    error: str | None = None
    limit: dict | None = None
    finished_at: float | None = None
    task: asyncio.Task | None = None

    def progress(self, values: dict):
        for key in ("phase", "accepted_count", "attempt"):
            if key in values:
                setattr(self, key, values[key])

    def snapshot(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "status": self.status,
            "phase": self.phase,
            "accepted_count": self.accepted_count,
            "requested_count": self.requested_count,
            "attempt": self.attempt,
            "error": self.error,
            "limit": self.limit,
            "result": self.result if self.status == "completed" else None,
        }


class GenerationJobs:
    retention_seconds = 900
    max_finished = 20

    def __init__(self, generator, lock: asyncio.Lock, incidents):
        self._generator, self._lock, self._incidents = (generator, lock, incidents)
        self._jobs: dict[str, GenerationJob] = {}

    def prune(self):
        finished = sorted(
            (job for job in self._jobs.values() if job.finished_at is not None),
            key=lambda job: job.finished_at,
        )
        for index, job in enumerate(finished):
            if (
                monotonic() - job.finished_at > self.retention_seconds
                or index < len(finished) - self.max_finished
            ):
                self._jobs.pop(job.id, None)

    async def start(
        self, owner_id: str, selection: GenerateRequest, provider: StudyProvider
    ) -> GenerationJob:
        self.prune()
        if self._lock.locked():
            raise GenerationBusy(
                "A generation request is already running. Wait for it to finish or cancel it."
            )
        await self._lock.acquire()
        job = GenerationJob(owner_id, selection.count)
        self._jobs[job.id] = job
        logging.getLogger(__name__).info(
            "Study job created job_id=%s requested=%s mode=%s",
            job.id,
            selection.count,
            selection.mode,
        )
        job.task = asyncio.create_task(self.run(job, selection, provider))
        return job

    def get(self, job_id: str, owner_id: str) -> GenerationJob:
        self.prune()
        job = self._jobs.get(job_id)
        if job is None or job.owner_id != owner_id:
            raise KeyError(
                "Generation was interrupted or has expired. Start a new generation."
            )
        return job

    async def _run_job(
        self, job: GenerationJob, selection: GenerateRequest, provider: StudyProvider
    ):
        logger, token, failure_context, error_details = self._begin_job_log(job)
        try:
            job.result = await self._generator.execute(
                job.owner_id, selection, provider, job.progress
            )
            job.status = "completed"
            logger.info(
                "Study job completed requested=%s accepted=%s",
                job.requested_count,
                job.accepted_count,
            )
        except asyncio.CancelledError:
            job.status = "cancelled"
            logger.info(
                "Study job cancelled accepted=%s requested=%s",
                job.accepted_count,
                job.requested_count,
            )
        except QuotaExceeded as error:
            job.status, job.error, job.limit = ("failed", str(error), error.payload())
            logger.info("Study job limited reason=%s", error.reason)
        except (GenerationError, ValueError) as error:
            failure_context, error_details = self._generation_failure(
                job, error, logger
            )
        except KeyError:
            job.status, job.error = (
                "failed",
                "A selected file is no longer available. Reopen your library and try again.",
            )
        except Exception as error:
            failure_context = exception_summary(error)
            error_details = error_identity(error)
            job.status, job.error = (
                "failed",
                "Generation failed unexpectedly. Please try again.",
            )
            log_exception(logger, "Study job failed unexpectedly", error)
        finally:
            await self._finish_job(
                job, selection, failure_context, error_details, logger, token
            )

    async def cancel(self, job_id: str, owner_id: str) -> GenerationJob:
        job = self.get(job_id, owner_id)
        if job.status == "running":
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
            if job.finished_at is None:
                job.status, job.finished_at = ("cancelled", monotonic())
                self._lock.release()
        return job

    async def close(self):
        for job in list(self._jobs.values()):
            if job.status == "running":
                await self.cancel(job.id, job.owner_id)

    def _generation_failure(self, job, error, logger):
        failure_context = exception_summary(error)
        error_details = error_identity(error)
        job.status, job.error = ("failed", str(error))
        logger.warning(
            "Study generation failed", extra={"event": "study.failed", **error_details}
        )
        return (failure_context, error_details)

    def _begin_job_log(self, job):
        logger = logging.getLogger(__name__)
        token = job_context.set(job.id)
        logger.info("Study job started requested=%s", job.requested_count)
        failure_context = None
        error_details = None
        return (logger, token, failure_context, error_details)

    async def _finish_job(
        self, job, selection, failure_context, error_details, logger, token
    ):
        if job.status == "failed" and job.limit is None:
            try:
                await self._incidents.execute(
                    job, selection, failure_context, error_details
                )
            except Exception as error:
                logger.warning(
                    "Failed generation report unavailable type=%s", type(error).__name__
                )
        job.finished_at = monotonic()
        self._lock.release()
        self.prune()
        job_context.reset(token)

    async def run(self, job, selection, provider):
        with CorrelationScope(
            job.request_id,
            job.id,
            {"service": "app", "operation": "generation", "user_id": job.owner_id},
        ):
            await self._run_job(job, selection, provider)
