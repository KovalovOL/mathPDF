"""Provider-independent study contract and selected-page generation service."""

import hashlib
import io
import json
import logging
import re
from asyncio import timeout, to_thread
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from time import perf_counter
from typing import Callable, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader, PdfWriter
from .workspace import Document, Workspace
from .usage import usage_context


MAX_ITEMS = 50
GENERATION_SECONDS = 150
Progress = Callable[[dict], None]
logger = logging.getLogger(__name__)
INLINE_MATH = re.compile(r"\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    document_id: str | None = None
    page: int = Field(ge=1)
    line_start: int | None = Field(ge=1)
    line_end: int | None = Field(ge=1)
    quote: str | None = Field(max_length=1200)

    @model_validator(mode="after")
    def valid_lines(self):
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("Supply both line numbers or neither")
        if self.line_start is not None and self.line_end < self.line_start:
            raise ValueError("Line range must be ordered")
        return self


class TextBlock(StrictModel):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=8000)


class MathBlock(StrictModel):
    kind: Literal["math"]
    latex: str = Field(min_length=1, max_length=5000)
    display: bool
    source: Citation
    original_latex: str | None = Field(max_length=5000)
    change: str | None = Field(max_length=1000)

    @model_validator(mode="after")
    def valid_change(self):
        if self.original_latex == self.latex:
            self.original_latex = None
            self.change = None
        if (self.original_latex is None) != (self.change is None):
            raise ValueError("A quiz variant needs its original formula and change description")
        return self


Block = TextBlock | MathBlock
Skill = Literal["recall", "meaning", "conditions", "application", "error_diagnosis",
                "why_justification", "counterexample", "comparison"]


class StudyItem(StrictModel):
    goal_step: int | None = Field(default=None, ge=1, le=MAX_ITEMS)
    title: str = Field(min_length=1, max_length=180)
    skill: Skill | None = Field(default=None, exclude_if=lambda value: value is None)
    question: list[Block] = Field(min_length=1, max_length=40)
    from_notes: list[Block] | None = Field(default=None, max_length=40, exclude_if=lambda value: value is None)
    explanation: list[Block] | None = Field(default=None, max_length=40, exclude_if=lambda value: value is None)
    answer: list[Block] = Field(min_length=1, max_length=40)
    source: Citation | None = None


class GeneratedContent(StrictModel):
    items: list[StudyItem] = Field(max_length=MAX_ITEMS)
    notes: list[str] = Field(max_length=10)


class ContextSelection(StrictModel):
    document_id: str
    pages: list[int] | None = Field(default=None, min_length=1, max_length=100)


class GenerateRequest(StrictModel):
    document_id: str | None = None
    pages: list[int] | None = Field(default=None, min_length=1, max_length=100)
    context: list[ContextSelection] = Field(default_factory=list, max_length=6)
    comment: str = Field(default="", max_length=4000)
    mode: Literal["flashcards", "problems"]
    count: int = Field(default=4, ge=1, le=MAX_ITEMS)
    difficulty: int = Field(default=3, ge=1, le=5, strict=True)


class ContextSnapshot(StrictModel):
    document: Document
    pages: list[int] | None


class StudySet(GeneratedContent):
    # Unmarked historical records and browser drafts are version 1 as well.
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    title: str = Field(min_length=1, max_length=200)
    document: Document
    pages: list[int] = Field(min_length=1, max_length=100)
    context_documents: list[ContextSnapshot] = Field(default_factory=list, max_length=6)
    comment: str = Field(default="", max_length=4000)
    mode: Literal["flashcards", "problems"]
    difficulty: int = Field(default=3, ge=1, le=5, strict=True)
    metadata: dict


@dataclass
class InputDocument:
    document: Document
    data: bytes
    filename: str
    role: str
    pages: list[int] | None
    label: str = ""


class ProviderResult(StrictModel):
    content: GeneratedContent
    provider: str
    model: str
    insufficient_source: bool = False


class StudyProvider(Protocol):
    async def generate(self, documents: list[InputDocument], system: str, task: str,
                       *, count: int, mode: Literal["flashcards", "problems"]) -> ProviderResult: ...


class GenerationError(Exception):
    """A safe, user-facing provider failure, without credentials or request bodies."""


class ContentValidationError(GenerationError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


PROMPTS = Path(__file__).parent / "prompts"


def load_prompts(request: GenerateRequest, documents: list[InputDocument]) -> tuple[str, str, dict[str, str]]:
    names = ["study-system.md", f"{request.mode}.md", "formula-guide.md", "math-patterns.md",
             "context.md", "attachment-label.md", "comment.md", "difficulty.md"]
    resources = {name: (PROMPTS / name).read_text(encoding="utf-8") for name in names}
    source = documents[0]
    mapping = ", ".join(f"{index + 1} -> {page}" for index, page in enumerate(source.pages))
    task = Template(resources[f"{request.mode}.md"]).substitute(count=request.count, page_mapping=mapping)
    task += "\n\n" + Template(resources["difficulty.md"]).substitute(difficulty=request.difficulty)
    metadata = []
    for entry in documents:
        info = {"document_id": entry.document.id, "filename": entry.filename,
                "original_filename": entry.document.filename, "role": entry.role,
                "original_pages": entry.pages}
        metadata.append(info)
        entry.label = Template(resources["attachment-label.md"]).substitute(metadata=json.dumps(info, ensure_ascii=False))
    task += "\n\n" + Template(resources["context.md"]).substitute(attachments=json.dumps(metadata, ensure_ascii=False))
    if request.comment.strip():
        task += "\n\n" + Template(resources["comment.md"]).substitute(comment=json.dumps(request.comment.strip(), ensure_ascii=False))
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in resources.items()}
    system = "\n\n".join(resources[name] for name in ("study-system.md", "formula-guide.md", "math-patterns.md"))
    return system, task, hashes


def selected_pdf(path: Path, pages: list[int]) -> bytes:
    reader = PdfReader(path)
    if len(set(pages)) != len(pages):
        raise ValueError("Select each PDF page only once")
    if any(page < 1 or page > len(reader.pages) for page in pages):
        raise ValueError(f"Page numbers must be between 1 and {len(reader.pages)}")
    writer = PdfWriter()
    for page in pages:
        writer.add_page(reader.pages[page - 1])
    output = io.BytesIO()
    writer.write(output)
    data = output.getvalue()
    if len(data) > 40 * 1024 * 1024:
        raise ValueError("Selected PDF pages exceed the 40 MB generation limit")
    return data


def prepare_documents(workspace: Workspace, request: GenerateRequest, owner_id: str) -> list[InputDocument]:
    source_id = request.document_id
    if source_id is None:
        raise ValueError("Upload a PDF and choose it as the primary source.")
    source = workspace.document(source_id, owner_id)
    if source.media_type != "application/pdf":
        raise ValueError("Choose a PDF as the primary source.")
    entries = [(source, request.pages, "source")]
    used = {source.id}
    for context in request.context:
        if context.document_id in used:
            raise ValueError("Include each file only once in a generation request.")
        used.add(context.document_id)
        entries.append((workspace.document(context.document_id, owner_id), context.pages, "context"))
    result = []
    total_pages = 0
    for document, pages, role in entries:
        path = workspace.path(document.id, owner_id)
        if document.page_count is not None:
            pages = pages if pages is not None else list(range(1, document.page_count + 1))
            total_pages += len(pages)
            if total_pages > 100:
                raise ValueError("Select at most 100 PDF pages across all attached files.")
            data = selected_pdf(path, pages)
        else:
            if pages is not None:
                raise ValueError("Page ranges apply only to PDF files.")
            data = path.read_bytes()
        result.append(InputDocument(document, data, f"{role}-{document.id}{path.suffix}", role, pages))
    if sum(len(entry.data) for entry in result) > 40 * 1024 * 1024:
        raise ValueError("Selected attachments exceed the 40 MB generation limit.")
    return result


def validate_item(item: StudyItem, mode: str, document_id: str, pages: list[int]):
    maths = [block for block in item.question + item.answer if isinstance(block, MathBlock)]
    if not maths and item.source is None:
        raise ContentValidationError("missing_formula", "A study item is missing its source formula or page reference.")
    sources = [block.source for block in maths] + ([item.source] if item.source else [])
    for source in sources:
        if source.document_id is None:
            source.document_id = document_id
        if source.page not in pages or source.document_id != document_id:
            raise ContentValidationError("invalid_source", "A study item references pages outside the selected source.")


def item_expressions(item: StudyItem) -> list[tuple[str, bool]]:
    expressions = []
    for block in item.question + item.answer:
        if isinstance(block, MathBlock):
            expressions.extend((text, block.display) for text in [block.latex, block.original_latex] if text is not None)
        else:
            for match in INLINE_MATH.finditer(block.text):
                expressions.append((next(part for part in match.groups() if part is not None),
                                    match[2] is not None or match[3] is not None))
    return expressions


def validate_study(content: GeneratedContent, mode: str, document_id: str, pages: list[int]):
    for item in content.items:
        validate_item(item, mode, document_id, pages)
    if not content.items and not any(note.strip() for note in content.notes):
        raise GenerationError("The provider returned no study material or explanation.")


def question_fingerprint(item: StudyItem) -> str:
    # Ignore titles/citations and superficial spacing when rejecting exact repeats.
    blocks = [(block.kind, " ".join(block.text.casefold().split())) if isinstance(block, TextBlock)
              else (block.kind, re.sub(r"\s+", "", block.latex)) for block in item.question]
    return hashlib.sha256(json.dumps(blocks, ensure_ascii=False).encode()).hexdigest()


async def collect_study(documents: list[InputDocument], request: GenerateRequest,
                        provider: StudyProvider, progress: Progress) -> tuple[GeneratedContent, dict]:
    source = documents[0]
    system, task, hashes = load_prompts(request, documents)
    started = perf_counter()
    progress({"phase": "generating", "accepted_count": 0, "attempt": 1})
    logger.info("Study single request started requested=%s mode=%s", request.count, request.mode)
    result = await provider.generate(documents, system, task, count=request.count, mode=request.mode)
    if result.insufficient_source:
        raise GenerationError(f"The selected pages could not support {request.count} distinct items. "
                              "Choose more source pages or request fewer items.")
    if len(result.content.items) != request.count:
        logger.warning("Study response rejected code=wrong_count requested=%s received=%s",
                       request.count, len(result.content.items))
        raise GenerationError(f"The model returned {len(result.content.items)} of {request.count} requested items. "
                              "No partial set was created. Please try again.")
    progress({"phase": "checking"})
    seen = set()
    try:
        for index, item in enumerate(result.content.items, 1):
            item.goal_step = index  # Stable order without a separate model-generated plan.
            validate_item(item, request.mode, source.document.id, source.pages)
            fingerprint = question_fingerprint(item)
            if fingerprint in seen:
                raise ContentValidationError("duplicate_question", "The model returned a repeated question.")
            seen.add(fingerprint)
    except ContentValidationError as error:
        logger.warning("Study response rejected code=%s requested=%s", error.code, request.count)
        raise GenerationError(str(error) + " No partial set was created. Please try again.") from None
    progress({"accepted_count": request.count})
    elapsed = round((perf_counter() - started) * 1000)
    logger.info("Study single request completed requested=%s accepted=%s duration_ms=%s",
                request.count, request.count, elapsed)
    return result.content, {"provider": result.provider, "model": result.model, "prompt_hashes": hashes,
                            "math_check": "on_display", "formatting_policy": "best_effort", "requested_count": request.count,
                            "generation_attempts": 1, "provider_requests": 1,
                            "generation_strategy": "single_request", "generation_duration_ms": elapsed}


async def generate_study(workspace: Workspace, owner_id: str, request: GenerateRequest,
                         provider: StudyProvider, progress: Progress | None = None) -> StudySet:
    if getattr(workspace,'usage',None):await to_thread(workspace.usage.quota.check,owner_id)
    tracking={"store":getattr(workspace,"usage",None),"user_id":owner_id,"request":request.model_dump(mode="json"),"attempt_id":None}
    context_token=usage_context.set(tracking)
    progress = progress or (lambda _: None)
    try:
        async with timeout(GENERATION_SECONDS):
            progress({"phase": "preparing", "accepted_count": 0})
            documents = await to_thread(prepare_documents, workspace, request, owner_id)
            content, metadata = await collect_study(documents, request, provider, progress)
    except BaseException as error:
        if tracking['store'] and tracking['attempt_id']:
            try:
                await to_thread(tracking['store'].outcome,tracking['attempt_id'],'cancelled' if type(error).__name__=='CancelledError' else 'failed')
            except Exception:
                logger.warning('Could not update the failed provider attempt status id=%s',tracking['attempt_id'])
        if isinstance(error,TimeoutError):
            raise GenerationError(f"Generation timed out before all {request.count} items were ready. "
                                  "Try again with fewer items or fewer source pages.") from None
        raise
    finally:
        usage_context.reset(context_token)
    if tracking['store'] and tracking['attempt_id']:
        await to_thread(tracking['store'].outcome,tracking['attempt_id'],'completed')
    source = documents[0]
    label = "Flashcards" if request.mode == "flashcards" else "Problems"
    selection = str(source.pages[0]) if len(source.pages) == 1 else f"{source.pages[0]}–{source.pages[-1]}"
    return StudySet(
        title=f"{label} · {source.document.filename} · {selection}",
        document=source.document, pages=source.pages, mode=request.mode,
        comment=request.comment.strip(), difficulty=request.difficulty,
        context_documents=[ContextSnapshot(document=entry.document, pages=entry.pages) for entry in documents[1:]],
        **content.model_dump(),
        metadata={**metadata,
                  "source_check": "unchecked", "line_references": "page-only",
                  "created_at": datetime.now(timezone.utc).isoformat()},
    )
