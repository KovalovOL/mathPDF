"""OpenAI adapter: one compact response expanded into canonical study blocks."""

from asyncio import to_thread
from .usage import usage_context
import base64
import logging
import re
from functools import lru_cache
from time import perf_counter
from typing import Annotated, Literal

from openai import APIError, AsyncOpenAI, pydantic_function_tool
from pydantic import Field, ValidationError, model_validator

from .study import (MAX_ITEMS, GeneratedContent, GenerationError, InputDocument,
                    ProviderResult, Skill, StrictModel, StudyItem)


class InsufficientSource(StrictModel):
    status: Literal["insufficient_source"]
    reason: str = Field(min_length=1, max_length=1000)


# The constrained provider decoder keeps mathematical syntax out of prose.
# Parsing stays permissive so an older/nonconforming response is still usable.
Prose = Annotated[str, Field(min_length=1, max_length=8000,
    json_schema_extra={"pattern": r"^[A-Za-z\u00C0-\u024F0-9 \t\r\n.,;:!?'\"()/%’‘“”–—…-]*$"})]


def normalize_model_tex(latex: str) -> str:
    """Undo uniform extra JSON escaping, preserving actual TeX rows.

    Only new provider output passes here. Mixed/singly escaped TeX is untouched;
    a consistently doubled expression has even backslash runs everywhere.
    """
    # A dangling escape at the end has no mathematical content and is invalid
    # TeX. Preserve even runs, which can represent genuine row separators.
    trailing = re.search(r"\\+$", latex)
    if trailing and len(trailing[0]) % 2:
        latex = latex[:-1]
    while True:
        runs = re.findall(r"\\+", latex)
        if not (runs and all(len(run) % 2 == 0 for run in runs)
                and re.search(r"\\\\(?:[A-Za-z]{2,}|[{}])", latex)):
            return latex
        latex = re.sub(r"\\+", lambda match: "\\" * (len(match[0]) // 2), latex)
        trailing = re.search(r"\\+$", latex)
        if trailing and len(trailing[0]) % 2:
            latex = latex[:-1]


def normalize_model_prose(text: str) -> str:
    """Typeset only unambiguous standalone TeX lines, as the legacy UI does."""
    text = normalize_model_tex(text)
    lines = []
    for line in text.split("\n"):
        expression = line.strip()
        without_commands = re.sub(r"\\[A-Za-z]+", "", expression)
        if (not any(marker in expression for marker in ("$", r"\(", r"\["))
                and re.search(r"\\[A-Za-z]+", expression)
                and re.match(r"^(?:[\\\d+\-({\[]|[A-Za-z](?=[\s_^=<>]))", expression)
                and not re.search(r"\b[A-Za-z]{3,}\b", without_commands)):
            line = "$" + expression + "$"
        lines.append(line)
    return "\n".join(lines)


class FormulaVariant(StrictModel):
    original: str = Field(min_length=1, max_length=5000)
    change: str = Field(min_length=1, max_length=1000)


class Formula(StrictModel):
    latex: str = Field(min_length=1, max_length=5000)
    page: int = Field(ge=1)
    variant: FormulaVariant | None

    @model_validator(mode="after")
    def decoded_tex(self):
        self.latex = normalize_model_tex(self.latex)
        if self.variant:
            self.variant.original = normalize_model_tex(self.variant.original)
        return self


class InlineMath(StrictModel):
    math: str = Field(min_length=1, max_length=5000)


class Paragraph(StrictModel):
    parts: list[Prose | InlineMath] = Field(min_length=1, max_length=40)


class SourcePage(StrictModel):
    page: int = Field(ge=1)


class CompactItem(StrictModel):
    title: str = Field(min_length=1, max_length=180)
    formula: Formula | SourcePage
    skill: Skill | None = None
    question: list[Prose | Formula | Paragraph] = Field(min_length=1, max_length=40)
    answer: list[Prose | Formula | Paragraph] = Field(min_length=1, max_length=40)

    def expand(self, document_id: str, index: int, mode: str = "flashcards") -> StudyItem:
        from_notes = getattr(self, "from_notes", None)
        explanation = getattr(self, "explanation", None)
        answer_entries = []
        if from_notes is not None:
            answer_entries.extend([Paragraph(parts=["From notes"]), *from_notes])
        if explanation:
            answer_entries.extend([Paragraph(parts=["Explanation"]), *explanation])
        answer_entries.extend(self.answer)
        known = ([self.formula] if isinstance(self.formula, Formula) else []) + [
            entry for entry in self.question + answer_entries if isinstance(entry, Formula)]

        def blocks(entries):
            output = []
            for entry in entries:
                if isinstance(entry, Paragraph):
                    # Explicit parts use canonical delimiters supplied locally;
                    # no model guessing, renderer startup or second request.
                    text = "".join(part if isinstance(part, str) else
                                   r"\(" + normalize_model_tex(part.math) + r"\)" for part in entry.parts)
                    output.append({"kind": "text", "text": text})
                    continue
                if isinstance(entry, str):
                    text = normalize_model_tex(entry)
                    # A model may repeat its typed formula as a bare prose entry.
                    # Reuse that exact formula's citation; never infer a new formula/page.
                    matching = next((formula for formula in known if text.strip() == formula.latex.strip()), None)
                    if matching is None:
                        output.append({"kind": "text", "text": normalize_model_prose(text)})
                        continue
                    entry = matching
                output.append({
                    "kind": "math", "latex": entry.latex, "display": True,
                    "source": {"document_id": document_id, "page": entry.page,
                               "line_start": None, "line_end": None, "quote": None},
                    "original_latex": entry.variant.original if entry.variant else None,
                    "change": entry.variant.change if entry.variant else None,
                })
            return output
        question, answer = blocks(self.question), blocks(answer_entries)
        main = blocks([self.formula])[0] if isinstance(self.formula, Formula) else None
        if mode == "flashcards":
            # Recall cards must not disclose the answer formula before flipping,
            # even when a provider repeats it in the question array.
            answer = [block for block in question if block["kind"] == "math"] + answer
            question = [block for block in question if block["kind"] == "text"]
            if not question:
                question = [{"kind": "text", "text": "Recall the formula."}]
        existing = answer if mode == "flashcards" else question + answer
        if main and not any(block["kind"] == "math" and block["latex"] == main["latex"]
                   and block["source"]["page"] == main["source"]["page"]
                   and block["original_latex"] == main["original_latex"]
                   and block["change"] == main["change"] for block in existing):
            answer.insert(1 if from_notes is not None else 0, main)
        # Ignore only outer whitespace when comparing exact duplicates.
        # Do not equate alternative symbols, layout, punctuation or citations.
        for side in (question, answer):
            seen = set()
            unique = []
            for block in side:
                if block["kind"] == "math":
                    key = (block["latex"].strip(), block["source"]["page"], block["original_latex"], block["change"])
                    if key in seen:
                        continue
                    seen.add(key)
                unique.append(block)
            side[:] = unique
        source = None if main else {"document_id": document_id, "page": self.formula.page,
                                    "line_start": None, "line_end": None, "quote": None}
        return StudyItem(goal_step=index, title=self.title, skill=self.skill, question=question,
                         from_notes=blocks(from_notes) if from_notes is not None else None,
                         explanation=blocks(explanation) if explanation is not None else None,
                         answer=answer, source=source)


class FlashcardOutput(CompactItem):
    question: list[Prose] = Field(min_length=1, max_length=1)
    answer: list[Formula | Paragraph] = Field(default_factory=list, max_length=40)
    from_notes: list[Formula | Paragraph] | None = Field(default=None, max_length=20)
    explanation: list[Formula | Paragraph] | None = Field(default=None, max_length=16)


class ProblemOutput(CompactItem):
    answer: list[Formula | Paragraph] = Field(min_length=1, max_length=40)


class FlashcardRead(FlashcardOutput):
    question: list[Prose | Formula | Paragraph] = Field(min_length=1, max_length=40)
    answer: list[Prose | Formula | Paragraph] = Field(default_factory=list, max_length=40)
    from_notes: list[Prose | Formula | Paragraph] | None = Field(default=None, max_length=20)
    explanation: list[Prose | Formula | Paragraph] | None = Field(default=None, max_length=16)


@lru_cache(maxsize=MAX_ITEMS * 3)
def set_response_format(count: int, mode: str | None = None, *, permissive: bool = False) -> type[StrictModel]:
    if not 1 <= count <= MAX_ITEMS:
        raise ValueError("Invalid requested item count.")

    item_type = (FlashcardRead if permissive else FlashcardOutput) if mode == "flashcards" else (
        ProblemOutput if mode == "problems" and not permissive else CompactItem)

    class CompletedSet(StrictModel):
        status: Literal["completed"]
        items: list[item_type] = Field(min_length=count, max_length=count)

    class SetResponse(StrictModel):
        result: CompletedSet | InsufficientSource

    return SetResponse


class OpenAIProvider:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, documents: list[InputDocument], system: str, task: str,
                       *, count: int, mode: Literal["flashcards", "problems"]) -> ProviderResult:
        content = []
        for entry in documents:
            content.append({"type": "input_text", "text": entry.label})
            data_url = f"data:{entry.document.media_type};base64," + base64.b64encode(entry.data).decode()
            if entry.document.media_type.startswith("image/"):
                content.append({"type": "input_image", "image_url": data_url, "detail": "auto"})
            else:
                content.append({"type": "input_file", "filename": entry.filename, "file_data": data_url})
        content.append({"type": "input_text", "text": task})
        output_cap=min(30000,1000+(650 if mode=='flashcards' else 1000)*count)
        estimated_tokens=(output_cap
            +sum(len(d.pages)*4000 if d.pages is not None else (d.document.page_count*4000 if d.document.page_count else (len(d.data)+2)//3) for d in documents)
            +(len(system.encode())+len(task.encode())+2)//3)
        response_format = set_response_format(count, mode)
        function = pydantic_function_tool(response_format)["function"]
        logger = logging.getLogger(__name__)
        started = perf_counter()
        tracking=usage_context.get();attempt=None
        if tracking and tracking['store']:
            attempt=await to_thread(tracking['store'].start,tracking['user_id'],'openai',self.model,
                {'estimated_tokens':estimated_tokens,'selection':tracking['request'],'system_prompt':system,'task_prompt':task,
                 'documents':[{'id':d.document.id,'filename':d.document.filename,'sha256':d.document.sha256,'pages':d.pages,'role':d.role} for d in documents]})
            tracking['attempt_id']=attempt
        logger.info("Provider request started phase=generating requested=%s", count)
        try:
            # Exactly one HTTP attempt, including timeouts and provider errors.
            async with AsyncOpenAI(api_key=self.api_key, timeout=120, max_retries=0) as client:
                response = await client.responses.create(
                    model=self.model,
                    instructions=system,
                    input=[{"role": "user", "content": content}],
                    text={"format": {"type": "json_schema", "name": function["name"],
                                     "strict": True, "schema": function["parameters"]}},
                    max_output_tokens=output_cap,
                    store=False,
                )
        except APIError as error:
            if attempt:
                await to_thread(tracking['store'].finish,attempt,'provider_error',None,round((perf_counter()-started)*1000),getattr(error,'request_id',None),unbilled=getattr(error,'status_code',None) in {400,401,403,404,409,413,422,429})
            status = getattr(error, "status_code", None)
            logger.warning("Provider request failed status=%s error_type=%s duration_ms=%s",
                           status, type(error).__name__, round((perf_counter() - started) * 1000))
            messages = {
                401: "Generation is unavailable because of a server configuration problem.",
                429: "The generation service has reached its usage limit. Please try again later.",
                400: "The generation service could not process these files. Try fewer pages or different files.",
            }
            raise GenerationError(messages.get(status, "The generation service is unavailable or timed out. Try again later.")) from None
        if attempt:
            await to_thread(tracking['store'].finish,attempt,'received',getattr(response,'usage',None),round((perf_counter()-started)*1000),getattr(response,'_request_id',None))
            await to_thread(tracking['store'].response,attempt,getattr(response,'model',None) or self.model,response.status,response.output_text)
        logger.info("Provider request finished phase=generating status=%s output_tokens=%s duration_ms=%s",
                    response.status, getattr(response.usage, "output_tokens", None), round((perf_counter() - started) * 1000))
        if any(part.type == "refusal" for output in response.output if output.type == "message"
               for part in output.content):
            raise GenerationError("The generation service could not create material from these pages. Try different source pages.")
        if response.status != "completed":
            logger.warning("Study response incomplete reason=%s output_tokens=%s",
                           getattr(response.incomplete_details, "reason", None), getattr(response.usage, "output_tokens", None))
            raise GenerationError("The model did not complete the requested set. No partial set was created. Please try again.")
        try:
            # A broad local reader preserves old/nonconforming formatting;
            # the stricter generation schema guides only this one model call.
            result = set_response_format(count, mode, permissive=True).model_validate_json(response.output_text).result
            if isinstance(result, InsufficientSource):
                return ProviderResult(content=GeneratedContent(items=[], notes=[]), provider="openai", model=self.model,
                                      insufficient_source=True)
            items = [item.expand(documents[0].document.id, index, mode) for index, item in enumerate(result.items, 1)]
        except ValidationError as error:
            fields = [{"type": entry["type"], "loc": entry["loc"]} for entry in error.errors()]
            logger.warning("Study response invalid_fields=%s", fields)
            raise GenerationError("The model returned an invalid study set. No partial set was created. Please try again.") from None
        return ProviderResult(content=GeneratedContent(items=items, notes=[]), provider="openai", model=self.model)
