"""Current authenticated application routes; identities/provider are test fixtures."""
import io
import time
import pytest

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from formula_lab.app import create_app
from formula_lab.study import GeneratedContent, ProviderResult, StudyItem


class FixtureProvider:
    def __init__(self):
        self.calls = 0

    async def generate(self, documents, system, task, *, count, mode):
        self.calls += 1
        items = []
        for i in range(1, count + 1):
            items.append(StudyItem.model_validate({
                'goal_step': i, 'title': f'Expression {i}',
                'question': [{'kind': 'text', 'text': f'Recall expression {i}.'}],
                'answer': [{'kind': 'math', 'latex': f'x_{i}', 'display': True,
                              'source': {'document_id': documents[0].document.id, 'page': 1,
                                         'line_start': None, 'line_end': None, 'quote': None},
                              'original_latex': None, 'change': None},
                           {'kind': 'text', 'text': f'Test explanation {i}.'}]}))
        return ProviderResult(content=GeneratedContent(items=items, notes=[]), provider='fixture', model='fixture')


def sign_in(client, app, sub='account-one'):
    token = app.state.auth.create_session({'sub': sub, 'email': sub + '@example.invalid'}, None)
    client.cookies.set(app.state.auth.config.session_cookie, token)
    client.headers['Origin'] = app.state.auth.config.base_url


def upload(client):
    pdf = PdfWriter()
    pdf.add_blank_page(width=600, height=800)
    data = io.BytesIO()
    pdf.write(data)
    response = client.post('/api/documents', files={'file': ('notes.pdf', data.getvalue(), 'application/pdf')})
    assert response.status_code == 201
    return response.json()


def test_private_routes_and_origin_checks(tmp_path):
    app = create_app(tmp_path, FixtureProvider())
    with TestClient(app) as client:
        assert client.get('/', follow_redirects=False).status_code == 303
        assert client.get('/api/documents').status_code == 401
        sign_in(client, app)
        assert client.get('/').status_code == 200
        assert client.get('/api/documents').json() == []
        client.headers['Origin'] = 'https://untrusted.example'
        assert client.post('/api/study/jobs', json={'mode': 'flashcards'}).status_code == 403
        assert client.get('/.env').status_code == 404
        assert client.get('/static/%2e%2e/.env').status_code == 404


def test_job_exact_count_render_validation_save_and_restart(tmp_path):
    app = create_app(tmp_path, FixtureProvider())
    with TestClient(app) as client:
        sign_in(client, app)
        document = upload(client)
        response = client.post('/api/study/jobs', json={
            'document_id': document['id'], 'pages': [1], 'mode': 'flashcards', 'count': 5})
        assert response.status_code == 202
        job_id = response.json()['id']
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            job = client.get('/api/study/jobs/' + job_id).json()
            if job['status'] in {'completed', 'failed', 'cancelled'}:
                break
            time.sleep(.05)
        assert job['status'] == 'completed', job.get('error')
        result = job['result']
        assert len(result['items']) == job['accepted_count'] == 5
        assert all(block['kind'] == 'text' for item in result['items'] for block in item['question'])
        assert [item['goal_step'] for item in result['items']] == [1,2,3,4,5]
        assert result['metadata']['math_check'] == 'on_display'
        assert result['metadata']['generation_attempts'] == 1
        assert result['metadata']['provider_requests'] == 1
        assert app.state.provider.calls == 1
        assert client.post('/api/study-sets', json=result).status_code == 200
        assert client.get('/api/documents/' + document['id'] + '/file').content.startswith(b'%PDF')
        sign_in(client, app, 'account-two')
        assert client.get('/api/study/jobs/' + job_id).status_code == 404
        assert client.get('/api/documents/' + document['id'] + '/file').status_code == 404
        assert client.get('/api/study-sets/' + result['id']).status_code == 404
    restarted = create_app(tmp_path, FixtureProvider())
    with TestClient(restarted) as client:
        sign_in(client, restarted)
        assert len(client.get('/api/documents').json()) == 1
        assert len(client.get('/api/study-sets/' + result['id']).json()['items']) == 5


@pytest.mark.parametrize('legacy_front_formula', [False, True])
def test_raw_math_completes_saves_and_exports(tmp_path, legacy_front_formula):
    from pypdf import PdfReader

    class RawProvider(FixtureProvider):
        async def generate(self, *args, **kwargs):
            result = await super().generate(*args, **kwargs)
            result.content.items[0].question[0].text = r'Explain x \in A in words.'
            result.content.items[0].answer[0].latex = r'\unknownCommand{x}'
            result.content.items[0].answer[0].original_latex = 'x'
            result.content.items[0].answer[0].change = 'Answer-only variant explanation.'
            if legacy_front_formula:
                for item in result.content.items:
                    item.question.append(item.answer.pop(0))
            return result

    app = create_app(tmp_path, RawProvider())
    with TestClient(app) as client:
        sign_in(client, app)
        document = upload(client)
        response = client.post('/api/study/generate', json={
            'document_id': document['id'], 'pages': [1], 'mode': 'flashcards', 'count': 5})
        assert response.status_code == 200
        result = response.json()
        assert len(result['items']) == 5
        assert app.state.provider.calls == 1
        assert result['metadata']['formatting_policy'] == 'best_effort'
        assert client.post('/api/study-sets', json=result).status_code == 200
        exported = client.post('/api/study/export.pdf', json=result)
        assert exported.status_code == 200
        assert exported.content.startswith(b'%PDF')
        pdf = PdfReader(io.BytesIO(exported.content))
        questions, answers = '\n'.join(page.extract_text() for page in pdf.pages).split('Answers', 1)
        assert 'unknownCommand' not in questions
        assert 'Expression 1' not in questions
        assert 'Answer-only variant explanation.' not in questions
        assert 'Card 1' in questions
        assert 'unknownCommand' in answers
        assert 'Expression 1' in answers
        assert answers.count('Answer-only variant explanation.') == 1


def test_prose_definition_saves_exports_and_enforces_its_page_reference(tmp_path):
    from pypdf import PdfReader
    from formula_lab.study import Citation

    class DefinitionProvider(FixtureProvider):
        async def generate(self,*args,**kwargs):
            result=await super().generate(*args,**kwargs)
            for item in result.content.items:
                item.answer.pop(0)
                item.source=Citation(document_id=None,page=1,line_start=None,line_end=None,quote=None)
            return result

    app=create_app(tmp_path,DefinitionProvider())
    with TestClient(app) as client:
        sign_in(client,app)
        doc=upload(client)
        result=client.post('/api/study/generate',json={
            'document_id':doc['id'],'pages':[1],'mode':'flashcards','count':1}).json()
        assert result['items'][0]['source']['document_id']==doc['id']
        assert client.post('/api/study-sets',json=result).status_code==200
        exported=client.post('/api/study/export.pdf',json=result)
        assert exported.status_code==200
        text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(exported.content)).pages)
        assert 'notes.pdf · page 1' in text.split('Answers',1)[1]
        result['items'][0]['source']['document_id']='f'*32
        assert client.post('/api/study-sets',json=result).status_code==502
