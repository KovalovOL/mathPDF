"""Scoped correlation state shared by HTTP requests and background operations."""

from app.core.observability.diagnostics import (
    request_context,
    job_context,
    http_context,
)


class CorrelationScope:
    def __init__(self, request_id: str, job_id: str = "-", context: dict | None = None):
        self._request_id, self._job_id = request_id, job_id
        self._context = dict(context or {})

    def __enter__(self):
        self._request_token = request_context.set(self._request_id)
        self._job_token = job_context.set(self._job_id)
        self._http_token = http_context.set(self._context)
        return self

    def __exit__(self, kind, error, traceback):
        request_context.reset(self._request_token)
        job_context.reset(self._job_token)
        http_context.reset(self._http_token)
