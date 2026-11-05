"""Authenticated real workspace smoke through the isolated public gateway."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.infrastructure.export.browser import chromium_executable
from test_gateway import gateway, sign_in, upload_pdf


def saved_browser_deck(client, credentials):
    sign_in(client, credentials, "free")
    document = upload_pdf(client)
    raw = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/study-sets/legacy-flashcards.json"
        ).read_text()
    )
    raw["document"], raw["pages"] = document, [1]
    for item in raw["items"]:
        for block in item["question"] + item["answer"]:
            if block["kind"] == "math":
                block["source"].update(document_id=document["id"], page=1)
    response = client.post(
        "/api/study-sets", json=raw, headers={"Origin": "http://127.0.0.1:18770"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_authenticated_workspace_survives_mobile_resize_and_reload(gateway):
    client, credentials = gateway
    deck = saved_browser_deck(client, credentials)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=chromium_executable()
        )
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            context.add_cookies(
                [
                    {
                        "name": credentials["cookie"],
                        "value": credentials["free"]["token"],
                        "url": "http://127.0.0.1:18770",
                    }
                ]
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:18770/workspace?set=" + deck["id"])
            page.locator(".flashcard").wait_for()
            page.locator(".flashcard").click()
            page.wait_for_function(
                "document.querySelector('.flashcard').classList.contains('flipped')"
            )
            assert page.locator(".card-back .math-output").count() > 0
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.reload()
            page.locator(".flashcard").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert errors == []
        finally:
            browser.close()
