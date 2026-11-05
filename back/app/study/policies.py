import hashlib, json, logging, re
from app.study.contract import MathBlock, StudyItem, TextBlock
from app.generation.models import (
    ContentValidationError,
    GeneratedContent,
    GenerationError,
)

logger = logging.getLogger(__name__)
INLINE_MATH = re.compile(
    r"\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$"
)


def validate_item(item: StudyItem, mode: str, document_id: str, pages: list[int]):
    maths = [
        block for block in item.question + item.answer if isinstance(block, MathBlock)
    ]
    if not maths and item.source is None:
        raise ContentValidationError(
            "missing_formula",
            "A study item is missing its source formula or page reference.",
        )
    sources = [block.source for block in maths] + ([item.source] if item.source else [])
    for source in sources:
        if source.document_id is None:
            source.document_id = document_id
        if source.page not in pages or source.document_id != document_id:
            raise ContentValidationError(
                "invalid_source",
                "A study item references pages outside the selected source.",
            )


def item_expressions(item: StudyItem) -> list[tuple[str, bool]]:
    expressions = []
    for block in item.question + item.answer:
        if isinstance(block, MathBlock):
            expressions.extend(
                (text, block.display)
                for text in [block.latex, block.original_latex]
                if text is not None
            )
        else:
            for match in INLINE_MATH.finditer(block.text):
                expressions.append(
                    (
                        next(part for part in match.groups() if part is not None),
                        match[2] is not None or match[3] is not None,
                    )
                )
    return expressions


def validate_study(
    content: GeneratedContent, mode: str, document_id: str, pages: list[int]
):
    for item in content.items:
        validate_item(item, mode, document_id, pages)
    if not content.items and not any(note.strip() for note in content.notes):
        raise GenerationError("The provider returned no study material or explanation.")


def question_fingerprint(item: StudyItem) -> str:
    # Ignore titles/citations and superficial spacing when rejecting exact repeats.
    blocks = [
        (
            (block.kind, " ".join(block.text.casefold().split()))
            if isinstance(block, TextBlock)
            else (block.kind, re.sub(r"\s+", "", block.latex))
        )
        for block in item.question
    ]
    return hashlib.sha256(json.dumps(blocks, ensure_ascii=False).encode()).hexdigest()
