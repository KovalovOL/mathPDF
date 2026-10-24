from pathlib import Path
from fastapi.testclient import TestClient
from formula_lab.app import create_app


PDF=Path(__file__).resolve().parents[1]/"main.pdf"


def test_workbench_full_variant_review_export_and_restart(tmp_path):
    app=create_app(PDF,tmp_path)
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        page=client.get('/api/pages/7').json()
        candidate=next(c for c in page['candidates'] if '∑' in c['text'])
        payload={'page':7,'bbox':candidate['bbox'],'title':'Sum'}
        preview=client.post('/api/preview',json=payload).json()
        assert preview['review']['state']=='unverified'
        assert client.get('/api/formulas').json()==[]
        response=client.post('/api/formulas',json=payload)
        assert response.status_code==201
        original=response.json()
        sign=next(n for n in original['nodes'] if n['kind']=='text' and n['text']=='+')
        response=client.post(f"/api/formulas/{original['id']}/variants",json={'node_id':sign['id'],'replacement':'−'})
        assert response.status_code==201
        variant=response.json()
        assert variant['original_id']==original['id']
        reviewed=client.patch(f"/api/formulas/{variant['id']}/review",json={'state':'needs_correction','notes':'Test review'})
        assert reviewed.status_code==200
        assert client.get(f"/api/formulas/{original['id']}").json()==original
        exported=client.get('/api/export')
        assert exported.status_code==200
        assert len(exported.json()['formulas'])==2
        font=next(f for f in original['fonts'] if f['url'])
        assert client.get(font['url']).content.startswith(b'OTTO')
        assert client.get('/source.pdf').content.startswith(b'%PDF')
    with TestClient(create_app(PDF,tmp_path)) as restarted:
        result=restarted.get(f"/api/formulas/{variant['id']}").json()
        assert result['review']['notes']=='Test review'


def test_invalid_page_source_boundaries_and_bad_operations(tmp_path):
    with TestClient(create_app(PDF,tmp_path)) as client:
        assert client.get('/api/pages/0').status_code==400
        assert client.get('/api/pages/999').status_code==400
        assert client.post('/api/preview',json={'page':4,'bbox':[-1,0,2,3]}).status_code==400
        assert client.get('/api/formulas/missing').status_code==404
        assert client.get('/fonts/invalid.otf').status_code==404
        assert client.get('/.env').status_code==404
        assert client.get('/static/%2e%2e/.env').status_code==404
        assert client.get('/source.pdf?path=.env').content.startswith(b'%PDF')


def test_unsupported_source_graphics_cannot_be_marked_accepted(tmp_path):
    with TestClient(create_app(PDF,tmp_path)) as client:
        page=client.get('/api/pages/38').json()
        response=client.post('/api/formulas',json={'page':38,'bbox':[0,0,page['width'],page['height']]})
        record=response.json()
        assert record['warnings']
        assert client.patch(f"/api/formulas/{record['id']}/review",json={'state':'accepted'}).status_code==400
        assert client.patch(f"/api/formulas/{record['id']}/review",json={'state':'needs_correction'}).status_code==200
