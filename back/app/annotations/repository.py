from app.core.ports import PersistencePort
from pathlib import Path
from app.annotations.models import AnnotationConflict
from app.annotations.ports import AnnotationSavePlan


class AnnotationRepository:
    def __init__(self, context: PersistencePort):
        self._context = context

    def load(self, original_id: str, owner_id: str) -> dict | None:
        with self._context.connection() as db:
            row = db.execute(
                "SELECT * FROM document_edits WHERE original_document_id=? AND owner_id=?",
                (original_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def persist(
        self, plan: AnnotationSavePlan, owner_id: str
    ) -> tuple[str, str | None]:
        with self._context.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._check_revision(db, plan, owner_id)
            self._context.storage.put(
                "documents/" + plan.stored_name, plan.binary, "application/pdf"
            )
            if current:
                return self._update_copy(db, plan, owner_id)
            return self._insert_copy(db, plan, owner_id), None

    @staticmethod
    def _check_revision(db, plan, owner):
        if not db.execute(
            "SELECT 1 FROM documents WHERE id=? AND owner_id=?",
            (plan.original.id, owner),
        ).fetchone():
            raise KeyError("Document not found")
        current = db.execute(
            "SELECT * FROM document_edits WHERE original_document_id=? AND owner_id=?",
            (plan.original.id, owner),
        ).fetchone()
        if current and (
            current["document_id"] != plan.target
            or current["revision"] != plan.expected_revision
        ):
            raise AnnotationConflict(
                "This edited copy changed in another tab. Your unsaved notes have been kept."
            )
        if not current and plan.state["document"]["original_document_id"]:
            raise KeyError("Document not found")
        return current

    @staticmethod
    def _update_copy(db, plan, owner):
        previous = db.execute(
            "SELECT stored_name FROM documents WHERE id=? AND owner_id=?",
            (plan.target, owner),
        ).fetchone()["stored_name"]
        db.execute(
            "UPDATE documents SET sha256=?,size=?,stored_name=? WHERE id=? AND owner_id=?",
            (plan.digest, len(plan.binary), plan.stored_name, plan.target, owner),
        )
        db.execute(
            "UPDATE document_edits SET revision=?,payload=? WHERE document_id=? AND owner_id=?",
            (plan.revision, plan.data.model_dump_json(), plan.target, owner),
        )
        return plan.state["document"]["filename"], previous

    @staticmethod
    def _insert_copy(db, plan, owner):
        filename = f"{Path(plan.original.filename).stem[:170]} - annotated.pdf"
        db.execute(
            """INSERT INTO documents
            (id,owner_id,filename,sha256,media_type,page_count,size,stored_name,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                plan.target,
                owner,
                filename,
                plan.digest,
                "application/pdf",
                plan.original.page_count,
                len(plan.binary),
                plan.stored_name,
                plan.created_at,
            ),
        )
        db.execute(
            "INSERT INTO document_edits VALUES (?,?,?,?,?)",
            (
                plan.target,
                owner,
                plan.original.id,
                plan.revision,
                plan.data.model_dump_json(),
            ),
        )
        return filename
