from app.core.ports import PersistencePort

"""Actual provider-attempt accounting with immutable effective tariff snapshots."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from app.core.observability.diagnostics import request_context, job_context

PRICING_SOURCE = "https://developers.openai.com/api/docs/models/gpt-4.1-mini"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class UsageRepository:

    def __init__(self, persistence: PersistencePort, allowance, identifiers):
        self._persistence, self._allowance = persistence, allowance
        self._identifiers = identifiers

    def start(self, user_id, provider, model, context):
        from app.core.serialization import bounded

        identifier = self._identifiers.new_id()
        estimate = context.get("estimated_tokens", 1)
        context = bounded(context)
        with self._persistence.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            stamp = utcnow()
            price = db.execute(
                "SELECT id FROM model_prices WHERE provider=? AND model=? AND effective_at<=? ORDER BY effective_at DESC,id DESC LIMIT 1",
                (provider, model, stamp),
            ).fetchone()
            db.execute(
                "INSERT INTO ai_usage (id,user_id,request_id,job_id,provider,model,started_at,status,price_id,context)\n                VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    user_id,
                    request_context.get(),
                    job_context.get(),
                    provider,
                    model,
                    stamp,
                    "running",
                    price["id"] if price else None,
                    json.dumps(context, ensure_ascii=False),
                ),
            )
            self._allowance.reserve(
                db, identifier, user_id, estimate, now=datetime.fromisoformat(stamp)
            )
        return identifier

    def finish(
        self,
        identifier,
        status,
        usage=None,
        duration_ms=None,
        provider_request_id=None,
        finished_at=None,
        unbilled=False,
    ):
        inputs, outputs, cached, reasoning = self._usage_counts(usage)
        with self._persistence.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT price_id,input_tokens,output_tokens FROM ai_usage WHERE id=?",
                (identifier,),
            ).fetchone()
            if not row:
                return
            if (
                (inputs is None or outputs is None)
                and row["input_tokens"] is not None
                and (row["output_tokens"] is not None)
            ):
                return
            cost = self._observation_cost(db, row, inputs, outputs, cached)
            db.execute(
                "UPDATE ai_usage SET finished_at=?,status=?,input_tokens=?,cached_tokens=?,output_tokens=?,reasoning_tokens=?,\n                duration_ms=?,provider_request_id=?,cost_usd=? WHERE id=?",
                (
                    finished_at or utcnow(),
                    status,
                    inputs,
                    cached,
                    outputs,
                    reasoning,
                    duration_ms,
                    provider_request_id,
                    cost,
                    identifier,
                ),
            )
            self._allowance.settle(
                db, identifier, inputs is not None and outputs is not None, unbilled
            )

    def response(self, identifier, model, status, text):
        from app.core.serialization import sanitize

        with self._persistence.connection() as db:
            row = db.execute(
                "SELECT context FROM ai_usage WHERE id=?", (identifier,)
            ).fetchone()
            if not row:
                return
            context = json.loads(row["context"])
            context["provider_response"] = sanitize(
                {"status": status, "output_text": text}
            )
            db.execute(
                "UPDATE ai_usage SET context=?,model=? WHERE id=?",
                (json.dumps(context, ensure_ascii=False), model, identifier),
            )

    def outcome(self, identifier, status):
        with self._persistence.connection() as db:
            db.execute("UPDATE ai_usage SET status=? WHERE id=?", (status, identifier))

    def dashboard(self, days=7, user_id=None):
        point = datetime.now(timezone.utc)
        since = (
            point.replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=days - 1)
        ).isoformat()
        with self._persistence.connection() as db:
            query = "SELECT user_id,provider,model,started_at,status,input_tokens,output_tokens,cached_tokens,cost_usd FROM ai_usage WHERE started_at>=?"
            args = [since]
            if user_id:
                query += " AND user_id=?"
                args.append(user_id)
            rows = [dict(r) for r in db.execute(query + " ORDER BY started_at", args)]
        users = sorted({r["user_id"] for r in rows})
        models = sorted({r["model"] for r in rows})
        daily = {}
        for r in rows:
            daily.setdefault(r["started_at"][:10], []).append(r)
        return {
            "days": days,
            "since": since,
            "timezone": "UTC",
            "totals": self._aggregate(rows, days),
            "users": [
                {
                    "user_id": u,
                    **self._aggregate([r for r in rows if r["user_id"] == u], days),
                }
                for u in users
            ],
            "models": [
                {
                    "model": m,
                    **self._aggregate([r for r in rows if r["model"] == m], days),
                }
                for m in models
            ],
            "daily": [
                {
                    "date": (point - timedelta(days=n)).date().isoformat(),
                    **self._aggregate(
                        daily.get((point - timedelta(days=n)).date().isoformat(), []),
                        days,
                    ),
                }
                for n in reversed(range(days))
            ],
        }

    def _aggregate(self, entries, days):
        known = [
            r
            for r in entries
            if r["input_tokens"] is not None and r["output_tokens"] is not None
        ]
        priced = [r for r in entries if r["cost_usd"] is not None]
        tokens = sum((r["input_tokens"] + r["output_tokens"] for r in known))
        total = sum((Decimal(r["cost_usd"]) for r in priced), Decimal(0))
        return {
            "requests": len(entries),
            "known_usage_requests": len(known),
            "unknown_usage_requests": len(entries) - len(known),
            "input_tokens": sum((r["input_tokens"] for r in known)),
            "output_tokens": sum((r["output_tokens"] for r in known)),
            "cached_tokens": sum((r["cached_tokens"] or 0 for r in known)),
            "total_tokens": tokens,
            "average_tokens_per_day": round(tokens / days, 2),
            "average_requests_per_day": round(len(entries) / days, 2),
            "estimated_cost_usd": str(total),
            "average_cost_usd_per_day": str(total / Decimal(days)),
            "unpriced_requests": len(entries) - len(priced),
        }

    def _usage_counts(self, usage):

        def count(name, default=None):
            value = (
                usage.get(name, default)
                if isinstance(usage, dict)
                else getattr(usage, name, default) if usage is not None else default
            )
            return (
                value
                if isinstance(value, int)
                and (not isinstance(value, bool))
                and (value >= 0)
                else None
            )

        inputs, outputs = (count("input_tokens"), count("output_tokens"))

        def detail(parent, key):
            entry = (
                usage.get(parent)
                if isinstance(usage, dict)
                else getattr(usage, parent, None)
            )
            return (
                entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
            )

        cached = detail("input_tokens_details", "cached_tokens")
        reasoning = detail("output_tokens_details", "reasoning_tokens")
        cached = (
            cached
            if isinstance(cached, int)
            and (not isinstance(cached, bool))
            and (cached >= 0)
            else 0 if inputs is not None else None
        )
        reasoning = (
            reasoning
            if isinstance(reasoning, int)
            and (not isinstance(reasoning, bool))
            and (reasoning >= 0)
            else None
        )
        if inputs is not None and cached is not None and (cached > inputs):
            cached = None
        return (inputs, outputs, cached, reasoning)

    def _observation_cost(self, db, row, inputs, outputs, cached):
        price = (
            db.execute(
                "SELECT * FROM model_prices WHERE id=?", (row["price_id"],)
            ).fetchone()
            if row["price_id"]
            else None
        )
        cost = None
        if (
            price
            and inputs is not None
            and (outputs is not None)
            and (cached is not None)
        ):
            cost = str(
                (
                    Decimal(inputs - cached) * Decimal(price["input_per_million"])
                    + Decimal(cached) * Decimal(price["cached_per_million"])
                    + Decimal(outputs) * Decimal(price["output_per_million"])
                )
                / Decimal(1000000)
            )
        return cost
