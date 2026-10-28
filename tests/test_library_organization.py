"""Organization never mutates canonical content or crosses account boundaries."""
import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from formula_lab.app import create_app
from formula_lab.study import StudySet


def sign_in(client, app, subject='organizer'):
    token=app.state.auth.create_session({'sub':subject,'email':subject+'@example.invalid'},None)
    client.cookies.set(app.state.auth.config.session_cookie,token)
    client.headers['Origin']=app.state.auth.config.base_url
    return app.state.auth.session_user(token).id


def file(client,width=600):
    writer,data=PdfWriter(),io.BytesIO();writer.add_blank_page(width=width,height=800);writer.write(data)
    r=client.post('/api/documents',files={'file':('notes.pdf',data.getvalue(),'application/pdf')})
    assert r.status_code==201
    return r.json()


def folder(client,name,parent=None):
    r=client.post('/api/library/folders',json={'name':name,'parent_id':parent})
    assert r.status_code==201,r.text
    return r.json()


def item_path(kind,id):return '/api/library/items/'+kind+'/'+id

def saved(document):
    return StudySet.model_validate({'title':'Original content','document':document,'pages':[1],'mode':'flashcards',
        'items':[{'title':'Source','question':[{'kind':'text','text':'What is the definition?'}],
        'answer':[{'kind':'text','text':'An unchanged answer.'}],'source':{'page':1,'line_start':None,'line_end':None,'quote':None}}],
        'notes':[],'metadata':{'historical':'preserved'}}).model_dump(mode='json')


def test_organization_preserves_history_and_restart_and_isolation(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        owner=sign_in(c,app);doc=file(c);raw=saved(doc);raw.pop('schema_version');raw.pop('difficulty')
        app.state.workspace.save_set(raw,owner)
        start=c.get('/api/library').json()
        assert start['sets'][0]['difficulty']==3 and start['files'][0]['folder_id'] is None
        a=folder(c,'Algebra');b=folder(c,'Week 1',a['id'])
        for kind,id in [('documents',doc['id']),('study-sets',raw['id'])]:
            assert c.patch(item_path(kind,id),json={'folder_id':b['id'],'archived':True}).status_code==200
        assert app.state.workspace.study_set(raw['id'],owner)==raw
        # Archived sources and sets remain readable, and canonical saves do not reset placement.
        assert c.get('/api/documents/'+doc['id']+'/file').status_code==200
        opened=c.get('/api/study-sets/'+raw['id']).json()
        response=c.post('/api/study-sets',json=opened);assert response.status_code==200
        opened=response.json()
        assert c.get('/api/library').json()['sets'][0]['archived'] is True
        sign_in(c,app,'foreign')
        assert c.get('/api/library').json()=={'folders':[],'files':[],'sets':[]}
        for path in ['/api/library/folders/'+a['id'],item_path('documents',doc['id']),item_path('study-sets',raw['id'])]:
            assert c.patch(path,json={'parent_id':None} if 'folders/' in path else {'archived':False}).status_code==404
        foreign=folder(c,'Foreign');sign_in(c,app)
        assert c.patch(item_path('documents',doc['id']),json={'folder_id':foreign['id']}).status_code==404
        assert c.patch(item_path('documents',doc['id']),json={'archived':False}).status_code==200
    restarted=create_app(tmp_path)
    with TestClient(restarted) as c:
        sign_in(c,restarted);data=c.get('/api/library').json()
        assert data['files'][0]['folder_id']==b['id'] and not data['files'][0]['archived']
        assert data['sets'][0]['folder_id']==b['id'] and data['sets'][0]['archived']
        assert data['sets'][0]['document_id']==doc['id']
        assert restarted.state.workspace.study_set(raw['id'],owner)==opened


def test_tree_cycles_depth_names_and_safe_removal(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        sign_in(c,app);doc=file(c);a=folder(c,'Math');b=folder(c,'Week',a['id'])
        assert c.post('/api/library/folders',json={'name':' math '}).status_code==400
        assert c.post('/api/library/folders',json={'name':'   '}).status_code==400
        assert c.patch('/api/library/folders/'+a['id'],json={'parent_id':b['id']}).status_code==400
        parent=b
        for n in range(6):parent=folder(c,'Nested '+str(n),parent['id'])
        assert c.post('/api/library/folders',json={'name':'Too deep','parent_id':parent['id']}).status_code==400
        assert c.patch('/api/library/folders/'+b['id'],json={'name':'Renamed'}).status_code==200
        c.patch(item_path('documents',doc['id']),json={'folder_id':a['id'],'archived':True})
        url='/api/library/folders/'+a['id'];impact=c.get(url+'/deletion').json()
        assert c.delete(url).status_code==428
        c.patch(item_path('documents',doc['id']),json={'archived':False})
        assert c.delete(url,headers={'If-Match':impact['revision']}).status_code==409
        impact=c.get(url+'/deletion').json()
        assert c.delete(url,headers={'If-Match':impact['revision']}).status_code==200
        data=c.get('/api/library').json();assert data['files'][0]['folder_id'] is None
        assert next(f for f in data['folders'] if f['id']==b['id'])['parent_id'] is None
        assert c.get('/api/documents/'+doc['id']).status_code==200
        # Existing sibling names block folder removal atomically.
        box=folder(c,'Box');child=folder(c,'Duplicate',box['id']);folder(c,'Duplicate')
        c.patch(item_path('documents',doc['id']),json={'folder_id':box['id']})
        impact=c.get('/api/library/folders/'+box['id']+'/deletion').json()
        assert c.delete('/api/library/folders/'+box['id'],headers={'If-Match':impact['revision']}).status_code==400
        data=c.get('/api/library').json();assert data['files'][0]['folder_id']==box['id']
        assert next(f for f in data['folders'] if f['id']==child['id'])['parent_id']==box['id']


def test_archive_does_not_cascade_but_explicit_delete_still_does(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        owner=sign_in(c,app);doc=file(c);other=file(c,610);raw=saved(doc);app.state.workspace.save_set(raw,owner)
        c.patch(item_path('documents',doc['id']),json={'archived':True})
        data=c.get('/api/library').json()
        assert not data['sets'][0]['archived'] and data['sets'][0]['document_id']==doc['id']
        c.patch(item_path('study-sets',raw['id']),json={'archived':True})
        impact=c.get('/api/documents/'+doc['id']+'/deletion').json()
        assert c.delete('/api/documents/'+doc['id'],headers={'If-Match':impact['revision']}).status_code==200
        data=c.get('/api/library').json();assert not data['sets'] and [d['id'] for d in data['files']]==[other['id']]
        assert c.patch(item_path('documents',other['id']),json={'archived':'true'}).status_code==422
        with app.state.workspace.connection() as db:
            assert db.execute('SELECT COUNT(*) FROM library_items WHERE item_id IN (?,?)',(doc['id'],raw['id'])).fetchone()[0]==0
        # Removing a folder with an identically named child keeps that child intact.
        a=folder(c,'Same');child=folder(c,'Same',a['id'])
        impact=c.get('/api/library/folders/'+a['id']+'/deletion').json()
        assert c.delete('/api/library/folders/'+a['id'],headers={'If-Match':impact['revision']}).status_code==200
        assert next(f for f in c.get('/api/library').json()['folders'] if f['id']==child['id'])['parent_id'] is None


def test_library_projection_preserves_control_characters_in_saved_content(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        owner=sign_in(c,app);doc=file(c);raw=saved(doc)
        raw['items'][0]['answer'][0]['text']='Keep the original\x00text and formula $x^2$.'
        app.state.workspace.save_set(raw,owner)
        result=c.get('/api/library');assert result.status_code==200
        assert result.json()['files'][0]['id']==doc['id'] and result.json()['sets'][0]['document_id']==doc['id']
        assert app.state.workspace.study_set(raw['id'],owner)==raw
