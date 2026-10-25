"""Authenticated personal PDF library and study workspace."""

import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .auth import Authentication, AuthConfig, FLOW_SECONDS, LoginError, SESSION_SECONDS, safe_next
from .pdf_export import ExportError, export_pdf
from .providers import OpenAIProvider
from .generation_jobs import GenerationBusy, GenerationJobs
from .study import GENERATION_SECONDS, MAX_ITEMS, GenerateRequest, GenerationError, StudyProvider, StudySet, generate_study, validate_study
from .workspace import MAX_UPLOAD_BYTES, Workspace


PUBLIC_ROUTES = {"/login", "/auth/config", "/auth/google/login", "/auth/google/callback"}
PUBLIC_ASSETS = {".css", ".js", ".mjs", ".svg", ".png", ".ico", ".woff", ".woff2", ".ttf", ".map"}


def create_app(data_dir: Path = Path(".formula-lab"), provider: StudyProvider | None = None) -> FastAPI:
    application_logger = logging.getLogger("formula_lab")
    if not application_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        application_logger.addHandler(handler)
    application_logger.setLevel(logging.INFO)
    application_logger.propagate = False
    load_dotenv(Path.cwd() / ".env", override=False)
    workspace = Workspace(data_dir)
    auth = Authentication(workspace, AuthConfig.from_environment())
    generation_lock = asyncio.Lock()
    jobs = GenerationJobs(workspace, generation_lock)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await jobs.close()

    app = FastAPI(title="mathPDF", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
    app.state.workspace, app.state.auth = workspace, auth
    static = Path(__file__).parent / "static"
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY", "")
    app.state.provider = provider or (OpenAIProvider(key, model) if key else None)
    export_lock = asyncio.Lock()

    @app.middleware("http")
    async def private_application(request: Request, call_next):
        path = request.url.path
        public_asset = path.startswith("/static/") and Path(path).suffix.lower() in PUBLIC_ASSETS
        public = path in PUBLIC_ROUTES or public_asset
        user = None
        if not public_asset:
            user = await run_in_threadpool(auth.session_user, request.cookies.get(auth.config.session_cookie))
        request.state.user = user
        if not public and user is None:
            if path.startswith("/api/") or request.method not in {"GET", "HEAD"}:
                response = JSONResponse({"detail": "Sign in to continue."}, status_code=401)
            else:
                target = safe_next(path + (f"?{request.url.query}" if request.url.query else ""))
                response = RedirectResponse("/login?" + urlencode({"next": target}), status_code=303)
        elif user and path.startswith("/api/") and request.headers.get("x-mathpdf-user", user.id) != user.id:
            response = JSONResponse({"detail": "The active account has changed."}, status_code=409,
                                    headers={"X-MathPDF-Account-Changed": "1"})
        elif request.method not in {"GET", "HEAD", "OPTIONS"} and (
                request.headers.get("origin") != auth.config.base_url
                or request.headers.get("sec-fetch-site") == "cross-site"):
            response = JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if not public_asset:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Cookie"
        return response

    @app.exception_handler(ExportError)
    @app.exception_handler(GenerationError)
    async def generation_failed(request, error):
        logging.getLogger(__name__).warning("Study request failed path=%s error_type=%s", request.url.path, type(error).__name__)
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(GenerationBusy)
    async def generation_busy(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_request(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing_record(request, error):
        return JSONResponse({"detail": str(error.args[0]) if error.args else "Resource not found"}, status_code=404)

    @app.get("/login", include_in_schema=False)
    def login(request: Request, next: str = "/"):
        if request.state.user:
            return RedirectResponse(safe_next(next), status_code=303)
        return FileResponse(static / "login.html")

    @app.get("/auth/config", include_in_schema=False)
    def auth_config():
        return {"configured": auth.config.configured}

    @app.get("/auth/google/login", include_in_schema=False)
    def google_login(request: Request, next: str = "/"):
        try:
            cookie, url = auth.begin(next, request.cookies.get(auth.config.flow_cookie))
        except LoginError:
            return RedirectResponse("/login?error=unavailable", status_code=303)
        response = RedirectResponse(url, status_code=303)
        auth.set_cookie(response, auth.config.flow_cookie, cookie, FLOW_SECONDS)
        return response

    @app.get("/auth/google/callback", include_in_schema=False)
    async def google_callback(request: Request, state: str | None = None,
                              code: str | None = None, error: str | None = None):
        try:
            token, next_path = await auth.finish(request.cookies.get(auth.config.flow_cookie), state, code,
                                                 error, request.cookies.get(auth.config.session_cookie))
            response = RedirectResponse(next_path, status_code=303)
            auth.set_cookie(response, auth.config.session_cookie, token, SESSION_SECONDS)
        except LoginError:
            response = RedirectResponse("/login?error=failed", status_code=303)
        auth.clear_cookie(response, auth.config.flow_cookie)
        return response

    @app.post("/auth/logout", include_in_schema=False)
    def logout(request: Request):
        auth.revoke(request.cookies.get(auth.config.session_cookie))
        response = RedirectResponse("/login", status_code=303)
        auth.clear_cookie(response, auth.config.session_cookie)
        auth.clear_cookie(response, auth.config.flow_cookie)
        return response

    @app.get("/api/me")
    def me(request: Request):
        return request.state.user

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(static / "home.html")

    @app.get("/workspace", include_in_schema=False)
    def index(request: Request, document: str | None = None, set: str | None = None):
        owner = request.state.user.id
        if document:
            workspace.document(document, owner)
        if set:
            workspace.study_set(set, owner)
        return FileResponse(static / "index.html")

    @app.get("/api/generation/config")
    def generation_config():
        return {"configured": app.state.provider is not None, "max_pages": 100, "max_items": MAX_ITEMS,
                "max_context_files": 6, "max_upload_mb": 25, "default_document_id": None,
                "generation_timeout_seconds": GENERATION_SECONDS}

    @app.get("/api/documents")
    def documents(request: Request):
        return workspace.documents(request.state.user.id)

    @app.post("/api/documents", status_code=201)
    async def upload_document(request: Request, file: UploadFile):
        try:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
            return await run_in_threadpool(workspace.add_document, file.filename or "document", data,
                                           request.state.user.id)
        finally:
            await file.close()

    @app.get("/api/documents/{identifier}/file")
    def workspace_file(request: Request, identifier: str, download: bool = False):
        owner = request.state.user.id
        record = workspace.document(identifier, owner)
        return FileResponse(workspace.path(identifier, owner), media_type=record.media_type,
                            filename=record.filename,
                            content_disposition_type="attachment" if download else "inline")

    @app.get("/api/study-sets")
    def study_sets(request: Request):
        return workspace.sets(request.state.user.id)

    @app.get("/api/study-sets/{identifier}")
    def study_set(request: Request, identifier: str):
        return StudySet.model_validate(workspace.study_set(identifier, request.state.user.id))

    def validate_result(result: StudySet, owner: str):
        workspace.check_set_owner(result.id, owner)
        result.document = workspace.document(result.document.id, owner)
        if not result.document.page_count or any(p < 1 or p > result.document.page_count for p in result.pages):
            raise ValueError("The study set contains invalid source pages.")
        if len(set(result.pages)) != len(result.pages):
            raise ValueError("The study set repeats a source page.")
        for entry in result.context_documents:
            entry.document = workspace.document(entry.document.id, owner)
            if entry.pages is not None and (not entry.document.page_count or any(
                    p < 1 or p > entry.document.page_count for p in entry.pages)):
                raise ValueError("The study set contains invalid context pages.")
        validate_study(result, result.mode, result.document.id, result.pages)
        if not result.items:
            raise ValueError("There are no study items to save or export.")

    @app.post("/api/study-sets")
    def save_study_set(request: Request, result: StudySet):
        owner = request.state.user.id
        validate_result(result, owner)
        return workspace.save_set(result.model_dump(mode="json"), owner)

    @app.post("/api/study/export.pdf")
    async def download_study_pdf(request: Request, result: StudySet):
        await run_in_threadpool(validate_result, result, request.state.user.id)
        if export_lock.locked():
            raise HTTPException(409, "A PDF export is already running. Wait for it to finish.")
        async with export_lock:
            try:
                data = await asyncio.wait_for(export_pdf(result.model_dump(mode="json")), timeout=90)
            except TimeoutError:
                raise HTTPException(504, "PDF export timed out. Try a smaller set.") from None
        filename = quote(result.title.replace("/", "-").replace("\\", "-") + ".pdf", safe="")
        return Response(data, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})

    @app.post("/api/study/generate")
    async def generate(request: Request, selection: GenerateRequest):
        if app.state.provider is None:
            raise HTTPException(503, "The generation service is unavailable. Try again later.")
        if generation_lock.locked():
            raise HTTPException(409, "A generation request is already running. Wait for it to finish.")
        async with generation_lock:
            return await generate_study(workspace, request.state.user.id, selection, app.state.provider)

    @app.post("/api/study/jobs", status_code=202)
    async def start_generation(request: Request, selection: GenerateRequest):
        if app.state.provider is None:
            raise HTTPException(503, "The generation service is unavailable. Try again later.")
        return (await jobs.start(request.state.user.id, selection, app.state.provider)).snapshot()

    @app.get("/api/study/jobs/{job_id}")
    async def generation_status(request: Request, job_id: str):
        return jobs.get(job_id, request.state.user.id).snapshot()

    @app.delete("/api/study/jobs/{job_id}")
    async def cancel_generation(request: Request, job_id: str):
        return (await jobs.cancel(job_id, request.state.user.id)).snapshot()

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description="Run the mathPDF personal study workspace")
    parser.add_argument("--data-dir", type=Path, default=Path(".formula-lab"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    # Callback query strings contain short-lived authorization codes.
    uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port, access_log=False)
