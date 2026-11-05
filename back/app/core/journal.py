"""Durable, bounded-batch replay of named technical observations."""

import json
import logging
from pathlib import Path
from time import time_ns
from uuid import uuid4
from app.core.serialization import sanitize


class DurableJournal:
    def __init__(self, directory: Path, transient_errors: tuple[type[Exception], ...]):
        self._directory, self._transient_errors = directory, transient_errors
        directory.mkdir(exist_ok=True)

    @property
    def directory(self) -> Path:
        return self._directory

    def execute(self, operation: str, method, args: tuple, kwargs: dict):
        try:
            return method(*args, **kwargs)
        except self._transient_errors:
            self._queue(operation, args, kwargs)

    def replay(self, operations: dict) -> None:
        for path in sorted(self._directory.glob("*.json"))[:100]:
            payload = json.loads(path.read_text())
            method = operations.get(payload["operation"])
            if method is None:
                raise ValueError("Invalid usage observation.")
            method(*payload["args"], **payload["kwargs"])
            path.unlink()

    def _queue(self, operation, args, kwargs):
        payload = sanitize(
            {
                "operation": operation,
                "args": self._serial(args),
                "kwargs": self._serial(kwargs),
            }
        )
        target = self._directory / (str(time_ns()) + "-" + uuid4().hex + ".json")
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False))
        temporary.chmod(0o600)
        temporary.replace(target)
        logging.getLogger(__name__).warning(
            "Usage observation durably queued operation=%s attempt=%s",
            operation,
            args[0],
        )

    def _serial(self, value):
        if isinstance(value, dict):
            return {k: self._serial(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serial(v) for v in value]
        if hasattr(value, "model_dump"):
            return self._serial(value.model_dump())
        if hasattr(value, "__dict__"):
            return self._serial(vars(value))
        return value
