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


def test_generation_does_not_launch_a_validation_browser(monkeypatch):
    from formula_lab.study import GeneratedContent, ProviderResult, StudyItem

    async def forbidden_start(self):
        pytest.fail('Generation must not start a server validation browser')

    monkeypatch.setattr(MathValidator, '_start', forbidden_start)
    document = Document(id='a'*32, filename='notes.pdf', sha256='b'*64,
                        media_type='application/pdf', page_count=1, size=10)
    source = InputDocument(document=document, data=b'', filename='notes.pdf', role='primary', pages=[1])

    class Provider:
        async def generate(self, *args, **kwargs):
            entry = StudyItem.model_validate({'title':'Raw math',
                'question':[{'kind':'math','latex':r'\unknownCommand{x}','display':True,
                             'source':{'page':1,'line_start':None,'line_end':None,'quote':None},
                             'original_latex':None,'change':None}],
                'answer':[{'kind':'text','text':'An explanation.'}]})
            return ProviderResult(content=GeneratedContent(items=[entry],notes=[]),provider='fixture',model='fixture')

    content, metadata = asyncio.run(collect_study([source], GenerateRequest(mode='flashcards',count=1),
                                                 Provider(), lambda _: None))
    assert len(content.items) == 1
    assert metadata['math_check'] == 'on_display'
