"""Actual provider-attempt accounting with immutable effective tariff snapshots."""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import sqlite3
import time
from functools import wraps
import psycopg
from uuid import uuid4

from .diagnostics import request_context,job_context

usage_context=ContextVar('mathpdf_usage',default=None)
PRICING_SOURCE='https://developers.openai.com/api/docs/models/gpt-4.1-mini'


def utcnow():return datetime.now(timezone.utc).isoformat()


def durable_write(method):
    """A completed paid response must survive a temporary database outage."""
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        if method.__name__=='finish':kwargs.setdefault('finished_at',utcnow())
        try:return method(self,*args,**kwargs)
        except (psycopg.OperationalError,psycopg.InterfaceError,sqlite3.OperationalError):
            from .report_safety import sanitize
            def serial(value):
                if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
                if isinstance(value,(list,tuple)):return [serial(v) for v in value]
                if hasattr(value,'model_dump'):return serial(value.model_dump())
                if hasattr(value,'__dict__'):return serial(vars(value))
                return value
            payload=sanitize({'operation':method.__name__,'args':serial(args),'kwargs':serial(kwargs)})
            target=self.spool/(str(time.time_ns())+'-'+uuid4().hex+'.json');temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps(payload,ensure_ascii=False));temporary.chmod(0o600);temporary.replace(target)
            logging.getLogger(__name__).warning('Usage observation durably queued operation=%s attempt=%s',method.__name__,args[0])
    return wrapped


class Usage:
    def __init__(self,workspace):
        self.workspace=workspace;self.spool=workspace.directory/'usage-spool';self.spool.mkdir(exist_ok=True)
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.executescript('''CREATE TABLE IF NOT EXISTS model_prices (
                id TEXT PRIMARY KEY,provider TEXT NOT NULL,model TEXT NOT NULL,effective_at TEXT NOT NULL,
                input_per_million TEXT NOT NULL,cached_per_million TEXT NOT NULL,output_per_million TEXT NOT NULL,
                source TEXT NOT NULL,created_by TEXT);
                CREATE TABLE IF NOT EXISTS ai_usage (
                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
                job_id TEXT,provider TEXT NOT NULL,model TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,
                status TEXT NOT NULL,input_tokens BIGINT,cached_tokens BIGINT,output_tokens BIGINT,reasoning_tokens BIGINT,
                duration_ms BIGINT,provider_request_id TEXT,price_id TEXT,cost_usd TEXT,context TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ai_usage_user_time ON ai_usage(user_id,started_at);
                CREATE INDEX IF NOT EXISTS ai_usage_time ON ai_usage(started_at);''')
            for model in ['gpt-4.1-mini','gpt-4.1-mini-2025-04-14']:
                db.execute('''INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING''',
                    ('openai-standard-2026-10-28-'+model,'openai',model,'2026-10-28T00:00:00+00:00','0.40','0.10','1.60',PRICING_SOURCE,None))
        from .quotas import GenerationQuota
        self.quota=GenerationQuota(workspace)
    def start(self,user_id,provider,model,context):
        from .report_safety import bounded
        identifier=uuid4().hex;stamp=utcnow();estimate=context.get('estimated_tokens',1);context=bounded(context)
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            price=db.execute('SELECT id FROM model_prices WHERE provider=? AND model=? AND effective_at<=? ORDER BY effective_at DESC,id DESC LIMIT 1',(provider,model,stamp)).fetchone()
            db.execute('''INSERT INTO ai_usage (id,user_id,request_id,job_id,provider,model,started_at,status,price_id,context)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',(identifier,user_id,request_context.get(),job_context.get(),provider,model,stamp,'running',price['id'] if price else None,json.dumps(context,ensure_ascii=False)))
            self.quota.reserve(db,identifier,user_id,estimate)
        return identifier
    @durable_write
    def finish(self,identifier,status,usage=None,duration_ms=None,provider_request_id=None,finished_at=None,unbilled=False):
        def count(name,default=None):
            value=usage.get(name,default) if isinstance(usage,dict) else getattr(usage,name,default) if usage is not None else default
            return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None
        inputs,outputs=count('input_tokens'),count('output_tokens')
        def detail(parent,key):
            entry=usage.get(parent) if isinstance(usage,dict) else getattr(usage,parent,None)
            return entry.get(key) if isinstance(entry,dict) else getattr(entry,key,None)
        cached=detail('input_tokens_details','cached_tokens')
        reasoning=detail('output_tokens_details','reasoning_tokens')
        cached=cached if isinstance(cached,int) and not isinstance(cached,bool) and cached>=0 else (0 if inputs is not None else None)
        reasoning=reasoning if isinstance(reasoning,int) and not isinstance(reasoning,bool) and reasoning>=0 else None
        if inputs is not None and cached is not None and cached>inputs:cached=None
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT price_id,input_tokens,output_tokens FROM ai_usage WHERE id=?',(identifier,)).fetchone()
            if not row:return
            # A late timeout/cancellation observation cannot erase paid usage
            # already received (including a durable observation replay).
            if (inputs is None or outputs is None) and row['input_tokens'] is not None and row['output_tokens'] is not None:return
            price=db.execute('SELECT * FROM model_prices WHERE id=?',(row['price_id'],)).fetchone() if row['price_id'] else None
            cost=None
            if price and inputs is not None and outputs is not None and cached is not None:
                cost=str((Decimal(inputs-cached)*Decimal(price['input_per_million'])+Decimal(cached)*Decimal(price['cached_per_million'])+Decimal(outputs)*Decimal(price['output_per_million']))/Decimal(1000000))
            db.execute('''UPDATE ai_usage SET finished_at=?,status=?,input_tokens=?,cached_tokens=?,output_tokens=?,reasoning_tokens=?,
                duration_ms=?,provider_request_id=?,cost_usd=? WHERE id=?''',(finished_at or utcnow(),status,inputs,cached,outputs,reasoning,duration_ms,provider_request_id,cost,identifier))
            self.quota.settle(db,identifier,inputs is not None and outputs is not None,unbilled)
    @durable_write
    def response(self,identifier,model,status,text):
        from .report_safety import sanitize
        with self.workspace.connection() as db:
            row=db.execute('SELECT context FROM ai_usage WHERE id=?',(identifier,)).fetchone()
            if not row:return
            context=json.loads(row['context']);context['provider_response']=sanitize({'status':status,'output_text':text})
            db.execute('UPDATE ai_usage SET context=?,model=? WHERE id=?',(json.dumps(context,ensure_ascii=False),model,identifier))
    @durable_write
    def outcome(self,identifier,status):
        with self.workspace.connection() as db:db.execute('UPDATE ai_usage SET status=? WHERE id=?',(status,identifier))
    def flush_spool(self):
        for path in sorted(self.spool.glob('*.json'))[:100]:
            payload=json.loads(path.read_text());operation=payload['operation']
            if operation not in {'finish','response','outcome'}:raise ValueError('Invalid usage observation.')
            method=getattr(type(self),operation).__wrapped__
            method(self,*payload['args'],**payload['kwargs']);path.unlink()

    def dashboard(self,days=7,user_id=None):
        point=datetime.now(timezone.utc)
        since=(point.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=days-1)).isoformat()
        with self.workspace.connection() as db:
            query='SELECT user_id,provider,model,started_at,status,input_tokens,output_tokens,cached_tokens,cost_usd FROM ai_usage WHERE started_at>=?';args=[since]
            if user_id:query+=' AND user_id=?';args.append(user_id)
            rows=[dict(r) for r in db.execute(query+' ORDER BY started_at',args)]
        def aggregate(entries):
            known=[r for r in entries if r['input_tokens'] is not None and r['output_tokens'] is not None]
            priced=[r for r in entries if r['cost_usd'] is not None]
            tokens=sum(r['input_tokens']+r['output_tokens'] for r in known)
            total=sum((Decimal(r['cost_usd']) for r in priced),Decimal(0))
            return {'requests':len(entries),'known_usage_requests':len(known),'unknown_usage_requests':len(entries)-len(known),
                'input_tokens':sum(r['input_tokens'] for r in known),'output_tokens':sum(r['output_tokens'] for r in known),
                'cached_tokens':sum(r['cached_tokens'] or 0 for r in known),'total_tokens':tokens,
                'average_tokens_per_day':round(tokens/days,2),'average_requests_per_day':round(len(entries)/days,2),
                'estimated_cost_usd':str(total),'average_cost_usd_per_day':str(total/Decimal(days)),
                'unpriced_requests':len(entries)-len(priced)}
        users=sorted({r['user_id'] for r in rows});models=sorted({r['model'] for r in rows})
        daily={}
        for r in rows:daily.setdefault(r['started_at'][:10],[]).append(r)
        return {'days':days,'since':since,'timezone':'UTC','totals':aggregate(rows),
            'users':[{'user_id':u,**aggregate([r for r in rows if r['user_id']==u])} for u in users],
            'models':[{'model':m,**aggregate([r for r in rows if r['model']==m])} for m in models],
            'daily':[{'date':(point-timedelta(days=n)).date().isoformat(),
                **aggregate(daily.get((point-timedelta(days=n)).date().isoformat(),[]))} for n in reversed(range(days))]}
