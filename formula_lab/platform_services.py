"""Dedicated report ingestion/collection and RBAC-protected administration services."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,RedirectResponse,Response
from pydantic import BaseModel,ConfigDict,Field,ValidationError

from .auth import Authentication,AuthConfig
from .diagnostics import configure_logging,correlation_id,log_exception
from .library import Library
from .reports import Reports,ReportInput,ReportUpdate
from .roles import RoleChange
from .usage import Usage
from .quotas import DefaultAllowance,UserAllowance
from .web_assets import html_page,build_id
from .workspace import Workspace
from .report_safety import sanitize,MAX_CONTEXT_BYTES


class PriceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:str=Field(default='openai',pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    model:str=Field(min_length=1,max_length=180,pattern=r'^[A-Za-z0-9_.:/-]+$')
    input_per_million:Decimal=Field(ge=0,le=1000000)
    cached_per_million:Decimal=Field(ge=0,le=1000000)
    output_per_million:Decimal=Field(ge=0,le=1000000)
    source:str=Field(min_length=1,max_length=500)


async def limited_json(request):
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>MAX_CONTEXT_BYTES:raise HTTPException(413,'Report context is too large.')
    try:return json.loads(body)
    except ValueError:raise HTTPException(400,'A valid JSON report is required.') from None


def create_service(kind,directory=None):
    if kind not in {'admin','reports'}:raise ValueError('Unknown platform service')
    load_dotenv(Path.cwd()/'.env',override=False);configure_logging()
    workspace=Workspace(Path(directory or os.getenv('MATHPDF_DATA_DIR','.formula-lab')))
    auth=Authentication(workspace,AuthConfig.from_environment());Library(workspace)
    usage=Usage(workspace);workspace.usage=usage;reports=Reports(workspace)
    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(reports.worker()) if kind=='reports' else None
        try:yield
        finally:
            if task:task.cancel();await asyncio.gather(task,return_exceptions=True)
    app=FastAPI(title='MathPDF '+kind,docs_url=None,redoc_url=None,lifespan=lifespan)
    app.state.workspace,app.state.auth,app.state.usage,app.state.reports=workspace,auth,usage,reports
    @app.middleware('http')
    async def security(request,call_next):
        reference=correlation_id(request.headers.get('x-mathpdf-request-id'))
        try:
            if request.url.path=='/health':response=await call_next(request)
            else:
                user=await asyncio.to_thread(auth.session_user,request.cookies.get(auth.config.session_cookie));request.state.user=user
                if not user:
                    response=RedirectResponse('/login?next=%2Fadmin',status_code=303) if request.url.path=='/admin' else JSONResponse({'detail':'Sign in to continue.'},status_code=401)
                elif request.headers.get('x-mathpdf-user',user.id)!=user.id:response=JSONResponse({'detail':'The active account has changed.'},status_code=409)
                elif request.method not in {'GET','HEAD','OPTIONS'} and (request.headers.get('origin')!=auth.config.base_url or request.headers.get('sec-fetch-site')=='cross-site'):
                    response=JSONResponse({'detail':'Request origin is not allowed.'},status_code=403)
                elif kind=='admin' and auth.roles.role(user.id) not in {'admin','owner'}:
                    response=JSONResponse({'detail':'Administrator access is required.'},status_code=403)
                else:response=await call_next(request)
        except Exception as error:
            import logging
            log_exception(logging.getLogger(__name__),'Platform service request failed',error)
            response=JSONResponse({'detail':'The service is temporarily unavailable.','request_id':reference},status_code=500)
        response.headers.update({'X-MathPDF-Request-ID':reference,'X-MathPDF-Build':build_id(),
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'SAMEORIGIN','Vary':'Cookie'})
        return response
    @app.exception_handler(ValueError)
    async def invalid(request,error):return JSONResponse({'detail':str(error)},status_code=400)
    @app.exception_handler(KeyError)
    async def missing(request,error):return JSONResponse({'detail':str(error.args[0])},status_code=404)
    @app.get('/health')
    def health():
        with workspace.connection() as db:db.execute('SELECT 1')
        return {'status':'ok','service':kind,'build':build_id()}
    if kind=='reports':
        @app.post('/api/reports',status_code=202)
        async def submit(request:Request):
            try:data=ReportInput.model_validate(await limited_json(request))
            except ValidationError:raise HTTPException(400,'Invalid report fields.') from None
            return await asyncio.to_thread(reports.record,request.state.user,data)
        @app.get('/api/reports/{identifier}')
        def report_status(request:Request,identifier:str):
            report=reports.get(identifier)
            if report['user_id']!=request.state.user.id:raise KeyError('Report not found')
            return {key:report[key] for key in ['id','status','collection_status','created_at']}
        return app
    @app.get('/admin')
    def admin():return html_page('admin.html')
    @app.get('/api/admin/overview')
    def overview():
        with workspace.connection() as db:
            count=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            roles=[dict(r) for r in db.execute("SELECT COALESCE(r.role,'free') AS role,COUNT(*) AS count FROM users u LEFT JOIN user_roles r ON r.user_id=u.id GROUP BY COALESCE(r.role,'free')")]
            report_counts=[dict(r) for r in db.execute('SELECT status,COUNT(*) AS count FROM reports GROUP BY status')]
            start=db.execute('SELECT MIN(started_at) AS start FROM ai_usage').fetchone()['start']
        return {'users':count,'roles':roles,'reports':report_counts,'tracking_since':start,'history_note':'Earlier AI calls did not record actual token usage. Their token counts and costs are unavailable.'}
    @app.get('/api/admin/users')
    def users(q:str='',offset:int=0):
        if offset<0 or len(q)>200:raise ValueError('Invalid user search.')
        with workspace.connection() as db:
            return [dict(r) for r in db.execute('''SELECT u.id,u.email,u.name,u.created_at,u.updated_at,COALESCE(r.role,'free') AS role,
                (SELECT COUNT(*) FROM documents d WHERE d.owner_id=u.id) AS file_count,
                (SELECT COUNT(*) FROM study_sets s WHERE s.owner_id=u.id) AS set_count,
                (SELECT MAX(e.created_at) FROM request_events e WHERE e.user_id=u.id) AS last_activity
                FROM users u LEFT JOIN user_roles r ON r.user_id=u.id
                WHERE LOWER(u.email) LIKE ? OR LOWER(u.name) LIKE ? ORDER BY u.created_at DESC,u.id LIMIT 200 OFFSET ?''',
                ('%'+q.casefold()+'%','%'+q.casefold()+'%',offset))]
    @app.get('/api/admin/users/{identifier}')
    def user_details(identifier:str):
        with workspace.connection() as db:
            row=db.execute("SELECT u.id,u.email,u.name,u.created_at,u.updated_at,COALESCE(r.role,'free') AS role FROM users u LEFT JOIN user_roles r ON r.user_id=u.id WHERE u.id=?",(identifier,)).fetchone()
            if not row:raise KeyError('User not found')
            files=[dict(r) for r in db.execute('SELECT id,filename,size,page_count FROM documents WHERE owner_id=? ORDER BY created_at DESC',(identifier,))]
            sets=[dict(r) for r in db.execute('SELECT id,title,mode,item_count,updated_at FROM study_sets WHERE owner_id=? ORDER BY updated_at DESC',(identifier,))]
        return {'user':dict(row),'files':files,'sets':sets,'allowance':usage.quota.status(identifier),'usage':{str(days):usage.dashboard(days,identifier) for days in [1,7,30]}}
    @app.patch('/api/admin/users/{identifier}/role')
    def role(request:Request,identifier:str,change:RoleChange):return auth.roles.change(request.state.user,identifier,change.role)
    @app.get('/api/admin/generation-limits')
    def generation_limits():return usage.quota.settings()
    @app.patch('/api/admin/generation-limits')
    def default_limit(request:Request,data:DefaultAllowance):return usage.quota.update(request.state.user,data.daily_tokens)
    @app.patch('/api/admin/users/{identifier}/generation-limit')
    def individual_limit(request:Request,identifier:str,data:UserAllowance):return usage.quota.update(request.state.user,data.daily_tokens,identifier)

    @app.get('/api/admin/usage')
    def metrics(days:int=7,user_id:str|None=None):
        if days not in {1,7,30}:raise ValueError('Choose day, week or month.')
        return usage.dashboard(days,user_id)
    @app.get('/api/admin/prices')
    def prices():
        with workspace.connection() as db:return [dict(r) for r in db.execute('SELECT * FROM model_prices ORDER BY effective_at DESC,provider,model')]
    @app.post('/api/admin/prices',status_code=201)
    def new_price(request:Request,price:PriceInput):
        if auth.roles.role(request.state.user.id)!='owner':raise HTTPException(403,'Only the owner can add a tariff.')
        identifier=uuid4().hex;now=datetime.now(timezone.utc).isoformat()
        with workspace.connection() as db:
            db.execute('INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?)',(identifier,price.provider,price.model,now,str(price.input_per_million),str(price.cached_per_million),str(price.output_per_million),price.source,request.state.user.id))
            db.execute('INSERT INTO admin_audit VALUES (?,?,?,?,?)',(uuid4().hex,request.state.user.id,'price_add',json.dumps({'id':identifier,'model':price.model}),now))
        return {'id':identifier,'effective_at':now}
    @app.get('/api/admin/reports')
    def report_list(offset:int=0,status:str|None=None):
        if offset<0 or status not in {None,'new','investigating','resolved'}:raise ValueError('Invalid report page.')
        return reports.list(offset=offset,status=status)
    @app.get('/api/admin/reports/{identifier}')
    def detail(identifier:str):return reports.get(identifier)
    @app.patch('/api/admin/reports/{identifier}')
    def update(request:Request,identifier:str,data:ReportUpdate):return reports.update(identifier,data,request.state.user)
    @app.get('/api/admin/reports/{identifier}/bundle')
    async def download(identifier:str):
        binary=await asyncio.to_thread(reports.bundle,identifier)
        return Response(binary,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="report-{identifier}.zip"'})
    return app


def admin_app():return create_service('admin')
def reports_app():return create_service('reports')
