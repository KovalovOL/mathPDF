"""Current authenticated application routes; identities/provider are test fixtures."""
import io
import time

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from formula_lab.app import create_app
from formula_lab.study import GeneratedContent, LearningGoal, PlanResult, ProviderResult, StudyItem


class FixtureProvider:
    def __init__(self):
        self.next_step = 1

    async def plan(self, documents, system, task, *, count):
        return PlanResult(provider='fixture', model='fixture', goals=[
            LearningGoal(step=i, topic=f'Topic {i}', objective=f'Explain property {i}',
                         activity=['recognition', 'explanation', 'application'][(i-1) % 3],
                         challenge=f'Reason about property {i}', source_pages=[1])
            for i in range(1, count+1)])

    async def generate(self, documents, system, task, *, count):
        items = []
        for i in range(self.next_step, self.next_step + count):
            items.append(StudyItem.model_validate({
                'goal_step': i, 'title': f'Expression {i}',
                'question': [{'kind': 'text', 'text': f'Identify expression {i}.'},
                             {'kind': 'math', 'latex': f'x_{i}', 'display': True,
                              'source': {'document_id': documents[0].document.id, 'page': 1,
                                         'line_start': None, 'line_end': None, 'quote': None},
                              'original_latex': None, 'change': None}],
                'answer': [{'kind': 'text', 'text': f'Test explanation {i}.'}]}))
        self.next_step += count
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
        assert [item['goal_step'] for item in result['items']] == [1,2,3,4,5]
        assert result['metadata']['math_check'] == 'katex'
        assert result['metadata']['generation_attempts'] == 3
        assert result['metadata']['rejection_counts'] == {}
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


def test_renderer_failure_produces_terminal_job_error(tmp_path, monkeypatch):
    from formula_lab.math_validation import MathValidationError

    class UnavailableRenderer:
        async def __aenter__(self):
            raise MathValidationError('The server formula renderer is unavailable. Please try again later.')
        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr('formula_lab.study.MathValidator', UnavailableRenderer)
    app = create_app(tmp_path, FixtureProvider())
    with TestClient(app) as client:
        sign_in(client, app)
        document = upload(client)
        response = client.post('/api/study/jobs', json={
            'document_id': document['id'], 'pages': [1], 'mode': 'flashcards', 'count': 5})
        job_id = response.json()['id']
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = client.get('/api/study/jobs/' + job_id).json()
            if job['status'] == 'failed':
                break
            time.sleep(.05)
        assert job['status'] == 'failed'
        assert 'formula renderer is unavailable' in job['error']
        assert job['accepted_count'] == 0
        assert job.get('result') is None
