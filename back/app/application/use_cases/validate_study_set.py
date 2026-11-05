from app.study.contract import StudySet
from app.study.policies import validate_study


class ValidateStudySet:
    def __init__(self, sets, documents):
        self._sets, self._documents = sets, documents

    def execute(self, result: StudySet, owner: str):
        self._sets.check_set_owner(result.id, owner)
        result.document = self._documents.document(result.document.id, owner)
        if not result.document.page_count or any(
            (p < 1 or p > result.document.page_count for p in result.pages)
        ):
            raise ValueError("The study set contains invalid source pages.")
        if len(set(result.pages)) != len(result.pages):
            raise ValueError("The study set repeats a source page.")
        for entry in result.context_documents:
            entry.document = self._documents.document(entry.document.id, owner)
            if entry.pages is not None and (
                not entry.document.page_count
                or any((p < 1 or p > entry.document.page_count for p in entry.pages))
            ):
                raise ValueError("The study set contains invalid context pages.")
        validate_study(result, result.mode, result.document.id, result.pages)
        if not result.items:
            raise ValueError("There are no study items to save or export.")
