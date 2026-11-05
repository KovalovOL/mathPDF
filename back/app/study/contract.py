from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.documents.models import Document

MAX_ITEMS = 50


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    document_id: str | None = None
    page: int = Field(ge=1)
    line_start: int | None = Field(ge=1)
    line_end: int | None = Field(ge=1)
    quote: str | None = Field(max_length=1200)

    @model_validator(mode="after")
    def valid_lines(self):
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("Supply both line numbers or neither")
        if self.line_start is not None and self.line_end < self.line_start:
            raise ValueError("Line range must be ordered")
        return self


class TextBlock(StrictModel):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=8000)


class MathBlock(StrictModel):
    kind: Literal["math"]
    latex: str = Field(min_length=1, max_length=5000)
    display: bool
    source: Citation
    original_latex: str | None = Field(max_length=5000)
    change: str | None = Field(max_length=1000)

    @model_validator(mode="after")
    def valid_change(self):
        if self.original_latex == self.latex:
            self.original_latex = None
            self.change = None
        if (self.original_latex is None) != (self.change is None):
            raise ValueError(
                "A quiz variant needs its original formula and change description"
            )
        return self


Block = TextBlock | MathBlock

Skill = Literal[
    "recall",
    "meaning",
    "conditions",
    "application",
    "error_diagnosis",
    "why_justification",
    "counterexample",
    "comparison",
]


class StudyItem(StrictModel):
    goal_step: int | None = Field(default=None, ge=1, le=MAX_ITEMS)
    title: str = Field(min_length=1, max_length=180)
    skill: Skill | None = Field(default=None, exclude_if=lambda value: value is None)
    question: list[Block] = Field(min_length=1, max_length=40)
    from_notes: list[Block] | None = Field(
        default=None, max_length=40, exclude_if=lambda value: value is None
    )
    explanation: list[Block] | None = Field(
        default=None, max_length=40, exclude_if=lambda value: value is None
    )
    answer: list[Block] = Field(min_length=1, max_length=40)
    source: Citation | None = None


class GeneratedContent(StrictModel):
    items: list[StudyItem] = Field(max_length=MAX_ITEMS)
    notes: list[str] = Field(max_length=10)


class ContextSnapshot(StrictModel):
    document: Document
    pages: list[int] | None


class StudySet(GeneratedContent):
    # Unmarked historical records and browser drafts are version 1 as well.
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    title: str = Field(min_length=1, max_length=200)
    document: Document
    pages: list[int] = Field(min_length=1, max_length=100)
    context_documents: list[ContextSnapshot] = Field(default_factory=list, max_length=6)
    comment: str = Field(default="", max_length=4000)
    mode: Literal["flashcards", "problems"]
    difficulty: int = Field(default=3, ge=1, le=5, strict=True)
    metadata: dict
