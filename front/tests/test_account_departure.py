"""The shared account menu respects leave approval and reports sign-out failures."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_signout_awaits_approval_and_uses_an_origin_checked_request():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (
        Path(__file__).parent / "fixtures/browser/account_departure-1.html"
    ).read_text()
    asyncio.run(
        _signout_awaits_approval_and_uses_an_origin_checked_request(static, html)
    )


async def _signout_awaits_approval_and_uses_an_origin_checked_request(static, html):
    calls = []
    fail = True
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page()
            local = _make_signout_route(static, calls, lambda: fail, html)
            await page.route("**/*", local)
            await _assert_signout_approval_origin_and_failure(calls, page)
            fail = False
            await _assert_successful_signout(calls, page)
        finally:
            await browser.close()


async def _assert_successful_signout(calls, page):
    await page.get_by_role("button", name="Sign out", exact=True).click()
    await page.get_by_role("heading", name="Signed out", exact=True).wait_for()
    assert len(calls) == 2


async def _assert_signout_approval_origin_and_failure(calls, page):
    await page.goto("http://localhost/")
    await page.locator(".account-menu summary").click()
    await page.get_by_role("button", name="Sign out", exact=True).click()
    assert calls == []
    await page.evaluate("window.permit=true")
    await page.get_by_role("button", name="Sign out", exact=True).click()
    await page.get_by_role("alert").wait_for()
    assert calls == [{"method": "POST", "origin": "http://localhost"}]
    assert await page.evaluate("window.resets") == 1
    assert await page.get_by_role("button", name="Sign out", exact=True).is_enabled()


def _make_signout_route(static, calls, fail, html):

    async def local(route):
        path = route.request.url.split("localhost", 1)[1].split("?", 1)[0]
        if path.startswith("/static/"):
            await route.fulfill(
                content_type="text/javascript",
                body=(static / path.removeprefix("/static/")).read_text(),
            )
        elif path == "/api/me":
            await route.fulfill(
                json={
                    "id": "owner",
                    "name": "Fixture user",
                    "email": "fixture@example.invalid",
                }
            )
        elif path == "/auth/logout":
            calls.append(
                {
                    "method": route.request.method,
                    "origin": route.request.headers.get("origin"),
                }
            )
            await route.fulfill(
                status=503 if fail() else 200,
                content_type="text/html",
                body="Sign-out response",
            )
        elif path == "/login":
            await route.fulfill(content_type="text/html", body="<h1>Signed out</h1>")
        else:
            await route.fulfill(
                content_type="text/html",
                body=html,
                headers={"Referrer-Policy": "no-referrer"},
            )

    return local
