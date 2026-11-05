from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from app.documents.constants import MAX_UPLOAD_BYTES
from app.annotations.models import AnnotationWrite


class DocumentsHandler:
    def __init__(self, documents, reader, saver, preview, delete):
        self._documents, self._reader, self._saver = documents, reader, saver
        self._preview, self._delete = preview, delete

    def register(self, router):
        router.add_api_route("/api/documents", self.documents, methods=["GET"])
        router.add_api_route(
            "/api/documents/{identifier}", self.document_metadata, methods=["GET"]
        )
        router.add_api_route(
            "/api/documents/{identifier}/annotations", self.annotations, methods=["GET"]
        )
        router.add_api_route(
            "/api/documents/{identifier}/annotations",
            self.save_annotations,
            methods=["PUT"],
        )
        router.add_api_route(
            "/api/documents/{identifier}/deletion",
            self.document_deletion,
            methods=["GET"],
        )
        router.add_api_route(
            "/api/documents/{identifier}", self.delete_document, methods=["DELETE"]
        )
        router.add_api_route(
            "/api/documents", self.upload_document, methods=["POST"], status_code=201
        )
        router.add_api_route(
            "/api/documents/{identifier}/file", self.workspace_file, methods=["GET"]
        )

    def documents(self, request: Request):
        return self._documents.documents(request.state.user.id)

    def document_metadata(self, request: Request, identifier: str):
        return self._documents.document(identifier, request.state.user.id)

    def annotations(self, request: Request, identifier: str):
        return self._reader.execute(identifier, request.state.user.id)

    def save_annotations(
        self, request: Request, identifier: str, data: AnnotationWrite
    ):
        return self._saver.execute(identifier, request.state.user.id, data)

    def document_deletion(self, request: Request, identifier: str):
        return self._preview.execute("document", identifier, request.state.user.id)

    def delete_document(self, request: Request, identifier: str):
        revision = request.headers.get("if-match", "").strip('"')
        if not revision:
            raise HTTPException(428, "Review the deletion and confirm it first.")
        return self._delete.execute(
            "document", identifier, request.state.user.id, revision
        )

    async def upload_document(self, request: Request, file: UploadFile):
        try:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            return await run_in_threadpool(
                self._documents.add_document,
                file.filename or "document",
                data,
                request.state.user.id,
            )
        finally:
            await file.close()

    def workspace_file(self, request: Request, identifier: str, download: bool = False):
        owner = request.state.user.id
        record = self._documents.document(identifier, owner)
        return FileResponse(
            self._documents.path(identifier, owner),
            media_type=record.media_type,
            filename=record.filename,
            content_disposition_type="attachment" if download else "inline",
        )
