"""One-time welcome receipt is durable and does not interrupt existing users."""
from fastapi.testclient import TestClient
from app.bootstrap.api import create_app
from test_app import sign_in


def test_welcome_claim_once_and_existing_users_are_not_interrupted(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/welcome/claim").status_code == 401
        sign_in(client, app)
        assert client.get("/api/me").json()["welcome_pending"] is True
        assert client.post("/api/welcome/claim").json() == {"show": True}
        assert client.post("/api/welcome/claim").json() == {"show": False}
        sign_in(client, app)
        assert client.get("/api/me").json()["welcome_pending"] is False
        sign_in(client, app, "new-account")
        assert client.get("/api/me").json()["welcome_pending"] is True


def test_welcome_claim_requires_same_origin(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        sign_in(client, app)
        client.headers["Origin"] = "https://untrusted.example"
        assert client.post("/api/welcome/claim").status_code == 403
