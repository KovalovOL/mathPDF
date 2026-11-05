from datetime import datetime

"""Narrow technical boundaries shared by repository implementations."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol


class ConnectionPort(Protocol):
    def execute(self, statement: str, parameters=()) -> Any: ...
    def executemany(self, statement: str, parameters) -> Any: ...


class UnitOfWorkPort(Protocol):
    def connection(self) -> AbstractContextManager[ConnectionPort]: ...


class BinaryStoragePort(Protocol):
    def path(self, key: str, expected_sha: str | None = None) -> Path: ...
    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str: ...
    def copy(
        self, source: str, target: str, expected_sha: str | None = None
    ) -> Any: ...
    def delete(self, key: str) -> None: ...


class PersistencePort(UnitOfWorkPort, Protocol):
    @property
    def directory(self) -> Path: ...
    @property
    def storage(self) -> BinaryStoragePort: ...


class ClockPort(Protocol):
    def now(self) -> "datetime": ...


class IdentifierPort(Protocol):
    def new_id(self) -> str: ...


class ObservationJournalPort(Protocol):
    @property
    def directory(self) -> Path: ...
    def execute(self, operation: str, method, args: tuple, kwargs: dict) -> Any: ...
    def replay(self, operations: dict) -> None: ...
