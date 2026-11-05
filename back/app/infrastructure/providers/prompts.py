import hashlib, json
from pathlib import Path
from string import Template

from app.generation.models import GenerateRequest, InputDocument

PROMPTS = Path(__file__).resolve().parents[2] / "generation" / "prompts"


class PromptLoader:
    def __init__(self, directory: Path = PROMPTS):
        self._directory = directory

    def load(
        self, request: GenerateRequest, documents: list[InputDocument]
    ) -> tuple[str, str, dict[str, str]]:
        names = [
            "study-system.md",
            f"{request.mode}.md",
            "formula-guide.md",
            "math-patterns.md",
            "context.md",
            "attachment-label.md",
            "comment.md",
            "difficulty.md",
        ]
        resources = {
            name: (self._directory / name).read_text(encoding="utf-8") for name in names
        }
        source = documents[0]
        mapping = ", ".join(
            (f"{index + 1} -> {page}" for index, page in enumerate(source.pages))
        )
        task = Template(resources[f"{request.mode}.md"]).substitute(
            count=request.count, page_mapping=mapping
        )
        task += "\n\n" + Template(resources["difficulty.md"]).substitute(
            difficulty=request.difficulty
        )
        metadata = self._attachment_metadata(documents, resources)
        task += "\n\n" + Template(resources["context.md"]).substitute(
            attachments=json.dumps(metadata, ensure_ascii=False)
        )
        if request.comment.strip():
            task += "\n\n" + Template(resources["comment.md"]).substitute(
                comment=json.dumps(request.comment.strip(), ensure_ascii=False)
            )
        hashes = {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in resources.items()
        }
        system = "\n\n".join(
            (
                resources[name]
                for name in ("study-system.md", "formula-guide.md", "math-patterns.md")
            )
        )
        return (system, task, hashes)

    def _attachment_metadata(self, documents, resources):
        metadata = []
        for entry in documents:
            info = {
                "document_id": entry.document.id,
                "filename": entry.filename,
                "original_filename": entry.document.filename,
                "role": entry.role,
                "original_pages": entry.pages,
            }
            metadata.append(info)
            entry.label = Template(resources["attachment-label.md"]).substitute(
                metadata=json.dumps(info, ensure_ascii=False)
            )
        return metadata
