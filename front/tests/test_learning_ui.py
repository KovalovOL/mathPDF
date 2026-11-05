"""Isolated UI components: no live service, accounts or external requests."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_assessment_resume_retry_summary_and_percentage_meter():
    static = Path(__file__).resolve().parents[1] / "dist"
    harness = (
        Path(__file__).parent / "fixtures/browser/learning_ui-1.html"
    ).read_text()
    asyncio.run(_assessment_resume_retry_summary_and_percentage_meter(static, harness))


async def _assessment_resume_retry_summary_and_percentage_meter(static, harness):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            local = _make_learning_route(static, harness)
            await page.route("**/*", local)
            await page.goto("http://learning.local/")
            await page.wait_for_function(
                "window.fixture.rounds.length===1 && document.querySelector('.review-status').hidden"
            )
            assert not await page.get_by_role(
                "button", name="✓ Correct", exact=True
            ).is_visible()
            assert "75% left" in await page.locator(".allowance-header").inner_text()
            assert "25% used" in await page.locator(
                ".allowance-header [role=progressbar]"
            ).get_attribute("aria-valuetext")
            assert "Resets in 1h 00m" in await page.locator(
                ".allowance-header"
            ).get_attribute("title")
            assert (
                await page.locator(
                    ".allowance-header [role=progressbar]"
                ).get_attribute("aria-valuenow")
                == "75"
            )
            await _assert_review_resume_and_rating_retry(page)
            await _assert_new_round_conflict_and_rename(page)
        finally:
            await browser.close()


async def _assert_new_round_conflict_and_rename(page):
    await page.get_by_role("button", name="Practice again").click()
    await page.get_by_role("button", name="Flip", exact=True).wait_for()
    assert await page.evaluate("window.fixture.rounds.length") == 2
    await page.evaluate("window.fixture.conflict=true")
    await page.get_by_role("button", name="Flip", exact=True).click()
    await page.get_by_role("button", name="✓ Correct", exact=True).click()
    await page.get_by_role("button", name="Use saved progress").click()
    await page.wait_for_function(
        "window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden"
    )
    assert await page.evaluate("window.fixture.record.itemIndex") == 1
    await page.get_by_role("button", name="Rename fixture").click()
    await page.get_by_label("Name", exact=True).fill("My title")
    await page.get_by_role("button", name="Save name").click()
    await page.wait_for_function("window.fixture.renamed==='My title'")
    assert not await page.locator("dialog").is_visible()
    assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")


async def _assert_review_resume_and_rating_retry(page):
    await page.get_by_role("button", name="Flip", exact=True).click()
    await page.get_by_role("button", name="✓ Correct", exact=True).click()
    await page.wait_for_function(
        "window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden"
    )
    await page.evaluate("window.remount()")
    await page.wait_for_function(
        "window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden"
    )
    assert await page.evaluate("window.fixture.record.itemIndex") == 1
    await page.evaluate("window.fixture.fail=true")
    await page.get_by_role("button", name="Flip", exact=True).click()
    await page.get_by_role("button", name="✕ Incorrect", exact=True).click()
    await page.get_by_role("button", name="Retry saving answer").click()
    await page.get_by_role("heading", name="50% correct").wait_for()
    assert (
        "1 correct · 1 incorrect · 2 cards"
        in await page.locator(".review-summary").inner_text()
    )
    assert await page.evaluate("window.fixture.rounds[0].answers.length") == 2
    assert (
        await page.evaluate(
            "Object.keys(localStorage).filter(k=>k.includes('review-pending')).length"
        )
        == 0
    )


def _make_learning_route(static, harness):

    async def local(route):
        name = route.request.url.split("?", 1)[0].rsplit("/", 1)[-1]
        await route.fulfill(
            body=(
                (static / name).read_text()
                if name.endswith(".js")
                else (
                    '<link rel="stylesheet" href="/static/style.css">' + harness
                    if name != "style.css"
                    else (static / name).read_text()
                )
            ),
            content_type=(
                "text/javascript"
                if name.endswith(".js")
                else "text/css" if name == "style.css" else "text/html"
            ),
        )

    return local
