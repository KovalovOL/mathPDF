"""Correlated diagnostics without request bodies, secrets, or OAuth queries."""

import logging
import re
import time
import traceback
from collections import deque
from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


request_context = ContextVar("mathpdf_request", default="-")
job_context = ContextVar("mathpdf_job", default="-")
REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")


class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_context.get()
        record.job_id = job_context.get()
        return True


def configure_logging():
    logger = logging.getLogger("formula_lab")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    formatter = logging.Formatter(
        "%(asctime)sZ %(levelname)s request=%(request_id)s job=%(job_id)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    for handler in logger.handlers:
        handler.setFormatter(formatter)
        if not any(isinstance(item, CorrelationFilter) for item in handler.filters):
            handler.addFilter(CorrelationFilter())
    logger.setLevel(logging.INFO)
    logger.propagate = False


def correlation_id(value: str | None) -> str:
    return value if value and REQUEST_ID.fullmatch(value) else uuid4().hex


def route_label(path: str) -> str:
    if path.startswith("/api/"):
        path = re.sub(r"[a-f0-9]{32}|[a-f0-9-]{36}", "{id}", path)
        return path if re.fullmatch(r"/api/[A-Za-z0-9_/{}/.-]{1,160}", path) else "/api/other"
    if path.startswith("/static/"):
        return "/static/*"
    return path if path in {"/", "/workspace", "/login", "/auth/config", "/auth/logout",
                           "/auth/google/login", "/auth/google/callback"} else "/other"


def exception_summary(error: BaseException):
    # Exception messages can contain source content or credentials. Keep only
    # exception types and stack locations, including nested exception groups.
    def locations(exc, depth=0):
        frames = [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                  for frame in traceback.extract_tb(exc.__traceback__)[-16:]]
        details = [{"type": type(exc).__name__, "frames": frames}]
        if depth < 2:
            for child in getattr(exc, "exceptions", ())[:4]:
                details.extend(locations(child, depth + 1))
        return details
    return locations(error)


def log_exception(logger: logging.Logger, event: str, error: BaseException):
    logger.error("%s exceptions=%s", event, exception_summary(error))


class ClientDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["invalid_json", "unexpected_content_type", "network_error", "timeout", "http_error"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: str = Field(pattern=r"^/api/[A-Za-z0-9_/{}/.-]{1,160}$")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
    status: int | None = Field(default=None, ge=100, le=599)
    received_bytes: int | None = Field(default=None, ge=0, le=100 * 1024 * 1024)
    expected_bytes: int | None = Field(default=None, ge=0, le=100 * 1024 * 1024)
    content_type: str = Field(default="", max_length=80, pattern=r"^[A-Za-z0-9.+/-]*$")
    redirected: bool = False
    response_route: str = Field(default="/other", max_length=180, pattern=r"^/[A-Za-z0-9_/{}/.*-]*$")
    server_build: str | None = Field(default=None, pattern=r"^[a-f0-9]{12}$")
    client_build: str | None = Field(default=None, pattern=r"^[a-f0-9]{12}$")


class ClientReportLimit:
    def __init__(self):
        self.reports: dict[str, deque] = {}

    def allow(self, owner_id: str) -> bool:
        now = time.monotonic()
        for owner, reports in list(self.reports.items()):
            while reports and reports[0] < now - 60:
                reports.popleft()
            if not reports:
                del self.reports[owner]
        if owner_id not in self.reports and len(self.reports) >= 500:
            return False
        reports = self.reports.setdefault(owner_id, deque())
        if len(reports) >= 10:
            return False
        reports.append(now)
        return True
