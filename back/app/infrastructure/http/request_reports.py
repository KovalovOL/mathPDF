"""HTTP incident delivery adapter; persistence failures never replace the response."""

import asyncio
import logging
from app.reports.models import ReportInput
from app.infrastructure.http.request_capture import HttpExchange
from app.infrastructure.http.frontend import build_id

logger = logging.getLogger(__name__)


class RequestReports:
    def __init__(self, app, reports):
        self._app, self._reports = app, reports

    async def __call__(self, scope, receive, send):
        if not self._target(scope):
            return await self._app(scope, receive, send)
        exchange = HttpExchange(scope, receive, send, build_id())
        try:
            await self._app(scope, exchange.receive, exchange.send)
        finally:
            if exchange.should_record:
                await self._persist(
                    exchange.user,
                    exchange.event(),
                    exchange.status,
                    exchange.reference,
                    exchange.is_quota,
                )

    async def _persist(self, user, event, status, reference, quota):
        try:
            await asyncio.to_thread(self._reports.event, user, event)
        except Exception as error:
            logger.warning(
                "Request report persistence unavailable type=%s", type(error).__name__
            )
        if status < 400 or quota:
            return
        try:
            request = ReportInput(
                origin="automatic",
                request_id=reference,
                context={"server": event},
            )
            await asyncio.to_thread(self._reports.record, user, request)
        except Exception as error:
            logger.warning("Automatic report unavailable type=%s", type(error).__name__)

    @staticmethod
    def _target(scope):
        path = scope.get("path", "")
        return (
            scope["type"] == "http"
            and path.startswith("/api/")
            and not path.startswith(("/api/reports", "/api/client-errors"))
        )
