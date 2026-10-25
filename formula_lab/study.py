"""Provider-independent study contract and selected-page generation service."""

import hashlib
import io
import json
import logging
import re
from collections import Counter
from asyncio import timeout, to_thread
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from string import Template
from typing import Callable, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader, PdfWriter
from .workspace import Document, Workspace
from .math_validation import MathValidator, MathValidationError


MAX_ITEMS = 50
BATCH_SIZE = 2
EXTRA_ATTEMPTS = 3
PLAN_ATTEMPTS = 2
GENERATION_SECONDS = 600
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


class StudyItem(StrictModel):
    goal_step: int | None = Field(default=None, ge=1, le=MAX_ITEMS)
    title: str = Field(min_length=1, max_length=180)
    question: list[Block] = Field(min_length=1, max_length=40)
    answer: list[Block] = Field(min_length=1, max_length=40)


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


class ContextSnapshot(StrictModel):
    document: Document
    pages: list[int] | None


class StudySet(GeneratedContent):
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    title: str = Field(min_length=1, max_length=200)
    document: Document
    pages: list[int] = Field(min_length=1, max_length=100)
    context_documents: list[ContextSnapshot] = Field(default_factory=list, max_length=6)
    comment: str = Field(default="", max_length=4000)
    mode: Literal["flashcards", "problems"]
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


class LearningGoal(StrictModel):
    step: int = Field(ge=1, le=MAX_ITEMS)
    topic: str = Field(min_length=1, max_length=80)
    objective: str = Field(min_length=1, max_length=180)
    activity: Literal["recognition", "explanation", "application", "comparison", "error_analysis", "justification", "synthesis"]
    challenge: str = Field(min_length=1, max_length=180)
    source_pages: list[int] = Field(min_length=1, max_length=5)


class PlanResult(StrictModel):
    goals: list[LearningGoal] = Field(max_length=MAX_ITEMS)
    provider: str
    model: str
    insufficient_source: bool = False


class StudyProvider(Protocol):
    async def plan(self, documents: list[InputDocument], system: str, task: str,
                   *, count: int) -> PlanResult: ...

    async def generate(self, documents: list[InputDocument], system: str, task: str,
                       *, count: int) -> ProviderResult: ...


class GenerationError(Exception):
    """A safe, user-facing provider failure, without credentials or request bodies."""


class RetryableGenerationError(GenerationError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


PROMPTS = Path(__file__).parent / "prompts"


def load_prompts(request: GenerateRequest, documents: list[InputDocument], *,
                 accepted: list[StudyItem] | None = None, feedback: list[str] | None = None,
                 total_count: int | None = None, plan: list[LearningGoal] | None = None,
                 goal_steps: list[int] | None = None, planning: bool = False,
                 rejected: list[dict] | None = None) -> tuple[str, str, dict[str, str]]:
    names = (["plan-system.md", "learning-plan.md"] if planning else ["study-system.md", f"{request.mode}.md"]) + [
        "context.md", "attachment-label.md", "comment.md", "continuation.md", "goals.md", "concise.md"]
    resources = {name: (PROMPTS / name).read_text(encoding="utf-8") for name in names}
    source = documents[0]
    mapping = ", ".join(f"{index + 1} -> {page}" for index, page in enumerate(source.pages))
    task = Template(resources[names[1]]).substitute(count=request.count, page_mapping=mapping,
                                                  mode=request.mode, feedback=json.dumps(feedback or []))
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
    if not planning:
        task += "\n\n" + Template(resources["goals.md"]).substitute(
            plan=json.dumps([goal.model_dump(mode="json") for goal in plan or []], ensure_ascii=False),
            goal_steps=json.dumps(goal_steps or []))
        task += "\n\n" + Template(resources["continuation.md"]).substitute(
            total_count=total_count or request.count, batch_count=request.count,
            accepted=json.dumps([item.model_dump(mode="json") for item in accepted or []], ensure_ascii=False),
            feedback=json.dumps(feedback or []), rejected=json.dumps(rejected or [], ensure_ascii=False))
    task += "\n\n" + resources["concise.md"]
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in resources.items()}
    return resources[names[0]], task, hashes


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


def validate_item(item: StudyItem, mode: str, document_id: str, pages: list[int], *, strict_blocks: bool = False):
    maths = [block for block in item.question + item.answer if isinstance(block, MathBlock)]
    if not maths:
        raise RetryableGenerationError("missing_formula", "A study item is missing its source formula.")
    if mode == "flashcards" and not any(isinstance(block, MathBlock) for block in item.question):
        raise RetryableGenerationError("missing_question_formula", "A flashcard question is missing its formula.")
    if strict_blocks:
        prose = [item.title] + [INLINE_MATH.sub("", block.text) for block in item.question + item.answer if isinstance(block, TextBlock)]
        prose += [block.change for block in maths if block.change]
        if any(re.search(r"\\(?:[A-Za-z]+|[{}\[\]()])|\$", text) for text in prose):
            raise RetryableGenerationError("math_in_text", "Mathematical expressions need formatted math blocks.")
        for block in maths:
            for expression in [block.latex, block.original_latex]:
                if expression and prose_in_math(expression):
                    raise RetryableGenerationError("prose_in_math", "Exercise prose needs separate text blocks.")
    for block in maths:
        if block.source.document_id is None:
            block.source.document_id = document_id
        if block.source.page not in pages or block.source.document_id != document_id:
            raise RetryableGenerationError("invalid_source", "A formula references pages outside the selected source.")


def prose_in_math(latex: str) -> bool:
    if re.search(r"(?:^|\\text\s*\{)\s*(?:exercise|problem|question)\s+\d", latex, re.I):
        return True
    # Long sentences inside \text are usually a copied prompt, not a formula condition.
    text_runs = re.findall(r"\\text\s*\{([^{}]*)\}", latex)
    if any(len(re.findall(r"[A-Za-z]{2,}", run)) >= 12 for run in text_runs):
        return True
    without_commands = re.sub(r"\\[A-Za-z]+", "", latex)
    return len(re.findall(r"\b[A-Za-z]{3,}\b", without_commands)) >= 14


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


def question_repeats(item: StudyItem, previous: list[StudyItem], activities: dict[int, str]) -> bool:
    def formula_signature(candidate):
        return tuple(sorted(re.sub(r"\s+", "", block.latex) for block in candidate.question if isinstance(block, MathBlock)))

    def prose(candidate):
        return " ".join(re.findall(r"[a-z0-9]+", " ".join(
            block.text.casefold() for block in candidate.question if isinstance(block, TextBlock))))

    fingerprint, formulas, words = question_fingerprint(item), formula_signature(item), prose(item)
    for other in previous:
        if fingerprint == question_fingerprint(other):
            return True
        if activities.get(item.goal_step) != activities.get(other.goal_step):
            continue
        # A conservative paraphrase guard: different formulas are often legitimate exercises.
        # For prose-only questions compare the source formulas in their answers as well.
        left = formulas or tuple(sorted(block.latex for block in item.answer if isinstance(block, MathBlock)))
        right = formula_signature(other) or tuple(sorted(block.latex for block in other.answer if isinstance(block, MathBlock)))
        if left != right:
            continue
        other_words = prose(other)
        if not words or not other_words:
            continue
        a, b = set(words.split()), set(other_words.split())
        overlap = len(a & b) / len(a | b)
        if overlap >= .8 or SequenceMatcher(None, words, other_words).ratio() >= .87:
            return True
    return False


def validate_plan(goals: list[LearningGoal], count: int, pages: list[int]):
    if len(goals) != count:
        raise RetryableGenerationError("wrong_plan_count", "The learning plan has the wrong number of goals.")
    if [goal.step for goal in goals] != list(range(1, count + 1)):
        raise RetryableGenerationError("invalid_plan_steps", "The learning plan needs consecutive goal numbers.")
    seen = []
    for goal in goals:
        if not set(goal.source_pages).issubset(pages) or len(set(goal.source_pages)) != len(goal.source_pages):
            raise RetryableGenerationError("invalid_plan_source", "A learning goal cites unavailable pages.")
        normalized = " ".join(re.findall(r"\w+", goal.objective.casefold()))
        topic = " ".join(re.findall(r"\w+", goal.topic.casefold()))
        if any(topic == old_topic and goal.activity == activity and (normalized == text or
               SequenceMatcher(None, normalized, text).ratio() >= .9) for text, activity, old_topic in seen):
            raise RetryableGenerationError("duplicate_goal", "The learning plan repeats an objective.")
        seen.append((normalized, goal.activity, topic))
    required_activities = 3 if count >= 8 else 2 if count >= 4 else 1
    if len({goal.activity for goal in goals}) < required_activities:
        raise RetryableGenerationError("insufficient_variety", "The learning plan needs more varied reasoning activities.")


async def create_plan(documents: list[InputDocument], request: GenerateRequest,
                      provider: StudyProvider, progress: Progress) -> tuple[list[LearningGoal], dict]:
    feedback = []
    for attempt in range(1, PLAN_ATTEMPTS + 1):
        progress({"phase": "planning", "attempt": attempt})
        logger.info("Study planning attempt=%s requested=%s", attempt, request.count)
        system, task, hashes = load_prompts(request, documents, planning=True, feedback=feedback)
        try:
            result = await provider.plan(documents, system, task, count=request.count)
            if result.insufficient_source:
                raise GenerationError(f"The selected pages could not support {request.count} distinct progressive items. "
                                      "Choose more source pages or request fewer items.")
            validate_plan(result.goals, request.count, documents[0].pages)
            return result.goals, {"planning_attempts": attempt, "plan_provider": result.provider, "plan_model": result.model,
                                  "prompt_hashes": hashes, "learning_plan": [goal.model_dump() for goal in result.goals]}
        except RetryableGenerationError as error:
            logger.warning("Study plan rejected attempt=%s code=%s", attempt, error.code)
            feedback = [error.code]
    raise GenerationError("We couldn't plan a varied study sequence from these pages. "
                          "Try again, choose more source pages, or request fewer items.")


async def collect_study(documents: list[InputDocument], request: GenerateRequest,
                        provider: StudyProvider, progress: Progress) -> tuple[GeneratedContent, dict]:
    plan, planning = await create_plan(documents, request, provider, progress)
    accepted: dict[int, StudyItem] = {}
    notes: list[str] = []
    feedback: list[str] = []
    rejected: list[dict] = []
    rejection_counts: Counter = Counter()
    activities = {goal.step: goal.activity for goal in plan}
    source = documents[0]
    limit = request.count + EXTRA_ATTEMPTS
    batch_size = BATCH_SIZE
    async with MathValidator() as validator:
        for attempt in range(1, limit + 1):
            goal_steps = [goal.step for goal in plan if goal.step not in accepted][:batch_size]
            batch_count = len(goal_steps)
            batch = request.model_copy(update={"count": batch_count})
            previous = [accepted[step] for step in sorted(accepted)]
            system, task, hashes = load_prompts(batch, documents, accepted=previous, plan=plan, goal_steps=goal_steps,
                                              feedback=feedback, total_count=request.count, rejected=rejected)
            progress({"phase": "generating", "accepted_count": len(accepted), "attempt": attempt})
            logger.info("Study batch attempt=%s accepted=%s requested=%s batch=%s", attempt, len(accepted), request.count, batch_count)
            try:
                result = await provider.generate(documents, system, task, count=batch_count)
            except RetryableGenerationError as error:
                feedback = [error.code]
                rejection_counts.update(feedback)
                if error.code in {"output_limit", "invalid_response", "incomplete_response"}:
                    batch_size = 1
                logger.warning("Study batch rejected attempt=%s code=%s", attempt, error.code)
                continue
            if result.insufficient_source:
                raise GenerationError(f"The selected pages could not support all {request.count} items. "
                                      "Choose more source pages or request fewer items.")
            feedback = []
            rejected = []
            if len(result.content.items) > batch_count:
                feedback = ["wrong_count"]
                rejection_counts.update(feedback)
                continue
            for item in result.content.items:
                diagnostics = []
                progress({"phase": "checking", "accepted_count": len(accepted), "attempt": attempt})
                try:
                    if item.goal_step not in goal_steps or item.goal_step in accepted:
                        raise RetryableGenerationError("wrong_goal", "A study item has an unexpected learning goal.")
                    validate_item(item, request.mode, source.document.id, source.pages, strict_blocks=True)
                    if question_repeats(item, list(accepted.values()), activities):
                        raise RetryableGenerationError("duplicate_question", "A study question repeats an earlier item.")
                    diagnostics = await validator.errors(item_expressions(item))
                    if diagnostics:
                        raise RetryableGenerationError("invalid_math", "A formula needs its formatting repaired.")
                except RetryableGenerationError as error:
                    feedback.append(error.code)
                    rejected.append({"code": error.code, "diagnostics": diagnostics, "item": item.model_dump(mode="json")})
                    continue
                accepted[item.goal_step] = item
                progress({"accepted_count": len(accepted)})
            if len(result.content.items) < batch_count:
                feedback.append("wrong_count")
            rejection_counts.update(feedback)
            logger.info("Study batch reviewed attempt=%s accepted=%s requested=%s rejected=%s",
                        attempt, len(accepted), request.count, dict(Counter(feedback)))
            batch_size = BATCH_SIZE
            for note in result.content.notes:
                if note.strip() and note not in notes and len(notes) < 10:
                    notes.append(note)
            if len(accepted) == request.count:
                content = GeneratedContent(items=[accepted[step] for step in range(1, request.count + 1)], notes=notes)
                validate_study(content, request.mode, source.document.id, source.pages)
                return content, {**planning, "provider": result.provider, "model": result.model,
                                 "prompt_hashes": {**planning["prompt_hashes"], **hashes}, "math_check": "katex",
                                 "rejection_counts": dict(rejection_counts),
                                 "requested_count": request.count, "generation_attempts": attempt}
    reasons = {"invalid_math": "formula formatting", "math_in_text": "unformatted math in prose",
               "duplicate_question": "repeated questions", "output_limit": "truncated model responses",
               "invalid_response": "invalid model responses", "invalid_source": "source references",
               "wrong_goal": "learning goal identifiers", "prose_in_math": "prose inside formulas"}
    detail = ", ".join(reasons.get(code, code.replace("_", " ")) for code, _ in rejection_counts.most_common(3))
    raise GenerationError(f"Generation stopped after accepting {len(accepted)} of {request.count} items. "
                          f"Repeated issues: {detail or 'incomplete responses'}. No partial set was created. Try again.")


async def generate_study(workspace: Workspace, owner_id: str, request: GenerateRequest,
                         provider: StudyProvider, progress: Progress | None = None) -> StudySet:
    progress = progress or (lambda _: None)
    try:
        async with timeout(GENERATION_SECONDS):
            progress({"phase": "preparing", "accepted_count": 0})
            documents = await to_thread(prepare_documents, workspace, request, owner_id)
            content, metadata = await collect_study(documents, request, provider, progress)
    except TimeoutError:
        raise GenerationError(f"Generation timed out before all {request.count} items were ready. "
                              "Try again with fewer items or fewer source pages.") from None
    except MathValidationError as error:
        raise GenerationError(str(error)) from None
    source = documents[0]
    label = "Flashcards" if request.mode == "flashcards" else "Problems"
    selection = str(source.pages[0]) if len(source.pages) == 1 else f"{source.pages[0]}–{source.pages[-1]}"
    return StudySet(
        title=f"{label} · {source.document.filename} · {selection}",
        document=source.document, pages=source.pages, mode=request.mode,
        comment=request.comment.strip(),
        context_documents=[ContextSnapshot(document=entry.document, pages=entry.pages) for entry in documents[1:]],
        **content.model_dump(),
        metadata={**metadata,
                  "source_check": "unchecked", "line_references": "model-reported",
                  "created_at": datetime.now(timezone.utc).isoformat()},
    )
