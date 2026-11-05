"""Default technical time and identifier implementations, without business policy."""

from datetime import datetime, timezone
from uuid import uuid4


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class RandomIdentifiers:
    def new_id(self) -> str:
        return uuid4().hex
