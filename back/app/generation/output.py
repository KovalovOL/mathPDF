"""Provider-neutral compact generation schemas and canonical expansion."""

import re
from functools import lru_cache
from typing import Annotated, Literal
from pydantic import Field, model_validator
from app.study.contract import MAX_ITEMS, Skill, StrictModel, StudyItem


class InsufficientSource(StrictModel):
    status: Literal["insufficient_source"]
    reason: str = Field(min_length=1, max_length=1000)


Prose = Annotated[
    str,
    Field(
        min_length=1,
        max_length=8000,
        json_schema_extra={
            "pattern": "^[A-Za-z\\u00C0-\\u024F0-9 \\t\\r\\n.,;:!?'\\\"()/%’‘“”–—…-]*$"
        },
    ),
]


def normalize_model_tex(latex: str) -> str:
    """Undo uniform extra JSON escaping, preserving actual TeX rows.

    Only new provider output passes here. Mixed/singly escaped TeX is untouched;
    a consistently doubled expression has even backslash runs everywhere.
    """
    trailing = re.search("\\\\+$", latex)
    if trailing and len(trailing[0]) % 2:
        latex = latex[:-1]
    while True:
        runs = re.findall("\\\\+", latex)
        if not (
            runs
            and all((len(run) % 2 == 0 for run in runs))
            and re.search("\\\\\\\\(?:[A-Za-z]{2,}|[{}])", latex)
        ):
            return latex
        latex = re.sub("\\\\+", lambda match: "\\" * (len(match[0]) // 2), latex)
        trailing = re.search("\\\\+$", latex)
        if trailing and len(trailing[0]) % 2:
            latex = latex[:-1]


def normalize_model_prose(text: str) -> str:
    """Typeset only unambiguous standalone TeX lines, as the legacy UI does."""
    text = normalize_model_tex(text)
    lines = []
    for line in text.split("\n"):
        expression = line.strip()
        without_commands = re.sub("\\\\[A-Za-z]+", "", expression)
        if (
            not any((marker in expression for marker in ("$", "\\(", "\\[")))
            and re.search("\\\\[A-Za-z]+", expression)
            and re.match("^(?:[\\\\\\d+\\-({\\[]|[A-Za-z](?=[\\s_^=<>]))", expression)
            and (not re.search("\\b[A-Za-z]{3,}\\b", without_commands))
        ):
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

    def expand(
        self, document_id: str, index: int, mode: str = "flashcards"
    ) -> StudyItem:
        from_notes, explanation, answer_entries = self._back_entries()
        known = ([self.formula] if isinstance(self.formula, Formula) else []) + [
            entry
            for entry in self.question + answer_entries
            if isinstance(entry, Formula)
        ]
        blocks = lambda entries: self._blocks(entries, known, document_id)
        question, answer = (blocks(self.question), blocks(answer_entries))
        main = blocks([self.formula])[0] if isinstance(self.formula, Formula) else None
        if mode == "flashcards":
            answer = [block for block in question if block["kind"] == "math"] + answer
            question = [block for block in question if block["kind"] == "text"]
            if not question:
                question = [{"kind": "text", "text": "Recall the formula."}]
        self._ensure_main(question, answer, main, from_notes, mode)
        self._unique_math(question, answer)
        source = (
            None
            if main
            else {
                "document_id": document_id,
                "page": self.formula.page,
                "line_start": None,
                "line_end": None,
                "quote": None,
            }
        )
        return StudyItem(
            goal_step=index,
            title=self.title,
            skill=self.skill,
            question=question,
            from_notes=blocks(from_notes) if from_notes is not None else None,
            explanation=blocks(explanation) if explanation is not None else None,
            answer=answer,
            source=source,
        )

    def _blocks(self, entries, known, document_id):
        output = []
        for entry in entries:
            if isinstance(entry, Paragraph):
                text = "".join(
                    (
                        (
                            part
                            if isinstance(part, str)
                            else "\\(" + normalize_model_tex(part.math) + "\\)"
                        )
                        for part in entry.parts
                    )
                )
                output.append({"kind": "text", "text": text})
                continue
            if isinstance(entry, str):
                text = normalize_model_tex(entry)
                matching = next(
                    (
                        formula
                        for formula in known
                        if text.strip() == formula.latex.strip()
                    ),
                    None,
                )
                if matching is None:
                    output.append({"kind": "text", "text": normalize_model_prose(text)})
                    continue
                entry = matching
            output.append(self._math_block(entry, document_id))
        return output

    def _math_block(self, entry, document_id):
        return {
            "kind": "math",
            "latex": entry.latex,
            "display": True,
            "source": {
                "document_id": document_id,
                "page": entry.page,
                "line_start": None,
                "line_end": None,
                "quote": None,
            },
            "original_latex": entry.variant.original if entry.variant else None,
            "change": entry.variant.change if entry.variant else None,
        }

    def _unique_math(self, question, answer):
        for side in (question, answer):
            seen = set()
            unique = []
            for block in side:
                if block["kind"] == "math":
                    key = (
                        block["latex"].strip(),
                        block["source"]["page"],
                        block["original_latex"],
                        block["change"],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                unique.append(block)
            side[:] = unique

    def _ensure_main(self, question, answer, main, from_notes, mode):
        existing = answer if mode == "flashcards" else question + answer
        if main and (
            not any(
                (
                    block["kind"] == "math"
                    and block["latex"] == main["latex"]
                    and (block["source"]["page"] == main["source"]["page"])
                    and (block["original_latex"] == main["original_latex"])
                    and (block["change"] == main["change"])
                    for block in existing
                )
            )
        ):
            answer.insert(1 if from_notes is not None else 0, main)

    def _back_entries(self):
        from_notes = getattr(self, "from_notes", None)
        explanation = getattr(self, "explanation", None)
        answer_entries = []
        if from_notes is not None:
            answer_entries.extend([Paragraph(parts=["From notes"]), *from_notes])
        if explanation:
            answer_entries.extend([Paragraph(parts=["Explanation"]), *explanation])
        answer_entries.extend(self.answer)
        return (from_notes, explanation, answer_entries)


class FlashcardOutput(CompactItem):
    question: list[Prose] = Field(min_length=1, max_length=1)
    answer: list[Formula | Paragraph] = Field(default_factory=list, max_length=40)
    from_notes: list[Formula | Paragraph] | None = Field(default=None, max_length=20)
    explanation: list[Formula | Paragraph] | None = Field(default=None, max_length=16)


class ProblemOutput(CompactItem):
    answer: list[Formula | Paragraph] = Field(min_length=1, max_length=40)


class FlashcardRead(FlashcardOutput):
    question: list[Prose | Formula | Paragraph] = Field(min_length=1, max_length=40)
    answer: list[Prose | Formula | Paragraph] = Field(
        default_factory=list, max_length=40
    )
    from_notes: list[Prose | Formula | Paragraph] | None = Field(
        default=None, max_length=20
    )
    explanation: list[Prose | Formula | Paragraph] | None = Field(
        default=None, max_length=16
    )


@lru_cache(maxsize=MAX_ITEMS * 3)
def set_response_format(
    count: int, mode: str | None = None, *, permissive: bool = False
) -> type[StrictModel]:
    if not 1 <= count <= MAX_ITEMS:
        raise ValueError("Invalid requested item count.")
    item_type = (
        (FlashcardRead if permissive else FlashcardOutput)
        if mode == "flashcards"
        else ProblemOutput if mode == "problems" and (not permissive) else CompactItem
    )

    class CompletedSet(StrictModel):
        status: Literal["completed"]
        items: list[item_type] = Field(min_length=count, max_length=count)

    class SetResponse(StrictModel):
        result: CompletedSet | InsufficientSource

    return SetResponse
