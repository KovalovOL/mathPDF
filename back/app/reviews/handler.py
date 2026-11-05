from fastapi import Request
from app.reviews.models import ReviewStart, ReviewAnswer


class ReviewsHandler:
    def __init__(self, reviews, start):
        self._reviews, self._start = reviews, start

    def register(self, router):
        router.add_api_route(
            "/api/study-sets/{identifier}/reviews", self.review_start, methods=["POST"]
        )
        router.add_api_route(
            "/api/reviews/{identifier}/answers", self.review_answer, methods=["POST"]
        )

    def review_start(self, request: Request, identifier: str, data: ReviewStart):
        return self._start.execute(request.state.user.id, identifier, data)

    def review_answer(self, request: Request, identifier: str, data: ReviewAnswer):
        return self._reviews.answer(request.state.user.id, identifier, data)
