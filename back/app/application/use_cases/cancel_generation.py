class CancelGeneration:
    def __init__(self, jobs):
        self._jobs = jobs

    async def execute(self, owner: str, job_id: str):
        return await self._jobs.cancel(job_id, owner)
