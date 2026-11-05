from dataclasses import dataclass
from typing import Callable, Literal, Protocol
from pydantic import Field
from app.documents.models import Document
from app.study.contract import MAX_ITEMS, StrictModel, GeneratedContent

GENERATION_SECONDS = 150
Progress = Callable[[dict], None]


class ContextSelection(StrictModel):
    document_id: str
    pages: list[int] | None = Field(default=None, min_length=1, max_length=100)


class GenerateRequest(StrictModel):
    document_id: str | None = None
    pages: list[int] | None = Field(default=None, min_length=1, max_length=100)
    context: list[ContextSelection] = Field(default_factory=list, max_length=6)
    comment: str = Field(default="", max_length=4000)
    mode: Literal["flashcards", "problems"]
    count: int = Field(default=4, ge=1, le=MAX_ITEMS)
    difficulty: int = Field(default=3, ge=1, le=5, strict=True)


@dataclass
class InputDocument:
    document: Document
    data: bytes
    filename: str
    role: str
    pages: list[int] | None
    label: str = ""


class ProviderResult(StrictModel):
    content: GeneratedContent
    provider: str
    model: str
    insufficient_source: bool = False


class StudyProvider(Protocol):
    async def generate(
        self,
        documents: list[InputDocument],
        system: str,
        task: str,
        *,
        count: int,
        mode: Literal["flashcards", "problems"],
    ) -> ProviderResult: ...


class GenerationError(Exception):
    """A safe, user-facing provider failure, without credentials or request bodies."""


class ContentValidationError(GenerationError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
