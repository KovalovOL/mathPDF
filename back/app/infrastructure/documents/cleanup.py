import json, logging
from botocore.exceptions import BotoCoreError, ClientError


class BinaryCleanup:
    def __init__(self, context):
        self._context = context

    def execute(self, stored_names: list[str]):
        # Protect an identical file re-uploaded between commit and cleanup.
        try:
            with self._context.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                report_columns = {
                    r["name"] for r in connection.execute("PRAGMA table_info(reports)")
                }
                pinned = {}
                if report_columns:
                    for row in connection.execute(
                        "SELECT manifest FROM reports WHERE collection_status<>'ready'"
                    ):
                        pinned.update(
                            {
                                source["stored_name"]: source["sha256"]
                                for source in json.loads(row["manifest"]).get(
                                    "sources", []
                                )
                            }
                        )
                for stored_name in stored_names:
                    if not connection.execute(
                        "SELECT 1 FROM documents WHERE stored_name=?", (stored_name,)
                    ).fetchone():
                        if stored_name in pinned:
                            self._context.storage.retain(
                                "documents/" + stored_name,
                                "report-source-cache/" + stored_name,
                                pinned[stored_name],
                            )
                        else:
                            self._context.storage.delete("documents/" + stored_name)
                            self._context.storage.delete(
                                "report-source-cache/" + stored_name
                            )
        except (OSError, ValueError, BotoCoreError, ClientError):
            logging.getLogger(__name__).warning(
                "Deleted document binary cleanup deferred"
            )
