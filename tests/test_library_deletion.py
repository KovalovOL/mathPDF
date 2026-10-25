"""Deletion is explicit, owner-scoped and cascades only primary-source sets."""
import copy
import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from formula_lab.app import create_app
from formula_lab.study import StudySet


def identity(client, app, subject='deletion-owner'):
    token = app.state.auth.create_session({'sub': subject, 'email': subject+'@example.invalid'}, None)
    client.cookies.set(app.state.auth.config.session_cookie, token)
    client.headers['Origin'] = app.state.auth.config.base_url
    return app.state.auth.session_user(token).id


def upload(client, width):
    writer, data = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=width, height=800); writer.write(data)
    response = client.post('/api/documents', files={'file': ('notes.pdf', data.getvalue(), 'application/pdf')})
    assert response.status_code == 201
    return response.json()


def payload(document, context=None):
    return StudySet.model_validate({'title': 'Owned set', 'mode': 'flashcards', 'document': document, 'pages': [1],
        'items': [{'title': 'Definition', 'question': [{'kind':'text','text':'Recall the definition.'}],
                   'answer': [{'kind':'text','text':'The saved explanation.'}],
                   'source': {'page':1,'document_id':document['id'],'line_start':None,'line_end':None,'quote':None}}],
        'notes':[], 'metadata':{'retained':'original'},
        'context_documents': [{'document':context,'pages':[1]}] if context else []}).model_dump(mode='json')


def test_primary_cascade_preserves_context_only_content_and_other_accounts(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        owner = identity(client, app)
        primary, other = upload(client, 600), upload(client, 610)
        source_set, context_set = payload(primary), payload(other, primary)
        assert client.post('/api/study-sets', json=source_set).status_code == 200
        # Persist a versionless snapshot to exercise backward-compatible context detachment.
        context_set.pop('schema_version')
        app.state.workspace.save_set(context_set, owner)
        original = copy.deepcopy(context_set)
        path = app.state.workspace.path(primary['id'], owner)
        impact = client.get('/api/documents/'+primary['id']+'/deletion').json()
        assert [entry['id'] for entry in impact['study_sets']] == [source_set['id']]
        assert [entry['id'] for entry in impact['context_sets']] == [context_set['id']]
        assert client.delete('/api/documents/'+primary['id']).status_code == 428
        identity(client, app, 'another-owner')
        for path_suffix in ['', '/deletion', '/file']:
            assert client.get('/api/documents/'+primary['id']+path_suffix).status_code == 404
        assert client.delete('/api/documents/'+primary['id'], headers={'If-Match':impact['revision']}).status_code == 404
        identity(client, app)
        response = client.delete('/api/documents/'+primary['id'], headers={'If-Match':impact['revision']})
        assert response.status_code == 200
        assert response.json()['deleted_set_ids'] == [source_set['id']]
        assert not path.exists()
        assert client.get('/api/study-sets/'+source_set['id']).status_code == 404
        retained = app.state.workspace.study_set(context_set['id'], owner)
        original['context_documents'] = []
        assert retained == original  # No normalization, item loss or metadata rewriting.
        opened = client.get('/api/study-sets/'+context_set['id'])
        assert opened.status_code == 200
        assert client.post('/api/study-sets', json=opened.json()).status_code == 200
        assert client.post('/api/study/export.pdf', json=opened.json()).status_code == 200
        assert client.get('/api/documents/'+other['id']+'/file').status_code == 200


def test_stale_delete_requires_review_and_set_deletion_keeps_files(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        identity(client, app)
        document = upload(client, 600)
        impact = client.get('/api/documents/'+document['id']+'/deletion').json()
        saved = payload(document)
        assert client.post('/api/study-sets', json=saved).status_code == 200
        assert client.delete('/api/documents/'+document['id'], headers={'If-Match':impact['revision']}).status_code == 409
        assert client.get('/api/documents/'+document['id']).status_code == 200
        set_impact = client.get('/api/study-sets/'+saved['id']+'/deletion').json()
        assert client.delete('/api/study-sets/'+saved['id']).status_code == 428
        saved['title'] = 'Edited after confirmation opened'
        client.post('/api/study-sets', json=saved)
        assert client.delete('/api/study-sets/'+saved['id'], headers={'If-Match':set_impact['revision']}).status_code == 409
        current = client.get('/api/study-sets/'+saved['id']+'/deletion').json()
        identity(client, app, 'another-owner')
        assert client.delete('/api/study-sets/'+saved['id'], headers={'If-Match':current['revision']}).status_code == 404
        identity(client, app)
        assert client.delete('/api/study-sets/'+saved['id'], headers={'If-Match':current['revision']}).status_code == 200
        assert client.get('/api/documents/'+document['id']+'/file').status_code == 200
