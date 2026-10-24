"""Provider-independent study contract and selected-page generation service."""

import hashlib
import io
import json
from asyncio import to_thread
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader, PdfWriter
from .workspace import Document, Workspace


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
    title: str = Field(min_length=1, max_length=180)
    question: list[Block] = Field(min_length=1, max_length=40)
    answer: list[Block] = Field(min_length=1, max_length=40)


class GeneratedContent(StrictModel):
    items: list[StudyItem] = Field(max_length=10)
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
    count: int = Field(default=4, ge=1, le=10)


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


class StudyProvider(Protocol):
    async def generate(self, documents: list[InputDocument], system: str, task: str) -> ProviderResult: ...


class GenerationError(Exception):
    """A safe, user-facing provider failure, without credentials or request bodies."""


PROMPTS = Path(__file__).parent / "prompts"


def load_prompts(request: GenerateRequest, documents: list[InputDocument]) -> tuple[str, str, dict[str, str]]:
    names = ["study-system.md", f"{request.mode}.md", "context.md", "attachment-label.md", "comment.md"]
    resources = {name: (PROMPTS / name).read_text(encoding="utf-8") for name in names}
    source = documents[0]
    mapping = ", ".join(f"{index + 1} -> {page}" for index, page in enumerate(source.pages))
    task = Template(resources[names[1]]).substitute(count=request.count, page_mapping=mapping)
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


def prepare_documents(workspace: Workspace, request: GenerateRequest, default_id: str) -> list[InputDocument]:
    source = workspace.document(request.document_id or default_id)
    if source.media_type != "application/pdf":
        raise ValueError("Choose a PDF as the primary source.")
    entries = [(source, request.pages, "source")]
    used = {source.id}
    for context in request.context:
        if context.document_id in used:
            raise ValueError("Include each file only once in a generation request.")
        used.add(context.document_id)
        entries.append((workspace.document(context.document_id), context.pages, "context"))
    result = []
    total_pages = 0
    for document, pages, role in entries:
        path = workspace.path(document.id)
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


def validate_study(content: GeneratedContent, mode: str, document_id: str, pages: list[int]):
    for item in content.items:
        maths = [block for block in item.question + item.answer if isinstance(block, MathBlock)]
        if not maths or (mode == "flashcards" and not any(isinstance(block, MathBlock) for block in item.question)):
            raise GenerationError("The provider returned an item without the required formula.")
        for block in maths:
            if block.source.document_id is None:
                block.source.document_id = document_id
            if block.source.page not in pages or block.source.document_id != document_id:
                raise GenerationError("A formula cites material outside the selected source pages.")
    if not content.items and not any(note.strip() for note in content.notes):
        raise GenerationError("The provider returned no study material or explanation.")


async def generate_study(workspace: Workspace, default_id: str, request: GenerateRequest,
                         provider: StudyProvider) -> StudySet:
    documents = await to_thread(prepare_documents, workspace, request, default_id)
    system, task, hashes = load_prompts(request, documents)
    result = await provider.generate(documents, system, task)
    content = result.content
    if len(content.items) > request.count:
        raise GenerationError("The provider returned more items than requested. Generate again.")
    source = documents[0]
    validate_study(content, request.mode, source.document.id, source.pages)
    label = "Flashcards" if request.mode == "flashcards" else "Problems"
    selection = str(source.pages[0]) if len(source.pages) == 1 else f"{source.pages[0]}–{source.pages[-1]}"
    return StudySet(
        title=f"{label} · {source.document.filename} · {selection}",
        document=source.document, pages=source.pages, mode=request.mode,
        comment=request.comment.strip(),
        context_documents=[ContextSnapshot(document=entry.document, pages=entry.pages) for entry in documents[1:]],
        **content.model_dump(),
        metadata={"provider": result.provider, "model": result.model, "prompt_hashes": hashes,
                  "source_check": "unchecked", "line_references": "model-reported",
                  "created_at": datetime.now(timezone.utc).isoformat()},
    )
