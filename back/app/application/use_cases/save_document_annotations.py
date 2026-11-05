import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from app.annotations.models import AnnotationConflict, AnnotationData, AnnotationWrite
from app.annotations.ports import (
    AnnotationSavePlan,
    AnnotationRepositoryPort,
    AnnotationRendererPort,
)
from app.documents.models import Document
from app.documents.ports import SourceDocuments


class SaveDocumentAnnotations:
    def __init__(
        self,
        reader,
        documents: SourceDocuments,
        repository: AnnotationRepositoryPort,
        renderer: AnnotationRendererPort,
        cleanup,
    ):
        self._reader, self._documents, self._repository = reader, documents, repository
        self._renderer, self._cleanup = renderer, cleanup

    def execute(self, identifier: str, owner_id: str, request: AnnotationWrite) -> dict:
        plan = self._prepare(identifier, owner_id, request)
        filename, previous = self._repository.persist(plan, owner_id)
        if previous and previous != plan.stored_name:
            self._cleanup.execute([previous])
        document = Document(
            id=plan.target,
            filename=filename,
            sha256=plan.digest,
            media_type="application/pdf",
            page_count=plan.original.page_count,
            size=len(plan.binary),
            original_document_id=plan.original.id,
            annotation_revision=plan.revision,
        )
        return {
            "document": document.model_dump(),
            "base_document": plan.original.model_dump(),
            "copy_document": document.model_dump(),
            "revision": plan.revision,
            "annotations": plan.data.model_dump(mode="json"),
        }

    def _prepare(self, identifier, owner, request):
        state = self._reader.execute(identifier, owner)
        if not state["document"]["original_document_id"] and state["copy_document"]:
            raise AnnotationConflict(
                "An edited copy already exists. Open that copy to continue editing."
            )
        if request.expected_revision != state["revision"]:
            raise AnnotationConflict(
                "This edited copy changed in another tab. Your unsaved notes have been kept."
            )
        original = Document.model_validate(state["base_document"])
        data = AnnotationData.model_validate(
            request.model_dump(exclude={"expected_revision"})
        )
        target = (
            identifier if state["document"]["original_document_id"] else uuid4().hex
        )
        binary = self._renderer.render(
            self._documents.path(original.id, owner),
            data,
            target,
            request.expected_revision + 1,
        )
        digest = hashlib.sha256(binary).hexdigest()
        return AnnotationSavePlan(
            target,
            original,
            request.expected_revision,
            state,
            data,
            binary,
            digest,
            f"{owner}/{digest}.pdf",
            datetime.now(timezone.utc).isoformat(),
        )
