from app.annotations.models import AnnotationData
from app.annotations.ports import AnnotationRepositoryPort
from app.documents.ports import SourceDocuments


class GetDocumentAnnotations:
    def __init__(
        self, documents: SourceDocuments, repository: AnnotationRepositoryPort
    ):
        self._documents, self._repository = documents, repository

    def execute(self, identifier: str, owner_id: str) -> dict:
        document = self._documents.document(identifier, owner_id)
        if document.media_type != "application/pdf":
            raise ValueError("Annotations are available for PDF files.")
        original = self._documents.document(
            document.original_document_id or identifier, owner_id
        )
        row = self._repository.load(original.id, owner_id)
        copy = self._documents.document(row["document_id"], owner_id) if row else None
        data = (
            AnnotationData.model_validate_json(row["payload"])
            if row and document.original_document_id
            else AnnotationData()
        )
        return {
            "document": document.model_dump(),
            "base_document": original.model_dump(),
            "copy_document": copy.model_dump() if copy else None,
            "revision": document.annotation_revision,
            "annotations": data.model_dump(mode="json"),
        }
