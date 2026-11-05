"""Isolated parent bridge: dirty context, cancellation, original and failed save."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_generation_choices_preserve_notes_and_wait_for_a_successful_save():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (
        Path(__file__).parent / "fixtures/browser/annotation_choices-1.html"
    ).read_text()
    asyncio.run(
        _generation_choices_preserve_notes_and_wait_for_a_successful_save(static, html)
    )


async def _generation_choices_preserve_notes_and_wait_for_a_successful_save(
    static, html
):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page()

            async def local(route):
                name = route.request.url.split("?", 1)[0].rsplit("/", 1)[-1]
                await route.fulfill(
                    content_type=(
                        "text/javascript" if name.endswith(".js") else "text/html"
                    ),
                    body=(static / name).read_text() if name.endswith(".js") else html,
                )

            await page.route("**/*", local)
            await page.goto("http://localhost/")
            await page.wait_for_function("window.ready")
            await page.evaluate(
                "()=>{const range=document.createRange();range.selectNodeContents(document.querySelector('#selection'));getSelection().addRange(range);}"
            )
            await page.get_by_role("button", name="Red", exact=True).click()
            await page.wait_for_function(
                "document.querySelector('[aria-label=Red]').getAttribute('aria-pressed')==='true'"
            )
            assert (
                await page.evaluate("getSelection().toString()") == "Selected PDF text"
            )
            await _assert_original_pdf_choice_preserves_unsaved_notes(page)
            await _assert_generation_waits_for_successful_annotation_save(page)
        finally:
            await browser.close()


async def _assert_generation_waits_for_successful_annotation_save(page):
    await page.evaluate("window.prepare()")
    await page.get_by_role(
        "button", name="Save and use edited copy", exact=True
    ).click()
    await page.wait_for_function("window.commands.length===1")
    assert await page.evaluate("window.result===undefined")
    await page.evaluate("window.finishSave('Simulated save conflict')")
    await page.wait_for_function("window.failure")
    assert await page.evaluate("window.failure") == "Simulated save conflict"
    assert await page.evaluate("window.result===undefined && window.hasNotes()")
    await page.evaluate("window.prepare()")
    await page.get_by_role(
        "button", name="Save and use edited copy", exact=True
    ).click()
    await page.wait_for_function("window.commands.length===2")
    await page.evaluate("window.finishSave()")
    await page.wait_for_function("window.result")
    assert await page.evaluate("window.result.context[0].document_id") == "context-copy"


async def _assert_original_pdf_choice_preserves_unsaved_notes(page):
    await page.evaluate("window.prepare()")
    assert (
        "Context - annotated.pdf"
        in await page.locator("#annotation-choice-message").inner_text()
    )
    await page.get_by_role("button", name="Cancel", exact=True).click()
    await page.wait_for_function("window.result===null")
    assert await page.evaluate("window.hasNotes()")
    await page.evaluate("window.prepare()")
    await page.get_by_role("button", name="Use original PDF", exact=True).click()
    await page.wait_for_function("window.result")
    assert (
        await page.evaluate("window.result.context[0].document_id")
        == "context-original"
    )
    assert await page.evaluate("window.hasNotes()")
