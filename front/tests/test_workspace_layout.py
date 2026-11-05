"""Isolated layout component checks; no account or application UI is loaded."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_source_collapse_and_mobile_pull_preserve_the_viewer():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (
        Path(__file__).parent / "fixtures/browser/workspace_layout-1.html"
    ).read_text()
    asyncio.run(_source_collapse_and_mobile_pull_preserve_the_viewer(static, html))


async def _source_collapse_and_mobile_pull_preserve_the_viewer(static, html):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(
                viewport={"width": 390, "height": 844}, has_touch=True
            )

            async def local(route):
                name = route.request.url.split("?", 1)[0].rsplit("/", 1)[-1]
                if name in {"workspace-layout.js", "style.css"}:
                    await route.fulfill(
                        content_type=(
                            "text/javascript" if name.endswith(".js") else "text/css"
                        ),
                        body=(static / name).read_text(),
                    )
                else:
                    await route.fulfill(content_type="text/html", body=html)

            await page.route("**/*", local)
            await page.goto("http://layout.local/")
            await page.wait_for_function("window.ready")
            await _assert_mobile_pull_and_scroll_preserve_viewer(page)
            await page.set_viewport_size({"width": 1280, "height": 720})
            await page.locator("#splitter").press("Home")
            assert (
                await page.locator("#document-pane").get_attribute("aria-hidden")
                == "true"
            )
            await page.locator("#show-source").click()
            assert (
                await page.locator("#document-pane").get_attribute("aria-hidden")
                == "false"
            )
            assert await page.evaluate(
                "document.querySelector('iframe')===window.initialFrame"
            )
        finally:
            await browser.close()


async def _assert_mobile_pull_and_scroll_preserve_viewer(page):
    await page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
    await page.wait_for_function(
        "document.querySelector('#workspace').classList.contains('source-collapsed')"
    )

    async def pull(target="#answer", horizontal=0):
        return await page.evaluate(
            (
                Path(__file__).parent / "fixtures/browser/workspace_layout-1.js"
            ).read_text(),
            {"target": target, "horizontal": horizontal},
        )

    assert await pull(horizontal=70)
    assert await pull("#show-source")
    await page.evaluate("document.querySelector('.practice-content').scrollTop=100")
    assert await pull()
    await page.evaluate("document.querySelector('.practice-content').scrollTop=0")
    assert not await pull()
    assert await page.evaluate("document.querySelector('iframe')===window.initialFrame")
    await page.locator("#hide-source").click()
    await page.locator("#show-source").click()
    assert await page.locator("#document-pane").get_attribute("aria-hidden") == "false"
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
