"""Focused checks for the new explicit ports, private state and gateway contract."""

import asyncio
import json
import logging
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from app.bootstrap.api import create_app
from app.core.observability.context import CorrelationScope
from app.core.observability.diagnostics import (
    JsonFormatter,
    request_context,
    job_context,
)
from app.identity.authentication import Authentication
from app.identity.models import AuthConfig, LoginError
from app.identity.policies import token_hash
from app.application.use_cases.collect_report_bundle import CollectReportBundle
from test_platform import login, session


def identity_fixture():
    repository, roles, identity = Mock(), Mock(), Mock()
    flows = {}
    fields = (
        "cookie_hash",
        "state_hash",
        "nonce",
        "verifier",
        "next_path",
        "expires_at",
    )
    repository.store_flow.side_effect = lambda values, previous, now: flows.__setitem__(
        values[0], dict(zip(fields, values))
    )
    repository.consume_flow.side_effect = lambda key: flows.pop(key, None)
    repository.create.return_value = "a" * 32
    identity.exchange = AsyncMock(return_value="fixture-id-token")
    identity.verify.return_value = {
        "sub": "fixture",
        "email": "fixture@example.invalid",
    }
    auth = Authentication(
        repository,
        AuthConfig("client", "fixture-secret", "http://localhost"),
        roles,
        identity,
    )
    return auth, repository, roles, identity, flows


def test_identity_ports_keep_pkce_nonce_and_one_use_flow():
    auth, repository, roles, identity, flows = identity_fixture()
    target = "/workspace?document=" + "d" * 32 + "&set=" + "e" * 32
    cookie, url = auth.begin(target, None)
    query = parse_qs(urlsplit(url).query)
    stored = flows[token_hash(cookie)]
    assert cookie not in flows and stored["state_hash"] == token_hash(query["state"][0])
    assert query["code_challenge_method"] == ["S256"]
    token, next_path = asyncio.run(
        auth.finish(cookie, query["state"][0], "code", None, None)
    )
    assert next_path == target and token_hash(token) != token
    identity.verify.assert_called_once_with(
        "fixture-id-token", stored["nonce"], "client"
    )
    roles.verified_login.assert_called_once_with("a" * 32, "fixture@example.invalid")
    assert repository.create.call_args.args[2] == token_hash(token)
    with pytest.raises(LoginError):
        asyncio.run(auth.finish(cookie, query["state"][0], "code", None, None))
    assert identity.exchange.await_count == 1


def test_invalid_oauth_state_is_consumed_without_provider_dispatch():
    auth, repository, roles, identity, flows = identity_fixture()
    cookie, _ = auth.begin("https://foreign.invalid/", None)
    with pytest.raises(LoginError):
        asyncio.run(auth.finish(cookie, "wrong-state", "code", None, None))
    assert not flows
    identity.exchange.assert_not_awaited()
    roles.verified_login.assert_not_called()


def test_correlation_scope_resets_after_nested_failure(monkeypatch):
    secret = "fixture-secret-value-for-redaction"
    monkeypatch.setenv("MATHPDF_API_KEY", secret)
    before = request_context.get(), job_context.get()
    formatter = JsonFormatter(service="reports", build="fixture-release")
    with CorrelationScope("a" * 32, "b" * 32, {"user_id": "c" * 32}):
        with pytest.raises(RuntimeError):
            with CorrelationScope("d" * 32):
                raise RuntimeError("fixture")
        record = logging.LogRecord(
            "app.fixture", logging.INFO, __file__, 1, secret, (), None
        )
        payload = json.loads(formatter.format(record))
        assert payload["request_id"] == "a" * 32 and payload["job_id"] == "b" * 32
        assert payload["service"] == "reports" and payload["build"] == "fixture-release"
        assert payload["schema_version"] == 1 and payload["message"] == "[REDACTED]"
    assert (request_context.get(), job_context.get()) == before


@pytest.mark.parametrize("changed", [False, True])
def test_report_lease_completion_controls_binary_cleanup(changed):
    reports, bundles, cleanup, usage = Mock(), Mock(), Mock(), Mock()
    report = {"id": "a" * 32}
    manifest = {"sources": [{"stored_name": "fixture.pdf"}]}
    reports.claim_collection.return_value = report, "lease"
    reports.complete_collection.return_value = changed
    bundles.collect.return_value = manifest
    assert CollectReportBundle(reports, bundles, cleanup, usage).execute()
    reports.complete_collection.assert_called_once_with(report, "lease", manifest)
    assert cleanup.execute.call_count == int(changed)
    usage.flush_spool.assert_called_once_with()


@pytest.mark.parametrize(
    "path",
    [
        "/admin",
        "/static/admin.html/",
        "/static/%61dmin.html",
        "/static//admin.html",
        "/static/a/../admin.html",
    ],
)
def test_gateway_requires_role_for_every_admin_html_alias(tmp_path, path):
    app = create_app(tmp_path)
    token, _ = login(app)
    with TestClient(app) as client:
        session(client, app, token)
        response = client.get(
            "/internal/access", headers={"X-MathPDF-Original-URI": path}
        )
        assert response.status_code == 403


def test_gateway_preserves_deep_link_and_missing_resource_semantics(tmp_path):
    app = create_app(tmp_path)
    target = "/workspace?document=" + "d" * 32 + "&set=" + "e" * 32
    with TestClient(app) as client:
        response = client.get(
            "/internal/access", headers={"X-MathPDF-Original-URI": target}
        )
        assert response.status_code == 401
        assert parse_qs(urlsplit(response.headers["x-mathpdf-signin"]).query)[
            "next"
        ] == [target]
        token, _ = login(app)
        session(client, app, token)
        missing = client.get(
            "/internal/access", headers={"X-MathPDF-Original-URI": target}
        )
        assert (
            missing.status_code == 403
            and missing.headers["x-mathpdf-access-status"] == "404"
        )
        with pytest.raises(AttributeError):
            app.state.services.persistence.directory = tmp_path / "other"
        with pytest.raises(AttributeError):
            app.state.runtime.provider = object()
