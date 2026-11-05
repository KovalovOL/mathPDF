import asyncio
from app.core.errors import ApplicationError


class StartGeneration:
    def __init__(self, usage, jobs, provider):
        self._usage, self._jobs, self._provider = usage, jobs, provider

    async def execute(self, owner: str, selection):
        if self._provider is None:
            raise ApplicationError(
                503, "The generation service is unavailable. Try again later."
            )
        await asyncio.to_thread(self._usage.quota.check, owner)
        return await self._jobs.start(owner, selection, self._provider)
