import logging
from time import perf_counter
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.observability.context import CorrelationScope
from app.core.observability.diagnostics import (
    correlation_id,
    route_label,
    frontend_context,
    REQUEST_ID,
    exception_summary,
    error_identity,
    log_exception,
)
from app.infrastructure.http.frontend import build_id

logger = logging.getLogger(__name__)


class DiagnosticMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service: str = "app"):
        super().__init__(app)
        self._service = service

    async def dispatch(self, request: Request, call_next):
        reference = correlation_id(request.headers.get("x-mathpdf-request-id"))
        request.state.request_id = reference
        route = route_label(request.url.path)
        job_id = (
            request.url.path.rsplit("/", 1)[-1]
            if route == "/api/study/jobs/{id}"
            else "-"
        )
        job_id = job_id if REQUEST_ID.fullmatch(job_id) else "-"
        context = {
            "service": self._service,
            "method": request.method,
            "route": route,
            "ui": frontend_context(request.headers.get("x-mathpdf-ui-context")),
        }
        quiet = route == "/api/client-errors" or (
            request.method == "GET" and route == "/api/study/jobs/{id}"
        )
        started = perf_counter()
        with CorrelationScope(reference, job_id, context):
            if route.startswith("/api/") and not quiet:
                logger.info(
                    "Request started",
                    extra={"event": "http.request_started", "build": build_id()},
                )
            response = await self._response(request, call_next, reference, route)
            response.headers.update(
                {"X-MathPDF-Request-ID": reference, "X-MathPDF-Build": build_id()}
            )
            self._completed(request, response, route, quiet, started)
            return response

    async def _response(self, request, call_next, reference, route):
        try:
            return await call_next(request)
        except Exception as error:
            request.state.exception = exception_summary(error)
            request.state.error_details = error_identity(error, route=route)
            log_exception(
                logger, f"HTTP exception method={request.method} route={route}", error
            )
            details = {
                k: v
                for k, v in request.state.error_details.items()
                if k in {"error_code", "summary"}
            }
            return JSONResponse(
                {
                    "detail": "An unexpected server error occurred. Use the reference to locate its logs.",
                    "request_id": reference,
                    **details,
                },
                status_code=500,
                headers={"Cache-Control": "no-store"},
            )

    def _completed(self, request, response, route, quiet, started):
        status = response.status_code
        if not route.startswith("/api/") and status < 400:
            return
        level = self._level(status, quiet)
        details = getattr(request.state, "error_details", None)
        if not details:
            details = (
                error_identity(route=route, status=status) if status >= 400 else {}
            )
        logger.log(
            level,
            "Request failed" if status >= 400 else "Request completed",
            extra={
                "event": (
                    "http.request_failed" if status >= 400 else "http.request_completed"
                ),
                "status": status,
                "content_type": response.headers.get("content-type", "-"),
                "response_bytes": response.headers.get("content-length"),
                "duration_ms": round((perf_counter() - started) * 1000),
                "build": build_id(),
                **details,
            },
        )

    @staticmethod
    def _level(status, quiet):
        if status >= 500:
            return logging.ERROR
        if status >= 400:
            return logging.WARNING
        return logging.DEBUG if quiet else logging.INFO
