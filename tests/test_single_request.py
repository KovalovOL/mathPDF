"""One model request for success and every invalid-response path."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from formula_lab.providers import OpenAIProvider, set_response_format
from formula_lab.study import (GeneratedContent, GenerationError, GenerateRequest, InputDocument,
                               ProviderResult, StudyItem, collect_study, load_prompts, PROMPTS)
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
    assert 'math-patterns.md' in hashes
    assert 'Reusable LaTeX structures' in system
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
        assert all(block.kind == 'text' for block in result.content.items[0].question)
        formula = result.content.items[0].answer[0]
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
    assert all(block.kind == 'text' for block in expanded.question)
    assert expanded.answer[1].original_latex == r'x \in A'
    assert expanded.answer[1].change == 'Negate the membership relation.'


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


@pytest.mark.parametrize('mode', ['flashcards', 'problems'])
def test_central_formula_is_in_answer_without_spoiling_question(source, mode):
    payload = compact_payload()
    payload['result']['items'][0]['question'] = ['Explain this relation.']
    compact = set_response_format(1).model_validate(payload).result.items[0]
    expanded = compact.expand(source.document.id, 1, mode=mode)
    assert all(block.kind == 'text' for block in expanded.question)
    assert expanded.answer[0].kind == 'math'
    from formula_lab.study import validate_item
    validate_item(expanded, mode, source.document.id, source.pages)


def test_flashcard_prompt_requires_recall_without_answer_hints(source):
    system, task, _ = load_prompts(GenerateRequest(mode='flashcards', count=5), [source])
    assert 'Do not reveal or hint at the correct answer on the front' in task
    assert 'BACK separates From notes from Explanation' in task
    assert 'never on the flashcard front' in system


def test_problem_question_inputs_stay_in_question(source):
    compact = set_response_format(1).model_validate(compact_payload()).result.items[0]
    expanded = compact.expand(source.document.id, 1, mode='problems')
    assert expanded.question[1].kind == 'math'


def test_formula_only_flashcard_keeps_question_and_answer(source):
    payload = compact_payload()
    entry = payload['result']['items'][0]
    entry['question'] = [entry['formula']]
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id, 1)
    assert expanded.question[0].text == 'Recall the formula.'
    assert expanded.answer[0].latex == r'x \in A'


def test_multiple_extra_escape_layers_and_exact_formula_prose_reuse(source):
    from formula_lab.providers import normalize_model_tex
    tex = r'x \in A'
    assert normalize_model_tex(tex.replace('\\', '\\\\\\\\')) == tex
    payload = compact_payload()
    payload['result']['items'][0]['question'] = ['Explain this relation.', tex.replace('\\', '\\\\')]
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id, 1)
    assert all(block.kind == 'text' for block in expanded.question)
    assert expanded.answer[0].source.page == 4
    assert sum(block.kind == 'math' for block in expanded.answer) == 1


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


def test_explicit_paragraph_parts_supply_math_delimiters_locally(source):
    payload = compact_payload()
    payload['result']['items'][0]['answer'] = [{'parts': [
        'The coefficient ', {'math': r'\binom{n}{m}'}, ' counts ', {'math': 'm'}, ' selections.']}]
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id, 1)
    assert expanded.answer[-1].text == r'The coefficient \(\binom{n}{m}\) counts \(m\) selections.'
    assert expanded.answer[0].source.page == 4


def test_page_only_source_preserves_prose_without_manufacturing_formula(source):
    from formula_lab.study import validate_item, ContentValidationError
    payload = compact_payload()
    entry = payload['result']['items'][0]
    entry.update(formula={'page':4},question=['What defines vector equality?'],
                 answer=[{'parts':['Two vectors are equal when their directions and magnitudes agree.']}])
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id,1)
    assert all(block.kind == 'text' for block in expanded.question + expanded.answer)
    assert expanded.source.page == 4
    assert expanded.source.document_id == source.document.id
    validate_item(expanded, 'flashcards',source.document.id,source.pages)
    expanded.source.page = 9
    with pytest.raises(ContentValidationError):
        validate_item(expanded,'flashcards',source.document.id,source.pages)


@pytest.mark.parametrize('tex', [r'\bar{w} \Leftrightarrow 0',r'\overline{\bar{w}\&\bar{y}}',
    r'P(n,m)=n(n-1)\cdots(n-m+1)=\frac{n!}{(n-m)!}',r's\&x\Rightarrow r\vee y'])
def test_source_operators_bar_scope_and_equality_order_are_not_normalized(tex):
    from formula_lab.providers import normalize_model_tex
    assert normalize_model_tex(tex) == tex


def test_prose_generation_constraint_does_not_discard_legacy_formatting(source):
    import re
    from formula_lab.providers import CompactItem
    branches = CompactItem.model_json_schema()['properties']['answer']['items']['anyOf']
    pattern = next(branch['pattern'] for branch in branches if branch.get('type') == 'string')
    assert re.fullmatch(pattern, 'An ordinary explanation.')
    assert not re.fullmatch(pattern, r'Bare \binom{n}{m} and x^n = y')
    payload = compact_payload()
    payload['result']['items'][0]['answer'] = [r'Bare \binom{n}{m} and x^n = y']
    # Formatting is a decoding guide, never a second local rejection/retry gate.
    assert set_response_format(1).model_validate(payload).result.items


def test_generation_schema_requires_complete_flashcard_question_and_structured_answers():
    schema = set_response_format(5, 'flashcards').model_json_schema()
    item = schema['$defs']['FlashcardOutput']['properties']
    assert item['question']['maxItems'] == 1
    assert item['question']['items']['type'] == 'string'
    assert all(branch.get('type') != 'string' for branch in item['answer']['items']['anyOf'])
    assert 'Paragraph' in schema['$defs']


def test_exact_formula_repetitions_are_removed_without_merging_sources_or_variants(source):
    payload = compact_payload()
    entry = payload['result']['items'][0]
    same = entry['formula'].copy()
    entry['answer'] = [same, same.copy(), {**same, 'page':5},
                       {**same, 'variant': {'original':'x', 'change':'Restore the membership relation.'}}]
    expanded = set_response_format(1).model_validate(payload).result.items[0].expand(source.document.id, 1)
    assert len(expanded.answer) == 3
    assert [block.source.page for block in expanded.answer] == [4,5,4]
    assert expanded.answer[-1].original_latex == 'x'


def test_shared_math_examples_are_valid_json_and_tex():
    from formula_lab.math_validation import MathValidator
    examples = [json.loads(line) for line in (PROMPTS/'math-patterns.md').read_text().splitlines()
                if line.startswith('{')]
    expressions = []
    for example in examples:
        if 'parts' in example:
            expressions.extend((part['math'], False) for part in example['parts'] if isinstance(part, dict))
        elif 'latex' in example:
            expressions.append((example['latex'], True))
        elif 'math' in example:
            expressions.append((example['math'], False))
    assert len(expressions) >= 12
    async def check():
        async with MathValidator() as validator:
            assert await validator.errors(expressions) == []
    asyncio.run(check())

@pytest.mark.parametrize('level', range(1,6))
def test_difficulty_reaches_single_provider_prompt_and_legacy_default(source,level):
    request=GenerateRequest(mode='flashcards',count=2,difficulty=level)
    system,task,hashes=load_prompts(request,[source])
    assert f'Requested overall difficulty: {level} out of 5.' in task
    assert 'Within the selected level' in task and '45–90' not in system
    assert 'per-skill quotas' in system and 'from_notes' in system and 'explanation' in system
    assert 'difficulty.md' in hashes
    provider=Provider()
    content,metadata=asyncio.run(collect_study([source],request,provider,lambda _:None))
    assert len(content.items)==2 and provider.calls==metadata['provider_requests']==1
    assert GenerateRequest(mode='problems').difficulty==3
    from pydantic import ValidationError
    for invalid in [0,6,2.5,True,'4']:
        with pytest.raises(ValidationError):GenerateRequest(mode='problems',difficulty=invalid)


@pytest.mark.parametrize('shape', ['split', 'formula_only', 'page_only', 'permissive_prose'])
def test_split_flashcard_back_survives_the_actual_adapter_reader(source, monkeypatch, shape):
    entry={'title':'Membership','skill':'meaning',
           'formula':{'latex':r'x \in A','page':4,'variant':None},
           'question':['What does membership mean?'],'answer':[],
           'from_notes':[{'parts':['The object belongs to the set.']}],
           'explanation':[{'parts':['This relates an object to a set.']}]}
    if shape=='formula_only':entry.update(from_notes=[],explanation=[])
    if shape=='page_only':entry['formula']={'page':4}
    if shape=='permissive_prose':
        entry['question']=['What does membership mean?',{'latex':r'x \in A','page':4,'variant':None}]
        entry['from_notes']=['The object belongs to the set.']
        entry['explanation']=[r'Bare x \in A']
    create=AsyncMock(return_value=SimpleNamespace(status='completed',usage=SimpleNamespace(output_tokens=100),
        output=[],output_text=json.dumps({'result':{'status':'completed','items':[entry]}})))
    class Client:
        def __init__(self,**kwargs):self.responses=SimpleNamespace(create=create)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
    monkeypatch.setattr('formula_lab.providers.AsyncOpenAI',Client)
    result=asyncio.run(OpenAIProvider('fixture','fixture').generate([source],'system','task',count=1,mode='flashcards'))
    card=result.content.items[0]
    assert create.await_count==1 and card.skill=='meaning'
    assert all(b.kind=='text' for b in card.question)
    assert card.from_notes is not None and card.explanation is not None
    assert any(b.kind=='text' and b.text=='From notes' for b in card.answer)
    assert any(b.kind=='text' and b.text=='Explanation' for b in card.answer)==bool(entry['explanation'])
    if shape=='page_only':assert card.source.page==4
    else:assert any(b.kind=='math' and b.latex==r'x \in A' and b.source.document_id==source.document.id for b in card.answer)
    assert StudyItem.model_validate(card.model_dump(mode='json'))==card


@pytest.mark.parametrize('mode', ['flashcards', 'problems'])
def test_skill_precedes_question_in_strict_provider_and_saved_schema(mode):
    from openai import pydantic_function_tool
    schema=pydantic_function_tool(set_response_format(2,mode))['function']['parameters']
    name='FlashcardOutput' if mode=='flashcards' else 'ProblemOutput'
    properties=schema['$defs'][name]['properties']
    assert list(properties).index('skill')<list(properties).index('question')
    assert list(StudyItem.model_fields).index('skill')<list(StudyItem.model_fields).index('question')
    values=next(v['enum'] for v in properties['skill']['anyOf'] if 'enum' in v)
    assert values==['recall','meaning','conditions','application','error_diagnosis','why_justification','counterexample','comparison']
    if mode=='flashcards':
        assert {'skill','from_notes','explanation'}<=set(schema['$defs'][name]['required'])


def test_varied_problem_keeps_its_source_reference_and_original(source):
    reference={'latex':'x+1=2','page':4,'variant':None}
    variation={'latex':'x+3=7','page':4,'variant':{'original':'x+1=2','change':'Use three and seven as the constants.'}}
    raw={'result':{'status':'completed','items':[{'title':'Solve a linear equation','skill':'application',
         'formula':reference,'question':['Solve the stated equation.',variation],
         'answer':[{'parts':['Subtract three from both sides.']},{'latex':'x=4','page':4,'variant':None}]}]}}
    result=set_response_format(1,'problems',permissive=True).model_validate(raw).result.items[0].expand(source.document.id,1,'problems')
    assert result.answer[0].latex=='x+1=2' and result.answer[0].original_latex is None
    changed=result.question[1]
    assert changed.latex=='x+3=7' and changed.original_latex=='x+1=2' and changed.change
    assert result.skill=='application' and result.from_notes is result.explanation is None


def test_split_card_section_bounds_fit_canonical_answer(source):
    entry={'title':'Membership','skill':'meaning','formula':{'latex':'x','page':4,'variant':None},
           'question':['What is the object?'],'answer':[],
           'from_notes':[{'parts':[f'Source statement {i}.']} for i in range(20)],
           'explanation':[{'parts':[f'Added context {i}.']} for i in range(16)]}
    raw={'result':{'status':'completed','items':[entry]}}
    card=set_response_format(1,'flashcards',permissive=True).model_validate(raw).result.items[0].expand(source.document.id,1)
    assert len(card.answer)==39 and len(card.from_notes)==20 and len(card.explanation)==16


def test_quality_prompts_keep_source_and_added_material_distinct(source):
    system,card_task,_=load_prompts(GenerateRequest(mode='flashcards',count=5,difficulty=5),[source])
    assert 'Never refer to numbered exercises, theorems, examples, figures or sections.' in card_task
    assert 'from_notes: only what the selected primary source actually says' in card_task
    assert 'explanation: short AI-added context' in card_task
    assert 'at least 40% why_justification or counterexample; recall at most 20%' in card_task
    assert 'at least 70% recall or meaning' in card_task
    assert 'at least 40% conditions, application or error_diagnosis' in card_task
    assert 'correct complete answers, the requested difficulty and skill distribution, then question variety' in system
    assert '45–90' not in system+card_task and "source's exercise number in words" not in card_task
    _,problem_task,_=load_prompts(GenerateRequest(mode='problems',count=5),[source])
    assert 'Make the problem statement a variation by default' in problem_task
    assert 'Copy original exercise expressions literally' not in problem_task
    assert 'Normally variant is null' not in system
