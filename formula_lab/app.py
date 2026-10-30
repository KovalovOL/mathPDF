"""Authenticated personal PDF library and study workspace."""

import argparse
import asyncio
import logging
import os
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from urllib.parse import quote, urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .auth import Authentication, AuthConfig, FLOW_SECONDS, LoginError, SESSION_SECONDS, safe_next
from .pdf_export import ExportError, export_pdf
from .providers import OpenAIProvider
from .generation_jobs import GenerationBusy, GenerationJobs
from .diagnostics import (ClientDiagnostic, ClientReportLimit, configure_logging, correlation_id,
                          job_context, log_exception,exception_summary, request_context, route_label, REQUEST_ID,
                          http_context,frontend_context,error_identity)
from .study import GENERATION_SECONDS, MAX_ITEMS, GenerateRequest, GenerationError, StudyProvider, StudySet, generate_study, validate_study
from .web_assets import ApplicationAssets, build_id, html_page
from .workspace import MAX_UPLOAD_BYTES, DeletionChanged, Workspace, RenameRequest, RenameConflict
from .annotations import AnnotationConflict, AnnotationWrite
from .reports import Reports
from .request_reports import RequestReports
from .usage import Usage
from .quotas import QuotaExceeded
from .reviews import Reviews,ReviewStart,ReviewAnswer
from .library import FolderCreate, FolderUpdate, ItemUpdate, Library


PUBLIC_ROUTES = {"/health", "/login", "/auth/config", "/auth/google/login", "/auth/google/callback"}
PUBLIC_ASSETS = {".css", ".js", ".mjs", ".svg", ".png", ".ico", ".woff", ".woff2", ".ttf", ".map"}


def create_app(data_dir: Path = Path(".formula-lab"), provider: StudyProvider | None = None) -> FastAPI:
    configure_logging()
    logger = logging.getLogger(__name__)
    load_dotenv(Path.cwd() / ".env", override=False)
    workspace = Workspace(data_dir)
    library = Library(workspace)
    auth = Authentication(workspace, AuthConfig.from_environment())
    workspace.usage=Usage(workspace)
    workspace.reports=Reports(workspace)
    reviews=Reviews(workspace)
    generation_lock = asyncio.Lock()
    jobs = GenerationJobs(workspace, generation_lock)
    client_reports = ClientReportLimit()

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
        logger.info("Application started build=%s http_diagnostics=enabled", build_id())
        try:
            yield
        finally:
            await jobs.close()

    app = FastAPI(title="mathPDF", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)
    app.state.workspace, app.state.auth, app.state.library = workspace, auth, library
    app.state.reviews=reviews
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
        if user and http_context.get() is not None:http_context.get()['user_id']=user.id
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
        elif path in {'/admin','/static/admin.html'} or path.startswith('/api/admin/'):
            if user is None or auth.roles.role(user.id) not in {'admin','owner'}:
                response=JSONResponse({'detail':'Administrator access is required.'},status_code=403)
            else:response=await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if not public_asset:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Cookie"
        return response

    @app.middleware("http")
    async def request_diagnostics(request: Request, call_next):
        reference = correlation_id(request.headers.get("x-mathpdf-request-id"))
        request.state.request_id = reference
        token = request_context.set(reference)
        started = perf_counter()
        route = route_label(request.url.path)
        context_token=http_context.set({'method':request.method,'route':route,'ui':frontend_context(request.headers.get('x-mathpdf-ui-context'))})
        is_api = route.startswith("/api/")
        polling = request.method == "GET" and route == "/api/study/jobs/{id}"
        job_id = request.url.path.rsplit("/", 1)[-1] if route == "/api/study/jobs/{id}" else ""
        job_token = job_context.set(job_id if REQUEST_ID.fullmatch(job_id) else "-")
        quiet = polling or route == "/api/client-errors"
        if is_api and not quiet:
            logger.info('Request started',extra={'event':'http.request_started','build':build_id()})
        try:
            try:
                response = await call_next(request)
            except Exception as error:
                request.state.exception=exception_summary(error)
                request.state.error_details=error_identity(error,route=route)
                log_exception(logger, f"HTTP exception method={request.method} route={route}", error)
                response = JSONResponse({"detail": "An unexpected server error occurred. Use the reference to locate its logs.",
                                         "request_id": reference,**{k:v for k,v in request.state.error_details.items() if k in {'error_code','summary'}}}, status_code=500)
                response.headers["Cache-Control"] = "no-store"
            response.headers["X-MathPDF-Request-ID"] = reference
            response.headers["X-MathPDF-Build"] = build_id()
            level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.DEBUG if quiet else logging.INFO
            if is_api or response.status_code >= 400:
                details=getattr(request.state,'error_details',None) or (error_identity(route=route,status=response.status_code) if response.status_code>=400 else {})
                logger.log(level,'Request failed' if response.status_code>=400 else 'Request completed',extra={
                    'event':'http.request_failed' if response.status_code>=400 else 'http.request_completed','status':response.status_code,
                    'content_type':response.headers.get('content-type','-'),'response_bytes':response.headers.get('content-length'),
                    'duration_ms':round((perf_counter()-started)*1000),'build':build_id(),**details})
            return response
        finally:
            request_context.reset(token)
            job_context.reset(job_token)
            http_context.reset(context_token)

    @app.exception_handler(ExportError)
    @app.exception_handler(GenerationError)
    async def generation_failed(request, error):
        request.state.error_details=error_identity(error,route=route_label(request.url.path),status=502)
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(GenerationBusy)
    async def generation_busy(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(DeletionChanged)
    @app.exception_handler(AnnotationConflict)
    async def deletion_changed(request, error):
        return JSONResponse({'detail': str(error)}, status_code=409)

    @app.exception_handler(ValueError)
    async def invalid_request(request, error):
        request.state.error_details=error_identity(error,route=route_label(request.url.path),status=400)
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing_record(request, error):
        request.state.error_details=error_identity(error,route=route_label(request.url.path),status=404)
        return JSONResponse({"detail": str(error.args[0]) if error.args else "Resource not found"}, status_code=404)

    @app.get("/login", include_in_schema=False)
    def login(request: Request, next: str = "/"):
        if request.state.user:
            return RedirectResponse(safe_next(next), status_code=303)
        return html_page("login.html")

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

    async def platform_proxy(request:Request):
        admin=request.url.path.startswith(('/admin','/api/admin'))
        endpoint=os.getenv('MATHPDF_ADMIN_URL' if admin else 'MATHPDF_REPORTS_URL')
        if not endpoint:
            raise HTTPException(503,'This platform service has not been configured.')
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>2*1024*1024:raise HTTPException(413,'The request context is too large.')
        headers={key:value for key,value in request.headers.items() if key.lower() in {'cookie','origin','content-type','x-mathpdf-user','x-mathpdf-request-id','x-mathpdf-ui-context','sec-fetch-site'}}
        url=endpoint.rstrip('/')+request.url.path+('?' +request.url.query if request.url.query else '')
        try:
            async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
                result=await client.request(request.method,url,headers=headers,content=bytes(body))
        except httpx.HTTPError:
            raise HTTPException(503,'The platform service is temporarily unavailable. Please try again.') from None
        return Response(result.content,status_code=result.status_code,headers={key:value for key,value in result.headers.items() if key.lower() in {'content-type','content-disposition','location','x-mathpdf-request-id'}})

    app.add_api_route('/admin',platform_proxy,methods=['GET'])
    app.add_api_route('/api/admin/{path:path}',platform_proxy,methods=['GET','POST','PATCH','DELETE'])
    app.add_api_route('/api/reports',platform_proxy,methods=['POST'])
    app.add_api_route('/api/reports/{path:path}',platform_proxy,methods=['GET'])

    @app.get('/health')
    def health():
        with workspace.connection() as db:db.execute('SELECT 1')
        return {'status':'ok','build':build_id()}

    @app.exception_handler(QuotaExceeded)
    async def quota_error(request,error):
        request.state.error_details={'error_code':'generation_limit','summary':'The daily generation allowance cannot fit this request.'}
        return JSONResponse(error.payload(),status_code=429)
    @app.exception_handler(RenameConflict)
    async def rename_conflict(request,error):return JSONResponse({'detail':str(error)},status_code=409)

    @app.get('/api/generation/allowance')
    def allowance(request:Request):return workspace.usage.quota.status(request.state.user.id)

    @app.patch('/api/library/items/{kind}/{identifier}/name')
    def rename_item(request:Request,kind:str,identifier:str,data:RenameRequest):
        return workspace.rename_item(kind,identifier,request.state.user.id,data)

    @app.post('/api/study-sets/{identifier}/reviews')
    def review_start(request:Request,identifier:str,data:ReviewStart):
        if not REQUEST_ID.fullmatch(identifier):raise ValueError('Invalid study set identifier.')
        owner=request.state.user.id
        if data.content is None:content=StudySet.model_validate(workspace.study_set(identifier,owner)).model_dump(mode='json')
        else:
            if len(__import__('json').dumps(data.content))>2*1024*1024:raise ValueError('The review content is too large.')
            candidate=StudySet.model_validate(data.content)
            if candidate.id!=identifier:raise ValueError('The review content does not match this set.')
            workspace.check_set_owner(identifier,owner)
            workspace.document(candidate.document.id,owner)
            content=candidate.model_dump(mode='json')
        return reviews.start(owner,identifier,content,data.new_round)

    @app.post('/api/reviews/{identifier}/answers')
    def review_answer(request:Request,identifier:str,data:ReviewAnswer):return reviews.answer(request.state.user.id,identifier,data)

    @app.get("/api/me")
    def me(request: Request):
        with workspace.connection() as db:
            receipt = db.execute("SELECT pending FROM welcome_receipts WHERE user_id=?", (request.state.user.id,)).fetchone()
        return {**request.state.user.model_dump(), "welcome_pending": bool(receipt and receipt['pending'])}

    @app.post("/api/welcome/claim")
    def claim_welcome(request: Request):
        # Atomically claim the one-time display, including simultaneous tabs/devices.
        with workspace.connection() as db:
            receipt = db.execute("UPDATE welcome_receipts SET pending=0 WHERE user_id=? AND pending=1 RETURNING user_id",
                                 (request.state.user.id,)).fetchone()
        return {"show": receipt is not None}

    @app.get("/", include_in_schema=False)
    def home():
        return html_page("home.html")

    @app.get("/workspace", include_in_schema=False)
    def index(request: Request, document: str | None = None, set: str | None = None):
        owner = request.state.user.id
        if document:
            workspace.document(document, owner)
        if set:
            workspace.study_set(set, owner)
        return html_page("index.html")

    @app.get("/api/generation/config")
    def generation_config():
        return {"configured": app.state.provider is not None, "max_pages": 100, "max_items": MAX_ITEMS,
                "max_context_files": 6, "max_upload_mb": 25, "default_document_id": None,
                "generation_timeout_seconds": GENERATION_SECONDS}

    @app.get("/api/documents")
    def documents(request: Request):
        return workspace.documents(request.state.user.id)

    @app.get('/api/documents/{identifier}')
    def document_metadata(request: Request, identifier: str):
        return workspace.document(identifier, request.state.user.id)

    @app.get('/api/documents/{identifier}/annotations')
    def annotations(request: Request, identifier: str):
        return workspace.annotation_state(identifier, request.state.user.id)

    @app.put('/api/documents/{identifier}/annotations')
    def save_annotations(request: Request, identifier: str, data: AnnotationWrite):
        return workspace.save_annotations(identifier, request.state.user.id, data)

    @app.get('/api/documents/{identifier}/deletion')
    def document_deletion(request: Request, identifier: str):
        return workspace.deletion_info('document', identifier, request.state.user.id)

    @app.delete('/api/documents/{identifier}')
    def delete_document(request: Request, identifier: str):
        revision = request.headers.get('if-match', '').strip('"')
        if not revision:
            raise HTTPException(428, 'Review the deletion and confirm it first.')
        return workspace.delete('document', identifier, request.state.user.id, revision)

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

    @app.get('/api/library')
    def library_contents(request: Request):
        return library.snapshot(request.state.user.id)

    @app.post('/api/library/folders', status_code=201)
    def create_folder(request: Request, folder: FolderCreate):
        return library.create_folder(request.state.user.id, folder)

    @app.patch('/api/library/folders/{identifier}')
    def update_folder(request: Request, identifier: str, folder: FolderUpdate):
        return library.update_folder(request.state.user.id, identifier, folder)

    @app.get('/api/library/folders/{identifier}/deletion')
    def folder_deletion(request: Request, identifier: str):
        return library.deletion_info(request.state.user.id, identifier)

    @app.delete('/api/library/folders/{identifier}')
    def delete_folder(request: Request, identifier: str):
        revision = request.headers.get('if-match', '').strip('"')
        if not revision:
            raise HTTPException(428, 'Review the folder removal and confirm it first.')
        return library.delete_folder(request.state.user.id, identifier, revision)

    @app.patch('/api/library/items/{kind}/{identifier}')
    def organize_item(request: Request, kind: str, identifier: str, update: ItemUpdate):
        if kind not in {'documents', 'study-sets'}:
            raise HTTPException(404, 'Item not found')
        return library.update_item(request.state.user.id, kind, identifier, update)

    @app.get("/api/study-sets")
    def study_sets(request: Request):
        return workspace.sets(request.state.user.id)

    @app.get("/api/study-sets/{identifier}")
    def study_set(request: Request, identifier: str):
        return StudySet.model_validate(workspace.study_set(identifier, request.state.user.id))

    @app.get('/api/study-sets/{identifier}/deletion')
    def set_deletion(request: Request, identifier: str):
        return workspace.deletion_info('study-set', identifier, request.state.user.id)

    @app.delete('/api/study-sets/{identifier}')
    def delete_set(request: Request, identifier: str):
        revision = request.headers.get('if-match', '').strip('"')
        if not revision:
            raise HTTPException(428, 'Review the deletion and confirm it first.')
        return workspace.delete('study-set', identifier, request.state.user.id, revision)

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
        await run_in_threadpool(workspace.usage.quota.check,request.state.user.id)
        return (await jobs.start(request.state.user.id, selection, app.state.provider)).snapshot()

    @app.get("/api/study/jobs/{job_id}")
    async def generation_status(request: Request, job_id: str):
        return jobs.get(job_id, request.state.user.id).snapshot()

    @app.delete("/api/study/jobs/{job_id}")
    async def cancel_generation(request: Request, job_id: str):
        return (await jobs.cancel(job_id, request.state.user.id)).snapshot()

    @app.post("/api/client-errors", status_code=204)
    async def client_error(request: Request):
        if not client_reports.allow(request.state.user.id):
            return Response(status_code=204)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 4096:
                raise HTTPException(413, "Diagnostic report exceeds the size limit.")
        try:
            report = ClientDiagnostic.model_validate_json(bytes(data))
        except ValidationError:
            raise HTTPException(422, "Invalid diagnostic report.") from None
        logger.warning("Browser API failure report=%s", report.model_dump_json())
        return Response(status_code=204)

    app.add_middleware(RequestReports,reports=workspace.reports)
    app.mount("/static", ApplicationAssets(directory=static), name="static")
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
