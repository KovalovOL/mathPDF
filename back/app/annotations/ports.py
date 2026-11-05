from dataclasses import dataclass
from typing import Protocol
from pathlib import Path
from app.documents.models import Document
from app.annotations.models import AnnotationData


@dataclass(frozen=True, slots=True)
class AnnotationSavePlan:
    target: str
    original: Document
    expected_revision: int
    state: dict
    data: AnnotationData
    binary: bytes
    digest: str
    stored_name: str
    created_at: str

    @property
    def revision(self) -> int:
        return self.expected_revision + 1


class AnnotationRepositoryPort(Protocol):
    def load(self, original_id: str, owner_id: str) -> dict | None: ...
    def persist(
        self, plan: AnnotationSavePlan, owner_id: str
    ) -> tuple[str, str | None]: ...


class AnnotationRendererPort(Protocol):
    def render(
        self, source: Path, data: AnnotationData, identifier: str, revision: int
    ) -> bytes: ...
