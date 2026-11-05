"""Synchronous HTTP generation shares admission with background jobs."""

from app.core.errors import ApplicationError


class GenerateStudyNow:
    def __init__(self, generator, provider, lock):
        self._generator, self._provider, self._lock = generator, provider, lock

    async def execute(self, owner: str, selection):
        if self._provider is None:
            raise ApplicationError(
                503, "The generation service is unavailable. Try again later."
            )
        if self._lock.locked():
            raise ApplicationError(
                409, "A generation request is already running. Wait for it to finish."
            )
        async with self._lock:
            return await self._generator.execute(owner, selection, self._provider)
