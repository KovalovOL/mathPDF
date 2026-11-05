"""Validate generated TeX with the exact renderer and options used by the UI."""

from asyncio import timeout, wait_for, to_thread
import logging
from types import MappingProxyType

from playwright.async_api import Error as BrowserError, async_playwright

from app.infrastructure.export.browser import ExportError, chromium_executable
from app.infrastructure.http.frontend import FrontendAssets

logger = logging.getLogger(__name__)


class MathValidationError(Exception):
    """A safe operational failure; never includes model text or browser details."""


class MathValidator:
    """Optional offline renderer diagnostic; generation never invokes it."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._cache: dict[tuple[str, bool], str | None] = {}

    @property
    def page(self):
        return self._page

    @property
    def cache(self):
        return MappingProxyType(self._cache)

    async def __aenter__(self):
        try:
            # A broken renderer is a server failure, not something the model can
            # repair. Check known-valid TeX before spending any provider calls.
            if await self.errors([("x+1", False)]):
                logger.error("Formula renderer self-check failed")
                raise MathValidationError(
                    "The server formula renderer is unavailable. Please try again later."
                )
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *_):
        try:
            if self._browser:
                try:
                    async with timeout(10):
                        await self._browser.close()
                except (BrowserError, TimeoutError):
                    pass
        finally:
            if self._playwright:
                try:
                    async with timeout(5):
                        await self._playwright.stop()
                except (BrowserError, TimeoutError):
                    pass

    async def _start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        context = await self._browser.new_context(java_script_enabled=True)
        await context.route("**/*", lambda route: route.abort())
        self._page = await context.new_page()
        self._page.set_default_timeout(15000)
        # about:blank defaults to quirks mode, which KaTeX rejects even for x+1.
        # Match the standards-mode documents used by the UI and PDF export.
        await self._page.set_content(
            "<!doctype html><html><head><meta charset='utf-8'></head><body></body></html>"
        )
        assets = FrontendAssets()
        await self.page.add_script_tag(
            content=(await to_thread(assets.read, "vendor/katex/katex.min.js")).decode()
        )
        await self.page.add_script_tag(
            content=(await to_thread(assets.read, "math-renderer.js")).decode()
        )

    async def errors(self, expressions: list[tuple[str, bool]]) -> list[str]:
        pending = list(
            dict.fromkeys(
                expression
                for expression in expressions
                if expression not in self._cache
            )
        )
        try:
            if pending:
                if self._page is None:
                    await self._start()
                results = await wait_for(
                    self._page.evaluate(
                        """expressions => expressions.map(([latex, display]) => {
                    const target = document.createElement('div');
                    return window.MathPDF.renderMath(target, latex, display) ? null :
                        (target.dataset.mathError || target.textContent).slice(0, 400);
                })""",
                        pending,
                    ),
                    timeout=20,
                )
                self._cache.update(zip(pending, results))
            return list(
                dict.fromkeys(
                    self._cache[expression]
                    for expression in expressions
                    if self._cache[expression]
                )
            )
        except (BrowserError, ExportError, OSError, TimeoutError):
            raise MathValidationError(
                "Formula validation could not start. Configure Chromium on the server and try again."
            ) from None
