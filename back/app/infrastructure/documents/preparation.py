import io, logging
from pathlib import Path
from pypdf import PdfReader, PdfWriter

from app.generation.models import GenerateRequest, InputDocument

logger = logging.getLogger(__name__)


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


def prepare_documents(
    workspace, request: GenerateRequest, owner_id: str
) -> list[InputDocument]:
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
        entries.append(
            (
                workspace.document(context.document_id, owner_id),
                context.pages,
                "context",
            )
        )
    result = []
    total_pages = 0
    for document, pages, role in entries:
        path = workspace.path(document.id, owner_id)
        if document.page_count is not None:
            pages = (
                pages if pages is not None else list(range(1, document.page_count + 1))
            )
            total_pages += len(pages)
            if total_pages > 100:
                raise ValueError(
                    "Select at most 100 PDF pages across all attached files."
                )
            data = selected_pdf(path, pages)
        else:
            if pages is not None:
                raise ValueError("Page ranges apply only to PDF files.")
            data = path.read_bytes()
        result.append(
            InputDocument(
                document, data, f"{role}-{document.id}{path.suffix}", role, pages
            )
        )
    if sum(len(entry.data) for entry in result) > 40 * 1024 * 1024:
        raise ValueError("Selected attachments exceed the 40 MB generation limit.")
    return result


class SelectedDocumentPreparation:
    def __init__(self, documents):
        self._documents = documents

    def prepare(self, request: GenerateRequest, owner_id: str) -> list[InputDocument]:
        return prepare_documents(self._documents, request, owner_id)
