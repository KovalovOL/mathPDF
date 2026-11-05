"""A bounded ASGI tee that never buffers binary document transfers."""

import json
from time import perf_counter
from starlette.datastructures import Headers
from app.core.serialization import bounded, MAX_CONTEXT_BYTES
from app.core.observability.diagnostics import correlation_id, frontend_context


class HttpExchange:
    def __init__(self, scope, receive, send, build: str):
        self._scope, self._receive, self._send, self._build = (
            scope,
            receive,
            send,
            build,
        )
        self._headers = Headers(scope=scope)
        self._request_body, self._response_body = bytearray(), bytearray()
        self._response_headers = {}
        self._status = 500
        self._reference = None
        self._started = perf_counter()

    async def receive(self):
        message = await self._receive()
        if message[
            "type"
        ] == "http.request" and "application/json" in self._headers.get(
            "content-type", ""
        ):
            self._append(self._request_body, message.get("body", b""))
        return message

    async def send(self, message):
        if message["type"] == "http.response.start":
            self._status = message["status"]
            self._response_headers = dict(Headers(raw=message.get("headers", [])))
        if message[
            "type"
        ] == "http.response.body" and "application/json" in self._response_headers.get(
            "content-type", ""
        ):
            self._append(self._response_body, message.get("body", b""))
        await self._send(message)

    @property
    def user(self):
        return self._scope.get("state", {}).get("user")

    @property
    def should_record(self) -> bool:
        return self.user is not None and (
            self._scope["method"] not in {"GET", "HEAD"} or self._status >= 400
        )

    @property
    def status(self) -> int:
        return self._status

    @property
    def is_quota(self) -> bool:
        response = self._decode(self._response_body)
        return (
            self._status == 429
            and isinstance(response, dict)
            and response.get("code") == "generation_limit"
        )

    @property
    def reference(self) -> str:
        if self._reference is None:
            self._reference = correlation_id(
                self._response_headers.get("x-mathpdf-request-id")
                or self._headers.get("x-mathpdf-request-id")
            )
        return self._reference

    def event(self) -> dict:
        reference = self.reference
        return bounded(
            {
                "request_id": reference,
                "method": self._scope["method"],
                "path": self._scope["path"],
                "request": self._decode(self._request_body),
                "response": self._decode(self._response_body),
                "status": self._status,
                "exception": self._scope.get("state", {}).get("exception"),
                "error_details": self._scope.get("state", {}).get("error_details"),
                "ui": frontend_context(self._headers.get("x-mathpdf-ui-context")),
                "duration_ms": round((perf_counter() - self._started) * 1000),
                "server_build": self._build,
                "user_agent": self._headers.get("user-agent", "")[:500],
                "request_content_type": self._headers.get("content-type", ""),
                "response_content_type": self._response_headers.get("content-type", ""),
            }
        )

    @staticmethod
    def _append(target, data):
        if len(target) <= MAX_CONTEXT_BYTES:
            target.extend(data[: MAX_CONTEXT_BYTES + 1 - len(target)])

    @staticmethod
    def _decode(data):
        if not data:
            return None
        if len(data) > MAX_CONTEXT_BYTES:
            return {"_truncated": True, "reason": "HTTP JSON limit"}
        try:
            return json.loads(data)
        except (ValueError, UnicodeError):
            return {"_unreadable": True, "bytes": len(data)}
