"""Platform boundaries and accounting use synthetic users and documents only."""
from datetime import datetime,timezone
from decimal import Decimal
import io
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from formula_lab.app import create_app
from formula_lab.platform_services import create_service
from formula_lab.report_safety import sanitize,bounded
from formula_lab.reports import ReportInput,ReportUpdate
from formula_lab.roles import OWNER_EMAIL
from formula_lab.usage import Usage
from formula_lab.migration import read_snapshot,digest_rows
from formula_lab.database import parameters


def login(app,email='tester@example.invalid'):
    token=app.state.auth.create_session({'sub':'test-'+email,'email':email,'name':'<b>Fixture</b>'},None)
    return token,app.state.auth.session_user(token)


def session(client,app,token):
    client.cookies.set(app.state.auth.config.session_cookie,token)
    client.headers['Origin']=app.state.auth.config.base_url


def test_owner_only_grants_and_immediate_revocation(tmp_path):
    app=create_service('admin',tmp_path);owner_token,owner=login(app,OWNER_EMAIL.upper());token,user=login(app)
    with TestClient(app) as c:
        session(c,app,token)
        for path in ['/admin','/api/admin/users','/api/admin/overview','/api/admin/prices','/api/admin/reports']:
            assert c.get(path).status_code==403
        assert c.patch('/api/admin/users/'+user.id+'/role',json={'role':'admin'}).status_code==403
        session(c,app,owner_token);assert c.get('/admin').status_code==200
        assert c.patch('/api/admin/users/'+user.id+'/role',json={'role':'admin'}).status_code==200
        session(c,app,token);assert c.get('/api/admin/overview').status_code==200
        assert c.patch('/api/admin/users/'+owner.id+'/role',json={'role':'free'}).status_code==403
        assert c.post('/api/admin/prices',json={'provider':'openai','model':'x','input_per_million':'1','cached_per_million':'.1','output_per_million':'2','source':'https://example.invalid'}).status_code==403
        session(c,app,owner_token);assert c.patch('/api/admin/users/'+owner.id+'/role',json={'role':'free'}).status_code==400
        assert c.patch('/api/admin/users/'+user.id+'/role',json={'role':'premium'}).status_code==200
        session(c,app,token);assert c.get('/api/admin/users').status_code==403
        assert app.state.auth.session_user(token).role=='premium'
        session(c,app,owner_token);assert c.patch('/api/admin/users/'+user.id+'/role',json={'role':'owner'}).status_code==422
        assert c.patch('/api/admin/users/'+user.id+'/role',json={'role':'free'},headers={'Origin':'https://evil.invalid'}).status_code==403
    with app.state.workspace.connection() as db:assert db.execute('SELECT COUNT(*) FROM role_audit').fetchone()[0]==2


def test_free_cannot_read_admin_html_from_app(tmp_path):
    app=create_app(tmp_path);token,user=login(app)
    with TestClient(app) as c:
        session(c,app,token)
        assert c.get('/static/admin.html').status_code==403
        assert c.get('/static/admin.html/').status_code==403
        assert c.get('/api/me').json()['role']=='free'
        c.cookies.clear();assert c.get('/health').status_code==200


def test_real_usage_and_immutable_price_snapshot(tmp_path):
    app=create_app(tmp_path);_,user=login(app);usage=app.state.workspace.usage
    ident=usage.start(user.id,'openai','gpt-4.1-mini',{'request':{'count':10},'secret':'hidden'})
    usage.finish(ident,'received',SimpleNamespace(input_tokens=1000,output_tokens=200,input_tokens_details=SimpleNamespace(cached_tokens=400),output_tokens_details=SimpleNamespace(reasoning_tokens=100)),250,'provider-id')
    usage.response(ident,'gpt-4.1-mini-2025-04-14','completed','not valid study JSON')
    usage.outcome(ident,'failed')
    with app.state.workspace.connection() as db:
        row=dict(db.execute('SELECT * FROM ai_usage WHERE id=?',(ident,)).fetchone())
        assert Decimal(row['cost_usd'])==Decimal('0.0006')
        assert row['status']=='failed' and row['input_tokens']==1000 and row['output_tokens']==200
        assert '[REDACTED]' in row['context']
        db.execute('INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?)',(uuid4().hex,'openai','gpt-4.1-mini',datetime.now(timezone.utc).isoformat(),'50','50','50','fixture',user.id))
    usage.outcome(ident,'failed')
    unknown=usage.start(user.id,'openai','unknown-model',{})
    usage.finish(unknown,'provider_error')
    dashboard=usage.dashboard(7);t=dashboard['totals']
    assert t['requests']==2 and t['total_tokens']==1200 and t['average_tokens_per_day']==round(1200/7,2)
    assert t['unknown_usage_requests']==1 and t['unpriced_requests']==1
    assert Decimal(t['estimated_cost_usd'])==Decimal('.0006')
    assert len(dashboard['daily'])==7 and len(dashboard['models'])==2


def test_redaction_nested_credentials_and_boundaries(monkeypatch):
    monkeypatch.setenv('SAMPLE_SECRET','top-secret-known-value')
    dirty={'cookies':['session'],'clientSecret':'x','X_API_KEY':'y','refreshToken':'z','context':{'comment':'top-secret-known-value'},'formula':r'A \cap B','payload':'Bearer abcdefghijklmnop','private_key':'-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----'}
    result=sanitize(dirty)
    assert all(result[k]=='[REDACTED]' for k in ['cookies','clientSecret','X_API_KEY','refreshToken','private_key'])
    assert result['formula']==dirty['formula'] and result['context']['comment']=='[REDACTED]' and result['payload']=='[REDACTED]'
    assert bounded({'text':'я'*10000},1000)['_truncated'] is True
    assert len(json.dumps(bounded({'text':'я'*10000},1000),ensure_ascii=False).encode())<1000


def test_report_dedup_source_isolation_and_private_bundle(tmp_path):
    app=create_app(tmp_path);_,user=login(app);_,other=login(app,'other@example.invalid');ws=app.state.workspace;reports=ws.reports
    doc=ws.add_document('notes.txt',b'original version',user.id);foreign=ws.add_document('private.txt',b'foreign secret',other.id);ref=uuid4().hex
    reports.event(user,{'request_id':ref,'status':500,'request':{'document_id':doc.id,'password':'no'}})
    initial=reports.record(user,ReportInput(origin='automatic',request_id=ref,context={'server':{'status':500,'document_id':doc.id}}))
    enriched=reports.record(user,ReportInput(origin='automatic',request_id=ref,context={'active':{'document':foreign.model_dump()},'comment':'<script>no</script>'}))
    assert initial['id']==enriched['id'] and len(reports.list())==1
    stored=reports.get(initial['id']);assert stored['payload']['server']['status']==500
    assert [s['id'] for s in stored['manifest']['sources']]==[doc.id]
    assert 'no' not in json.dumps(stored['payload']['recent_requests'][0]['request']['password'])
    assert reports.collect_one();assert reports.get(initial['id'])['collection_status']=='ready'
    import zipfile
    packet=zipfile.ZipFile(io.BytesIO(reports.bundle(initial['id'])))
    assert packet.read('files/'+doc.id+'/notes.txt')==b'original version'
    assert b'foreign secret' not in packet.read('report.json')
    reports.update(initial['id'],ReportUpdate(status='investigating',note='secret sk-abcdefghijklmnop'),user)
    assert '[REDACTED]' in reports.get(initial['id'])['note']
    manual=reports.record(user,ReportInput(category='too_slow',comment='Please respond faster.'))
    assert manual['id']!=initial['id']


def test_worker_retries_storage_outage_and_retains_snapshots(tmp_path,monkeypatch):
    app=create_app(tmp_path);_,user=login(app);ws=app.state.workspace;doc=ws.add_document('a.txt',b'fixture',user.id);r=ws.reports
    entry=r.record(user,ReportInput(context={'document_id':doc.id}));real=ws.storage.copy
    monkeypatch.setattr(ws.storage,'copy',lambda *args:(_ for _ in ()).throw(OSError('offline')))
    assert not r.collect_one();assert r.get(entry['id'])['collection_status']=='retrying'
    monkeypatch.setattr(ws.storage,'copy',real)
    with ws.connection() as db:db.execute('UPDATE reports SET next_attempt=? WHERE id=?',('2000',entry['id']))
    assert r.collect_one();ws.storage.delete('documents/'+doc.id)  # unrelated absent key is harmless
    assert r.get(entry['id'])['manifest']['files'][0]['status']=='available'


def test_report_spool_survives_database_outage(tmp_path,monkeypatch):
    app=create_app(tmp_path);_,user=login(app);ws=app.state.workspace;r=ws.reports;real=ws.connection
    monkeypatch.setattr(ws,'connection',lambda:(_ for _ in ()).throw(OSError('offline')))
    queued=r.record(user,ReportInput(comment='fixture',category='bug'))
    assert queued['collection_status']=='spooled' and len(list(r.spool.glob('*.json')))==1
    monkeypatch.setattr(ws,'connection',real);r.flush_spool()
    assert not list(r.spool.glob('*.json')) and len(r.list())==1
    assert r.list()[0]['id']==queued['id']


def test_reports_service_requires_session_origin_and_owner(tmp_path):
    app=create_service('reports',tmp_path);token,user=login(app);other_token,other=login(app,'other@example.invalid')
    with TestClient(app) as c:
        assert c.post('/api/reports',json={}).status_code==401
        session(c,app,token)
        assert c.post('/api/reports',json={},headers={'Origin':'https://evil.invalid'}).status_code==403
        r=c.post('/api/reports',json={'category':'formatting','comment':'A formula is clipped.'})
        assert r.status_code==202
        identifier=r.json()['id'];assert c.get('/api/reports/'+identifier).status_code==200
        session(c,app,other_token);assert c.get('/api/reports/'+identifier).status_code==404
        assert c.post('/api/reports',content='x'*2097153,headers={'Content-Type':'application/json'}).status_code==413


def test_automatic_server_reports_validation_failures_without_sensitive_inputs(tmp_path):
    app=create_app(tmp_path);token,user=login(app)
    with TestClient(app) as c:
        session(c,app,token)
        result=c.post('/api/study/jobs',json={'count':'invalid','secret':'do-not-retain'})
        assert result.status_code in {422,503}
    reports=app.state.workspace.reports.list();assert len(reports)==1
    report=app.state.workspace.reports.get(reports[0]['id'])
    assert report['request_id']==result.headers['x-mathpdf-request-id']
    assert 'do-not-retain' not in json.dumps(report)


def test_parameter_conversion_preserves_quoted_question_marks_and_percent():
    assert parameters("SELECT '?' AS literal, ? AS value, '50%' AS rate") == "SELECT '?' AS literal, %s AS value, '50%%' AS rate"


def test_migration_refuses_unknown_tables_and_preserves_raw_payload(tmp_path):
    import sqlite3
    path=tmp_path/'source.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE study_sets (id TEXT,owner_id TEXT,payload TEXT)')
        db.execute('INSERT INTO study_sets VALUES (?,?,?)',('id','owner','{ "formula": "\\cap", "version": null }'))
    entries=read_snapshot(path)
    assert entries['study_sets']['rows'][0][2]=='{ "formula": "\\cap", "version": null }'
    assert entries['study_sets']['sha256']==digest_rows(entries['study_sets']['rows'])
    with sqlite3.connect(path) as db:db.execute('CREATE TABLE unknown (id TEXT)')
    with pytest.raises(ValueError,match='unsupported source table'):read_snapshot(path)


def test_server_enrichment_retains_browser_context_when_it_arrives_first(tmp_path):
    app=create_app(tmp_path);_,user=login(app);reports=app.state.workspace.reports;ref=uuid4().hex
    record=reports.record(user,ReportInput(origin='automatic',request_id=ref,context={'active':{'item_index':3}}))
    reports.record(user,ReportInput(origin='automatic',request_id=ref,context={'server':{'job_error':'fixture'}}))
    stored=reports.get(record['id'])['payload']
    assert stored['client']['active']['item_index']==3 and stored['server']['job_error']=='fixture'


def test_pending_report_pins_deleted_source_until_private_snapshot_is_ready(tmp_path):
    app=create_app(tmp_path);_,user=login(app);ws=app.state.workspace;doc=ws.add_document('snapshot.txt',b'retain this revision',user.id)
    source=ws.path(doc.id,user.id);report=ws.reports.record(user,ReportInput(context={'document_id':doc.id}))
    impact=ws.deletion_info('document',doc.id,user.id);ws.delete('document',doc.id,user.id,impact['revision'])
    assert not source.exists()
    assert ws.reports.collect_one() and not source.exists()
    import zipfile
    packet=zipfile.ZipFile(io.BytesIO(ws.reports.bundle(report['id'])))
    assert packet.read('files/'+doc.id+'/snapshot.txt')==b'retain this revision'


def test_paid_usage_is_durably_replayed_after_database_outage(tmp_path,monkeypatch):
    import sqlite3
    app=create_app(tmp_path);_,user=login(app);ws=app.state.workspace;usage=ws.usage
    identifier=usage.start(user.id,'openai','gpt-4.1-mini',{})
    real=ws.connection
    monkeypatch.setattr(ws,'connection',lambda:(_ for _ in ()).throw(sqlite3.OperationalError('offline')))
    usage.finish(identifier,'received',SimpleNamespace(input_tokens=100,output_tokens=50,input_tokens_details=SimpleNamespace(cached_tokens=20)),20,'fixture')
    usage.response(identifier,'gpt-4.1-mini','completed','{"result":"invalid content"}')
    usage.outcome(identifier,'failed')
    assert len(list(usage.spool.glob('*.json')))==3
    monkeypatch.setattr(ws,'connection',real);usage.flush_spool()
    with ws.connection() as db:row=db.execute('SELECT * FROM ai_usage WHERE id=?',(identifier,)).fetchone()
    assert row['input_tokens']==100 and row['output_tokens']==50 and row['status']=='failed'
    assert Decimal(row['cost_usd'])==Decimal('.000114')
    assert not list(usage.spool.glob('*.json'))


def test_unexpected_server_report_has_safe_stack_locations(tmp_path):
    app=create_app(tmp_path);token,user=login(app)
    @app.get('/api/fixture-failure')
    def failing():raise RuntimeError('This private exception message must not be retained.')
    with TestClient(app) as c:
        session(c,app,token);assert c.get('/api/fixture-failure').status_code==500
    report=app.state.workspace.reports.get(app.state.workspace.reports.list()[0]['id'])
    summary=report['payload']['server']['exception']
    assert any(frame['type']=='RuntimeError' for frame in summary)
    assert 'private exception message' not in json.dumps(report)
