import pytest
from formula_lab.models import Formula, Source, Review
from formula_lab.store import FormulaStore


def empty_formula(identifier="original", document="a" * 64):
    return Formula(id=identifier, title="Test", source=Source(
        document_sha256=document, filename="notes.pdf", page=4, bbox=(1, 2, 3, 4)),
        width=2, height=2, nodes=[], fonts=[])


def test_round_trip_review_and_reopen(tmp_path):
    store = FormulaStore(tmp_path, "a" * 64)
    formula = empty_formula()
    store.add(formula)
    store.review(formula.id, Review(state="accepted", notes="Compared with page 4"))
    reopened = FormulaStore(tmp_path, "a" * 64)
    result = reopened.get(formula.id)
    assert result.source == formula.source
    assert result.review.state == "accepted"
    assert result.review.notes == "Compared with page 4"
    with pytest.raises(ValueError, match="already exists"):
        reopened.add(formula)


def test_document_isolation_and_variant_lineage(tmp_path):
    store = FormulaStore(tmp_path, "a" * 64)
    with pytest.raises(ValueError, match="different document"):
        store.add(empty_formula(document="b" * 64))
    variant = empty_formula("variant")
    variant.original_id = "missing"
    with pytest.raises(ValueError, match="saved first"):
        store.add(variant)
    store.add(empty_formula())
    assert FormulaStore(tmp_path, "b" * 64).list() == []
