from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from app.documents.models import Document


@dataclass(frozen=True, slots=True)
class InspectedUpload:
    filename: str
    suffix: str
    media_type: str
    page_count: int | None


class UploadInspectorPort(Protocol):
    def inspect(self, filename: str, data: bytes, owner_id: str) -> InspectedUpload: ...


class SourceDocuments(Protocol):
    def document(self, identifier: str, owner_id: str) -> Document: ...
    def path(self, identifier: str, owner_id: str) -> Path: ...


class DocumentRepositoryPort(SourceDocuments, Protocol):
    def documents(self, owner_id: str) -> list[Document]: ...
    def store(
        self, upload: InspectedUpload, data: bytes, owner_id: str
    ) -> Document: ...
