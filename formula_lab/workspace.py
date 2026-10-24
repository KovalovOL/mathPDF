"""Owner-scoped local documents and SQLite study-set persistence."""

import hashlib
import io
import json
import re
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pypdf import PdfReader


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MEDIA_TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown",
               ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp"}


class Document(BaseModel):
    id: str
    filename: str
    sha256: str
    media_type: str
    page_count: int | None
    size: int


class Workspace:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.files = self.directory / "documents"
        if self.files.is_symlink():
            raise ValueError("Managed document storage must not be a symbolic link.")
        self.files.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "workspace.sqlite3"
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            document_columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}
            set_columns = {row["name"] for row in connection.execute("PRAGMA table_info(study_sets)")}
            if ((document_columns and "owner_id" not in document_columns)
                    or (set_columns and "owner_id" not in set_columns)):
                # Explicitly authorized reset of the pre-authentication library.
                # Schema detection makes this one-time; owned data survives restarts.
                shutil.rmtree(self.files)
                self.files.mkdir()
                connection.execute("DROP TABLE IF EXISTS study_sets")
                connection.execute("DROP TABLE IF EXISTS documents")
            connection.execute("""CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, google_sub TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL, name TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
                    filename TEXT NOT NULL, sha256 TEXT NOT NULL,
                    media_type TEXT NOT NULL, page_count INTEGER, size INTEGER NOT NULL,
                    stored_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(owner_id, sha256)
                )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS study_sets (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL, mode TEXT NOT NULL,
                    item_count INTEGER NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )""")
            connection.execute("CREATE INDEX IF NOT EXISTS study_sets_owner ON study_sets(owner_id, updated_at)")

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add_document(self, filename: str, data: bytes, owner_id: str) -> Document:
        if not re.fullmatch(r"[a-f0-9]{32}", owner_id):
            raise ValueError("Invalid account identifier.")
        filename = Path(filename.replace("\\", "/")).name[:200]
        suffix = Path(filename).suffix.lower()
        media_type = MEDIA_TYPES.get(suffix)
        if not media_type:
            raise ValueError("Choose a PDF, TXT, Markdown, PNG, JPEG, or WebP file.")
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Each file must contain data and be no larger than 25 MB.")
        page_count = None
        if suffix == ".pdf":
            try:
                reader = PdfReader(io.BytesIO(data))
                if reader.is_encrypted:
                    raise ValueError("Password-protected PDFs are not supported.")
                page_count = len(reader.pages)
                if not page_count:
                    raise ValueError("The PDF has no pages.")
            except ValueError:
                raise
            except Exception:
                raise ValueError("This file could not be read as a PDF.") from None
        elif media_type.startswith("image/"):
            try:
                with Image.open(io.BytesIO(data)) as image:
                    expected = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[media_type]
                    if image.format != expected or image.width * image.height > 40_000_000:
                        raise ValueError("Use a valid image no larger than 40 megapixels.")
                    image.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                raise ValueError("This image could not be read.") from None
        else:
            if len(data) > 1024 * 1024:
                raise ValueError("Text context files must be no larger than 1 MB.")
            try:
                data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError("Save text and Markdown files as UTF-8.") from None
            if b"\x00" in data:
                raise ValueError("This file is not a supported text document.")
        digest = hashlib.sha256(data).hexdigest()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM documents WHERE owner_id=? AND sha256=?",
                                     (owner_id, digest)).fetchone()
            if row:
                return Document.model_validate(dict(row))
            identifier = uuid4().hex
            stored_name = f"{owner_id}/{digest}{suffix}"
            path = self.files / stored_name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                temporary = path.parent / f"{identifier}.upload"
                temporary.write_bytes(data)
                temporary.replace(path)
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("""INSERT INTO documents
                               (id,owner_id,filename,sha256,media_type,page_count,size,stored_name,created_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                               (identifier, owner_id, filename, digest, media_type, page_count, len(data), stored_name, now))
        return Document(id=identifier, filename=filename, sha256=digest, media_type=media_type,
                        page_count=page_count, size=len(data))

    def documents(self, owner_id: str) -> list[Document]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM documents WHERE owner_id=? ORDER BY created_at DESC, id",
                                      (owner_id,)).fetchall()
        return [Document.model_validate(dict(row)) for row in rows]

    def document(self, identifier: str, owner_id: str) -> Document:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id=? AND owner_id=?",
                                     (identifier, owner_id)).fetchone()
        if row is None:
            raise KeyError("Document not found")
        return Document.model_validate(dict(row))

    def path(self, identifier: str, owner_id: str) -> Path:
        with self.connection() as connection:
            row = connection.execute("SELECT stored_name FROM documents WHERE id=? AND owner_id=?",
                                     (identifier, owner_id)).fetchone()
        if row is None:
            raise KeyError("Document not found")
        path = (self.files / row["stored_name"]).resolve()
        if not path.is_relative_to(self.files) or not path.is_file():
            raise ValueError("The stored file is missing. Add it again.")
        return path

    def save_set(self, result: dict, owner_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as connection:
            cursor = connection.execute("""INSERT INTO study_sets
                (id,owner_id,title,mode,item_count,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, mode=excluded.mode,
                item_count=excluded.item_count, payload=excluded.payload, updated_at=excluded.updated_at
                WHERE study_sets.owner_id=excluded.owner_id""",
                (result["id"], owner_id, result["title"], result["mode"], len(result["items"]),
                 json.dumps(result, ensure_ascii=False), now, now))
            if cursor.rowcount != 1:
                raise KeyError("Study set not found")
        return result

    def sets(self, owner_id: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("""SELECT id,title,mode,item_count,created_at,updated_at
                                      FROM study_sets WHERE owner_id=? ORDER BY updated_at DESC""",
                                      (owner_id,)).fetchall()
        return [dict(row) for row in rows]

    def check_set_owner(self, identifier: str, owner_id: str):
        """Allow a new unsaved ID, but never reuse another account's saved ID."""
        with self.connection() as connection:
            foreign = connection.execute("SELECT 1 FROM study_sets WHERE id=? AND owner_id<>?",
                                         (identifier, owner_id)).fetchone()
        if foreign:
            raise KeyError("Study set not found")

    def study_set(self, identifier: str, owner_id: str) -> dict:
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM study_sets WHERE id=? AND owner_id=?",
                                     (identifier, owner_id)).fetchone()
        if row is None:
            raise KeyError("Study set not found")
        return json.loads(row["payload"])
