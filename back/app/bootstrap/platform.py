from app.infrastructure.http.frontend import build_id
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from app.bootstrap.container import Services
from app.bootstrap.routing import register_errors
from app.bootstrap.admin import create_admin_handler
from app.reports.ingestion_handler import ReportIngestionHandler
from app.infrastructure.http.gateway import GatewayHandler
from app.infrastructure.http.private_application import SecurityMiddleware
from app.infrastructure.http.request_diagnostics import DiagnosticMiddleware
from app.core.observability.diagnostics import configure_logging


class PlatformRuntime:
    def __init__(self, services, kind):
        self._services, self._kind = services, kind

    @asynccontextmanager
    async def lifespan(self, app):
        task = (
            asyncio.create_task(self._services.reports.worker())
            if self._kind == "reports"
            else None
        )
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


def create_service(kind, directory=None):
    if kind not in {"admin", "reports"}:
        raise ValueError("Unknown platform service")
    configure_logging(service=kind, build=build_id())
    s = Services.create(
        Path(directory or os.getenv("MATHPDF_DATA_DIR", ".formula-lab"))
    )
    runtime = PlatformRuntime(s, kind)
    app = FastAPI(
        title="MathPDF " + kind,
        docs_url=None,
        redoc_url=None,
        lifespan=runtime.lifespan,
    )
    app.state.services, app.state.auth = s, s.auth
    app.state.usage, app.state.reports = s.usage, s.reports
    handler = (
        create_admin_handler(s)
        if kind == "admin"
        else ReportIngestionHandler(s.auth, s.usage, s.reports)
    )
    handler.register(app)
    GatewayHandler(s.persistence, s.auth, s.documents, s.sets).register(app)
    register_errors(app)
    app.add_middleware(SecurityMiddleware, auth=s.auth)
    app.add_middleware(DiagnosticMiddleware, service=kind)
    return app


def admin_app():
    return create_service("admin")


def reports_app():
    return create_service("reports")
