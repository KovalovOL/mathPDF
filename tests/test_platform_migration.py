"""Opt-in real PostgreSQL/Garage checks; only disposable synthetic workspaces."""
import io
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from pypdf import PdfWriter

from formula_lab.app import create_app
from formula_lab.auth import Authentication,AuthConfig
from formula_lab.database import postgres_config
from formula_lab.library import FolderCreate,ItemUpdate
from formula_lab.migration import migrate,read_snapshot
from formula_lab.roles import OWNER_EMAIL
from formula_lab.annotations import AnnotationWrite
from test_platform import login


@pytest.fixture
def infrastructure(monkeypatch,tmp_path):
    if os.getenv('MATHPDF_INTEGRATION')!='1':pytest.skip('Set MATHPDF_INTEGRATION=1 with a disposable PostgreSQL and Garage.')
    config=postgres_config();database='test_'+uuid4().hex
    with psycopg.connect(config,autocommit=True) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    monkeypatch.delenv('DATABASE_URL',raising=False);monkeypatch.setenv('POSTGRES_DB',database)
    yield tmp_path
    with psycopg.connect(config,autocommit=True) as db:db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))


def historical(directory,monkeypatch):
    with monkeypatch.context() as local:
        for key in ['MATHPDF_POSTGRES_HOST','DATABASE_URL','MATHPDF_S3_ENDPOINT']:local.delenv(key,raising=False)
        app=create_app(directory);token,owner=login(app,OWNER_EMAIL);ws=app.state.workspace
        writer=PdfWriter();writer.add_blank_page(width=600,height=800);buffer=io.BytesIO();writer.write(buffer)
        doc=ws.add_document('fixture.pdf',buffer.getvalue(),owner.id)
        edited=ws.save_annotations(doc.id,owner.id,AnnotationWrite(expected_revision=0))
        folder=app.state.library.create_folder(owner.id,FolderCreate(name='Math'))
        nested=app.state.library.create_folder(owner.id,FolderCreate(name='Week 1',parent_id=folder['id']))
        app.state.library.update_item(owner.id,'documents',doc.id,ItemUpdate(folder_id=nested['id'],archived=True))
        import json
        legacy=json.loads((Path(__file__).parent/'fixtures/study-sets/legacy-flashcards.json').read_text())
        legacy.update(id=uuid4().hex,document=doc.model_dump(),pages=[1]);legacy.pop('schema_version',None)
        ws.save_set(legacy,owner.id)
        return token,owner,doc,edited,legacy,read_snapshot(ws.database)


def test_populated_migration_preserves_sessions_json_annotations_and_folders(infrastructure,monkeypatch):
    token,owner,doc,edited,legacy,before=historical(infrastructure,monkeypatch)
    manifest=migrate(infrastructure);assert migrate(infrastructure)==manifest
    app=create_app(infrastructure);ws=app.state.workspace
    assert app.state.auth.session_user(token).role=='owner'
    assert ws.study_set(legacy['id'],owner.id)==legacy
    snapshot=app.state.library.snapshot(owner.id)
    assert len(snapshot['files'])==2 and len(snapshot['folders'])==2 and snapshot['files'][1]['archived']
    assert ws.annotation_state(edited['document']['id'],owner.id)['revision']==1
    with ws.connection() as db:
        for table,entry in before.items():
            names=','.join('"'+c+'"' for c in entry['columns'])
            result=db.execute(f'SELECT {names} FROM {table}').fetchall()
            from formula_lab.migration import digest_rows
            assert digest_rows([tuple(r[c] for c in entry['columns']) for r in result])==entry['sha256']
    for obj in manifest['objects']:ws.storage.verify(obj['key'],obj['sha256'])
    # Cache bytes are not authoritative.
    path=ws.path(doc.id,owner.id);path.write_bytes(b'corrupt cache')
    assert ws.path(doc.id,owner.id).read_bytes()!=b'corrupt cache'
    assert read_snapshot(infrastructure/'workspace.sqlite3')==before
    from formula_lab.reports import ReportInput
    report=ws.reports.record(owner,ReportInput(context={'document_id':doc.id}))
    impact=ws.deletion_info('document',doc.id,owner.id);ws.delete('document',doc.id,owner.id,impact['revision'])
    assert not path.exists() and ws.reports.collect_one()
    assert ws.reports.get(report['id'])['manifest']['files'][0]['status']=='available'
    assert ws.reports.bundle(report['id'])[:2]==b'PK'


def test_empty_migration_and_post_cutover_writes_are_never_overwritten(infrastructure):
    assert migrate(infrastructure)['tables']=={}
    app=create_app(infrastructure);token,owner=login(app)
    doc=app.state.workspace.add_document('new.txt',b'created after cutover',owner.id)
    migrate(infrastructure)
    assert app.state.workspace.path(doc.id,owner.id).read_bytes()==b'created after cutover'


def test_hash_mismatch_aborts_and_retry_imports_exactly_once(infrastructure,monkeypatch):
    token,owner,doc,edited,legacy,before=historical(infrastructure,monkeypatch)
    binary=next((infrastructure/'documents').rglob('*.pdf'));original=binary.read_bytes();binary.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='bytes do not match'):migrate(infrastructure)
    app=create_app(infrastructure)
    with app.state.workspace.connection() as db:assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
    binary.write_bytes(original);manifest=migrate(infrastructure)
    assert len(manifest['objects'])==2
    assert app.state.auth.session_user(token).id==owner.id
