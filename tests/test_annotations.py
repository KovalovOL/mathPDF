"""Editable copies retain source content, ownership and their primary-only cascade."""
import io
import hashlib

import pypdfium2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, RectangleObject

from formula_lab.annotations import AnnotationData, annotated_pdf
from formula_lab.app import create_app
from formula_lab.study import GenerateRequest, prepare_documents
from test_library_deletion import identity, payload, upload


def marks():
    return {'schema_version':1,'items':[
        {'id':'highlight-one','kind':'highlight','page':1,'color':'#facc15',
         'quads':[[[150,650],[250,650],[250,625],[150,625]]]},
        {'id':'ink-one','kind':'ink','page':1,'color':'#2563eb','width':4,'points':[[200,600],[300,500]]}]}


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_vector_overlay_preserves_crop_rotation_and_source(tmp_path, rotation):
    writer = PdfWriter(); page = writer.add_blank_page(width=600,height=800)
    page.cropbox = RectangleObject([100,100,500,700]); page.rotate(rotation)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({
        NameObject('/F1'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),
            NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 120 680 Td (Source content stays selectable) Tj ET')
    page[NameObject('/Contents')]=stream
    source=tmp_path/'source.pdf';writer.write(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    result=annotated_pdf(source,AnnotationData.model_validate(marks()),'copy-one',1)
    parsed=PdfReader(io.BytesIO(result))
    assert parsed.pages[0].rotation==rotation
    assert list(parsed.pages[0].cropbox)==[100,100,500,700]
    assert 'Source content stays selectable' in parsed.pages[0].extract_text()
    assert len(parsed.pages[0].images)==0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    document=pypdfium2.PdfDocument(result); rendered=document[0].render(scale=1).to_pil()
    def screen(x,y):
        return {0:(x-100,700-y),90:(y-100,x-100),180:(500-x,y-100),270:(700-y,500-x)}[rotation]
    yellow=rendered.getpixel(tuple(map(int,screen(200,637))))
    blue=rendered.getpixel(tuple(map(int,screen(250,550))))
    assert yellow[0]>240 and yellow[1]>220 and yellow[2]<220
    assert blue[2]>180 and blue[0]<100
    document.close()


def test_editable_copy_saves_in_place_and_rejects_stale_or_foreign_writes(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        owner=identity(client,app)
        original=upload(client,600); original_path=app.state.workspace.path(original['id'],owner)
        before=original_path.read_bytes()
        uri='/api/documents/'+original['id']+'/annotations'
        assert client.get(uri).json()['annotations']['items']==[]
        saved=client.put(uri,json={**marks(),'expected_revision':0})
        assert saved.status_code==200
        copy=saved.json()['document']; copy_uri='/api/documents/'+copy['id']+'/annotations'
        assert copy['original_document_id']==original['id'] and copy['annotation_revision']==1
        assert original_path.read_bytes()==before
        assert len(client.get('/api/documents').json())==2
        assert client.get(uri).json()['annotations']['items']==[]
        assert client.get(uri).json()['copy_document']['id']==copy['id']
        assert client.put(uri,json={**marks(),'expected_revision':0}).status_code==409
        updated=marks();updated['items'][1]['width']=6
        second=client.put(copy_uri,json={**updated,'expected_revision':1})
        assert second.status_code==200 and second.json()['document']['id']==copy['id']
        assert second.json()['document']['annotation_revision']==2
        assert len(client.get('/api/documents').json())==2
        assert client.put(copy_uri,json={**marks(),'expected_revision':1}).status_code==409
        assert client.get(copy_uri).json()['annotations']==updated
        binary=client.get('/api/documents/'+copy['id']+'/file').content
        assert PdfReader(io.BytesIO(binary)).metadata['/MathPDFRevision']=='2'
        identity(client,app,'annotation-stranger')
        assert client.get(copy_uri).status_code==404
        assert client.put(copy_uri,json={**marks(),'expected_revision':2}).status_code==404
    restarted=create_app(tmp_path)
    with TestClient(restarted) as client:
        identity(client,restarted)
        assert client.get(copy_uri).json()['annotations']==updated


def test_original_deletion_includes_copy_and_only_primary_sets(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        identity(client,app)
        original,other=upload(client,600),upload(client,610)
        uri='/api/documents/'+original['id']
        old_impact=client.get(uri+'/deletion').json()
        copy=client.put(uri+'/annotations',json={**marks(),'expected_revision':0}).json()['document']
        copied_set,context_set=payload(copy),payload(other,copy)
        client.post('/api/study-sets',json=copied_set);client.post('/api/study-sets',json=context_set)
        assert client.delete(uri,headers={'If-Match':old_impact['revision']}).status_code==409
        impact=client.get(uri+'/deletion').json()
        assert [entry['id'] for entry in impact['edited_copies']]==[copy['id']]
        client.put('/api/documents/'+copy['id']+'/annotations',json={**marks(),'expected_revision':1})
        assert client.delete(uri,headers={'If-Match':impact['revision']}).status_code==409
        impact=client.get(uri+'/deletion').json()
        response=client.delete(uri,headers={'If-Match':impact['revision']})
        assert response.status_code==200
        assert set(response.json()['deleted_document_ids'])=={original['id'],copy['id']}
        assert client.get('/api/study-sets/'+copied_set['id']).status_code==404
        retained=client.get('/api/study-sets/'+context_set['id']).json()
        assert retained['items']==context_set['items'] and retained['context_documents']==[]
        assert client.get('/api/documents/'+other['id']).status_code==200


def test_invalid_marks_cannot_create_a_copy(tmp_path):
    with pytest.raises(ValidationError):
        AnnotationData.model_validate({'items':[marks()['items'][0]]*2})
    app=create_app(tmp_path)
    with TestClient(app) as client:
        identity(client,app);original=upload(client,600)
        invalid=marks();invalid['items'][1]['points'][0]=[-100,0]
        assert client.put('/api/documents/'+original['id']+'/annotations',json={**invalid,'expected_revision':0}).status_code==400
        assert len(client.get('/api/documents').json())==1


def test_copy_deletion_retains_original_and_selected_context_contains_marks(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        owner=identity(client,app); original,other=upload(client,600),upload(client,610)
        copy=client.put('/api/documents/'+original['id']+'/annotations',json={**marks(),'expected_revision':0}).json()['document']
        prepared=prepare_documents(app.state.workspace,GenerateRequest(document_id=other['id'],pages=[1],
            context=[{'document_id':copy['id'],'pages':[1]}],mode='flashcards',count=1),owner)
        assert prepared[1].document.original_document_id==original['id']
        assert prepared[1].role=='context' and b'NoteHighlight' in PdfReader(io.BytesIO(prepared[1].data)).pages[0].get_contents().get_data()
        original_set,copy_set=payload(original),payload(copy)
        client.post('/api/study-sets',json=original_set);client.post('/api/study-sets',json=copy_set)
        uri='/api/documents/'+copy['id'];impact=client.get(uri+'/deletion').json()
        assert client.delete(uri,headers={'If-Match':impact['revision']}).status_code==200
        assert client.get('/api/documents/'+original['id']+'/file').status_code==200
        assert client.get('/api/study-sets/'+original_set['id']).status_code==200
        assert client.get('/api/study-sets/'+copy_set['id']).status_code==404
