import asyncio
import json
from fastapi import HTTPException, Request
from pydantic import ValidationError
from app.reports.models import ReportInput
from app.core.serialization import MAX_CONTEXT_BYTES


class ReportIngestionHandler:
    def __init__(self, auth, usage, reports, queries=None):
        self._auth, self._usage, self._reports = auth, usage, reports
        self._queries = queries

    def register(self, router):
        router.add_api_route(
            "/api/reports", self.submit, methods=["POST"], status_code=202
        )
        router.add_api_route(
            "/api/reports/{identifier}", self.report_status, methods=["GET"]
        )

    async def submit(self, request: Request):
        try:
            data = ReportInput.model_validate(await limited_json(request))
        except ValidationError:
            raise HTTPException(400, "Invalid report fields.") from None
        return await asyncio.to_thread(self._reports.record, request.state.user, data)

    def report_status(self, request: Request, identifier: str):
        report = self._reports.get(identifier)
        if report["user_id"] != request.state.user.id:
            raise KeyError("Report not found")
        return {
            key: report[key]
            for key in ["id", "status", "collection_status", "created_at"]
        }


async def limited_json(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_CONTEXT_BYTES:
            raise HTTPException(413, "Report context is too large.")
    try:
        return json.loads(body)
    except ValueError:
        raise HTTPException(400, "A valid JSON report is required.") from None
