"""Atomic local JSON persistence. The document hash isolates workspaces."""

import json
import os
import tempfile
import threading
from pathlib import Path
from .models import Formula, Review


class FormulaStore:
    def __init__(self, directory: Path, document_sha256: str):
        self.directory = directory / document_sha256
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "formulas.json"
        self.document_sha256 = document_sha256
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Formula]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text())
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported formula-store schema version")
        return {k: Formula.model_validate(v) for k, v in data["formulas"].items()}

    def _write(self, records: dict[str, Formula]) -> None:
        data = {"schema_version": 1, "document_sha256": self.document_sha256,
                "formulas": {k: v.model_dump(mode="json") for k, v in records.items()}}
        fd, name = tempfile.mkstemp(dir=self.directory, prefix=".formulas-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def list(self) -> list[Formula]:
        with self._lock:
            return list(self._read().values())

    def get(self, identifier: str) -> Formula:
        with self._lock:
            try:
                return self._read()[identifier]
            except KeyError:
                raise KeyError("Formula not found") from None

    def add(self, formula: Formula) -> Formula:
        if formula.source.document_sha256 != self.document_sha256:
            raise ValueError("Formula belongs to a different document")
        with self._lock:
            records = self._read()
            if formula.id in records:
                raise ValueError("A formula with this identifier already exists")
            if formula.original_id and formula.original_id not in records:
                raise ValueError("The original formula must be saved first")
            records[formula.id] = formula.model_copy(deep=True)
            self._write(records)
        return formula

    def review(self, identifier: str, review: Review) -> Formula:
        with self._lock:
            records = self._read()
            if identifier not in records:
                raise KeyError("Formula not found")
            records[identifier].review = review
            self._write(records)
            return records[identifier]
