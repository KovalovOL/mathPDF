from urllib.parse import urlsplit, parse_qs, unquote
from posixpath import normpath
from fastapi import Request
from fastapi.responses import Response
from app.infrastructure.http.frontend import build_id


class GatewayHandler:
    def __init__(self, persistence, auth, documents, sets):
        self._persistence = persistence
        self._auth = auth
        self._documents = documents
        self._sets = sets

    def register(self, router):
        router.add_api_route("/health", self.health, methods=["GET"])
        router.add_api_route(
            "/internal/access", self.access, methods=["GET"], include_in_schema=False
        )

    def health(self):
        with self._persistence.connection() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "build": build_id()}

    def access(self, request: Request):
        try:
            return self._authorize(request)
        except KeyError:
            # auth_request supports 2xx/401/403; preserve the public 404 separately.
            return Response(status_code=403, headers={"X-MathPDF-Access-Status": "404"})

    def _authorize(self, request: Request):
        target = urlsplit(request.headers.get("x-mathpdf-original-uri", "/"))
        normalized = "/" + normpath(unquote(target.path)).lstrip("/")
        if normalized in {"/admin", "/static/admin.html"}:
            self._auth.roles.require_admin(request.state.user)
        if normalized == "/workspace":
            query = parse_qs(target.query)
            for identifier in query.get("document", []):
                self._documents.document(identifier, request.state.user.id)
            for identifier in query.get("set", []):
                self._sets.study_set(identifier, request.state.user.id)
        return Response(status_code=204)
