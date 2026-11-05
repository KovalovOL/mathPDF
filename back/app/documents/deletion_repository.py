from app.core.ports import PersistencePort
import hashlib, json
from app.documents.models import DeletionChanged


class DeletionRepository:

    def __init__(self, context: PersistencePort):
        self._context = context

    def _deletion_info(
        self, connection, kind: str, identifier: str, owner_id: str
    ) -> dict:
        table = "documents" if kind == "document" else "study_sets"
        row = connection.execute(
            f"SELECT * FROM {table} WHERE id=? AND owner_id=?", (identifier, owner_id)
        ).fetchone()
        if row is None:
            raise KeyError(
                "File not found" if kind == "document" else "Study set not found"
            )
        primary, context, copies = ([], [], [])
        document_ids = {identifier}
        if kind == "document":
            copies = [
                dict(copy)
                for copy in connection.execute(
                    "SELECT d.id,d.filename AS title,d.sha256\n                FROM document_edits e JOIN documents d ON d.id=e.document_id\n                WHERE e.original_document_id=? AND e.owner_id=? AND d.owner_id=?",
                    (identifier, owner_id, owner_id),
                )
            ]
            document_ids.update((copy["id"] for copy in copies))
            for saved in connection.execute(
                "SELECT id,title,payload FROM study_sets WHERE owner_id=?", (owner_id,)
            ):
                payload = json.loads(saved["payload"])
                if payload["document"]["id"] in document_ids:
                    primary.append({"id": saved["id"], "title": saved["title"]})
                elif any(
                    (
                        entry["document"]["id"] in document_ids
                        for entry in payload.get("context_documents", [])
                    )
                ):
                    context.append({"id": saved["id"], "title": saved["title"]})
        revision = self._revision(identifier, row, kind, copies, primary, context)
        return {
            "id": identifier,
            "title": row["filename"] if kind == "document" else row["title"],
            "revision": revision,
            "study_sets": primary,
            "context_sets": context,
            "edited_copies": copies,
            "document_ids": sorted(document_ids) if kind == "document" else [],
        }

    def deletion_info(self, kind: str, identifier: str, owner_id: str) -> dict:
        with self._context.connection() as connection:
            return self._deletion_info(connection, kind, identifier, owner_id)

    def delete(self, kind: str, identifier: str, owner_id: str, revision: str) -> dict:
        stored_names = []
        with self._context.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            impact = self._deletion_info(connection, kind, identifier, owner_id)
            if revision != impact["revision"]:
                raise DeletionChanged(
                    "Related content changed. Review the deletion again before confirming."
                )
            if kind == "study-set":
                connection.execute(
                    "DELETE FROM study_sets WHERE id=? AND owner_id=?",
                    (identifier, owner_id),
                )
                return ({"deleted_set_ids": [identifier]}, [])
            document_ids = set(impact["document_ids"])
            for document_id in document_ids:
                stored_names.append(
                    connection.execute(
                        "SELECT stored_name FROM documents WHERE id=? AND owner_id=?",
                        (document_id, owner_id),
                    ).fetchone()["stored_name"]
                )
            for entry in impact["study_sets"]:
                connection.execute(
                    "DELETE FROM study_sets WHERE id=? AND owner_id=?",
                    (entry["id"], owner_id),
                )
            self._detach_context(connection, impact, document_ids, owner_id)
            for document_id in document_ids:
                connection.execute(
                    "DELETE FROM document_edits WHERE document_id=? AND owner_id=?",
                    (document_id, owner_id),
                )
            for document_id in document_ids:
                connection.execute(
                    "DELETE FROM documents WHERE id=? AND owner_id=?",
                    (document_id, owner_id),
                )
        return (
            {
                "deleted_document_id": identifier,
                "deleted_document_ids": sorted(document_ids),
                "deleted_set_ids": [entry["id"] for entry in impact["study_sets"]],
                "detached_context_set_ids": [
                    entry["id"] for entry in impact["context_sets"]
                ],
            },
            stored_names,
        )

    def _revision(self, identifier, row, kind, copies, primary, context):
        revision = hashlib.sha256(
            json.dumps(
                [
                    identifier,
                    row["sha256"] if kind == "document" else row["payload"],
                    sorted(((copy["id"], copy["sha256"]) for copy in copies)),
                    sorted((entry["id"] for entry in primary)),
                    sorted((entry["id"] for entry in context)),
                ]
            ).encode()
        ).hexdigest()
        return revision

    def _detach_context(self, connection, impact, document_ids, owner_id):
        for entry in impact["context_sets"]:
            row = connection.execute(
                "SELECT payload FROM study_sets WHERE id=? AND owner_id=?",
                (entry["id"], owner_id),
            ).fetchone()
            payload = json.loads(row["payload"])
            payload["context_documents"] = [
                context
                for context in payload["context_documents"]
                if context["document"]["id"] not in document_ids
            ]
            connection.execute(
                "UPDATE study_sets SET payload=? WHERE id=? AND owner_id=?",
                (json.dumps(payload, ensure_ascii=False), entry["id"], owner_id),
            )
