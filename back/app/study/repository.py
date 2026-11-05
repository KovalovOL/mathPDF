from app.core.ports import PersistencePort
import json
from datetime import datetime, timezone


class StudySetRepository:
    def __init__(self, context: PersistencePort):
        self._context = context

    def save_set(self, result: dict, owner_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with self._context.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO study_sets
                (id,owner_id,title,mode,item_count,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, mode=excluded.mode,
                item_count=excluded.item_count, payload=excluded.payload, updated_at=excluded.updated_at
                WHERE study_sets.owner_id=excluded.owner_id""",
                (
                    result["id"],
                    owner_id,
                    result["title"],
                    result["mode"],
                    len(result["items"]),
                    json.dumps(result, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("Study set not found")
        return result

    def sets(self, owner_id: str) -> list[dict]:
        with self._context.connection() as connection:
            rows = connection.execute(
                """SELECT id,title,mode,item_count,created_at,updated_at
                                      FROM study_sets WHERE owner_id=? ORDER BY updated_at DESC""",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def check_set_owner(self, identifier: str, owner_id: str):
        """Allow a new unsaved ID, but never reuse another account's saved ID."""
        with self._context.connection() as connection:
            foreign = connection.execute(
                "SELECT 1 FROM study_sets WHERE id=? AND owner_id<>?",
                (identifier, owner_id),
            ).fetchone()
        if foreign:
            raise KeyError("Study set not found")

    def study_set(self, identifier: str, owner_id: str) -> dict:
        with self._context.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM study_sets WHERE id=? AND owner_id=?",
                (identifier, owner_id),
            ).fetchone()
        if row is None:
            raise KeyError("Study set not found")
        return json.loads(row["payload"])
