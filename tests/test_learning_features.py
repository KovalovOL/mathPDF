"""Names, allowances and self-assessment preserve historical content and ownership."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from formula_lab.app import create_app
from formula_lab.platform_services import create_service
from formula_lab.quotas import QuotaExceeded, period
from formula_lab.reviews import ReviewAnswer
from formula_lab.roles import OWNER_EMAIL
from test_platform import login, session
from test_library_organization import file, saved


def test_rename_preserves_legacy_content_binary_and_placement(tmp_path):
    app=create_app(tmp_path);token,user=login(app);other_token,other=login(app,'other@example.invalid');ws=app.state.workspace
    with TestClient(app) as c:
        session(c,app,token);doc=file(c)
        raw=json.loads((Path(__file__).parent/'fixtures/study-sets/legacy-flashcards.json').read_text())
        raw.update(document=doc,pages=[1]);raw.pop('schema_version',None);raw['metadata']['unknown_historical']={'formula':r'A \cap B','variants':[1,2]}
        ws.save_set(raw,user.id);binary=ws.path(doc['id'],user.id).read_bytes()
        c.patch('/api/library/items/study-sets/'+raw['id'],json={'archived':True})
        namepath='/api/library/items/documents/'+doc['id']+'/name'
        renamed=c.patch(namepath,json={'name':'New name','expected_name':doc['filename']})
        assert renamed.status_code==200 and renamed.json()['filename']=='New name.pdf'
        assert ws.path(doc['id'],user.id).read_bytes()==binary
        assert c.patch(namepath,json={'name':'stale','expected_name':doc['filename']}).status_code==409
        for name in ['../no','a\\b','   ','bad\nname']:
            assert c.patch(namepath,json={'name':name}).status_code==400
        setpath='/api/library/items/study-sets/'+raw['id']+'/name'
        assert c.patch(setpath,json={'name':'My recall set'}).status_code==200
        expected={**raw,'title':'My recall set'}
        assert ws.study_set(raw['id'],user.id)==expected
        assert c.get('/api/study-sets/'+raw['id']).status_code==200
        assert c.get('/api/library').json()['sets'][0]['archived']
        session(c,app,other_token)
        assert c.patch(namepath,json={'name':'foreign'}).status_code==404
        assert c.patch(setpath,json={'name':'foreign'}).status_code==404
    assert create_app(tmp_path).state.workspace.study_set(raw['id'],user.id)==expected


def test_quota_accounting_reservations_releases_and_month_reset(tmp_path):
    app=create_app(tmp_path);_,owner=login(app,OWNER_EMAIL);_,user=login(app);ws=app.state.workspace;u=ws.usage;q=u.quota
    q.update(owner,1000)
    attempt=u.start(user.id,'openai','gpt-4.1-mini',{'estimated_tokens':700})
    state=q.status(user.id);assert state['remaining_percent']==30 and state['reserved_tokens']==700
    with pytest.raises(QuotaExceeded):u.start(user.id,'openai','gpt-4.1-mini',{'estimated_tokens':400})
    u.finish(attempt,'received',{'input_tokens':200,'output_tokens':100,'input_tokens_details':{'cached_tokens':150}})
    u.outcome(attempt,'failed') # Charged even when content was unusable; cached input is not added twice.
    u.finish(attempt,'provider_error') # A late unknown observation must not erase known usage.
    assert q.status(user.id)['used_tokens']==300 and q.status(user.id)['reserved_tokens']==0
    rejected=u.start(user.id,'openai','gpt-4.1-mini',{'estimated_tokens':600})
    u.finish(rejected,'provider_error',unbilled=True)
    assert q.status(user.id)['remaining_tokens']==700
    unknown=u.start(user.id,'openai','gpt-4.1-mini',{'estimated_tokens':600})
    u.finish(unknown,'provider_error')
    assert q.status(user.id)['reserved_tokens']==600
    u.finish(unknown,'received',{'input_tokens':50,'output_tokens':20})
    assert q.status(user.id)['used_tokens']==370 and q.status(user.id)['reserved_tokens']==0
    # An underestimated provider response is still fully accounted for.
    over=u.start(user.id,'openai','gpt-4.1-mini',{'estimated_tokens':100})
    u.finish(over,'received',{'input_tokens':1000,'output_tokens':100})
    assert q.status(user.id)['remaining_percent']==0 and q.status(user.id)['used_tokens']==1470
    with pytest.raises(QuotaExceeded):q.check(user.id)
    with ws.connection() as db:
        next_month=q._status(db,user.id,datetime.fromisoformat(period()[1]))
    assert next_month['remaining_percent']==100
    assert period(datetime(2026,12,15,tzinfo=timezone.utc))[1].startswith('2027-01-01')


def test_quota_atomic_parallel_dispatch_and_role_changes(tmp_path):
    app=create_app(tmp_path);_,owner=login(app,OWNER_EMAIL);_,user=login(app);u=app.state.workspace.usage;q=u.quota
    q.update(owner,1000)
    def attempt(_):
        try:return u.start(user.id,'openai','fixture',{'estimated_tokens':600})
        except QuotaExceeded:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,range(2)))
    assert sum(r is not None for r in results)==1 and q.status(user.id)['reserved_tokens']==600
    app.state.auth.roles.change(owner,user.id,'premium')
    assert not q.status(user.id)['limited']
    assert u.start(user.id,'openai','fixture',{'estimated_tokens':1000000})
    app.state.auth.roles.change(owner,user.id,'free')
    assert q.status(user.id)['limited']


def test_admin_default_override_inheritance_and_authorization(tmp_path):
    app=create_service('admin',tmp_path);ot,owner=login(app,OWNER_EMAIL);token,user=login(app);_,admin=login(app,'admin@example.invalid');q=app.state.workspace.usage.quota
    app.state.auth.roles.change(owner,admin.id,'admin')
    with TestClient(app) as c:
        session(c,app,token)
        assert c.patch('/api/admin/generation-limits',json={'monthly_tokens':1234}).status_code==403
        session(c,app,ot)
        assert c.patch('/api/admin/generation-limits',json={'monthly_tokens':1234}).status_code==200
        route='/api/admin/users/'+user.id+'/generation-limit'
        assert c.patch(route,json={'monthly_tokens':2000}).json()['monthly_tokens']==2000
        assert c.get('/api/admin/users/'+user.id).json()['allowance']['override_monthly_tokens']==2000
        assert c.patch(route,json={'monthly_tokens':None}).json()['monthly_tokens']==1234
        for value in [-1,True,1.5,'5',None]:
            assert c.patch('/api/admin/generation-limits',json={'monthly_tokens':value}).status_code==422
    assert q.update(admin,1500)['monthly_tokens']==1500
    with pytest.raises(HTTPException):q.update(user,2000)
    with app.state.workspace.connection() as db:assert db.execute('SELECT COUNT(*) FROM admin_audit WHERE action=?',('generation_allowance',)).fetchone()[0]==4


def test_exhausted_allowance_blocks_both_generation_routes_before_provider(tmp_path):
    class Provider:
        calls=0
        async def generate(self,*args,**kwargs):self.calls+=1;raise AssertionError('Must not be called')
    provider=Provider();app=create_app(tmp_path,provider=provider);token,user=login(app);_,owner=login(app,OWNER_EMAIL)
    app.state.workspace.usage.quota.update(owner,0)
    with TestClient(app) as c:
        session(c,app,token);doc=file(c)
        for route in ['/api/study/generate','/api/study/jobs']:
            response=c.post(route,json={'document_id':doc['id'],'pages':[1],'count':1,'mode':'flashcards'})
            assert response.status_code==429,response.text
            assert 'renews' in response.json()['detail']
        assert c.get('/api/generation/allowance').json()['remaining_percent']==0
    assert provider.calls==0


def test_review_rounds_resume_idempotency_history_and_content_revision(tmp_path):
    app=create_app(tmp_path);token,user=login(app);other_token,other=login(app,'other@example.invalid');ws=app.state.workspace
    with TestClient(app) as c:
        session(c,app,token);doc=file(c);content=saved(doc)
        content['items'].append({**content['items'][0],'title':'Second card'})
        route='/api/study-sets/'+content['id']+'/reviews'
        # Progress also works before Save; saving this deck later keeps the same round.
        response=c.post(route,json={'content':content});assert response.status_code==200,response.text
        first=response.json();answer='/api/reviews/'+first['id']+'/answers'
        a=c.post(answer,json={'index':0,'correct':True});assert a.json()['answered_count']==1
        assert c.post(answer,json={'index':0,'correct':True}).json()['answered_count']==1
        assert c.post(answer,json={'index':0,'correct':False}).status_code==409
        assert c.post(answer,json={'index':2,'correct':True}).status_code==400
        assert c.post(answer,json={'index':True,'correct':True}).status_code==422
        ws.save_set(content,user.id)
        assert c.post(route,json={}).json()['id']==first['id']
        assert c.post(route,json={'new_round':True}).json()['id']==first['id']
        c.patch('/api/library/items/study-sets/'+content['id']+'/name',json={'name':'New deck title'})
        c.patch('/api/library/items/documents/'+doc['id']+'/name',json={'name':'Source renamed'})
        assert c.post(route,json={}).json()['id']==first['id']
        done=c.post(answer,json={'index':1,'correct':False}).json()
        assert done['completed_at'] and done['score_percent']==50 and done['incorrect_count']==1
        assert c.post(route,json={}).json()['completed_at']
        second=c.post(route,json={'new_round':True}).json()
        assert second['id']!=first['id'] and second['history'][0]['score_percent']==50
        assert c.post(route,json={'new_round':True}).json()['id']==second['id']
        changed=ws.study_set(content['id'],user.id);changed['items'][0]['answer'][0]['text']='New content'
        revision=c.post(route,json={'content':changed}).json()
        assert revision['id']!=second['id'] and not revision['history']
        session(c,app,other_token)
        assert c.post(route,json={}).status_code==404
        assert c.post(route,json={'content':content}).status_code==404
        assert c.post(answer,json={'index':0,'correct':True}).status_code==404
    restarted=create_app(tmp_path)
    assert restarted.state.reviews.start(user.id,content['id'],content)['id']==second['id']


def test_parallel_review_retries_do_not_double_count(tmp_path):
    app=create_app(tmp_path);_,user=login(app);ws=app.state.workspace
    doc=ws.add_document('fixture.txt',b'fixture',user.id);content=saved(doc.model_dump())
    round=app.state.reviews.start(user.id,content['id'],content)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:app.state.reviews.answer(user.id,round['id'],ReviewAnswer(index=0,correct=True)),range(2)))
    assert all(r['answered_count']==1 and len(r['history'])==1 for r in results)
