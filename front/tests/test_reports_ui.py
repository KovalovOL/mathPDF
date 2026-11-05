"""Isolated reporting component checks; no production browser or real user content."""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from browser_support import chromium_executable


def test_automatic_and_manual_context_redact_secrets_and_do_not_recurse():
    static = Path(__file__).resolve().parents[1] / "dist"
    html = (Path(__file__).parent / "fixtures/browser/reports_ui-1.html").read_text()
    asyncio.run(
        _automatic_and_manual_context_redact_secrets_and_do_not_recurse(static, html)
    )


def test_admin_report_starts_with_readable_summary_and_collapsed_original_evidence():
    static = Path(__file__).resolve().parents[1] / "dist"
    asyncio.run(
        _admin_report_starts_with_readable_summary_and_collapsed_original_evidence(
            static
        )
    )


async def _automatic_and_manual_context_redact_secrets_and_do_not_recurse(static, html):
    responses = json.loads(
        (
            Path(__file__).parent / "fixtures/scenarios/report-api-responses.json"
        ).read_text()
    )
    received = []
    outage = False
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 390, "height": 844})

            async def route(r):
                nonlocal outage
                path = r.request.url.split("localhost", 1)[1].split("?", 1)[0]
                if path.startswith("/static/"):
                    await r.fulfill(
                        content_type="text/javascript",
                        body=(static / path.removeprefix("/static/")).read_text(),
                    )
                elif path == "/api/reports":
                    received.append(json.loads(r.request.post_data))
                    await r.fulfill(
                        status=503 if outage else 202,
                        json={"id": "d" * 32, "status": "new"},
                    )
                elif path in responses:
                    await r.fulfill(**responses[path])
                else:
                    await r.fulfill(content_type="text/html", body=html)

            await page.route("**/*", route)
            await _send_automatic_and_manual_reports(page, received)
            await _assert_quota_exclusion_and_report_redaction(page, received)
            outage = True
            await _assert_report_queue_survives_outage(page, received)
            outage = False
            await _assert_report_queue_replays_after_reload(page, received)
        finally:
            await browser.close()


async def _admin_report_starts_with_readable_summary_and_collapsed_original_evidence(
    static,
):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            page = await browser.new_page(viewport={"width": 1100, "height": 900})
            report = json.loads(
                (
                    Path(__file__).parent / "fixtures/scenarios/reports_ui-202.json"
                ).read_text()
            )
            local = _make_admin_report_route(static, report)
            await page.route("**/*", local)
            await page.goto("http://admin.local/admin")
            await page.locator('[data-tab="reports"]').click()
            await page.locator("#report-list button").click()
            await page.locator(".incident-code").wait_for()
            assert (
                "Open library" in await page.locator(".incident-summary").inner_text()
            )
            assert "Notes.pdf" in await page.locator(".incident-summary").inner_text()
            assert (
                await page.locator(".incident-advanced").get_attribute("open") is None
            )
            assert not await page.locator(".admin-context").is_visible()
            await page.get_by_text("Advanced: full diagnostic JSON", exact=True).click()
            assert (
                "Original evidence" in await page.locator(".admin-context").inner_text()
            )
        finally:
            await browser.close()


async def _assert_report_queue_replays_after_reload(page, received):
    await page.reload()
    await page.locator(".account-menu summary").click()
    await page.get_by_role("button", name="Report a problem", exact=True).wait_for()
    await page.evaluate('dispatchEvent(new Event("online"))')
    await page.wait_for_function(
        'JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0'
    )
    assert len(received) == 6 and received[-1]["request_id"] == "b" * 32


async def _assert_report_queue_survives_outage(page, received):
    await page.evaluate('MathPDFSession.api("/api/bad",{method:"POST"}).catch(()=>{})')
    assert len(received) == 4
    await page.evaluate(
        'MathPDFSession.api("/api/outage",{method:"POST"}).catch(()=>{})'
    )
    await page.wait_for_function(
        'JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===1'
    )


async def _assert_quota_exclusion_and_report_redaction(page, received):
    quota = await page.evaluate(
        'MathPDFSession.api("/api/allowance-limited",{method:"POST"}).catch(e=>({code:e.code,status:e.status,reason:e.reason}))'
    )
    assert quota == {"code": "generation_limit", "status": 429, "reason": "exhausted"}
    await page.evaluate('MathPDFSession.api("/api/quota-job").catch(()=>{})')
    await page.wait_for_function(
        'JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0'
    )
    assert len(received) == 4
    assert {r["request_id"] for r in received[:3]} == {"e" * 32, "f" * 32, "a" * 32}
    assert (
        received[-1]["category"] == "answer_too_long"
        and received[-1]["comment"] == "Use a shorter explanation."
    )
    assert (
        received[-1]["context"]["active"]["page"] == 4
        and received[-1]["context"]["active"]["item_index"] == 2
    )
    serialized = json.dumps(received)
    assert "never retain" not in serialized and "credential" not in serialized
    assert received[-1]["context"]["active"]["answer"].endswith("\\cap")


async def _send_automatic_and_manual_reports(page, received):
    await page.goto("http://localhost/")
    await page.locator(".account-menu summary").click()
    await page.get_by_role("button", name="Report a problem", exact=True).wait_for()
    for path in ["/api/bad", "/api/server-error", "/api/failed-job"]:
        await page.evaluate(
            '(path)=>MathPDFSession.api(path,{method:"POST",body:JSON.stringify({document_id:"a".repeat(32),count:5,clientSecret:"secret",cookies:["credential"]})}).catch(()=>{})',
            path,
        )
    await page.wait_for_function(
        'JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0'
    )
    await page.get_by_role("button", name="Report a problem", exact=True).click()
    await page.get_by_label("Issue type", exact=True).select_option("answer_too_long")
    await page.get_by_label("What happened?", exact=True).fill(
        "Use a shorter explanation."
    )
    await page.get_by_role("button", name="Send report", exact=True).click()
    await page.get_by_text("Report sent. Reference:", exact=False).wait_for()
    assert len(received) == 4


def _make_admin_report_route(static, report):

    async def local(route):
        path = route.request.url.split("admin.local", 1)[1].split("?", 1)[0]
        if path == "/static/account.js":
            await route.fulfill(
                content_type="text/javascript",
                body="window.MathPDFSession={ready:Promise.resolve({role:'owner'}),api:async path=>(await fetch(path)).json()};",
            )
        elif path.startswith("/static/"):
            file = static / path.removeprefix("/static/")
            await route.fulfill(
                body=file.read_bytes(),
                content_type=(
                    "text/css"
                    if file.suffix == ".css"
                    else "text/javascript" if file.suffix == ".js" else "image/svg+xml"
                ),
            )
        elif path == "/api/admin/reports":
            await route.fulfill(json=[{**report, "email": "fixture@example.invalid"}])
        elif path.startswith("/api/admin/reports/"):
            await route.fulfill(json=report)
        elif path == "/api/admin/overview":
            await route.fulfill(
                json={"users": 1, "roles": [], "reports": [], "history_note": ""}
            )
        elif path == "/api/admin/usage":
            await route.fulfill(
                json={"totals": {}, "daily": [], "users": [], "models": []}
            )
        elif path == "/api/admin/users":
            await route.fulfill(json=[])
        elif path == "/api/admin/generation-limits":
            await route.fulfill(json={"daily_tokens": 200000})
        else:
            await route.fulfill(
                body=(static / "admin.html").read_text(), content_type="text/html"
            )

    return local
