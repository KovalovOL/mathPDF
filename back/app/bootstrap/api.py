from app.infrastructure.http.frontend import build_id
from app.infrastructure.documents.preparation import SelectedDocumentPreparation
from app.infrastructure.providers.prompts import PromptLoader
from app.generation.service import GenerationService
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from app.bootstrap.container import Services
from app.bootstrap.routing import register_handlers, register_errors
from app.application.use_cases.generate_study import GenerateStudy
from app.application.use_cases.record_incident import RecordIncident
from app.generation.jobs import GenerationJobs
from app.infrastructure.providers.openai import OpenAIProvider
from app.infrastructure.http.private_application import SecurityMiddleware
from app.infrastructure.http.request_diagnostics import DiagnosticMiddleware
from app.infrastructure.http.request_reports import RequestReports
from app.core.observability.diagnostics import configure_logging


class ApplicationRuntime:
    def __init__(self, services, provider):
        self._services = services
        self._provider = provider
        self._generation_lock = asyncio.Lock()
        self._export_lock = asyncio.Lock()
        self._generator = GenerateStudy(
            SelectedDocumentPreparation(services.documents),
            GenerationService(PromptLoader()),
            services.usage,
        )
        incidents = RecordIncident(services.users, services.reports)
        self._jobs = GenerationJobs(self._generator, self._generation_lock, incidents)

    @property
    def services(self):
        return self._services

    @property
    def provider(self):
        return self._provider

    @property
    def generation_lock(self):
        return self._generation_lock

    @property
    def export_lock(self):
        return self._export_lock

    @property
    def generator(self):
        return self._generator

    @property
    def jobs(self):
        return self._jobs

    @asynccontextmanager
    async def lifespan(self, app):
        configure_logging(build=build_id())
        logging.getLogger(__name__).info(
            "Application started", extra={"event": "application.started"}
        )
        try:
            yield
        finally:
            await self._jobs.close()


def create_app(data_dir: Path = Path(".formula-lab"), provider=None):
    load_dotenv(Path.cwd() / ".env", override=False)
    configure_logging(build=build_id())
    services = Services.create(data_dir)
    runtime = ApplicationRuntime(services, provider or configured_provider())
    app = FastAPI(
        title="Acadence", docs_url="/api/docs", redoc_url=None, lifespan=runtime.lifespan
    )
    app.state.services = services
    app.state.runtime = runtime
    app.state.auth = services.auth
    app.state.reviews = services.reviews
    register_handlers(app, runtime)
    register_errors(app)
    app.add_middleware(SecurityMiddleware, auth=services.auth)
    app.add_middleware(DiagnosticMiddleware)
    app.add_middleware(RequestReports, reports=services.reports)
    return app


def configured_provider():
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY", "")
    return (
        OpenAIProvider(key, os.getenv("OPENAI_MODEL", "gpt-4.1-mini")) if key else None
    )
