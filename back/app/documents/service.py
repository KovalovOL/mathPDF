"""Document operations depend on declared persistence and inspection ports."""

from pathlib import Path
from app.documents.models import Document
from app.documents.ports import DocumentRepositoryPort, UploadInspectorPort


class DocumentService:
    def __init__(
        self, repository: DocumentRepositoryPort, inspector: UploadInspectorPort
    ):
        self._repository = repository
        self._inspector = inspector

    def add_document(self, filename: str, data: bytes, owner_id: str) -> Document:
        inspected = self._inspector.inspect(filename, data, owner_id)
        return self._repository.store(inspected, data, owner_id)

    def document(self, identifier: str, owner_id: str) -> Document:
        return self._repository.document(identifier, owner_id)

    def documents(self, owner_id: str) -> list[Document]:
        return self._repository.documents(owner_id)

    def path(self, identifier: str, owner_id: str) -> Path:
        return self._repository.path(identifier, owner_id)
