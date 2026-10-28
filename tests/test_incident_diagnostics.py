"""Structured logs and compact summaries never expose exception messages or content."""
import io
import json
import logging
from urllib.parse import quote

from fastapi.testclient import TestClient
from formula_lab.app import create_app
from formula_lab.diagnostics import JsonFormatter,CorrelationFilter,http_context,request_context,frontend_context,error_identity
from formula_lab.report_summary import summarize
from test_platform import login,session


def test_json_log_is_one_safe_correlated_line(monkeypatch):
    monkeypatch.setenv('SAMPLE_SECRET','private-known-credential')
    buffer=io.StringIO();handler=logging.StreamHandler(buffer);handler.setFormatter(JsonFormatter());handler.addFilter(CorrelationFilter())
    logger=logging.Logger('formula_lab.fixture');logger.addHandler(handler)
    token=request_context.set('a'*32);context=http_context.set({'route':'/api/library','user_id':'b'*32,'ui':{'screen':'library','action':'Open library'}})
    try:
        try:raise RuntimeError('private exception content and private-known-credential')
        except RuntimeError as error:logger.error('Request failed',extra={'event':'http.request_failed',**error_identity(error,route='/api/library')})
    finally:request_context.reset(token);http_context.reset(context)
    lines=buffer.getvalue().splitlines();assert len(lines)==1
    record=json.loads(lines[0]);assert record['event']=='http.request_failed' and record['request_id']=='a'*32
    assert record['user_id']=='b'*32 and record['ui']['action']=='Open library'
    assert record['error_type']=='RuntimeError' and record['error_code']=='unexpected_server_error'
    assert 'private exception content' not in lines[0] and 'private-known-credential' not in lines[0]


def test_frontend_context_is_bounded_and_decodes_unicode_without_inputs():
    data={'screen':'workspace','action':'Save','file_name':'Нотатки.pdf','document_id':'a'*32,'page':2,'password':'do not log','answer':'private source text'}
    parsed=frontend_context(quote(json.dumps(data)))
    assert parsed['file_name']=='Нотатки.pdf' and parsed['page']==2
    assert 'password' not in parsed and 'answer' not in parsed
    assert frontend_context('x'*4097)=={} and frontend_context('%not-json')=={}
    assert frontend_context(quote('['*1100+']'*1100))=={}


def test_uvicorn_json_access_logs_drop_oauth_queries():
    record=logging.LogRecord('uvicorn.access',logging.INFO,__file__,1,'%s - "%s %s HTTP/%s" %s',
        ('127.0.0.1','GET','/auth/google/callback?code=private-oauth-code&state=private-state','1.1',302),None)
    line=JsonFormatter().format(record);data=json.loads(line)
    assert data['route']=='/auth/google/callback' and data['status']==302
    assert 'private-oauth-code' not in line and 'private-state' not in line


def test_historical_incident_summary_identifies_the_actual_library_failure():
    historical={'request_id':'a'*32,'user_id':'b'*32,'origin':'automatic','payload':{
        'server':{'path':'/api/library','method':'GET','status':500,'exception':[{'type':'UntranslatableCharacter','frames':['app.py:334:library_contents','library.py:132:snapshot','database.py:78:execute']}]},
        'client':{'page':{'path':'/'},'recent_actions':[{'type':'click','label':'MathPDF library'}]},
        'recent_requests':[{'request_id':str(i),'path':'/api/library','method':'GET','status':500} for i in range(10)]},'manifest':{'sources':[{'id':'c'*32,'filename':'Notes.pdf'}]}}
    summary=summarize(historical)
    assert summary['error_code']=='library_metadata_decode_failed' and summary['error_type']=='UntranslatableCharacter'
    assert summary['screen']=='library' and summary['location']=='library.py:132:snapshot'
    assert summary['documents'][0]['name']=='Notes.pdf'
    assert len(summary['timeline'])==1 and summary['timeline'][0]['count']==11
    assert len(json.dumps(summary))<2000
    # Adversarial optional client fields cannot make an administrator's detail view fail.
    assert summarize({'payload':{'client':{'recent_requests':[{'path':'/api/x','request_id':{},'status':{}}]},'server':{'exception':{},'error_details':[]}}})


def test_api_failure_records_typed_error_and_frontend_context(tmp_path):
    app=create_app(tmp_path);token,user=login(app)
    @app.get('/api/fixture-fail')
    def fail():raise RuntimeError('Never expose this private message.')
    with TestClient(app) as client:
        session(client,app,token)
        result=client.get('/api/fixture-fail',headers={'X-MathPDF-UI-Context':quote(json.dumps({'screen':'workspace','action':'Save study set','document_id':'a'*32,'page':3}))})
        assert result.status_code==500 and result.json()['error_code']=='unexpected_server_error'
    reports=app.state.workspace.reports
    report=reports.get(reports.list()[0]['id'])
    assert report['summary']['action']=='Save study set' and report['summary']['screen']=='workspace'
    assert report['summary']['page']==3 and report['summary']['error_type']=='RuntimeError'
    assert 'Never expose' not in json.dumps(report)
