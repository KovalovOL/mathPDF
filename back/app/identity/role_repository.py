from app.core.ports import PersistencePort

"""Atomic role persistence and audit writes."""

from uuid import uuid4
from datetime import datetime, timezone
from app.core.errors import ApplicationError
from app.identity.role_models import OWNER_EMAIL


def now():
    return datetime.now(timezone.utc).isoformat()


class RoleRepository:
    def __init__(self, workspace: PersistencePort):
        self._persistence = workspace

    @staticmethod
    def bootstrap_owner(db, identifier):
        current = db.execute(
            "SELECT user_id FROM user_roles WHERE role='owner'"
        ).fetchone()
        if current:
            return
        db.execute(
            """INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id)
            DO UPDATE SET role=excluded.role,updated_at=excluded.updated_at""",
            (identifier, "owner", now()),
        )

    def verified_login(self, identifier, email):
        with self._persistence.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if email.casefold() == OWNER_EMAIL:
                self.bootstrap_owner(db, identifier)
            else:
                db.execute(
                    "INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING",
                    (identifier, "free", now()),
                )

    def role(self, identifier):
        with self._persistence.connection() as db:
            row = db.execute(
                "SELECT role FROM user_roles WHERE user_id=?", (identifier,)
            ).fetchone()
        return row["role"] if row else "free"

    def change(self, actor, target, new_role):
        with self._persistence.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            role = db.execute(
                "SELECT role FROM user_roles WHERE user_id=?", (actor.id,)
            ).fetchone()
            if not role or role["role"] != "owner":
                raise ApplicationError(403, "Only the owner can change account roles.")
            if not db.execute("SELECT 1 FROM users WHERE id=?", (target,)).fetchone():
                raise KeyError("User not found")
            old = db.execute(
                "SELECT role FROM user_roles WHERE user_id=?", (target,)
            ).fetchone()
            old_role = old["role"] if old else "free"
            if old_role == "owner":
                raise ApplicationError(400, "Owner access cannot be changed here.")
            if new_role not in {"free", "premium", "admin"}:
                raise ValueError("Invalid account role.")
            stamp = now()
            db.execute(
                """INSERT INTO user_roles VALUES (?,?,?) ON CONFLICT(user_id)
                DO UPDATE SET role=excluded.role,updated_at=excluded.updated_at""",
                (target, new_role, stamp),
            )
            db.execute(
                "INSERT INTO role_audit VALUES (?,?,?,?,?,?)",
                (uuid4().hex, actor.id, target, old_role, new_role, stamp),
            )
        return {"user_id": target, "role": new_role}
