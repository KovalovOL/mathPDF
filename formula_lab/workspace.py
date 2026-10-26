"""Owner-scoped local documents and SQLite study-set persistence."""

import hashlib
import io
import json
import logging
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

from .annotations import AnnotationConflict, AnnotationData, AnnotationWrite, annotated_pdf


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MEDIA_TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown",
               ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp"}


class DeletionChanged(Exception):
    """The user must review a changed deletion impact before confirming again."""


class Document(BaseModel):
    id: str
    filename: str
    sha256: str
    media_type: str
    page_count: int | None
    size: int
    original_document_id: str | None = None
    annotation_revision: int = 0


DOCUMENT_SELECT = '''SELECT d.*, e.original_document_id, COALESCE(e.revision,0) AS annotation_revision
                     FROM documents d LEFT JOIN document_edits e ON e.document_id=d.id AND e.owner_id=d.owner_id'''


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
            connection.execute('''CREATE TABLE IF NOT EXISTS document_edits (
                document_id TEXT PRIMARY KEY REFERENCES documents(id),
                owner_id TEXT NOT NULL REFERENCES users(id),
                original_document_id TEXT NOT NULL REFERENCES documents(id),
                revision INTEGER NOT NULL, payload TEXT NOT NULL,
                UNIQUE(owner_id,original_document_id))''')

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
            rows = connection.execute(DOCUMENT_SELECT+" WHERE d.owner_id=? ORDER BY d.created_at DESC, d.id",
                                      (owner_id,)).fetchall()
        return [Document.model_validate(dict(row)) for row in rows]

    def document(self, identifier: str, owner_id: str) -> Document:
        with self.connection() as connection:
            row = connection.execute(DOCUMENT_SELECT+" WHERE d.id=? AND d.owner_id=?",
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

    def annotation_state(self, identifier: str, owner_id: str) -> dict:
        document = self.document(identifier, owner_id)
        if document.media_type != 'application/pdf':
            raise ValueError('Annotations are available for PDF files.')
        original = self.document(document.original_document_id or identifier, owner_id)
        with self.connection() as connection:
            row = connection.execute('SELECT * FROM document_edits WHERE original_document_id=? AND owner_id=?',
                                     (original.id, owner_id)).fetchone()
        copy = self.document(row['document_id'], owner_id) if row else None
        data = AnnotationData.model_validate_json(row['payload']) if row and document.original_document_id else AnnotationData()
        return {'document': document.model_dump(), 'base_document': original.model_dump(),
                'copy_document': copy.model_dump() if copy else None,
                'revision': document.annotation_revision, 'annotations': data.model_dump(mode='json')}

    def save_annotations(self, identifier: str, owner_id: str, request: AnnotationWrite) -> dict:
        state = self.annotation_state(identifier, owner_id)
        original = Document.model_validate(state['base_document'])
        if not state['document']['original_document_id'] and state['copy_document']:
            raise AnnotationConflict('An edited copy already exists. Open that copy to continue editing.')
        if request.expected_revision != state['revision']:
            raise AnnotationConflict('This edited copy changed in another tab. Your unsaved notes have been kept.')
        data = AnnotationData.model_validate(request.model_dump(exclude={'expected_revision'}))
        target = identifier if state['document']['original_document_id'] else uuid4().hex
        revision = request.expected_revision+1
        binary = annotated_pdf(self.path(original.id, owner_id), data, target, revision)
        digest, now = hashlib.sha256(binary).hexdigest(), datetime.now(timezone.utc).isoformat()
        stored_name = f'{owner_id}/{digest}.pdf'
        previous = None
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute('SELECT 1 FROM documents WHERE id=? AND owner_id=?', (original.id,owner_id)).fetchone():
                raise KeyError('Document not found')
            current = connection.execute('SELECT * FROM document_edits WHERE original_document_id=? AND owner_id=?',
                                         (original.id,owner_id)).fetchone()
            if current and (current['document_id'] != target or current['revision'] != request.expected_revision):
                raise AnnotationConflict('This edited copy changed in another tab. Your unsaved notes have been kept.')
            if not current and state['document']['original_document_id']:
                raise KeyError('Document not found')
            path = self.files/stored_name; path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.parent/f'{target}.upload'
            try:
                temporary.write_bytes(binary); temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            if current:
                previous = connection.execute('SELECT stored_name FROM documents WHERE id=? AND owner_id=?',
                                              (target,owner_id)).fetchone()['stored_name']
                connection.execute('UPDATE documents SET sha256=?,size=?,stored_name=? WHERE id=? AND owner_id=?',
                                   (digest,len(binary),stored_name,target,owner_id))
                connection.execute('UPDATE document_edits SET revision=?,payload=? WHERE document_id=? AND owner_id=?',
                                   (revision,data.model_dump_json(),target,owner_id))
                filename = state['document']['filename']
            else:
                filename = f'{Path(original.filename).stem[:170]} - annotated.pdf'
                connection.execute('''INSERT INTO documents
                    (id,owner_id,filename,sha256,media_type,page_count,size,stored_name,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (target,owner_id,filename,digest,'application/pdf',original.page_count,len(binary),stored_name,now))
                connection.execute('INSERT INTO document_edits VALUES (?,?,?,?,?)',
                                   (target,owner_id,original.id,revision,data.model_dump_json()))
        if previous and previous != stored_name:
            self._cleanup_binaries([previous])
        document = Document(id=target,filename=filename,sha256=digest,media_type='application/pdf',
            page_count=original.page_count,size=len(binary),original_document_id=original.id,annotation_revision=revision)
        return {'document':document.model_dump(), 'base_document':original.model_dump(),
                'copy_document':document.model_dump(), 'revision':revision,'annotations':data.model_dump(mode='json')}

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

    def _deletion_info(self, connection, kind: str, identifier: str, owner_id: str) -> dict:
        table = 'documents' if kind == 'document' else 'study_sets'
        row = connection.execute(f'SELECT * FROM {table} WHERE id=? AND owner_id=?',
                                 (identifier, owner_id)).fetchone()
        if row is None:
            raise KeyError('File not found' if kind == 'document' else 'Study set not found')
        primary, context, copies = [], [], []
        document_ids = {identifier}
        if kind == 'document':
            copies = [dict(copy) for copy in connection.execute('''SELECT d.id,d.filename AS title,d.sha256
                FROM document_edits e JOIN documents d ON d.id=e.document_id
                WHERE e.original_document_id=? AND e.owner_id=? AND d.owner_id=?''', (identifier,owner_id,owner_id))]
            document_ids.update(copy['id'] for copy in copies)
            for saved in connection.execute('SELECT id,title,payload FROM study_sets WHERE owner_id=?', (owner_id,)):
                payload = json.loads(saved['payload'])
                if payload['document']['id'] in document_ids:
                    primary.append({'id': saved['id'], 'title': saved['title']})
                elif any(entry['document']['id'] in document_ids for entry in payload.get('context_documents', [])):
                    context.append({'id': saved['id'], 'title': saved['title']})
        revision = hashlib.sha256(json.dumps([identifier, row['sha256'] if kind == 'document' else row['payload'],
            sorted((copy['id'],copy['sha256']) for copy in copies),
            sorted(entry['id'] for entry in primary), sorted(entry['id'] for entry in context)]).encode()).hexdigest()
        return {'id': identifier, 'title': row['filename'] if kind == 'document' else row['title'],
                'revision': revision, 'study_sets': primary, 'context_sets': context, 'edited_copies': copies,
                'document_ids': sorted(document_ids) if kind == 'document' else []}

    def deletion_info(self, kind: str, identifier: str, owner_id: str) -> dict:
        with self.connection() as connection:
            return self._deletion_info(connection, kind, identifier, owner_id)

    def delete(self, kind: str, identifier: str, owner_id: str, revision: str) -> dict:
        stored_names = []
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            impact = self._deletion_info(connection, kind, identifier, owner_id)
            if revision != impact['revision']:
                raise DeletionChanged('Related content changed. Review the deletion again before confirming.')
            if kind == 'study-set':
                connection.execute('DELETE FROM study_sets WHERE id=? AND owner_id=?', (identifier, owner_id))
                return {'deleted_set_ids': [identifier]}
            document_ids = set(impact['document_ids'])
            for document_id in document_ids:
                stored_names.append(connection.execute('SELECT stored_name FROM documents WHERE id=? AND owner_id=?',
                                    (document_id,owner_id)).fetchone()['stored_name'])
            for entry in impact['study_sets']:
                connection.execute('DELETE FROM study_sets WHERE id=? AND owner_id=?', (entry['id'], owner_id))
            for entry in impact['context_sets']:
                row = connection.execute('SELECT payload FROM study_sets WHERE id=? AND owner_id=?',
                                         (entry['id'], owner_id)).fetchone()
                payload = json.loads(row['payload'])
                payload['context_documents'] = [context for context in payload['context_documents']
                                                if context['document']['id'] not in document_ids]
                # An explicit attachment deletion detaches context only. Do not
                # normalize historical records or alter their items/metadata.
                connection.execute('UPDATE study_sets SET payload=? WHERE id=? AND owner_id=?',
                                   (json.dumps(payload, ensure_ascii=False), entry['id'], owner_id))
            for document_id in document_ids:
                connection.execute('DELETE FROM document_edits WHERE document_id=? AND owner_id=?', (document_id,owner_id))
            for document_id in document_ids:
                connection.execute('DELETE FROM documents WHERE id=? AND owner_id=?', (document_id,owner_id))
        self._cleanup_binaries(stored_names)
        return {'deleted_document_id': identifier, 'deleted_document_ids':sorted(document_ids),
                'deleted_set_ids': [entry['id'] for entry in impact['study_sets']],
                'detached_context_set_ids': [entry['id'] for entry in impact['context_sets']]}

    def _cleanup_binaries(self, stored_names: list[str]):
        # Protect an identical file re-uploaded between commit and cleanup.
        try:
            with self.connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                for stored_name in stored_names:
                    if not connection.execute('SELECT 1 FROM documents WHERE stored_name=?', (stored_name,)).fetchone():
                        path = (self.files / stored_name).resolve()
                        if path.is_relative_to(self.files):
                            path.unlink(missing_ok=True)
        except OSError:
            logging.getLogger(__name__).warning('Deleted document binary cleanup deferred')
