"""Isolated source-viewer runtime with a delayed PDF and corrupted derived image."""

import asyncio
import io
import mimetypes
from pathlib import Path
from playwright.async_api import async_playwright
from pypdf import PdfWriter
from browser_support import chromium_executable


def test_initial_pdf_queue_starts_and_replaces_an_invalid_cached_page():
    static = Path(__file__).resolve().parents[1] / "dist"
    writer, data = (PdfWriter(), io.BytesIO())
    writer.add_blank_page(width=600, height=800)
    writer.write(data)
    html = (
        Path(__file__).parent / "fixtures/browser/pdf_viewer_cache-1.html"
    ).read_text()
    asyncio.run(
        _initial_pdf_queue_starts_and_replaces_an_invalid_cached_page(
            static, data, html
        )
    )


async def _initial_pdf_queue_starts_and_replaces_an_invalid_cached_page(
    static, data, html
):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 700, "height": 850})

            async def local(route):
                path = route.request.url.split("viewer.local", 1)[1].split("?", 1)[0]
                if path.startswith("/static/"):
                    file = (static / path.removeprefix("/static/")).resolve()
                    assert file.is_relative_to(static.resolve())
                    await route.fulfill(
                        content_type=mimetypes.guess_type(file)[0]
                        or "application/octet-stream",
                        body=file.read_bytes(),
                    )
                elif path == "/api/documents/viewer-file/file":
                    await asyncio.sleep(0.3)
                    await route.fulfill(
                        content_type="application/pdf", body=data.getvalue()
                    )
                else:
                    await route.fulfill(content_type="text/html", body=html)

            await page.route("**/*", local)
            await page.goto("http://viewer.local/?document=viewer-file")
            await page.locator("#pages canvas[role=img]").wait_for(timeout=10000)
            assert await page.locator("#pages img").count() == 0
            assert await page.locator("#status").is_hidden()
            await page.wait_for_function(
                (
                    Path(__file__).parent
                    / "fixtures/browser/pdf_viewer_cache-source-1.js"
                ).read_text()
            )
        finally:
            await browser.close()
