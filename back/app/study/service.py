"""Canonical read projection over historical and current saved sets."""

from app.study.contract import StudySet
from app.study.ports import StudyRepositoryPort


class StudyQuery:
    def __init__(self, repository: StudyRepositoryPort):
        self._repository = repository

    def list(self, owner_id: str) -> list[dict]:
        return self._repository.sets(owner_id)

    def get(self, identifier: str, owner_id: str) -> StudySet:
        return StudySet.model_validate(self._repository.study_set(identifier, owner_id))
