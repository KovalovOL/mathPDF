from fastapi import HTTPException, Request
from app.documents.models import RenameRequest
from app.library.models import FolderCreate, FolderUpdate, ItemUpdate


class LibraryHandler:
    def __init__(self, library, snapshot, rename):
        self._library = library
        self._snapshot = snapshot
        self._rename = rename

    def register(self, router):
        router.add_api_route(
            "/api/library/items/{kind}/{identifier}/name",
            self.rename_item,
            methods=["PATCH"],
        )
        router.add_api_route("/api/library", self.library_contents, methods=["GET"])
        router.add_api_route(
            "/api/library/folders",
            self.create_folder,
            methods=["POST"],
            status_code=201,
        )
        router.add_api_route(
            "/api/library/folders/{identifier}", self.update_folder, methods=["PATCH"]
        )
        router.add_api_route(
            "/api/library/folders/{identifier}/deletion",
            self.folder_deletion,
            methods=["GET"],
        )
        router.add_api_route(
            "/api/library/folders/{identifier}", self.delete_folder, methods=["DELETE"]
        )
        router.add_api_route(
            "/api/library/items/{kind}/{identifier}",
            self.organize_item,
            methods=["PATCH"],
        )

    def rename_item(
        self, request: Request, kind: str, identifier: str, data: RenameRequest
    ):
        return self._rename.execute(kind, identifier, request.state.user.id, data)

    def library_contents(self, request: Request):
        return self._snapshot.execute(request.state.user.id)

    def create_folder(self, request: Request, folder: FolderCreate):
        return self._library.create_folder(request.state.user.id, folder)

    def update_folder(self, request: Request, identifier: str, folder: FolderUpdate):
        return self._library.update_folder(request.state.user.id, identifier, folder)

    def folder_deletion(self, request: Request, identifier: str):
        return self._library.deletion_info(request.state.user.id, identifier)

    def delete_folder(self, request: Request, identifier: str):
        revision = request.headers.get("if-match", "").strip('"')
        if not revision:
            raise HTTPException(428, "Review the folder removal and confirm it first.")
        return self._library.delete_folder(request.state.user.id, identifier, revision)

    def organize_item(
        self, request: Request, kind: str, identifier: str, update: ItemUpdate
    ):
        if kind not in {"documents", "study-sets"}:
            raise HTTPException(404, "Item not found")
        return self._library.update_item(
            request.state.user.id, kind, identifier, update
        )
