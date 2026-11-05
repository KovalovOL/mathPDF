from fastapi import HTTPException, Request
from fastapi.responses import Response
from app.study.contract import StudySet


class StudyHandler:
    def __init__(self, sets, saver, exporter, preview, delete):
        self._sets, self._saver, self._exporter = sets, saver, exporter
        self._preview, self._delete = preview, delete

    def register(self, router):
        router.add_api_route("/api/study-sets", self.study_sets, methods=["GET"])
        router.add_api_route(
            "/api/study-sets/{identifier}", self.study_set, methods=["GET"]
        )
        router.add_api_route(
            "/api/study-sets/{identifier}/deletion", self.set_deletion, methods=["GET"]
        )
        router.add_api_route(
            "/api/study-sets/{identifier}", self.delete_set, methods=["DELETE"]
        )
        router.add_api_route("/api/study-sets", self.save_study_set, methods=["POST"])
        router.add_api_route(
            "/api/study/export.pdf", self.download_study_pdf, methods=["POST"]
        )

    def study_sets(self, request: Request):
        return self._sets.list(request.state.user.id)

    def study_set(self, request: Request, identifier: str):
        return self._sets.get(identifier, request.state.user.id)

    def set_deletion(self, request: Request, identifier: str):
        return self._preview.execute("study-set", identifier, request.state.user.id)

    def delete_set(self, request: Request, identifier: str):
        revision = request.headers.get("if-match", "").strip('"')
        if not revision:
            raise HTTPException(428, "Review the deletion and confirm it first.")
        return self._delete.execute(
            "study-set", identifier, request.state.user.id, revision
        )

    def save_study_set(self, request: Request, result: StudySet):
        return self._saver.execute(result, request.state.user.id)

    async def download_study_pdf(self, request: Request, result: StudySet):
        data, filename = await self._exporter.execute(result, request.state.user.id)
        return Response(
            data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )
