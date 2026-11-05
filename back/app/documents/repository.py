from app.core.ports import PersistencePort
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from app.documents.models import Document
from app.documents.constants import DOCUMENT_SELECT


class DocumentRepository:
    def __init__(self, context: PersistencePort):
        self._context = context

    def store(self, upload, data: bytes, owner_id: str) -> Document:
        filename, suffix = upload.filename, upload.suffix
        media_type, page_count = upload.media_type, upload.page_count
        digest = hashlib.sha256(data).hexdigest()
        with self._context.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM documents WHERE owner_id=? AND sha256=?",
                (owner_id, digest),
            ).fetchone()
            if row:
                return Document.model_validate(dict(row))
            identifier = uuid4().hex
            stored_name = f"{owner_id}/{digest}{suffix}"
            self._context.storage.put("documents/" + stored_name, data, media_type)
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """INSERT INTO documents
                               (id,owner_id,filename,sha256,media_type,page_count,size,stored_name,created_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    identifier,
                    owner_id,
                    filename,
                    digest,
                    media_type,
                    page_count,
                    len(data),
                    stored_name,
                    now,
                ),
            )
        return Document(
            id=identifier,
            filename=filename,
            sha256=digest,
            media_type=media_type,
            page_count=page_count,
            size=len(data),
        )

    def documents(self, owner_id: str) -> list[Document]:
        with self._context.connection() as connection:
            rows = connection.execute(
                DOCUMENT_SELECT
                + " WHERE d.owner_id=? ORDER BY d.created_at DESC, d.id",
                (owner_id,),
            ).fetchall()
        return [Document.model_validate(dict(row)) for row in rows]

    def document(self, identifier: str, owner_id: str) -> Document:
        with self._context.connection() as connection:
            row = connection.execute(
                DOCUMENT_SELECT + " WHERE d.id=? AND d.owner_id=?",
                (identifier, owner_id),
            ).fetchone()
        if row is None:
            raise KeyError("Document not found")
        return Document.model_validate(dict(row))

    def path(self, identifier: str, owner_id: str) -> Path:
        with self._context.connection() as connection:
            row = connection.execute(
                "SELECT stored_name,sha256 FROM documents WHERE id=? AND owner_id=?",
                (identifier, owner_id),
            ).fetchone()
        if row is None:
            raise KeyError("Document not found")
        return self._context.storage.path(
            "documents/" + row["stored_name"], row["sha256"]
        )
