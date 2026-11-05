from pathlib import Path
from app.infrastructure.database.connection import Database
from app.infrastructure.object_storage.storage import BlobStorage


class PersistenceContext:
    """Infrastructure resources only; no business operations or mutable services."""

    def __init__(self, directory: Path):
        self._directory = directory.resolve()
        self._files = self._directory / "documents"
        if self._files.is_symlink():
            raise ValueError("Managed document storage must not be a symbolic link.")
        self._files.mkdir(parents=True, exist_ok=True)
        self._database = self._directory / "workspace.sqlite3"
        self._db = Database(self._database)
        self._storage = BlobStorage(self._directory)

    @property
    def directory(self):
        return self._directory

    @property
    def files(self):
        return self._files

    @property
    def database(self):
        return self._database

    @property
    def db(self):
        return self._db

    @property
    def storage(self):
        return self._storage

    def connection(self):
        return self._db.connection()
