from datetime import datetime, timezone


def initialize_base(context):
    with context.connection() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("BEGIN IMMEDIATE")
        context.db.initialize(connection)
        document_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(documents)")
        }
        set_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(study_sets)")
        }
        if (
            document_columns
            and "owner_id" not in document_columns
            or (set_columns and "owner_id" not in set_columns)
        ):
            raise ValueError(
                "Legacy unowned data requires an explicit ownership migration; no data was changed."
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users (\n                    id TEXT PRIMARY KEY, google_sub TEXT UNIQUE NOT NULL,\n                    email TEXT NOT NULL, name TEXT NOT NULL,\n                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL\n                )"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS documents (\n                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),\n                    filename TEXT NOT NULL, sha256 TEXT NOT NULL,\n                    media_type TEXT NOT NULL, page_count INTEGER, size INTEGER NOT NULL,\n                    stored_name TEXT NOT NULL, created_at TEXT NOT NULL,\n                    UNIQUE(owner_id, sha256)\n                )"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS study_sets (\n                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),\n                    title TEXT NOT NULL, mode TEXT NOT NULL,\n                    item_count INTEGER NOT NULL, payload TEXT NOT NULL,\n                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL\n                )"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS study_sets_owner ON study_sets(owner_id, updated_at)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS document_edits (\n                document_id TEXT PRIMARY KEY REFERENCES documents(id),\n                owner_id TEXT NOT NULL REFERENCES users(id),\n                original_document_id TEXT NOT NULL REFERENCES documents(id),\n                revision INTEGER NOT NULL, payload TEXT NOT NULL,\n                UNIQUE(owner_id,original_document_id))"
        )


def initialize_identity(context):
    with context.connection() as connection:
        connection.executescript(
            "\n                CREATE TABLE IF NOT EXISTS sessions (\n                    token_hash TEXT PRIMARY KEY,\n                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,\n                    expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL\n                );\n                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);\n                CREATE TABLE IF NOT EXISTS oauth_flows (\n                    cookie_hash TEXT PRIMARY KEY, state_hash TEXT NOT NULL,\n                    nonce TEXT NOT NULL, verifier TEXT NOT NULL,\n                    next_path TEXT NOT NULL, expires_at INTEGER NOT NULL\n                );\n            "
        )


def initialize_roles(context):
    from app.identity.role_models import OWNER_EMAIL
    from app.identity.role_repository import RoleRepository

    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.executescript(
            "CREATE TABLE IF NOT EXISTS user_roles (\n                user_id TEXT PRIMARY KEY REFERENCES users(id),role TEXT NOT NULL,\n                updated_at TEXT NOT NULL);\n                CREATE UNIQUE INDEX IF NOT EXISTS single_owner ON user_roles(role) WHERE role='owner';\n                CREATE TABLE IF NOT EXISTS role_audit (\n                id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,target_id TEXT NOT NULL,\n                old_role TEXT NOT NULL,new_role TEXT NOT NULL,created_at TEXT NOT NULL);\n                CREATE TABLE IF NOT EXISTS admin_audit (id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);"
        )
        candidate = db.execute(
            "SELECT id FROM users WHERE LOWER(email)=? ORDER BY updated_at DESC LIMIT 1",
            (OWNER_EMAIL,),
        ).fetchone()
        if candidate:
            RoleRepository.bootstrap_owner(db, candidate["id"])


def initialize_library(context):
    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS library_folders (\n                id TEXT PRIMARY KEY,owner_id TEXT NOT NULL REFERENCES users(id),\n                name TEXT NOT NULL,name_key TEXT NOT NULL,parent_id TEXT REFERENCES library_folders(id))"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS folder_siblings\n                ON library_folders(owner_id,COALESCE(parent_id,''),name_key)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS library_items (\n                owner_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,item_id TEXT NOT NULL,\n                folder_id TEXT REFERENCES library_folders(id),archived INTEGER NOT NULL DEFAULT 0,\n                PRIMARY KEY(owner_id,kind,item_id))"
        )
        for table, kind in [("documents", "documents"), ("study_sets", "study-sets")]:
            context.db.cleanup_trigger(db, table, kind)


def initialize_usage(context):
    from app.usage.repository import PRICING_SOURCE

    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.executescript(
            "CREATE TABLE IF NOT EXISTS model_prices (\n                id TEXT PRIMARY KEY,provider TEXT NOT NULL,model TEXT NOT NULL,effective_at TEXT NOT NULL,\n                input_per_million TEXT NOT NULL,cached_per_million TEXT NOT NULL,output_per_million TEXT NOT NULL,\n                source TEXT NOT NULL,created_by TEXT);\n                CREATE TABLE IF NOT EXISTS ai_usage (\n                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,\n                job_id TEXT,provider TEXT NOT NULL,model TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,\n                status TEXT NOT NULL,input_tokens BIGINT,cached_tokens BIGINT,output_tokens BIGINT,reasoning_tokens BIGINT,\n                duration_ms BIGINT,provider_request_id TEXT,price_id TEXT,cost_usd TEXT,context TEXT NOT NULL);\n                CREATE INDEX IF NOT EXISTS ai_usage_user_time ON ai_usage(user_id,started_at);\n                CREATE INDEX IF NOT EXISTS ai_usage_time ON ai_usage(started_at);"
        )
        for model in ["gpt-4.1-mini", "gpt-4.1-mini-2025-04-14"]:
            db.execute(
                "INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    "openai-standard-2026-10-28-" + model,
                    "openai",
                    model,
                    "2026-10-28T00:00:00+00:00",
                    "0.40",
                    "0.10",
                    "1.60",
                    PRICING_SOURCE,
                    None,
                ),
            )


def initialize_quotas(context):
    from app.usage.quotas import DEFAULT_DAILY_TOKENS

    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS generation_limits (\n                scope TEXT PRIMARY KEY,monthly_tokens BIGINT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT)"
        )
        columns = {
            r["name"] for r in db.execute("PRAGMA table_info(generation_limits)")
        }
        if "daily_tokens" not in columns:
            db.execute("ALTER TABLE generation_limits ADD COLUMN daily_tokens BIGINT")
        db.execute(
            "CREATE TABLE IF NOT EXISTS generation_reservations (\n                attempt_id TEXT PRIMARY KEY REFERENCES ai_usage(id),user_id TEXT NOT NULL REFERENCES users(id),\n                period_start TEXT NOT NULL,tokens BIGINT NOT NULL,state TEXT NOT NULL)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS generation_reservations_user ON generation_reservations(user_id,period_start)"
        )
        db.execute(
            "INSERT INTO generation_limits (scope,monthly_tokens,updated_at,updated_by,daily_tokens)\n                VALUES (?,?,?,?,?) ON CONFLICT(scope) DO NOTHING",
            (
                "default",
                DEFAULT_DAILY_TOKENS,
                datetime.now(timezone.utc).isoformat(),
                None,
                DEFAULT_DAILY_TOKENS,
            ),
        )


def initialize_reviews(context):
    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS review_rounds (\n                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),set_id TEXT NOT NULL,\n                content_hash TEXT NOT NULL,item_count INTEGER NOT NULL,created_at TEXT NOT NULL,completed_at TEXT)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS review_rounds_deck ON review_rounds(user_id,set_id,content_hash,created_at)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS review_answers (\n                round_id TEXT NOT NULL REFERENCES review_rounds(id) ON DELETE CASCADE,\n                item_index INTEGER NOT NULL,correct INTEGER NOT NULL,answered_at TEXT NOT NULL,\n                PRIMARY KEY(round_id,item_index))"
        )


def initialize_reports(context):
    with context.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.executescript(
            "CREATE TABLE IF NOT EXISTS request_events (\n                id TEXT PRIMARY KEY,user_id TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL);\n                CREATE INDEX IF NOT EXISTS request_events_user_time ON request_events(user_id,created_at);\n                CREATE INDEX IF NOT EXISTS request_events_time ON request_events(created_at);\n                CREATE TABLE IF NOT EXISTS reports (\n                id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),origin TEXT NOT NULL,category TEXT NOT NULL,\n                comment TEXT NOT NULL,request_id TEXT,dedupe_key TEXT UNIQUE NOT NULL,status TEXT NOT NULL,\n                collection_status TEXT NOT NULL,attempts INTEGER NOT NULL,next_attempt TEXT NOT NULL,\n                created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL,manifest TEXT NOT NULL,\n                note TEXT NOT NULL DEFAULT '');\n                CREATE INDEX IF NOT EXISTS reports_user_time ON reports(user_id,created_at);\n                CREATE INDEX IF NOT EXISTS reports_collection ON reports(collection_status,next_attempt);"
        )


def initialize(context):
    with context.db.schema_lock():
        initialize_base(context)
        initialize_roles(context)
        initialize_identity(context)
        initialize_library(context)
        initialize_usage(context)
        initialize_quotas(context)
        initialize_reviews(context)
        initialize_reports(context)
