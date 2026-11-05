import json
from pathlib import Path

"Exercise the bundled renderer, including its real Chromium document mode."
import asyncio
import pytest
from app.infrastructure.export.math_diagnostic import MathValidationError, MathValidator
from app.generation.models import GenerateRequest, InputDocument
from support import collect_study
from app.documents.models import Document


def test_real_renderer_accepts_valid_math_and_rejects_bad_tex():

    async def check():
        async with MathValidator() as validator:
            assert await validator.page.evaluate("document.compatMode") == "CSS1Compat"
            valid = [
                ("x+1", True),
                ("\\frac{1}{2}", False),
                ("\\sum_{k=1}^{n} k = \\frac{n(n+1)}{2}", True),
                ("\\begin{aligned}a&=b+c\\\\d&=e-f\\end{aligned}", True),
            ]
            assert await validator.errors(valid) == []
            assert all((validator.cache[expression] is None for expression in valid))
            assert await validator.errors(valid) == []
            errors = await validator.errors([("\\unknownCommand{x}", True)])
            assert len(errors) == 1
            assert "Undefined control sequence" in errors[0]
            assert await validator.errors(valid) == []

    asyncio.run(check())


def test_generation_does_not_launch_a_validation_browser(monkeypatch):
    from app.study.contract import GeneratedContent, StudyItem
    from app.generation.models import ProviderResult

    async def forbidden_start(self):
        pytest.fail("Generation must not start a server validation browser")

    monkeypatch.setattr(MathValidator, "_start", forbidden_start)
    document = Document(
        id="a" * 32,
        filename="notes.pdf",
        sha256="b" * 64,
        media_type="application/pdf",
        page_count=1,
        size=10,
    )
    source = InputDocument(
        document=document, data=b"", filename="notes.pdf", role="primary", pages=[1]
    )

    class Provider:

        async def generate(self, *args, **kwargs):
            entry = StudyItem.model_validate(
                json.loads(
                    (
                        Path(__file__).parent
                        / "fixtures/scenarios/math_validation-61.json"
                    ).read_text()
                )
            )
            return ProviderResult(
                content=GeneratedContent(items=[entry], notes=[]),
                provider="fixture",
                model="fixture",
            )

    content, metadata = asyncio.run(
        collect_study(
            [source],
            GenerateRequest(mode="flashcards", count=1),
            Provider(),
            lambda _: None,
        )
    )
    assert len(content.items) == 1
    assert metadata["math_check"] == "on_display"


def test_screenshot_legacy_fragments_render_without_changing_notation():
    cases = json.loads(
        (
            Path(__file__).parent / "fixtures/scenarios/math_validation-100.json"
        ).read_text()
    )

    async def check():
        async with MathValidator() as validator:
            for text, expected in cases:
                result = await validator.page.evaluate(
                    (
                        Path(__file__).parent / "fixtures/browser/math_validation-2.js"
                    ).read_text(),
                    text,
                )
                assert result["latex"] == expected, (text, result)
                assert result["errors"] == 0
                if not expected:
                    assert result["plain"] == text

    asyncio.run(check())


def test_unwrapped_source_rows_gain_layout_without_changing_nested_math():
    cases = [
        (
            "\\text{(P)}\\quad1\\Rightarrow p\\\\\\text{(F)}\\quad0\\vee\\bar p",
            "\\begin{aligned}&\\text{(P)}\\quad1\\Rightarrow p\\\\&\\text{(F)}\\quad0\\vee\\bar p\\end{aligned}",
        ),
        (
            "\\sum_{\\substack{i=1\\\\j=2}}^n a_i",
            "\\sum_{\\substack{i=1\\\\j=2}}^n a_i",
        ),
        (
            "\\begin{aligned}a&=b\\\\c&=d\\end{aligned}",
            "\\begin{aligned}a&=b\\\\c&=d\\end{aligned}",
        ),
    ]

    async def check():
        async with MathValidator() as validator:
            for latex, expected in cases:
                result = await validator.page.evaluate(
                    (
                        Path(__file__).parent / "fixtures/browser/math_validation-3.js"
                    ).read_text(),
                    latex,
                )
                assert result == {"ok": True, "latex": expected}

    asyncio.run(check())


def test_only_terminal_text_label_brace_is_completed():

    async def check():
        async with MathValidator() as validator:
            result = await validator.page.evaluate(
                (
                    Path(__file__).parent / "fixtures/browser/math_validation-1.js"
                ).read_text()
            )
            assert result == {
                "good": True,
                "source": "x+\\text{a label}",
                "bad": False,
                "raw": "\\overline{x",
            }

    asyncio.run(check())


def test_literal_ampersands_are_not_alignment_tabs():
    cases = json.loads(
        (
            Path(__file__).parent / "fixtures/scenarios/literal-ampersand-cases.json"
        ).read_text()
    )

    async def check():
        async with MathValidator() as validator:
            for latex, expected in cases:
                result = await validator.page.evaluate(
                    (
                        Path(__file__).parent / "fixtures/browser/math_validation-4.js"
                    ).read_text(),
                    latex,
                )
                assert result == {
                    "ok": True,
                    "latex": expected,
                    "idempotent": True,
                    "ampersands": expected.replace("\\\\", "").count("\\&"),
                }, (latex, result)
                assert expected.count("\\bar") == latex.count("\\bar")

    asyncio.run(check())


def test_shared_flashcard_projection_removes_text_math_without_mutating_content():
    from app.study.contract import StudyItem

    cases = [
        "Which expression denotes membership? \\(x \\in A\\)",
        "Which expression denotes membership? $x \\in A$",
        "Recall this expression: \\[x^2\\]",
        "Recall this expression: $$x^2$$",
        "Which relation is printed? t&t \\Leftrightarrow 0",
        "Which relation is printed? \\begin{aligned}t\\&t&\\Leftrightarrow t\\end{aligned}",
        "Which expression is printed? \\(\\unknownCommand{x}\\)",
        "Which expression is printed? \\unknownCommand{x}",
        "\\(x \\in A\\)",
        "What conditions define equality?",
    ]
    asyncio.run(_check_shared_flashcard_projection(cases, StudyItem))


async def _check_shared_flashcard_projection(cases, StudyItem):
    async with MathValidator() as validator:
        for text in cases:
            item = StudyItem.model_validate(
                {
                    "title": "Answer title",
                    "question": [{"kind": "text", "text": text}],
                    "answer": json.loads(
                        (
                            Path(__file__).parent
                            / "fixtures/scenarios/math_validation-293.json"
                        ).read_text()
                    ),
                }
            ).model_dump(mode="json")
            result = await validator.page.evaluate(
                (
                    Path(__file__).parent / "fixtures/browser/math_validation-5.js"
                ).read_text(),
                item,
            )
            assert result["unchanged"] and result["idempotent"], (text, result)
            assert result["frontMath"] == 0, (text, result)
            assert "\\" not in result["frontText"] and "$" not in result["frontText"]
            assert result["backMath"] >= 1
            assert result["answerBlocks"][-1] == item["answer"][0]
            if text == cases[0]:
                assert len(result["answerBlocks"]) == 1
            if text == cases[-2]:
                assert result["frontText"] == "Recall the formula."
            if text == cases[-1]:
                assert result["frontText"] == text
