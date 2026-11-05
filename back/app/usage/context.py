"""Task-local provider observations; no process-global service lookup."""

from contextvars import ContextVar
from typing import TypedDict
from app.usage.ports import UsageAttemptPort


class UsageTracking(TypedDict):
    store: UsageAttemptPort | None
    user_id: str
    request: dict
    attempt_id: str | None


usage_context: ContextVar[UsageTracking | None] = ContextVar(
    "mathpdf_usage", default=None
)
