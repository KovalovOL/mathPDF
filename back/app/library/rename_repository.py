from app.core.ports import PersistencePort
import json
from datetime import datetime, timezone
from pathlib import Path
from app.documents.models import RenameConflict

from app.documents.repository import DocumentRepository


class RenameRepository:
    def __init__(self, context: PersistencePort):
        self._context = context
        self._documents = DocumentRepository(context)

    def rename_item(self, kind, identifier, owner_id, request):
        name, table, column = self._rename_target(kind, request)
        with self._context.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT * FROM {table} WHERE id=? AND owner_id=?",
                (identifier, owner_id),
            ).fetchone()
            if not row:
                raise KeyError("Item not found")
            if (
                request.expected_name is not None
                and row[column] != request.expected_name
            ):
                raise RenameConflict(
                    "This name changed in another tab. Reopen Rename and try again."
                )
            if kind == "documents":
                if "/" in name or chr(92) in name or name in {".", ".."}:
                    raise ValueError("A file name cannot contain a path.")
                suffix = Path(row["filename"]).suffix
                if not name.lower().endswith(suffix.lower()):
                    name += suffix
                if len(name) > 200:
                    raise ValueError(
                        "Keep the complete file name within 200 characters."
                    )
                db.execute(
                    "UPDATE documents SET filename=? WHERE id=? AND owner_id=?",
                    (name, identifier, owner_id),
                )
            else:
                payload = json.loads(row["payload"])
                payload["title"] = name
                db.execute(
                    "UPDATE study_sets SET title=?,payload=?,updated_at=? WHERE id=? AND owner_id=?",
                    (
                        name,
                        json.dumps(payload, ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                        identifier,
                        owner_id,
                    ),
                )
        return (
            self._documents.document(identifier, owner_id).model_dump()
            if kind == "documents"
            else payload
        )

    def _rename_target(self, kind, request):
        if kind not in {"documents", "study-sets"}:
            raise KeyError("Item not found")
        name = request.name.strip()
        if not name or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError("Use a name with 1–200 printable characters.")
        table, column = (
            ("documents", "filename")
            if kind == "documents"
            else ("study_sets", "title")
        )
        return name, table, column
