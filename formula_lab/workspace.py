"""Local document adapter and SQLite study-set repository."""

import hashlib
import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pypdf import PdfReader


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# Content identity of the PDF automatically seeded by earlier application versions.
LEGACY_SAMPLE_SHA256 = "9e2c6389508da9cd771a0c52ceb06ee621bc2a5d410c99ca96668b5718b9d9b3"
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
        self.files.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "workspace.sqlite3"
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL,
                    media_type TEXT NOT NULL, page_count INTEGER, size INTEGER NOT NULL,
                    stored_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    hidden INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS study_sets (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, mode TEXT NOT NULL,
                    item_count INTEGER NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}
            if "hidden" not in columns:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("ALTER TABLE documents ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0")
                connection.execute("UPDATE documents SET hidden=1 WHERE sha256=?", (LEGACY_SAMPLE_SHA256,))

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add_document(self, filename: str, data: bytes) -> Document:
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
            row = connection.execute("SELECT * FROM documents WHERE sha256=?", (digest,)).fetchone()
            if row:
                connection.execute("UPDATE documents SET hidden=0 WHERE id=?", (row["id"],))
                return Document.model_validate(dict(row))
            identifier = uuid4().hex
            stored_name = f"{digest}{suffix}"
            path = self.files / stored_name
            if not path.exists():
                temporary = self.files / f"{identifier}.upload"
                temporary.write_bytes(data)
                temporary.replace(path)
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("""INSERT INTO documents
                               (id,filename,sha256,media_type,page_count,size,stored_name,created_at)
                               VALUES (?,?,?,?,?,?,?,?)""",
                               (identifier, filename, digest, media_type, page_count, len(data), stored_name, now))
        return Document(id=identifier, filename=filename, sha256=digest, media_type=media_type,
                        page_count=page_count, size=len(data))

    def documents(self) -> list[Document]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM documents WHERE hidden=0 ORDER BY created_at, id").fetchall()
        return [Document.model_validate(dict(row)) for row in rows]

    def document(self, identifier: str) -> Document:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError("Document not found")
        return Document.model_validate(dict(row))

    def path(self, identifier: str) -> Path:
        with self.connection() as connection:
            row = connection.execute("SELECT stored_name FROM documents WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError("Document not found")
        path = self.files / row["stored_name"]
        if not path.is_file():
            raise ValueError("The stored file is missing. Add it again.")
        return path

    def save_set(self, result: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as connection:
            connection.execute("""INSERT INTO study_sets VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, mode=excluded.mode,
                item_count=excluded.item_count, payload=excluded.payload, updated_at=excluded.updated_at""",
                (result["id"], result["title"], result["mode"], len(result["items"]),
                 json.dumps(result, ensure_ascii=False), now, now))
        return result

    def sets(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id,title,mode,item_count,created_at,updated_at FROM study_sets ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def study_set(self, identifier: str) -> dict:
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM study_sets WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError("Study set not found")
        return json.loads(row["payload"])
