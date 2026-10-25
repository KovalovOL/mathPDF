"""Frozen historical formats must remain readable by every newer release."""

import copy
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from formula_lab.app import create_app
from formula_lab.study import StudySet


FIXTURES = Path(__file__).parent / 'fixtures' / 'study-sets'
LEGACY = ['legacy-flashcards.json', 'legacy-problems.json']


@pytest.mark.parametrize('filename', LEGACY)
def test_unversioned_historical_payload_keeps_all_content(filename):
    raw = json.loads((FIXTURES / filename).read_text())
    before = copy.deepcopy(raw)
    parsed = StudySet.model_validate(raw)
    assert raw == before
    assert parsed.schema_version == 1
    assert parsed.context_documents == [] and parsed.comment == ''
    assert parsed.metadata == raw['metadata']
    for old, item in zip(raw['items'], parsed.items, strict=True):
        assert item.goal_step is item.source is None
        assert item.model_dump(exclude={'goal_step', 'source'}) == old
    assert StudySet.model_validate(parsed.model_dump(mode='json')) == parsed


@pytest.mark.parametrize('filename', LEGACY)
def test_old_set_read_save_restart_and_export_are_compatible(tmp_path, filename):
    class NoGeneration:
        async def generate(self, *args, **kwargs):
            pytest.fail('Reading, saving and exporting old content must not regenerate it')

    def sign_in(client, app):
        token = app.state.auth.create_session({'sub': 'compatibility-fixture',
                                                'email': 'compatibility@example.invalid'}, None)
        client.cookies.set(app.state.auth.config.session_cookie, token)
        client.headers['Origin'] = app.state.auth.config.base_url
        return app.state.auth.session_user(token).id

    raw = json.loads((FIXTURES / filename).read_text())
    app = create_app(tmp_path, NoGeneration())
    with TestClient(app) as client:
        owner = sign_in(client, app)
        pdf, data = PdfWriter(), io.BytesIO()
        pdf.add_blank_page(width=600, height=800)
        pdf.write(data)
        document = client.post('/api/documents', files={
            'file': ('legacy-notes.pdf', data.getvalue(), 'application/pdf')}).json()
        # Bind only the fixture's document identity to isolated owned storage.
        raw['document'] = document
        for item in raw['items']:
            for block in item['question'] + item['answer']:
                if block['kind'] == 'math':
                    block['source']['document_id'] = document['id']
        app.state.workspace.save_set(raw, owner)
        opened = client.get('/api/study-sets/' + raw['id'])
        assert opened.status_code == 200
        normalized = opened.json()
        assert normalized['schema_version'] == 1
        assert app.state.workspace.study_set(raw['id'], owner) == raw  # Read is non-destructive.
        assert client.post('/api/study-sets', json=normalized).status_code == 200
        assert client.get('/api/study-sets/' + raw['id']).json() == normalized
        exported = client.post('/api/study/export.pdf', json=normalized)
        assert exported.status_code == 200
        text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(exported.content)).pages)
        assert 'Answers' in text and raw['title'] in text
        if raw['mode'] == 'flashcards':
            questions, answers = text.split('Answers', 1)
            assert 'Negated membership' not in questions
            assert 'Negate the source membership relation.' in answers
    restarted = create_app(tmp_path, NoGeneration())
    with TestClient(restarted) as client:
        sign_in(client, restarted)
        assert client.get('/api/study-sets/' + raw['id']).json() == normalized
