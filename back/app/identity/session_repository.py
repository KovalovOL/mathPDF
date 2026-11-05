from app.core.ports import PersistencePort

"""Owner/session persistence. Raw tokens are never stored."""

from uuid import uuid4


class SessionRepository:
    def __init__(self, context: PersistencePort):
        self._context = context

    def find_session(self, digest: str, now: int) -> dict | None:
        with self._context.connection() as db:
            row = db.execute(
                """SELECT u.id,u.email,u.name,COALESCE(r.role,'free') AS role FROM users u
                LEFT JOIN user_roles r ON r.user_id=u.id JOIN sessions s ON s.user_id=u.id
                WHERE s.token_hash=? AND s.expires_at>?""",
                (digest, now),
            ).fetchone()
        return dict(row) if row else None

    def revoke(self, digest: str) -> None:
        with self._context.connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))

    def store_flow(self, values: tuple, previous: str | None, now: int) -> None:
        with self._context.connection() as db:
            db.execute("DELETE FROM oauth_flows WHERE expires_at<=?", (now,))
            if previous:
                db.execute("DELETE FROM oauth_flows WHERE cookie_hash=?", (previous,))
            db.execute("INSERT INTO oauth_flows VALUES (?,?,?,?,?,?)", values)

    def consume_flow(self, digest: str) -> dict | None:
        with self._context.connection() as db:
            row = db.execute(
                "DELETE FROM oauth_flows WHERE cookie_hash=? RETURNING *", (digest,)
            ).fetchone()
        return dict(row) if row else None

    def create(
        self,
        claims: dict,
        name: str,
        digest: str,
        previous: str | None,
        now: int,
        stamp: str,
        lifetime: int,
    ) -> str:
        with self._context.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """INSERT INTO users VALUES (?,?,?,?,?,?) ON CONFLICT(google_sub)
                DO UPDATE SET email=excluded.email,name=excluded.name,updated_at=excluded.updated_at""",
                (uuid4().hex, claims["sub"], claims["email"], name, stamp, stamp),
            )
            user = db.execute(
                "SELECT id FROM users WHERE google_sub=?", (claims["sub"],)
            ).fetchone()
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            if previous:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (previous,))
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (digest, user["id"], now + lifetime, now),
            )
        return user["id"]
