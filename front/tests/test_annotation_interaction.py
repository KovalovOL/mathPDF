"""Isolated annotation component: history, selection, pointer gestures and shortcuts."""

import asyncio
import io
import mimetypes
from pathlib import Path
import pytest
from playwright.async_api import async_playwright
from pypdf import PdfWriter
from pypdf.generic import RectangleObject
from browser_support import chromium_executable


def test_editable_marks_and_keyboard_history_in_an_isolated_runtime():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (
        Path(__file__).parent / "fixtures/browser/annotation_interaction-1.html"
    ).read_text()
    asyncio.run(
        _editable_marks_and_keyboard_history_in_an_isolated_runtime(static, html)
    )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_real_pdf_viewport_keeps_marks_aligned_after_resize(rotation):
    static = Path(__file__).resolve().parents[1] / "dist"
    writer = PdfWriter()
    sheet = writer.add_blank_page(width=600, height=800)
    sheet.cropbox = RectangleObject([100, 100, 500, 700])
    sheet.rotate(rotation)
    binary = io.BytesIO()
    writer.write(binary)
    html = (
        Path(__file__).parent / "fixtures/browser/annotation_interaction-2.html"
    ).read_text()
    asyncio.run(
        _real_pdf_viewport_keeps_marks_aligned_after_resize(static, html, binary)
    )


async def _editable_marks_and_keyboard_history_in_an_isolated_runtime(static, html):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 800, "height": 900})

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
            await _draw_highlight_and_save_annotations(page)
            await _assert_annotation_undo_redo_and_eraser(page)
            await _assert_annotation_save_failure_and_retry(page)
        finally:
            await browser.close()


async def _real_pdf_viewport_keeps_marks_aligned_after_resize(static, html, binary):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 700, "height": 850})
            local = _make_pdf_viewport_route(static, binary, html)
            await page.route("**/*", local)
            await page.goto("http://localhost/?document=original")
            await page.locator(".annotation-layer").wait_for()
            await page.evaluate(
                "postMessage({type:'annotation-command',documentId:'original',action:'tool',tool:'pen'},location.origin)"
            )
            await page.wait_for_function(
                "document.querySelector('.annotation-layer').classList.contains('drawing')"
            )
            start = await page.evaluate(
                "(()=>{const p=new DOMPoint(200,300).matrixTransform(document.querySelector('.annotation-layer g').getScreenCTM());return {x:p.x,y:p.y};})()"
            )
            await page.mouse.click(start["x"], start["y"])
            await page.keyboard.press("Control+s")
            await page.wait_for_function("window.saved.length===1")
            point = await page.evaluate("window.saved[0].items[0].points[0]")
            assert point == pytest.approx([200, 300], abs=0.01)
            await page.set_viewport_size({"width": 480, "height": 850})
            await page.wait_for_function(
                'Math.abs(document.querySelector(".pdf-sheet").getBoundingClientRect().width-456)<1'
            )
            actual = await page.locator(".annotation-layer circle").evaluate(
                (
                    Path(__file__).parent
                    / "fixtures/browser/annotation_interaction-2.js"
                ).read_text()
            )
            assert actual < 0.01
        finally:
            await browser.close()


async def _assert_annotation_save_failure_and_retry(page):
    await page.evaluate("window.command({action:'tool',tool:'pen'})")
    await page.mouse.click(300, 300)
    await page.evaluate("window.failSave=true")
    error = await page.evaluate(
        "window.command({action:'save'}).catch(error=>error.message)"
    )
    assert error == "Simulated save failure"
    await page.wait_for_function(
        "window.states.at(-1).dirty && !window.states.at(-1).saving"
    )
    assert await page.locator(".annotation-layer circle").count() == 1
    assert await page.evaluate("window.saved.length") == 1
    await page.evaluate("window.failSave=false;window.command({action:'save'})")
    await page.wait_for_function(
        "window.saved.length===2 && !window.states.at(-1).dirty"
    )
    assert await page.evaluate("window.saved[1].request.expected_revision") == 1


async def _assert_annotation_undo_redo_and_eraser(page):
    await page.keyboard.press("Meta+z")
    await page.wait_for_function("window.states.at(-1).dirty")
    assert await page.locator(".annotation-layer polygon").count() == 0
    await page.keyboard.press("Control+Shift+z")
    await page.wait_for_function("!window.states.at(-1).dirty")
    await page.evaluate("window.command({action:'tool',tool:'eraser'})")
    await page.mouse.click(200, 225)
    assert await page.locator(".annotation-layer polyline").count() == 0
    await page.keyboard.press("Control+z")
    assert await page.locator(".annotation-layer polyline").count() == 1
    await page.evaluate("window.command({action:'toggle'})")
    assert not await page.locator(".annotation-layer").evaluate(
        "node=>node.classList.contains('drawing')"
    )


async def _draw_highlight_and_save_annotations(page):
    await page.evaluate("window.command({action:'tool',tool:'pen'})")
    await page.mouse.move(150, 200)
    await page.mouse.down()
    await page.mouse.move(250, 250, steps=10)
    await page.mouse.up()
    assert await page.locator(".annotation-layer polyline").count() == 1
    await page.evaluate("window.command({action:'tool',tool:'select'})")
    await page.evaluate(
        (
            Path(__file__).parent / "fixtures/browser/annotation_interaction-1.js"
        ).read_text()
    )
    await page.evaluate("window.command({action:'tool',tool:'highlight'})")
    assert await page.locator(".annotation-layer polygon").count() >= 1
    await page.keyboard.press("Control+s")
    await page.wait_for_function(
        "window.saved.length===1 && window.states.at(-1).documentId==='copy' && !window.states.at(-1).saving && !window.states.at(-1).dirty"
    )
    result = await page.evaluate(
        "({items:window.saved[0].request.items,dirty:window.states.at(-1).dirty,error:window.error})"
    )
    assert [item["kind"] for item in result["items"]] == ["ink", "highlight"]
    assert result["items"][0]["points"][0] == [150, 600]
    assert result["dirty"] is False and result["error"] is None


def _make_pdf_viewport_route(static, binary, html):

    async def local(route):
        path = route.request.url.split("localhost", 1)[1].split("?", 1)[0]
        if path.startswith("/static/"):
            file = (static / path.removeprefix("/static/")).resolve()
            assert file.is_relative_to(static.resolve())
            await route.fulfill(
                content_type=mimetypes.guess_type(file)[0]
                or "application/octet-stream",
                body=file.read_bytes(),
            )
        elif path == "/api/documents/original/file":
            await route.fulfill(content_type="application/pdf", body=binary.getvalue())
        else:
            await route.fulfill(content_type="text/html", body=html)

    return local
