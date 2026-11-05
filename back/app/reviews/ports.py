from typing import Protocol
from app.reviews.models import ReviewAnswer


class ReviewRepositoryPort(Protocol):
    def start_round(
        self,
        user_id: str,
        set_id: str,
        content: dict,
        digest: str,
        new_round: bool = False,
    ) -> dict: ...
    def answer(self, user_id: str, round_id: str, answer: ReviewAnswer) -> dict: ...
