"""Print structured study content with the same local math renderer as the UI."""

import json
import mimetypes
import os
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.async_api import Error as BrowserError, async_playwright


class ExportError(Exception):
    pass


STATIC = Path(__file__).parent / "static"


def chromium_executable() -> str | None:
    configured = os.getenv("MATHPDF_CHROMIUM_EXECUTABLE")
    if configured:
        if not Path(configured).is_file():
            raise ExportError("The configured PDF browser executable could not be found.")
        return configured
    for candidate in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")]:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


async def export_pdf(result: dict) -> bytes:
    data = json.dumps(result, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = (STATIC / "print.html").read_text().replace("__STUDY_DATA__", data)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                context = await browser.new_context(viewport={"width": 1000, "height": 900})

                async def local_asset(route):
                    url = urlparse(route.request.url)
                    if url.netloc != "mathpdf.local":
                        await route.abort()
                    elif url.path == "/print":
                        await route.fulfill(status=200, content_type="text/html", body=html)
                    elif url.path.startswith("/static/"):
                        path = (STATIC / unquote(url.path[len("/static/"):])).resolve()
                        if path.is_relative_to(STATIC.resolve()) and path.is_file():
                            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                            await route.fulfill(status=200, content_type=mime, body=path.read_bytes())
                        else:
                            await route.abort()
                    else:
                        await route.abort()

                await context.route("**/*", local_asset)
                page = await context.new_page()
                await page.emulate_media(media="print")
                await page.goto("http://mathpdf.local/print", wait_until="load", timeout=30000)
                await page.wait_for_function("document.documentElement.dataset.exportStatus !== 'pending'", timeout=30000)
                if await page.locator("html").get_attribute("data-export-status") != "ready":
                    detail = await page.locator("#export-error").inner_text()
                    raise ExportError(detail or "The study formulas could not be formatted for PDF export.")
                return await page.pdf(format="A4", print_background=True, prefer_css_page_size=True,
                                      display_header_footer=False)
            finally:
                await browser.close()
    except BrowserError:
        raise ExportError("PDF export could not start Chromium. Install it with 'uv run playwright install chromium' or set MATHPDF_CHROMIUM_EXECUTABLE.") from None
