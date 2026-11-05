"""Real HTTP acceptance through Nginx and the three private backend processes."""

import io
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pypdf import PdfReader, PdfWriter


@pytest.fixture(scope="module")
def gateway():
    location = os.getenv("MATHPDF_GATEWAY_FIXTURE")
    if not location:
        pytest.skip("Set MATHPDF_GATEWAY_FIXTURE for the disposable local stack.")
    credentials = json.loads(Path(location).read_text())
    with httpx.Client(base_url="http://127.0.0.1:18770", timeout=100) as client:
        yield client, credentials


def sign_in(client, credentials, role):
    client.cookies.clear()
    client.cookies.set(credentials["cookie"], credentials[role]["token"])


def test_anonymous_deep_link_keeps_all_query_parameters(gateway):
    client, _ = gateway
    client.cookies.clear()
    target = "/workspace?document=" + "d" * 32 + "&set=" + "e" * 32
    response = client.get(target)
    assert response.status_code == 303
    assert parse_qs(urlsplit(response.headers["location"]).query)["next"] == [target]
    assert client.get("/internal/access").status_code == 404
    assert client.get("/login").status_code == 200


def test_role_checks_private_routes_and_missing_sources(gateway):
    client, credentials = gateway
    sign_in(client, credentials, "free")
    for path in ["/admin", "/static/admin.html/", "/static/%61dmin.html"]:
        assert client.get(path).status_code == 403
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/workspace?document=" + "f" * 32).status_code == 404
    assert client.get("/api/me").status_code == 200
    sign_in(client, credentials, "owner")
    assert client.get("/admin").status_code == 200
    assert client.get("/api/admin/overview").status_code == 200
    assert client.get("/api/reports/" + "f" * 32).status_code == 404


def upload_pdf(client):
    writer, data = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=600, height=800)
    writer.write(data)
    response = client.post(
        "/api/documents",
        files={"file": ("acceptance.pdf", data.getvalue(), "application/pdf")},
        headers={"Origin": "http://127.0.0.1:18770"},
    )
    assert response.status_code == 201
    return response.json()


def test_legacy_set_roundtrip_and_export_use_private_frontend_assets(gateway):
    client, credentials = gateway
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
    headers = {"Origin": "http://127.0.0.1:18770"}
    saved = client.post("/api/study-sets", json=raw, headers=headers)
    assert saved.status_code == 200, saved.text
    opened = client.get("/api/study-sets/" + raw["id"])
    assert opened.json() == saved.json()
    assert client.get("/workspace?set=" + raw["id"]).status_code == 200
    exported = client.post("/api/study/export.pdf", json=opened.json(), headers=headers)
    assert exported.status_code == 200, exported.text
    text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(exported.content)).pages
    )
    assert "Answers" in text and raw["title"] in text
    assert client.get("/api/library").json()["files"]
