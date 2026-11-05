from app.core.runtime import UtcClock, RandomIdentifiers
from sqlite3 import OperationalError
from psycopg import OperationalError as PostgresOperationalError, InterfaceError
from app.core.journal import DurableJournal
from app.usage.repository import UsageRepository
from app.usage.service import Usage
from app.usage.quotas import GenerationQuota


def create_usage(persistence):
    quota = GenerationQuota(persistence)
    journal = DurableJournal(
        persistence.directory / "usage-spool",
        (OperationalError, PostgresOperationalError, InterfaceError),
    )
    return Usage(
        UsageRepository(persistence, quota, RandomIdentifiers()),
        quota,
        journal,
        UtcClock(),
    )
