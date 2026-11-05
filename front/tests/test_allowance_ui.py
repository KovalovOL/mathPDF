"""Quota UI uses synthetic payloads only, including expiry and recovery states."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_daily_meter_limit_dialog_and_reset_refresh():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (Path(__file__).parent / "fixtures/browser/allowance_ui-1.html").read_text()
    asyncio.run(_daily_meter_limit_dialog_and_reset_refresh(static, html))


async def _daily_meter_limit_dialog_and_reset_refresh(static, html):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})

            async def local(route):
                name = route.request.url.split("?", 1)[0].rsplit("/", 1)[-1]
                await route.fulfill(
                    body=(
                        (static / name).read_text()
                        if name in ["style.css", "allowance-ui.js"]
                        else html
                    ),
                    content_type=(
                        "text/css"
                        if name == "style.css"
                        else "text/javascript" if name.endswith(".js") else "text/html"
                    ),
                )

            await page.clock.install()
            await page.route("**/*", local)
            await page.goto("http://allowance.local/")
            await page.get_by_text("10% left", exact=True).wait_for()
            meter = page.get_by_role(
                "progressbar", name="Daily generation allowance remaining", exact=True
            )
            await _assert_allowance_limit_and_recovery_dialog(meter, page)
            await _assert_disabled_plan_and_daily_reset_refresh(page)
        finally:
            await browser.close()


async def _assert_disabled_plan_and_daily_reset_refresh(page):
    await page.evaluate(
        "window.fixture.reason='disabled';window.fixture.state.daily_tokens=0;window.fixture.state.remaining_percent=0"
    )
    await page.get_by_role("button", name="Generate fixture").click()
    await page.get_by_role(
        "heading", name="Generation is paused for your plan"
    ).wait_for()
    assert not await page.get_by_role(
        "button", name="Adjust request", exact=True
    ).is_visible()
    await page.evaluate(
        "window.fixture.state.limited=false;dispatchEvent(new CustomEvent('mathpdf-allowance-updated',{detail:window.fixture.state}))"
    )
    await page.get_by_role("heading", name="Your allowance is ready").wait_for()
    await page.get_by_role("button", name="Close", exact=True).click()
    await page.evaluate(
        "window.fixture.state.limited=true;window.fixture.state.daily_tokens=200000;window.fixture.state.remaining_percent=100;window.fixture.state.resets_at=new Date(Date.now()+30000).toISOString()"
    )
    await page.evaluate("window.meter.refresh()")
    calls = await page.evaluate("window.fixture.calls")
    await page.clock.fast_forward(61000)
    await page.wait_for_function("(old)=>window.fixture.calls>old", arg=calls)
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert "200000" not in await page.locator(".allowance-header").inner_text()


async def _assert_allowance_limit_and_recovery_dialog(meter, page):
    assert await meter.get_attribute("aria-valuenow") == "10"
    assert "10% remaining, 90% used" == await meter.get_attribute("aria-valuetext")
    assert "Resets in 2h 00m · 00:00 UTC" in await page.locator(
        ".allowance-header"
    ).get_attribute("title")
    await page.get_by_role("button", name="Generate fixture").click()
    await page.get_by_role(
        "heading", name="This request needs more allowance"
    ).wait_for()
    assert (
        "Estimated request: 20%" in await page.locator(".allowance-dialog").inner_text()
    )
    await page.get_by_role("button", name="Adjust request", exact=True).click()
    assert not await page.locator("dialog").is_visible()
    assert await page.get_by_label("Items").input_value() == "10"
    assert await page.get_by_label("Comment").input_value() == "Keep my comment."
    await page.evaluate(
        "window.fixture.reason='exhausted';window.fixture.state.remaining_percent=0;window.fixture.state.remaining_tokens=0"
    )
    await page.get_by_role("button", name="Generate fixture").click()
    await page.get_by_role("heading", name="You've used today's allowance").wait_for()
    await page.evaluate(
        "window.fixture.state.remaining_percent=100;window.fixture.state.remaining_tokens=200000;dispatchEvent(new CustomEvent('mathpdf-allowance-updated',{detail:window.fixture.state}))"
    )
    await page.get_by_role("heading", name="Your allowance is ready").wait_for()
    await page.get_by_role("button", name="Continue", exact=True).click()
