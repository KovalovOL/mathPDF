from fastapi import Request
from app.generation.models import GENERATION_SECONDS, GenerateRequest
from app.study.contract import MAX_ITEMS


class GenerationHandler:
    def __init__(self, configured, allowance, jobs, start, cancel, generate):
        self._configured, self._allowance, self._jobs = configured, allowance, jobs
        self._start, self._cancel, self._generate = start, cancel, generate

    def register(self, router):
        router.add_api_route(
            "/api/generation/allowance", self.allowance, methods=["GET"]
        )
        router.add_api_route(
            "/api/generation/config", self.generation_config, methods=["GET"]
        )
        router.add_api_route("/api/study/generate", self.generate, methods=["POST"])
        router.add_api_route(
            "/api/study/jobs", self.start_generation, methods=["POST"], status_code=202
        )
        router.add_api_route(
            "/api/study/jobs/{job_id}", self.generation_status, methods=["GET"]
        )
        router.add_api_route(
            "/api/study/jobs/{job_id}", self.cancel_generation, methods=["DELETE"]
        )

    def allowance(self, request: Request):
        return self._allowance.status(request.state.user.id)

    def generation_config(self):
        return {
            "configured": self._configured,
            "max_pages": 100,
            "max_items": MAX_ITEMS,
            "max_context_files": 6,
            "max_upload_mb": 25,
            "default_document_id": None,
            "generation_timeout_seconds": GENERATION_SECONDS,
        }

    async def generate(self, request: Request, selection: GenerateRequest):
        return await self._generate.execute(request.state.user.id, selection)

    async def start_generation(self, request: Request, selection: GenerateRequest):
        return (await self._start.execute(request.state.user.id, selection)).snapshot()

    async def generation_status(self, request: Request, job_id: str):
        return self._jobs.get(job_id, request.state.user.id).snapshot()

    async def cancel_generation(self, request: Request, job_id: str):
        return (await self._cancel.execute(request.state.user.id, job_id)).snapshot()
