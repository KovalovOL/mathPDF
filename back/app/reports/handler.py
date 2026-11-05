import logging

logger = logging.getLogger(__name__)
from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError
from app.core.observability.diagnostics import ClientDiagnostic


class DiagnosticsHandler:
    def __init__(self, client_reports):
        self._client_reports = client_reports

    def register(self, router):
        router.add_api_route(
            "/api/client-errors", self.client_error, methods=["POST"], status_code=204
        )

    async def client_error(self, request: Request):
        if not self._client_reports.allow(request.state.user.id):
            return Response(status_code=204)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 4096:
                raise HTTPException(413, "Diagnostic report exceeds the size limit.")
        try:
            report = ClientDiagnostic.model_validate_json(bytes(data))
        except ValidationError:
            raise HTTPException(422, "Invalid diagnostic report.") from None
        logger.warning("Browser API failure report=%s", report.model_dump_json())
        return Response(status_code=204)
