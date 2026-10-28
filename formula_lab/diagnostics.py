"""Correlated diagnostics without request bodies, secrets, or OAuth queries."""

import logging
import json
import re
import time
import traceback
from datetime import datetime,timezone
from collections import deque
from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from uuid import uuid4
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field


request_context = ContextVar("mathpdf_request", default="-")
job_context = ContextVar("mathpdf_job", default="-")
http_context = ContextVar('mathpdf_http',default=None)
REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")


class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_context.get()
        record.job_id = job_context.get()
        return True


def frontend_context(value):
    """Read bounded, percent-encoded UI metadata; never headers, inputs or content."""
    if not value or len(value)>4096:return {}
    try:raw=json.loads(unquote(value))
    except (ValueError,UnicodeError,RecursionError):return {}
    if not isinstance(raw,dict):return {}
    result={}
    for key in ['screen','action','target','document_id','study_set_id','file_name']:
        item=raw.get(key)
        if isinstance(item,str):result[key]=item[:160]
    for key in ['page','item_index']:
        item=raw.get(key)
        if isinstance(item,int) and not isinstance(item,bool) and 0<=item<=100000:result[key]=item
    from .report_safety import sanitize
    return sanitize(result)


def error_identity(error=None,*,route='',status=500,exception_type=None):
    kind=exception_type or (type(error).__name__ if error else None)
    sqlstate=getattr(error,'sqlstate',None) if error else None
    if kind=='UntranslatableCharacter' or sqlstate=='22P05':
        code='library_metadata_decode_failed' if route=='/api/library' else 'database_unicode_conversion'
        summary='Stored JSON contains a character PostgreSQL cannot convert to JSONB.'
    elif kind in {'OperationalError','InterfaceError','ConnectionFailure'}:
        code,summary='database_unavailable','The database connection was unavailable.'
    elif kind in {'TimeoutError','APITimeoutError'}:
        code,summary='request_timeout','The operation did not complete before its deadline.'
    elif kind=='GenerationError':code,summary='generation_failed','The provider response could not produce the requested study set.'
    elif kind=='ValidationError' or status==422:code,summary='request_validation_failed','The request did not match the expected format.'
    elif status==404:code,summary='resource_not_found','The requested resource is unavailable for this account.'
    elif status==403:code,summary='access_denied','The account or request origin is not allowed to perform this action.'
    elif status<500:code,summary='request_rejected','The request could not be accepted.'
    else:code,summary='unexpected_server_error','An unexpected server error interrupted the operation.'
    result={'error_code':code,'summary':summary}
    if kind:result['error_type']=kind
    if sqlstate and re.fullmatch(r'[A-Z0-9]{5}',sqlstate):result['sqlstate']=sqlstate
    if error:
        frames=traceback.extract_tb(error.__traceback__)
        owned=[frame for frame in frames if 'formula_lab' in Path(frame.filename).parts]
        if owned:
            meaningful=[f for f in owned if Path(f.filename).name!='database.py'] or owned
            last=meaningful[-1];result['location']=f'{Path(last.filename).name}:{last.lineno}:{last.name}'
            result['application_frames']=[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in owned[-5:]]
        result['exception']=exception_summary(error)
    return result


class JsonFormatter(logging.Formatter):
    def format(self,record):
        from .report_safety import sanitize
        context=http_context.get() or {}
        access=record.name=='uvicorn.access'
        payload={'timestamp':datetime.fromtimestamp(record.created,timezone.utc).isoformat(timespec='milliseconds'),
            'level':record.levelname,'logger':record.name,'event':getattr(record,'event','http.access' if access else 'application.log'),
            'message':'HTTP access' if access else record.getMessage(),'request_id':getattr(record,'request_id',request_context.get()),
            'job_id':getattr(record,'job_id',job_context.get()),**context}
        if access and isinstance(record.args,tuple) and len(record.args)>=5:
            payload.update({'method':str(record.args[1])[:10],'route':route_label(str(record.args[2]).split('?',1)[0]),'status':record.args[4]})
        for key in ['error_code','error_type','summary','sqlstate','location','application_frames','report_id','status','duration_ms','response_bytes','content_type','build','document_id','study_set_id']:
            if hasattr(record,key):payload[key]=getattr(record,key)
        if record.exc_info and record.exc_info[1]:payload.update({k:v for k,v in error_identity(record.exc_info[1],route=context.get('route','')).items() if k!='exception'})
        return json.dumps(sanitize(payload),ensure_ascii=True,separators=(',',':'))


def configure_logging():
    for name in ['formula_lab','uvicorn','uvicorn.error','uvicorn.access']:
        logger=logging.getLogger(name)
        if not logger.handlers:logger.addHandler(logging.StreamHandler())
        for handler in logger.handlers:
            handler.setFormatter(JsonFormatter())
            if not any(isinstance(item,CorrelationFilter) for item in handler.filters):handler.addFilter(CorrelationFilter())
        logger.setLevel(logging.INFO);logger.propagate=False


def correlation_id(value: str | None) -> str:
    return value if value and REQUEST_ID.fullmatch(value) else uuid4().hex


def route_label(path: str) -> str:
    if path.startswith("/api/"):
        path = re.sub(r"[a-f0-9]{32}|[a-f0-9-]{36}", "{id}", path)
        return path if re.fullmatch(r"/api/[A-Za-z0-9_/{}/.-]{1,160}", path) else "/api/other"
    if path.startswith("/static/"):
        return "/static/*"
    return path if path in {"/", "/workspace", "/login", "/auth/config", "/auth/logout",
                           "/auth/google/login", "/auth/google/callback"} else "/other"


def exception_summary(error: BaseException):
    # Exception messages can contain source content or credentials. Keep only
    # exception types and stack locations, including nested exception groups.
    def locations(exc, depth=0):
        frames = [f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                  for frame in traceback.extract_tb(exc.__traceback__)[-16:]]
        details = [{"type": type(exc).__name__, "frames": frames}]
        if depth < 2:
            for child in getattr(exc, "exceptions", ())[:4]:
                details.extend(locations(child, depth + 1))
        return details
    return locations(error)


def log_exception(logger: logging.Logger, event: str, error: BaseException):
    logger.error(event,extra={'event':'operation.failed',**error_identity(error,route=(http_context.get() or {}).get('route',''))})


class ClientDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: Literal["invalid_json", "unexpected_content_type", "network_error", "timeout", "http_error"]
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    route: str = Field(pattern=r"^/api/[A-Za-z0-9_/{}/.-]{1,160}$")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]
    status: int | None = Field(default=None, ge=100, le=599)
    received_bytes: int | None = Field(default=None, ge=0, le=100 * 1024 * 1024)
    expected_bytes: int | None = Field(default=None, ge=0, le=100 * 1024 * 1024)
    content_type: str = Field(default="", max_length=80, pattern=r"^[A-Za-z0-9.+/-]*$")
    redirected: bool = False
    response_route: str = Field(default="/other", max_length=180, pattern=r"^/[A-Za-z0-9_/{}/.*-]*$")
    server_build: str | None = Field(default=None, pattern=r"^[a-f0-9]{12}$")
    client_build: str | None = Field(default=None, pattern=r"^[a-f0-9]{12}$")


class ClientReportLimit:
    def __init__(self):
        self.reports: dict[str, deque] = {}

    def allow(self, owner_id: str) -> bool:
        now = time.monotonic()
        for owner, reports in list(self.reports.items()):
            while reports and reports[0] < now - 60:
                reports.popleft()
            if not reports:
                del self.reports[owner]
        if owner_id not in self.reports and len(self.reports) >= 500:
            return False
        reports = self.reports.setdefault(owner_id, deque())
        if len(reports) >= 10:
            return False
        reports.append(now)
        return True
