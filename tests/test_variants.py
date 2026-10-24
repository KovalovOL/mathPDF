import pytest
from formula_lab.models import TextNode
from formula_lab.variants import replace_sign


@pytest.fixture
def sum_formula(pdf_source):
    candidate=next(c for c in pdf_source.page(7).candidates if "∑" in c.text)
    return pdf_source.select(7,candidate.bbox,"Sum and product")


def test_change_one_sign_preserves_source_and_all_other_nodes(sum_formula):
    before=sum_formula.model_dump(mode="json")
    target=next(n for n in sum_formula.nodes if isinstance(n,TextNode) and n.text=="+")
    variant=replace_sign(sum_formula,target.id,"−")
    assert sum_formula.model_dump(mode="json")==before
    assert variant.id != sum_formula.id
    assert variant.original_id==sum_formula.id
    assert variant.source==sum_formula.source
    assert variant.transformation.before=="+"
    assert variant.transformation.after=="−"
    assert variant.review.state=="unverified"
    for old,new in zip(sum_formula.nodes,variant.nodes):
        if old.id==target.id:
            assert new.text=="−"
        else:
            assert old==new
    with pytest.raises(ValueError,match="chaining"):
        replace_sign(variant,target.id,"+")


def test_reject_non_sign_and_missing_replacement(sum_formula):
    target=next(n for n in sum_formula.nodes if isinstance(n,TextNode) and n.text=="+")
    with pytest.raises(ValueError,match="plus/minus"):
        replace_sign(sum_formula,target.id,"×")
    with pytest.raises(ValueError,match="Select a plus"):
        replace_sign(sum_formula,"nonexistent","−")
    with pytest.raises(ValueError,match="unchanged"):
        replace_sign(sum_formula,target.id,"+")
    for f in sum_formula.fonts:
        f.glyphs=[g for g in f.glyphs if g.text!="−"]
    with pytest.raises(ValueError,match="not available"):
        replace_sign(sum_formula,target.id,"−")
