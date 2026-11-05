from support import workspace_for

"""Daily resets and typed quota transport preserve historical settings and attempts."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from app.bootstrap.api import create_app
from app.usage.quotas import period
from app.identity.role_models import OWNER_EMAIL
from app.usage.context import usage_context
from test_platform import login, session
from test_library_organization import file


def test_historical_four_column_limits_read_without_rewriting(tmp_path):
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/allowances/monthly-v1.json").read_text()
    )
    with sqlite3.connect(tmp_path / "workspace.sqlite3") as db:
        db.execute(
            "CREATE TABLE generation_limits (scope TEXT PRIMARY KEY,monthly_tokens BIGINT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT)"
        )
        db.executemany(
            "INSERT INTO generation_limits VALUES (?,?,?,?)", fixture["rows"]
        )
    app = create_app(tmp_path)
    _, user = login(app)
    _, owner = login(app, OWNER_EMAIL)
    q = workspace_for(app).usage.quota
    assert q.status(user.id)["daily_tokens"] == 54321
    with workspace_for(app).connection() as db:
        rows = [
            list(r)
            for r in db.execute(
                "SELECT scope,monthly_tokens,updated_at,updated_by FROM generation_limits ORDER BY scope"
            )
        ]
        assert rows == fixture["rows"]
        db.execute(
            "INSERT INTO generation_limits (scope,monthly_tokens,updated_at,updated_by) VALUES (?,?,?,?)",
            ("user:" + user.id, 12345, "2026-10-28T00:00:00+00:00", None),
        )
    assert q.status(user.id)["daily_tokens"] == 12345
    q.update(owner, 67890)
    with workspace_for(app).connection() as db:
        row = db.execute(
            "SELECT monthly_tokens,daily_tokens FROM generation_limits WHERE scope='default'"
        ).fetchone()
        assert tuple(row) == (54321, 67890)
    assert (
        workspace_for(create_app(tmp_path)).usage.quota.status(user.id)["daily_tokens"]
        == 12345
    )


def test_midnight_reset_retains_legacy_month_key_and_late_paid_usage(tmp_path):
    app = create_app(tmp_path)
    _, user = login(app)
    u = workspace_for(app).usage
    q = u.quota
    start, end = period()
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)
    previous = u.start(user.id, "openai", "fixture", {"estimated_tokens": 1000})
    held = u.start(user.id, "openai", "fixture", {"estimated_tokens": 500})
    with workspace_for(app).connection() as db:
        db.execute(
            "UPDATE ai_usage SET started_at=? WHERE id=?",
            ((start - timedelta(seconds=1)).isoformat(), previous),
        )
        db.execute(
            "UPDATE generation_reservations SET period_start=? WHERE attempt_id=?",
            (start.replace(day=1).isoformat(), held),
        )
        assert (
            q._status(db, user.id, start + timedelta(hours=23, minutes=59))[
                "reserved_tokens"
            ]
            == 500
        )
        assert q._status(db, user.id, end)["remaining_percent"] == 100
        assert q._status(db, user.id, end)["reserved_tokens"] == 0
    u.finish(held, "received", {"input_tokens": 200, "output_tokens": 100})
    with workspace_for(app).connection() as db:
        assert q._status(db, user.id, start)["used_tokens"] == 300
        assert q._status(db, user.id, end)["used_tokens"] == 0
        assert db.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0] == 2
        assert (
            db.execute("SELECT COUNT(*) FROM generation_reservations").fetchone()[0]
            == 2
        )


def test_daily_period_is_exactly_24_hours_across_dst_and_leap_day():
    for when in [
        datetime(2026, 10, 25, 23, 59, tzinfo=timezone(timedelta(hours=2))),
        datetime(2028, 2, 29, 23, 59, tzinfo=timezone.utc),
        datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
    ]:
        start, end = map(datetime.fromisoformat, period(when))
        assert (end - start).total_seconds() == 86400 and start.hour == end.hour == 0
        assert start.utcoffset().total_seconds() == 0


def test_typed_background_insufficient_limit_and_no_bug_report(tmp_path):
    class Provider:
        calls = 0

        async def generate(self, *args, **kwargs):
            self.calls += 1
            track = usage_context.get()
            track["store"].start(
                track["user_id"], "openai", "fixture", {"estimated_tokens": 1000}
            )
            raise AssertionError("Dispatch must be blocked")

    provider = Provider()
    app = create_app(tmp_path, provider=provider)
    token, user = login(app)
    _, owner = login(app, OWNER_EMAIL)
    workspace_for(app).usage.quota.update(owner, 500)
    with TestClient(app) as client:
        session(client, app, token)
        doc = file(client)
        selection = {
            "document_id": doc["id"],
            "pages": [1],
            "count": 2,
            "mode": "flashcards",
        }
        direct = client.post("/api/study/generate", json=selection)
        assert direct.status_code == 429 and direct.json()["reason"] == "insufficient"
        assert direct.json()["required_percent"] == 200
        response = client.post("/api/study/jobs", json=selection)
        assert response.status_code == 202

        async def finished():
            for task in asyncio.all_tasks():
                if (
                    task is not asyncio.current_task()
                    and getattr(task.get_coro(), "__qualname__", "")
                    == "GenerationJobs.run"
                ):
                    await task

        client.portal.call(finished)
        job = client.get("/api/study/jobs/" + response.json()["id"]).json()
        assert job["status"] == "failed" and job["limit"]["code"] == "generation_limit"
        assert job["limit"]["allowance"]["remaining_percent"] == 100
        assert not workspace_for(app).reports.list()
        with workspace_for(app).connection() as db:
            assert db.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0] == 0
    assert provider.calls == 2
