"""One model request for success and every invalid-response path."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from formula_lab.providers import OpenAIProvider, set_response_format
from formula_lab.study import (GeneratedContent, GenerationError, GenerateRequest, InputDocument,
                               ProviderResult, StudyItem, collect_study, load_prompts)
from formula_lab.workspace import Document


@pytest.fixture
def source():
    return InputDocument(Document(id='a'*32, filename='notes.pdf', sha256='b'*64,
        media_type='application/pdf', page_count=9, size=10), b'%PDF-test', 'pages.pdf', 'primary', [4,5])


def item(index, page=4, latex=None):
    return StudyItem.model_validate({'title': f'Property {index}',
        'question': [{'kind': 'text', 'text': f'Explain property {index}.'},
                     {'kind': 'math', 'latex': latex or f'x_{index}', 'display': True,
                      'source': {'page': page, 'line_start': None, 'line_end': None, 'quote': None},
                      'original_latex': None, 'change': None}],
        'answer': [{'kind': 'text', 'text': 'A complete explanation.'}]})


class Provider:
    def __init__(self, items=None, error=None, insufficient=False):
        self.items, self.error, self.insufficient, self.calls = items, error, insufficient, 0

    async def generate(self, documents, system, task, *, count, mode):
        self.calls += 1
        assert 'Formula-writing guide' in system
        assert f'exactly {count}' in task
        if self.error:
            raise self.error
        return ProviderResult(content=GeneratedContent(items=self.items if self.items is not None else
            [item(i) for i in range(1,count+1)], notes=[]), provider='fixture', model='fixture',
            insufficient_source=self.insufficient)


@pytest.mark.parametrize('mode', ['flashcards', 'problems'])
@pytest.mark.parametrize('count', [1, 10, 15])
def test_complete_set_uses_one_call(source, mode, count):
    provider = Provider()
    progress = []
    content, metadata = asyncio.run(collect_study([source], GenerateRequest(mode=mode, count=count),
                                                 provider, progress.append))
    assert provider.calls == metadata['provider_requests'] == metadata['generation_attempts'] == 1
    assert len(content.items) == count
    assert [entry.goal_step for entry in content.items] == list(range(1,count+1))
    assert metadata['math_check'] == 'on_display'
    assert 'planning' not in [entry.get('phase') for entry in progress]


@pytest.mark.parametrize('case', ['short', 'duplicate', 'source', 'provider', 'insufficient'])
def test_failures_never_trigger_another_model_request(source, case):
    entries = [item(1), item(2)]
    if case == 'short': entries.pop()
    if case == 'duplicate': entries[1] = entries[0].model_copy(deep=True)
    if case == 'source': entries[0] = item(1, page=9)
    if case == 'latex': entries[0] = item(1, latex=r'\unknownCommand{x}')
    if case == 'prose': entries[0].question[0].text = r'Unformatted x \in A'
    provider = Provider(entries, GenerationError('Provider timed out.') if case == 'provider' else None,
                        case == 'insufficient')
    with pytest.raises(GenerationError):
        asyncio.run(collect_study([source], GenerateRequest(mode='flashcards', count=2), provider, lambda _: None))
    assert provider.calls == 1


def test_prompts_load_guide_and_preserve_selected_page_mapping(source):
    system, task, hashes = load_prompts(GenerateRequest(mode='problems', count=10, comment='Short examples'), [source])
    assert 'Formula-writing guide' in system
    assert '1 -> 4, 2 -> 5' in task
    assert 'Short examples' in task
    assert 'formula-guide.md' in hashes
    assert not any('plan' in name or 'continuation' in name for name in hashes)
    assert source.label


def compact_payload():
    return {'result': {'status':'completed', 'items': [
        {'title': 'Membership', 'formula': {'latex': r'x \in A', 'page':4, 'variant':None}, 'question':['Explain this relation.',
            {'latex': r'x \in A', 'page':4, 'variant':None}], 'answer':['It denotes membership.']} ]}}


@pytest.mark.parametrize('case', ['completed', 'incomplete', 'invalid_json', 'wrong_count', 'refusal', 'timeout'])
def test_adapter_has_one_http_attempt_and_expands_compact_blocks(source, monkeypatch, case):
    payload = compact_payload()
    if case == 'wrong_count': payload['result']['items'] = []
    response = SimpleNamespace(status='incomplete' if case == 'incomplete' else 'completed',
        usage=SimpleNamespace(output_tokens=120), incomplete_details=SimpleNamespace(reason='max_output_tokens'),
        output=[SimpleNamespace(type='message', content=[SimpleNamespace(type='refusal')])] if case == 'refusal' else [],
        output_text='broken json' if case == 'invalid_json' else json.dumps(payload))
    create = AsyncMock(return_value=response)
    if case == 'timeout':
        import httpx
        from openai import APITimeoutError
        create.side_effect = APITimeoutError(request=httpx.Request('POST', 'https://api.openai.com/v1/responses'))
    settings = []

    class Client:
        def __init__(self, **kwargs):
            settings.append(kwargs)
            self.responses = SimpleNamespace(create=create)
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass

    monkeypatch.setattr('formula_lab.providers.AsyncOpenAI', Client)
    provider = OpenAIProvider('test-only-key', 'test-model')
    if case == 'completed':
        result = asyncio.run(provider.generate([source], 'system', 'task', count=1, mode='flashcards'))
        formula = result.content.items[0].question[1]
        assert formula.source.document_id == source.document.id
        assert formula.source.page == 4
        assert formula.source.quote is formula.original_latex is formula.change is None
        assert formula.display
        assert result.content.items[0].goal_step == 1
    else:
        with pytest.raises(GenerationError):
            asyncio.run(provider.generate([source], 'system', 'task', count=1, mode='flashcards'))
    assert create.await_count == 1
    assert settings[0]['max_retries'] == 0
    schema = create.call_args.kwargs['text']['format']['schema']
    complete = schema['$defs']['CompletedSet']['properties']['items']
    assert complete['minItems'] == complete['maxItems'] == 1
    assert 'document_id' not in json.dumps(schema)


def test_compact_variant_expands_original_and_change(source):
    payload = compact_payload()
    payload['result']['items'][0]['question'][1].update(latex=r'x \notin A',
        variant={'original': r'x \in A', 'change': 'Negate the membership relation.'})
    compact = set_response_format(1).model_validate(payload).result.items[0]
    expanded = compact.expand(source.document.id, 1)
    assert expanded.question[1].original_latex == r'x \in A'
    assert expanded.question[1].change == 'Negate the membership relation.'


@pytest.mark.parametrize('tex', [r'x \in A', r'\{1,2\}', r'\frac{a}{b}',
    r'\begin{aligned}a&=b+c\\d&=e-f\end{aligned}',
    r'\begin{pmatrix}a&b\\c&d\end{pmatrix}'])
def test_uniform_json_overescaping_is_fixed_without_changing_valid_tex(tex):
    from formula_lab.providers import normalize_model_tex
    assert normalize_model_tex(tex) == tex
    assert normalize_model_tex(tex.replace('\\', '\\\\')) == tex


@pytest.mark.parametrize('field', ['title', 'change'])
def test_compact_schema_accepts_raw_tex_in_noncritical_prose(field):
    payload = compact_payload()
    entry = payload['result']['items'][0]
    if field == 'title':
        entry['title'] = r'Explain x \in A'
    else:
        entry['formula']['variant'] = {'original':'x', 'change': r'Use \notin'}
    set_response_format(1).model_validate(payload)


@pytest.mark.parametrize('mode', ['flashcards', 'problems'])
@pytest.mark.parametrize('kind', ['prose', 'latex', 'title', 'prose_in_math'])
def test_formatting_does_not_discard_the_requested_set(source, mode, kind):
    entries = [item(1), item(2)]
    if kind == 'prose': entries[0].question[0].text = r'Explain x \in A in words.'
    if kind == 'latex': entries[0].question[1].latex = r'\unknownCommand{x}'
    if kind == 'title': entries[0].title = r'Relation x \in A'
    if kind == 'prose_in_math': entries[0].question[1].latex = 'Exercise 1. Explain this relation.'
    provider = Provider(entries)
    content, metadata = asyncio.run(collect_study([source], GenerateRequest(mode=mode, count=2), provider, lambda _: None))
    assert len(content.items) == 2
    assert provider.calls == metadata['provider_requests'] == 1
    assert metadata['formatting_policy'] == 'best_effort'
    assert content.items[0].question[0].text == entries[0].question[0].text


def test_required_formula_cannot_be_omitted_or_replaced_with_prose():
    from pydantic import ValidationError
    payload = compact_payload()
    del payload['result']['items'][0]['formula']
    with pytest.raises(ValidationError):
        set_response_format(1).model_validate(payload)
    payload['result']['items'][0]['formula'] = 'A prose explanation'
    with pytest.raises(ValidationError):
        set_response_format(1).model_validate(payload)


def test_central_problem_formula_is_in_answer_without_spoiling_question(source):
    payload = compact_payload()
    payload['result']['items'][0]['question'] = ['Explain this relation.']
    compact = set_response_format(1).model_validate(payload).result.items[0]
    expanded = compact.expand(source.document.id, 1, mode='problems')
    assert all(block.kind == 'text' for block in expanded.question)
    assert expanded.answer[0].kind == 'math'


def test_multiple_extra_escape_layers_and_exact_formula_prose_reuse(source):
    from formula_lab.providers import normalize_model_tex
    tex = r'x \in A'
    assert normalize_model_tex(tex.replace('\\', '\\\\\\\\')) == tex
    payload = compact_payload()
    payload['result']['items'][0]['question'] = ['Explain this relation.', tex.replace('\\', '\\\\')]
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id, 1)
    assert expanded.question[1].kind == 'math'
    assert expanded.question[1].source.page == 4
    assert sum(block.kind == 'math' for block in expanded.question) == 1


def test_dangling_escape_cleanup_preserves_valid_set_delimiters():
    from formula_lab.providers import normalize_model_tex
    assert normalize_model_tex('\\emptyset = \\{\\}\\') == r'\emptyset = \{\}'
    assert normalize_model_tex(r'\{x\}') == r'\{x\}'


def test_only_unambiguous_standalone_tex_is_delimited_locally():
    from formula_lab.providers import normalize_model_prose
    assert normalize_model_prose(r'A \times B') == r'$A \times B$'
    assert normalize_model_prose('An ordinary English explanation.') == 'An ordinary English explanation.'
    assert normalize_model_prose(r'Explain x \in A in words.') == r'Explain x \in A in words.'
    assert normalize_model_prose(r'Already $x \in A$.') == r'Already $x \in A$.'
