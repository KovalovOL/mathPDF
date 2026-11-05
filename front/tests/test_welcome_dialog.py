"""Welcome dialog works at desktop and mobile widths and restores focus."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_welcome_dialog_is_responsive_and_dismissible():
    static = Path(__file__).resolve().parents[1] / "dist"
    asyncio.run(_check_welcome_dialog(static))


async def _check_welcome_dialog(static):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            await _check_welcome_viewport(browser, static, 1280)
            await _check_welcome_viewport(browser, static, 320)
        finally:
            await browser.close()


async def _check_welcome_viewport(browser, static, width):
    page = await browser.new_page(viewport={"width": width, "height": 800})
    await page.set_content('<button id="before">Upload PDF</button>')
    await page.add_style_tag(path=str(static / "style.css"))
    source = (static / "welcome.js").read_text().replace(
        "export async function", "async function"
    )
    await page.add_script_tag(content=source)
    await page.locator("#before").focus()
    await page.evaluate("showWelcome({api: async () => ({show: true})})")
    dialog = page.get_by_role("dialog", name="Welcome to Acadence!")
    await dialog.wait_for(state="visible")
    assert await dialog.evaluate("element => element.getBoundingClientRect().width <= innerWidth")
    await page.keyboard.press("Escape")
    await dialog.wait_for(state="detached")
    assert await page.locator("#before").evaluate("element => element === document.activeElement")
    await page.close()
