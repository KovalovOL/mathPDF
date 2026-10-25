"""Validate generated TeX with the exact renderer and options used by the UI."""

from playwright.async_api import Error as BrowserError, async_playwright

from .pdf_export import STATIC, ExportError, chromium_executable


class MathValidationError(Exception):
    """A safe operational failure; never includes model text or browser details."""


class MathValidator:
    """One lazy, network-isolated browser per generation; reuse it for repairs."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.cache: dict[tuple[str, bool], bool] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        try:
            if self.browser:
                try:
                    await self.browser.close()
                except BrowserError:
                    pass
        finally:
            if self.playwright:
                await self.playwright.stop()

    async def _start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True, executable_path=chromium_executable())
        context = await self.browser.new_context(java_script_enabled=True)
        await context.route("**/*", lambda route: route.abort())
        self.page = await context.new_page()
        self.page.set_default_timeout(15000)
        await self.page.add_script_tag(path=str(STATIC / "vendor/katex/katex.min.js"))
        await self.page.add_script_tag(path=str(STATIC / "math-renderer.js"))

    async def invalid(self, expressions: list[tuple[str, bool]]) -> bool:
        pending = list(dict.fromkeys(expression for expression in expressions if expression not in self.cache))
        try:
            if pending:
                if self.page is None:
                    await self._start()
                results = await self.page.evaluate("""expressions => expressions.map(([latex, display]) => {
                    const target = document.createElement('div');
                    return window.MathPDF.renderMath(target, latex, display);
                })""", pending)
                self.cache.update(zip(pending, results))
            return any(not self.cache[expression] for expression in expressions)
        except (BrowserError, ExportError, OSError):
            raise MathValidationError(
                "Formula validation could not start. Configure Chromium on the server and try again."
            ) from None
