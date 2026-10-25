"""Exercise the bundled renderer, including its real Chromium document mode."""

import asyncio

import pytest

from formula_lab.math_validation import MathValidationError, MathValidator
from formula_lab.study import GenerateRequest, InputDocument, collect_study
from formula_lab.workspace import Document


def test_real_renderer_accepts_valid_math_and_rejects_bad_tex():
    async def check():
        async with MathValidator() as validator:
            assert await validator.page.evaluate("document.compatMode") == "CSS1Compat"
            valid = [("x+1", True), (r"\frac{1}{2}", False),
                     (r"\sum_{k=1}^{n} k = \frac{n(n+1)}{2}", True),
                     (r"\begin{aligned}a&=b+c\\d&=e-f\end{aligned}", True)]
            assert await validator.errors(valid) == []
            assert all(validator.cache[expression] is None for expression in valid)
            assert await validator.errors(valid) == []  # Cached checks stay valid.
            errors = await validator.errors([(r"\unknownCommand{x}", True)])
            assert len(errors) == 1
            assert "Undefined control sequence" in errors[0]
            assert await validator.errors(valid) == []  # A bad item does not poison later items.
    asyncio.run(check())


def test_renderer_fault_stops_before_any_provider_calls(monkeypatch):
    closed = []

    class BrokenValidator(MathValidator):
        async def errors(self, expressions):
            return ["Cannot render this formula: simulated renderer environment failure"]

        async def __aexit__(self, *_):
            closed.append(True)

    class UnusedProvider:
        async def generate(self, *args, **kwargs):
            pytest.fail("A broken renderer must not trigger model repair attempts")

    monkeypatch.setattr("formula_lab.study.MathValidator", BrokenValidator)
    document = Document(id="a" * 32, filename="notes.pdf", sha256="b" * 64,
                        media_type="application/pdf", page_count=1, size=10)
    source = InputDocument(document=document, data=b"", filename="notes.pdf", role="primary", pages=[1])
    with pytest.raises(MathValidationError, match="server formula renderer is unavailable"):
        asyncio.run(collect_study([source], GenerateRequest(mode="flashcards", count=5),
                                  UnusedProvider(), lambda _: None))
    assert closed == [True]
