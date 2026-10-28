"""Durable private reports, correlated request history and retriable source snapshots."""
import asyncio
from datetime import datetime,timedelta,timezone
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import time
from uuid import uuid4
import zipfile

from botocore.exceptions import ClientError
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

from .report_safety import bounded,sanitize,MAX_CONTEXT_BYTES
from .web_assets import build_id
from .diagnostics import error_identity


def stamp():return datetime.now(timezone.utc).isoformat()
ID=re.compile(r'^[a-f0-9]{32}$')


class ReportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    origin:Literal['automatic','manual']='manual'
    category:Literal['bug','incorrect_content','formatting','too_slow','answer_too_long','other']='bug'
    comment:str=Field(default='',max_length=5000)
    request_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')
    context:dict=Field(default_factory=dict)


class ReportUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status:Literal['new','investigating','resolved']
    note:str=Field(default='',max_length=5000)


class Reports:
    def __init__(self,workspace):
        self.workspace=workspace;self.spool=workspace.directory/'report-spool';self.spool.mkdir(exist_ok=True)
        with workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            db.executescript('''CREATE TABLE IF NOT EXISTS request_events (
                id TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS request_events_user_time ON request_events(user_id,created_at);
                CREATE INDEX IF NOT EXISTS request_events_time ON request_events(created_at);
                CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),origin TEXT NOT NULL,category TEXT NOT NULL,
                comment TEXT NOT NULL,request_id TEXT,dedupe_key TEXT UNIQUE NOT NULL,status TEXT NOT NULL,
                collection_status TEXT NOT NULL,attempts INTEGER NOT NULL,next_attempt TEXT NOT NULL,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL,manifest TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS reports_user_time ON reports(user_id,created_at);
                CREATE INDEX IF NOT EXISTS reports_collection ON reports(collection_status,next_attempt);''')
    def event(self,user,event):
        clean=bounded(event)
        with self.workspace.connection() as db:
            db.execute('INSERT INTO request_events VALUES (?,?,?,?) ON CONFLICT(id) DO NOTHING',
                (event['request_id'],user.id,stamp(),json.dumps(clean,ensure_ascii=False)))
            cutoff=(datetime.now(timezone.utc)-timedelta(days=14)).isoformat()
            db.execute('DELETE FROM request_events WHERE created_at<?',(cutoff,))
    def _sources(self,db,user_id,context):
        ids={}
        def walk(value,depth=0):
            if depth>24:return
            if isinstance(value,dict):
                if 'sha256' in value and 'media_type' in value and ID.fullmatch(str(value.get('id',''))):ids.setdefault(value['id'],None)
                for key,v in value.items():
                    if ('document_id' in key or key in {'current_file_id','active_file_id'}) and isinstance(v,str) and ID.fullmatch(v):ids.setdefault(v,None)
                    if key=='document' and isinstance(v,dict) and ID.fullmatch(str(v.get('id',''))):ids.setdefault(v['id'],None)
                    walk(v,depth+1)
            elif isinstance(value,list):
                for v in value[:300]:walk(v,depth+1)
        for name in ['client','server','latest_generation']:walk(context.get(name,{}))
        walk(context)
        sources=[]
        for identifier in list(ids)[:12]:
            row=db.execute('SELECT id,filename,stored_name,sha256,size FROM documents WHERE id=? AND owner_id=?',(identifier,user_id)).fetchone()
            if row:sources.append(dict(row))
        return sources
    def record(self,user,request:ReportInput,spool_on_failure=True,identifier=None,received_at=None):
        now=received_at or stamp();identifier=identifier or uuid4().hex
        key=hashlib.sha256((user.id+':'+request.origin+':'+(request.request_id or identifier)).encode()).hexdigest() if request.origin=='automatic' else identifier
        try:
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                existing=db.execute('SELECT * FROM reports WHERE dedupe_key=?',(key,)).fetchone()
                if not existing:
                    since=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
                    count=db.execute('SELECT COUNT(*) FROM reports WHERE user_id=? AND created_at>=?',(user.id,since)).fetchone()[0]
                    if count>=20:raise ValueError('Report limit reached. Please wait a minute and try again.')
                trace=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM request_events WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(user.id,))]
                usage=db.execute('SELECT id,context,status,model,started_at FROM ai_usage WHERE user_id=? ORDER BY started_at DESC LIMIT 1',(user.id,)).fetchone()
                context={'user':user.model_dump(),'build':build_id(),'client':request.context,'recent_requests':trace}
                if 'server' in request.context:
                    context['server']=request.context['server'];context['client']={}
                if usage:context['latest_generation']={'id':usage['id'],'model':usage['model'],'status':usage['status'],'started_at':usage['started_at'],'context':json.loads(usage['context'])}
                if existing:
                    context=json.loads(existing['payload']);context['recent_requests']=trace
                    if 'server' in request.context:context['server']={**context.get('server',{}),**request.context['server']}
                    else:context['client']=request.context
                    # Server context and initial source versions are retained when a browser enriches an automatic incident.
                    previous=json.loads(existing['manifest']);sources=previous.get('sources',[])
                    known={entry['id'] for entry in sources}
                    sources += [entry for entry in self._sources(db,user.id,context) if entry['id'] not in known]
                    context={k:context[k] for k in ['user','build','server','latest_generation','client','recent_requests'] if k in context}
                    payload=bounded(context);previous['sources']=sources[:12]
                    if len(sources)>12:previous['sources_truncated']=True
                    db.execute('UPDATE reports SET payload=?,manifest=?,updated_at=?,collection_status=?,next_attempt=? WHERE id=?',
                        (json.dumps(payload,ensure_ascii=False),json.dumps(previous,ensure_ascii=False),now,'pending',now,existing['id']))
                    return {'id':existing['id'],'status':existing['status'],'collection_status':'pending'}
                sources=self._sources(db,user.id,context)
                context={k:context[k] for k in ['user','build','server','latest_generation','client','recent_requests'] if k in context}
                payload=bounded(context)
                db.execute('''INSERT INTO reports (id,user_id,origin,category,comment,request_id,dedupe_key,status,
                    collection_status,attempts,next_attempt,created_at,updated_at,payload,manifest,note)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (identifier,user.id,request.origin,request.category,sanitize(request.comment),request.request_id,key,'new','pending',0,now,now,now,
                     json.dumps(payload,ensure_ascii=False),json.dumps({'sources':sources,'files':[]}),''))
            return {'id':identifier,'status':'new','collection_status':'pending'}
        except ValueError:raise
        except Exception as error:
            if not spool_on_failure:raise
            data={'user':user.model_dump(),'request':request.model_dump(mode='json'),'received_at':now}
            path=self.spool/(identifier+'.json');temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(sanitize(data),ensure_ascii=False));temp.chmod(0o600);temp.replace(path)
            logging.getLogger(__name__).warning('Report queued in durable local spool',extra={'event':'report.spooled','report_id':identifier,**error_identity(error)})
            return {'id':identifier,'status':'queued','collection_status':'spooled'}
    def flush_spool(self):
        from .auth import User
        for path in list(self.spool.glob('*.json'))[:20]:
            data=json.loads(path.read_text())
            self.record(User.model_validate(data['user']),ReportInput.model_validate(data['request']),False,identifier=path.stem,received_at=data.get('received_at'));path.unlink()
    def collect_one(self):
        if getattr(self.workspace,'usage',None):self.workspace.usage.flush_spool()
        self.flush_spool()
        now=stamp()
        with self.workspace.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM reports WHERE collection_status IN ('pending','collecting','retrying') AND next_attempt<=? ORDER BY created_at LIMIT 1",(now,)).fetchone()
            if not row:return False
            report=dict(row);lease=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
            db.execute("UPDATE reports SET collection_status='collecting',attempts=attempts+1,next_attempt=? WHERE id=?",(lease,report['id']))
        try:
            manifest=json.loads(report['manifest']);files=[]
            for source in manifest.get('sources',[]):
                target='reports/'+report['id']+'/files/'+source['id']+'/'+Path(source['stored_name']).name
                entry={'document_id':source['id'],'filename':source['filename'],'sha256':source['sha256'],'key':target}
                try:
                    try:self.workspace.storage.copy('documents/'+source['stored_name'],target,source['sha256'])
                    except ClientError as error:
                        if str(error.response.get('Error',{}).get('Code')) not in {'404','NoSuchKey','NotFound'}:raise
                        self.workspace.storage.copy('report-source-cache/'+source['stored_name'],target,source['sha256'])
                    except (FileNotFoundError,ValueError):
                        self.workspace.storage.copy('report-source-cache/'+source['stored_name'],target,source['sha256'])
                    entry['status']='available'
                except ClientError as error:
                    if str(error.response.get('Error',{}).get('Code')) not in {'404','NoSuchKey','NotFound'}:raise
                    entry['status']='unavailable';entry['reason']='The source was deleted before collection.'
                except (FileNotFoundError,ValueError):
                    entry['status']='unavailable';entry['reason']='The source version is missing or invalid.'
                files.append(entry)
            manifest['files']=files
            packet={'report':{k:report[k] for k in ['id','user_id','origin','category','comment','request_id','created_at']},'context':json.loads(report['payload']),'manifest':manifest}
            self.workspace.storage.put('reports/'+report['id']+'/context.json',json.dumps(bounded(packet,8*MAX_CONTEXT_BYTES),ensure_ascii=False).encode(),'application/json')
            with self.workspace.connection() as db:
                # Enrichment during collection requeues rather than being overwritten by this worker.
                changed=db.execute("UPDATE reports SET manifest=?,collection_status='ready',updated_at=? WHERE id=? AND collection_status='collecting' AND next_attempt=?",
                    (json.dumps(manifest,ensure_ascii=False),stamp(),report['id'],lease)).rowcount
            if changed:self.workspace._cleanup_binaries([source['stored_name'] for source in manifest.get('sources',[])])
            return True
        except Exception as error:
            delay=min(600,2**min(report['attempts']+1,9));retry=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat()
            with self.workspace.connection() as db:db.execute("UPDATE reports SET collection_status='retrying',next_attempt=? WHERE id=? AND collection_status='collecting' AND next_attempt=?",(retry,report['id'],lease))
            logging.getLogger(__name__).warning('Report collection will retry',extra={'event':'report.retry','report_id':report['id'],**error_identity(error)})
            return False
    async def worker(self):
        while True:
            try:
                worked=await asyncio.to_thread(self.collect_one)
                if not worked:await asyncio.sleep(2)
            except asyncio.CancelledError:raise
            except Exception as error:
                logging.getLogger(__name__).warning('Report worker unavailable',extra={'event':'report.worker_unavailable',**error_identity(error)});await asyncio.sleep(5)
    def list(self,limit=100,offset=0,status=None):
        with self.workspace.connection() as db:
            return [dict(r) for r in db.execute('''SELECT r.id,r.user_id,u.email,r.origin,r.category,r.comment,r.request_id,r.status,
                r.collection_status,r.attempts,r.created_at,r.updated_at FROM reports r JOIN users u ON u.id=r.user_id WHERE (CAST(? AS TEXT) IS NULL OR r.status=?) ORDER BY r.created_at DESC LIMIT ? OFFSET ?''',(status,status,limit,offset))]
    def get(self,identifier):
        with self.workspace.connection() as db:row=db.execute('SELECT * FROM reports WHERE id=?',(identifier,)).fetchone()
        if not row:raise KeyError('Report not found')
        data=dict(row);data['payload']=json.loads(data['payload']);data['manifest']=json.loads(data['manifest'])
        from .report_summary import summarize
        data['summary']=summarize(data);return data
    def update(self,identifier,request,actor):
        self.get(identifier)
        with self.workspace.connection() as db:
            db.execute('UPDATE reports SET status=?,note=?,updated_at=? WHERE id=?',(request.status,sanitize(request.note),stamp(),identifier))
            db.execute('INSERT INTO admin_audit VALUES (?,?,?,?,?)',(uuid4().hex,actor.id,'report_update',json.dumps(sanitize({'id':identifier,**request.model_dump()})),stamp()))
        return self.get(identifier)
    def bundle(self,identifier):
        report=self.get(identifier)
        if report['collection_status']!='ready':raise ValueError('This report is still collecting context. Try again shortly.')
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('report.json',json.dumps(report,ensure_ascii=False,indent=2))
            for entry in report['manifest'].get('files',[]):
                if entry['status']=='available':
                    path=self.workspace.storage.path(entry['key'],entry['sha256'])
                    archive.write(path,'files/'+entry['document_id']+'/'+Path(entry['filename']).name)
        return buffer.getvalue()
