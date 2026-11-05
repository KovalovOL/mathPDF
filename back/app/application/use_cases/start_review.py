from app.core.observability.diagnostics import REQUEST_ID
from app.study.contract import StudySet
from app.reviews.models import ReviewStart


class StartReview:
    def __init__(self, reviews, sets, documents):
        self._reviews, self._sets, self._documents = reviews, sets, documents

    def execute(self, owner: str, identifier: str, data: ReviewStart):
        if not REQUEST_ID.fullmatch(identifier):
            raise ValueError("Invalid study set identifier.")
        if data.content is None:
            content = StudySet.model_validate(
                self._sets.study_set(identifier, owner)
            ).model_dump(mode="json")
        else:
            if len(__import__("json").dumps(data.content)) > 2 * 1024 * 1024:
                raise ValueError("The review content is too large.")
            candidate = StudySet.model_validate(data.content)
            if candidate.id != identifier:
                raise ValueError("The review content does not match this set.")
            self._sets.check_set_owner(identifier, owner)
            self._documents.document(candidate.document.id, owner)
            content = candidate.model_dump(mode="json")
        return self._reviews.start(owner, identifier, content, data.new_round)
