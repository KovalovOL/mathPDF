"""Exercise the IndexedDB module in an isolated browser runtime, without app UI."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_visual_cache_is_private_bounded_content_keyed_and_invalidated():
    source = (Path(__file__).parents[1] / "dist/visual-cache.js").read_text()
    asyncio.run(_visual_cache_is_private_bounded_content_keyed_and_invalidated(source))


def test_image_bytes_legacy_blob_migration_and_decode_recovery():
    static = Path(__file__).resolve().parents[1] / "dist"
    source = (static / "visual-cache.js").read_text()
    asyncio.run(_image_bytes_legacy_blob_migration_and_decode_recovery(static, source))


async def _visual_cache_is_private_bounded_content_keyed_and_invalidated(source):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page()

            async def local(route):
                if route.request.url.endswith("/cache.js"):
                    await route.fulfill(content_type="text/javascript", body=source)
                else:
                    await route.fulfill(
                        content_type="text/html",
                        body="<!doctype html><title>Storage unit test</title>",
                    )

            await page.route("**/*", local)
            await page.goto("http://cache.local/")
            result = await page.evaluate(
                (
                    Path(__file__).parent / "fixtures/browser/visual_cache-source-1.js"
                ).read_text()
            )
            assert result == {
                "count": 10,
                "recent": True,
                "oldest": False,
                "other": None,
                "changed": None,
                "preview": "Cached excerpt",
                "deleted": None,
                "signedOut": None,
            }
            await page.close()
            unavailable = await browser.new_page()
            await unavailable.route("**/*", local)
            await unavailable.goto("http://cache.local/")
            result = await unavailable.evaluate(
                (
                    Path(__file__).parent / "fixtures/browser/visual_cache-source-2.js"
                ).read_text()
            )
            assert result == {"entry": None, "pages": []}
        finally:
            await browser.close()


async def _image_bytes_legacy_blob_migration_and_decode_recovery(static, source):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page()

            async def local(route):
                await route.fulfill(
                    content_type=(
                        "text/javascript"
                        if route.request.url.endswith(".js")
                        else "text/html"
                    ),
                    body=(
                        (static / "file-previews.js").read_text()
                        if route.request.url.endswith("file-previews.js")
                        else (
                            source
                            if route.request.url.endswith(".js")
                            else "<title>Cache recovery component</title>"
                        )
                    ),
                )

            await page.route("**/*", local)
            await page.goto("http://cache.local/")
            result = await page.evaluate(
                (
                    Path(__file__).parent / "fixtures/browser/visual_cache-source-3.js"
                ).read_text()
            )
            assert result == {
                "byteStorage": True,
                "legacyReadable": True,
                "unreadable": None,
                "badRemoved": True,
                "invalidImage": None,
                "decodeRemoved": True,
                "replacementReadable": True,
                "fallbackWorks": True,
            }
        finally:
            await browser.close()
