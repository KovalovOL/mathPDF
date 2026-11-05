from fastapi.responses import JSONResponse
from app.core.errors import ApplicationError
from app.documents.models import DeletionChanged, RenameConflict
from app.annotations.models import AnnotationConflict
from app.generation.models import GenerationError
from app.generation.jobs import GenerationBusy
from app.infrastructure.export.browser import ExportError
from app.usage.quotas import QuotaExceeded
from app.core.observability.diagnostics import error_identity, route_label


class ErrorHandlers:
    def register(self, app):
        for kind in [
            ApplicationError,
            ExportError,
            GenerationError,
            GenerationBusy,
            DeletionChanged,
            AnnotationConflict,
            RenameConflict,
            QuotaExceeded,
            ValueError,
            KeyError,
        ]:
            app.add_exception_handler(kind, self.handle)

    async def handle(self, request, error):
        status = self._status(error)
        request.state.error_details = error_identity(
            error, route=route_label(request.url.path), status=status
        )
        if isinstance(error, QuotaExceeded):
            request.state.error_details = {
                "error_code": "generation_limit",
                "summary": "The daily generation allowance cannot fit this request.",
            }
            return JSONResponse(error.payload(), status_code=429)
        detail = (
            str(error.args[0])
            if isinstance(error, KeyError) and error.args
            else str(error)
        )
        return JSONResponse({"detail": detail}, status_code=status)

    @staticmethod
    def _status(error):
        if isinstance(error, ApplicationError):
            return error.status_code
        if isinstance(error, QuotaExceeded):
            return 429
        if isinstance(error, (ExportError, GenerationError)):
            return 502
        if isinstance(
            error, (GenerationBusy, DeletionChanged, AnnotationConflict, RenameConflict)
        ):
            return 409
        return 404 if isinstance(error, KeyError) else 400
