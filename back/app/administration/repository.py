from app.core.ports import PersistencePort
from datetime import datetime, timezone
import json
from uuid import uuid4
from app.usage.models import PriceInput


class AdministrationQueries:
    def __init__(self, context: PersistencePort):
        self._context = context

    def overview(self):
        with self._context.connection() as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            roles = [
                dict(r)
                for r in db.execute(
                    "SELECT COALESCE(r.role,'free') AS role,COUNT(*) AS count FROM users u LEFT JOIN user_roles r ON r.user_id=u.id GROUP BY COALESCE(r.role,'free')"
                )
            ]
            report_counts = [
                dict(r)
                for r in db.execute(
                    "SELECT status,COUNT(*) AS count FROM reports GROUP BY status"
                )
            ]
            start = db.execute(
                "SELECT MIN(started_at) AS start FROM ai_usage"
            ).fetchone()["start"]
        return {
            "users": count,
            "roles": roles,
            "reports": report_counts,
            "tracking_since": start,
            "history_note": "Earlier AI calls did not record actual token usage. Their token counts and costs are unavailable.",
        }

    def users(self, q: str = "", offset: int = 0):
        if offset < 0 or len(q) > 200:
            raise ValueError("Invalid user search.")
        with self._context.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT u.id,u.email,u.name,u.created_at,u.updated_at,COALESCE(r.role,'free') AS role,\n                (SELECT COUNT(*) FROM documents d WHERE d.owner_id=u.id) AS file_count,\n                (SELECT COUNT(*) FROM study_sets s WHERE s.owner_id=u.id) AS set_count,\n                (SELECT MAX(e.created_at) FROM request_events e WHERE e.user_id=u.id) AS last_activity\n                FROM users u LEFT JOIN user_roles r ON r.user_id=u.id\n                WHERE LOWER(u.email) LIKE ? OR LOWER(u.name) LIKE ? ORDER BY u.created_at DESC,u.id LIMIT 200 OFFSET ?",
                    ("%" + q.casefold() + "%", "%" + q.casefold() + "%", offset),
                )
            ]

    def user_details(self, identifier: str):
        with self._context.connection() as db:
            row = db.execute(
                "SELECT u.id,u.email,u.name,u.created_at,u.updated_at,COALESCE(r.role,'free') AS role FROM users u LEFT JOIN user_roles r ON r.user_id=u.id WHERE u.id=?",
                (identifier,),
            ).fetchone()
            if not row:
                raise KeyError("User not found")
            files = [
                dict(r)
                for r in db.execute(
                    "SELECT id,filename,size,page_count FROM documents WHERE owner_id=? ORDER BY created_at DESC",
                    (identifier,),
                )
            ]
            sets = [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,mode,item_count,updated_at FROM study_sets WHERE owner_id=? ORDER BY updated_at DESC",
                    (identifier,),
                )
            ]
        return {
            "user": dict(row),
            "files": files,
            "sets": sets,
        }

    def prices(self):
        with self._context.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM model_prices ORDER BY effective_at DESC,provider,model"
                )
            ]

    def new_price(self, actor_id: str, price: PriceInput):
        identifier = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._context.connection() as db:
            db.execute(
                "INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    price.provider,
                    price.model,
                    now,
                    str(price.input_per_million),
                    str(price.cached_per_million),
                    str(price.output_per_million),
                    price.source,
                    actor_id,
                ),
            )
            db.execute(
                "INSERT INTO admin_audit VALUES (?,?,?,?,?)",
                (
                    uuid4().hex,
                    actor_id,
                    "price_add",
                    json.dumps({"id": identifier, "model": price.model}),
                    now,
                ),
            )
        return {"id": identifier, "effective_at": now}
