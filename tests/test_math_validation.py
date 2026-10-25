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


def test_screenshot_legacy_fragments_render_without_changing_notation():
    cases = [
        (r'The implication P \Rightarrow Q means if P then Q.', [r'P \Rightarrow Q']),
        (r'Equivalently, \neg P \lor Q (not P or Q).', [r'\neg P \lor Q']),
        (r'where \binom{n}{m} is the coefficient.', [r'\binom{n}{m}']),
        (r'where |A \cap B| is the intersection size.', [r'|A \cap B|']),
        (r'It evaluates as: \begin{aligned}\bar{w}\Leftrightarrow0=w\end{aligned}.',
         [r'\begin{aligned}\bar{w}\Leftrightarrow0=w\end{aligned}']),
        (r'From the law: \begin{aligned}w\vee y=\overline{\bar{w}\&\bar{y}}\end{aligned}.',
         [r'\begin{aligned}w\vee y=\overline{\bar{w}\&\bar{y}}\end{aligned}']),
        (r'If |S| = n, then |P(S)| = 2^n.', [r'|S| = n', r'|P(S)| = 2^n']),
        (r'Already $x \in A$, also \binom{n}{k} here.', [r'x \in A',r'\binom{n}{k}']),
        ('An ordinary English explanation. A vector has magnitude and direction.', []),
        (r'Unsupported \unknownCommand{x} remains readable.', []),
    ]
    async def check():
        async with MathValidator() as validator:
            for text, expected in cases:
                result = await validator.page.evaluate(r'''text => {
                    const container = document.createElement('div');
                    MathPDF.renderBlocks(container, [{kind:'text',text}], {editable:false});
                    return {latex:[...container.querySelectorAll('annotation[encoding="application/x-tex"]')].map(n=>n.textContent),
                            errors:container.querySelectorAll('.math-fallback').length,
                            plain:[...container.querySelector('p').childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join('')};
                }''', text)
                assert result['latex'] == expected, (text,result)
                assert result['errors'] == 0
                if not expected: assert result['plain'] == text
    asyncio.run(check())


def test_unwrapped_source_rows_gain_layout_without_changing_nested_math():
    cases = [
        (r'\text{(P)}\quad1\Rightarrow p\\\text{(F)}\quad0\vee\bar p',
         r'\begin{aligned}&\text{(P)}\quad1\Rightarrow p\\&\text{(F)}\quad0\vee\bar p\end{aligned}'),
        (r'\sum_{\substack{i=1\\j=2}}^n a_i',r'\sum_{\substack{i=1\\j=2}}^n a_i'),
        (r'\begin{aligned}a&=b\\c&=d\end{aligned}',r'\begin{aligned}a&=b\\c&=d\end{aligned}'),
    ]
    async def check():
        async with MathValidator() as validator:
            for latex,expected in cases:
                result=await validator.page.evaluate(r'''latex=>{
                    const target=document.createElement('div');
                    const ok=MathPDF.renderMath(target,latex,true);
                    return {ok,latex:target.querySelector('annotation')?.textContent};
                }''',latex)
                assert result=={'ok':True,'latex':expected}
    asyncio.run(check())


def test_only_terminal_text_label_brace_is_completed():
    async def check():
        async with MathValidator() as validator:
            result=await validator.page.evaluate(r'''()=>{
                const good=document.createElement('div'),bad=document.createElement('div');
                return {good:MathPDF.renderMath(good,'x+\\text{a label',false),
                        source:good.querySelector('annotation')?.textContent,
                        bad:MathPDF.renderMath(bad,'\\overline{x',false),raw:bad.textContent};
            }''')
            assert result=={'good':True,'source':r'x+\text{a label}', 'bad':False,'raw':r'\overline{x'}
    asyncio.run(check())
