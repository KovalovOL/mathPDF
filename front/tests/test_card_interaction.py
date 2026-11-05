"""Touch gestures and compact card layout use isolated synthetic content."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_workspace_entrypoint_parses_as_the_classic_script_served_by_index():
    """The workspace deliberately uses dynamic imports from its classic entrypoint."""
    static = Path(__file__).resolve().parents[1] / "dist"
    assert '<script src="/static/app.js?v=' in (static / "index.html").read_text()
    asyncio.run(
        _workspace_entrypoint_parses_as_the_classic_script_served_by_index(static)
    )


def test_touch_card_does_not_select_text_or_flip_during_scroll_and_fits_width():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (
        (Path(__file__).parent / "fixtures/browser/card_interaction-1.html")
        .read_text()
        .replace("LONGWORD", "variable" * 100)
    )
    asyncio.run(
        _touch_card_does_not_select_text_or_flip_during_scroll_and_fits_width(
            static, html
        )
    )


async def _workspace_entrypoint_parses_as_the_classic_script_served_by_index(static):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page()
            await page.evaluate(
                "(source)=>{new Function(source);}", (static / "app.js").read_text()
            )
        finally:
            await browser.close()


async def _touch_card_does_not_select_text_or_flip_during_scroll_and_fits_width(
    static, html
):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(
                viewport={"width": 320, "height": 740}, has_touch=True
            )

            async def local(route):
                name = route.request.url.split("?", 1)[0].rsplit("/", 1)[-1]
                await route.fulfill(
                    body=(
                        (static / name).read_text()
                        if name in ["style.css", "card-interaction.js"]
                        else html
                    ),
                    content_type=(
                        "text/css"
                        if name == "style.css"
                        else "text/javascript" if name.endswith(".js") else "text/html"
                    ),
                )

            await page.route("**/*", local)
            await page.goto("http://cards.local/")
            await page.wait_for_function("window.ready")
            assert (
                await page.locator("#text").evaluate(
                    "(e)=>getComputedStyle(e).userSelect"
                )
                == "none"
            )
            await page.locator("#text").tap()
            assert await page.evaluate("window.flips") == 1
            assert await page.evaluate("getSelection().toString()") == ""
            await _assert_scroll_gesture_keyboard_and_card_width(page)
        finally:
            await browser.close()


async def _assert_scroll_gesture_keyboard_and_card_width(page):
    await page.locator(".flashcard").dispatch_event(
        "pointerdown",
        {"pointerType": "touch", "isPrimary": True, "clientX": 50, "clientY": 50},
    )
    await page.locator(".flashcard").dispatch_event(
        "pointermove", {"pointerType": "touch", "clientX": 50, "clientY": 95}
    )
    await page.locator(".flashcard").dispatch_event("click")
    assert await page.evaluate("window.flips") == 1
    await page.get_by_role("link", name="Source page 1").tap()
    assert await page.evaluate("window.flips") == 1
    await page.locator(".flashcard").focus()
    await page.keyboard.press("Space")
    assert await page.evaluate("window.flips") == 2
    await page.keyboard.press("ArrowRight")
    assert await page.evaluate("window.moves") == 1
    assert await page.get_by_role("button", name="Flip card", exact=True).count() == 0
    assert await page.get_by_role("progressbar").count() == 0
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    rect = await page.locator(".deck-footer").bounding_box()
    assert rect["x"] >= 0 and rect["x"] + rect["width"] <= 320
    assert rect["y"] + rect["height"] <= 740
