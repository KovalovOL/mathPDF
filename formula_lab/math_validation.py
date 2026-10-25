"""Validate generated TeX with the exact renderer and options used by the UI."""

from asyncio import timeout, wait_for
import logging

from playwright.async_api import Error as BrowserError, async_playwright

from .pdf_export import STATIC, ExportError, chromium_executable


logger = logging.getLogger(__name__)


class MathValidationError(Exception):
    """A safe operational failure; never includes model text or browser details."""


class MathValidator:
    """One network-isolated browser per generation; reuse it for repairs."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.cache: dict[tuple[str, bool], str | None] = {}

    async def __aenter__(self):
        try:
            # A broken renderer is a server failure, not something the model can
            # repair. Check known-valid TeX before spending any provider calls.
            if await self.errors([("x+1", False)]):
                logger.error("Formula renderer self-check failed")
                raise MathValidationError("The server formula renderer is unavailable. Please try again later.")
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *_):
        try:
            if self.browser:
                try:
                    async with timeout(10):
                        await self.browser.close()
                except (BrowserError, TimeoutError):
                    pass
        finally:
            if self.playwright:
                try:
                    async with timeout(5):
                        await self.playwright.stop()
                except (BrowserError, TimeoutError):
                    pass

    async def _start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True, executable_path=chromium_executable())
        context = await self.browser.new_context(java_script_enabled=True)
        await context.route("**/*", lambda route: route.abort())
        self.page = await context.new_page()
        self.page.set_default_timeout(15000)
        # about:blank defaults to quirks mode, which KaTeX rejects even for x+1.
        # Match the standards-mode documents used by the UI and PDF export.
        await self.page.set_content("<!doctype html><html><head><meta charset='utf-8'></head><body></body></html>")
        await self.page.add_script_tag(path=str(STATIC / "vendor/katex/katex.min.js"))
        await self.page.add_script_tag(path=str(STATIC / "math-renderer.js"))

    async def errors(self, expressions: list[tuple[str, bool]]) -> list[str]:
        pending = list(dict.fromkeys(expression for expression in expressions if expression not in self.cache))
        try:
            if pending:
                if self.page is None:
                    await self._start()
                results = await wait_for(self.page.evaluate("""expressions => expressions.map(([latex, display]) => {
                    const target = document.createElement('div');
                    return window.MathPDF.renderMath(target, latex, display) ? null : target.textContent.slice(0, 400);
                })""", pending), timeout=20)
                self.cache.update(zip(pending, results))
            return list(dict.fromkeys(self.cache[expression] for expression in expressions if self.cache[expression]))
        except (BrowserError, ExportError, OSError, TimeoutError):
            raise MathValidationError(
                "Formula validation could not start. Configure Chromium on the server and try again."
            ) from None
