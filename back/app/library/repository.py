from app.core.ports import PersistencePort
from app.library.models import FolderCreate, FolderUpdate, ItemUpdate, LibrarySnapshot

"Owner-scoped organization metadata, independent of canonical document/set content."
import hashlib
import json
from typing import Literal
from uuid import uuid4
from app.documents.constants import DOCUMENT_SELECT
from app.documents.models import DeletionChanged, Document


class LibraryRepository:

    def __init__(
        self, workspace: PersistencePort, integrity_errors: tuple[type[Exception], ...]
    ):
        self._persistence = workspace
        self._integrity_errors = integrity_errors

    @staticmethod
    def _name(name):
        name = name.strip()
        if not name or any((ord(char) < 32 for char in name)):
            raise ValueError("Use a folder name with 1–100 printable characters.")
        return name

    @staticmethod
    def _folder(db, owner, identifier):
        row = db.execute(
            "SELECT * FROM library_folders WHERE id=? AND owner_id=?",
            (identifier, owner),
        ).fetchone()
        if row is None:
            raise KeyError("Folder not found")
        return dict(row)

    def _destination(self, db, owner, parent, identifier=None):
        rows = {
            r["id"]: dict(r)
            for r in db.execute(
                "SELECT * FROM library_folders WHERE owner_id=?", (owner,)
            )
        }
        current, depth = (parent, 1)
        while current is not None:
            if current == identifier:
                raise ValueError(
                    "A folder cannot be moved inside itself or its children."
                )
            if current not in rows:
                raise KeyError("Folder not found")
            current = rows[current]["parent_id"]
            depth += 1

        def height(node):
            return 1 + max(
                (height(r["id"]) for r in rows.values() if r["parent_id"] == node),
                default=0,
            )

        if depth - 1 + (height(identifier) if identifier else 1) > 8:
            raise ValueError("Folders can be nested up to eight levels deep.")

    def folders(self, owner):
        with self._persistence.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,parent_id FROM library_folders WHERE owner_id=? ORDER BY name_key,id",
                    (owner,),
                )
            ]

    def create_folder(self, owner, request: FolderCreate):
        name, identifier = (self._name(request.name), uuid4().hex)
        try:
            with self._persistence.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                if (
                    db.execute(
                        "SELECT COUNT(*) FROM library_folders WHERE owner_id=?",
                        (owner,),
                    ).fetchone()[0]
                    >= 300
                ):
                    raise ValueError("Your library can contain up to 300 folders.")
                self._destination(db, owner, request.parent_id)
                db.execute(
                    "INSERT INTO library_folders VALUES (?,?,?,?,?)",
                    (identifier, owner, name, name.casefold(), request.parent_id),
                )
        except self._integrity_errors:
            raise ValueError("A folder with that name already exists here.") from None
        return {"id": identifier, "name": name, "parent_id": request.parent_id}

    def update_folder(self, owner, identifier, request: FolderUpdate):
        try:
            with self._persistence.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                old = self._folder(db, owner, identifier)
                name = (
                    self._name(request.name)
                    if request.name is not None
                    else old["name"]
                )
                parent = (
                    request.parent_id
                    if "parent_id" in request.model_fields_set
                    else old["parent_id"]
                )
                self._destination(db, owner, parent, identifier)
                db.execute(
                    "UPDATE library_folders SET name=?,name_key=?,parent_id=? WHERE id=? AND owner_id=?",
                    (name, name.casefold(), parent, identifier, owner),
                )
        except self._integrity_errors:
            raise ValueError(
                "A folder with that name already exists at the destination."
            ) from None
        return {"id": identifier, "name": name, "parent_id": parent}

    def update_item(
        self,
        owner,
        kind: Literal["documents", "study-sets"],
        identifier,
        request: ItemUpdate,
    ):
        table = {"documents": "documents", "study-sets": "study_sets"}[kind]
        with self._persistence.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(
                f"SELECT 1 FROM {table} WHERE id=? AND owner_id=?", (identifier, owner)
            ).fetchone():
                raise KeyError("Item not found")
            if not request.model_fields_set or (
                "archived" in request.model_fields_set and request.archived is None
            ):
                raise ValueError("Choose a folder or archive state.")
            old = db.execute(
                "SELECT folder_id,archived FROM library_items WHERE owner_id=? AND kind=? AND item_id=?",
                (owner, kind, identifier),
            ).fetchone()
            folder = (
                request.folder_id
                if "folder_id" in request.model_fields_set
                else old["folder_id"] if old else None
            )
            if folder is not None:
                self._folder(db, owner, folder)
            archived = (
                request.archived
                if request.archived is not None
                else bool(old["archived"]) if old else False
            )
            db.execute(
                "INSERT INTO library_items VALUES (?,?,?,?,?) ON CONFLICT(owner_id,kind,item_id)\n                DO UPDATE SET folder_id=excluded.folder_id,archived=excluded.archived",
                (owner, kind, identifier, folder, int(archived)),
            )
        return {"id": identifier, "folder_id": folder, "archived": archived}

    def read_snapshot(self, owner):
        with self._persistence.connection() as db:
            db.execute("BEGIN")
            files = [
                Document.model_validate(dict(r))
                for r in db.execute(
                    DOCUMENT_SELECT
                    + " WHERE d.owner_id=? ORDER BY d.created_at DESC,d.id",
                    (owner,),
                )
            ]
            by_id = {file.id: file for file in files}
            sets = [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,mode,item_count,created_at,updated_at,payload\n                FROM study_sets WHERE owner_id=? ORDER BY updated_at DESC,id",
                    (owner,),
                )
            ]
            metadata = {
                (r["kind"], r["item_id"]): dict(r)
                for r in db.execute(
                    "SELECT * FROM library_items WHERE owner_id=?", (owner,)
                )
            }
            folders = [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,parent_id FROM library_folders WHERE owner_id=? ORDER BY name_key,id",
                    (owner,),
                )
            ]
        return LibrarySnapshot(files, sets, metadata, folders)

    def _impact(self, db, owner, identifier):
        folder = self._folder(db, owner, identifier)
        folders = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM library_folders WHERE owner_id=? ORDER BY id", (owner,)
            )
        ]
        items = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM library_items WHERE owner_id=? AND folder_id=? ORDER BY kind,item_id",
                (owner, identifier),
            )
        ]
        revision = hashlib.sha256(
            json.dumps([folders, items], sort_keys=True).encode()
        ).hexdigest()
        return {
            "id": identifier,
            "name": folder["name"],
            "parent_id": folder["parent_id"],
            "revision": revision,
            "item_count": len(items),
            "folder_count": sum((r["parent_id"] == identifier for r in folders)),
        }

    def deletion_info(self, owner, identifier):
        with self._persistence.connection() as db:
            return self._impact(db, owner, identifier)

    def delete_folder(self, owner, identifier, revision):
        try:
            with self._persistence.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                impact = self._impact(db, owner, identifier)
                if impact["revision"] != revision:
                    raise DeletionChanged(
                        "This folder changed. Review its contents and confirm again."
                    )
                db.execute(
                    "UPDATE library_folders SET name_key=? WHERE id=? AND owner_id=?",
                    (uuid4().hex, identifier, owner),
                )
                db.execute(
                    "UPDATE library_items SET folder_id=? WHERE owner_id=? AND folder_id=?",
                    (impact["parent_id"], owner, identifier),
                )
                db.execute(
                    "UPDATE library_folders SET parent_id=? WHERE owner_id=? AND parent_id=?",
                    (impact["parent_id"], owner, identifier),
                )
                db.execute(
                    "DELETE FROM library_folders WHERE id=? AND owner_id=?",
                    (identifier, owner),
                )
        except self._integrity_errors:
            raise ValueError(
                "A child folder has the same name as a folder at the destination. Rename or move it first."
            ) from None
        return {"deleted_folder_id": identifier, "parent_id": impact["parent_id"]}
