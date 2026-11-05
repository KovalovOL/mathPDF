from app.reviews.ports import ReviewRepositoryPort
from app.reviews.models import ReviewAnswer
from app.reviews.policies import fingerprint


class Reviews:
    def __init__(self, repository: ReviewRepositoryPort):
        self._repository = repository

    def start(self, user_id: str, set_id: str, content: dict, new_round=False) -> dict:
        if content["mode"] != "flashcards" or not content["items"]:
            raise ValueError("Choose a nonempty flashcard set.")
        return self._repository.start_round(
            user_id, set_id, content, fingerprint(content), new_round
        )

    def answer(self, user_id: str, round_id: str, answer: ReviewAnswer) -> dict:
        return self._repository.answer(user_id, round_id, answer)
