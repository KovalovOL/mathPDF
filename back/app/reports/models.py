from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: Literal["automatic", "manual"] = "manual"
    category: Literal[
        "bug", "incorrect_content", "formatting", "too_slow", "answer_too_long", "other"
    ] = "bug"
    comment: str = Field(default="", max_length=5000)
    request_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    context: dict = Field(default_factory=dict)


class ReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["new", "investigating", "resolved"]
    note: str = Field(default="", max_length=5000)
