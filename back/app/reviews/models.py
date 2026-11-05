from pydantic import BaseModel, ConfigDict, Field


class ReviewAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=0, strict=True)
    correct: bool = Field(strict=True)


class ReviewStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_round: bool = False
    content: dict | None = None
