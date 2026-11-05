from app.library.ports import LibraryRepositoryPort
from app.library.models import FolderCreate, FolderUpdate, ItemUpdate


class LibraryService:
    def __init__(self, repository: LibraryRepositoryPort):
        self._repository = repository

    def folders(self, owner: str) -> list[dict]:
        return self._repository.folders(owner)

    def create_folder(self, owner: str, request: FolderCreate) -> dict:
        return self._repository.create_folder(owner, request)

    def update_folder(self, owner: str, identifier: str, request: FolderUpdate) -> dict:
        return self._repository.update_folder(owner, identifier, request)

    def update_item(
        self, owner: str, kind: str, identifier: str, request: ItemUpdate
    ) -> dict:
        return self._repository.update_item(owner, kind, identifier, request)

    def deletion_info(self, owner: str, identifier: str) -> dict:
        return self._repository.deletion_info(owner, identifier)

    def delete_folder(self, owner: str, identifier: str, revision: str) -> dict:
        return self._repository.delete_folder(owner, identifier, revision)
