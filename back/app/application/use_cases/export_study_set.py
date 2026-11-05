import asyncio
from urllib.parse import quote
from app.core.errors import ApplicationError
from app.study.contract import StudySet


class ExportStudySet:
    def __init__(self, validator, exporter, lock):
        self._validator, self._exporter, self._lock = validator, exporter, lock

    async def execute(self, result: StudySet, owner: str) -> tuple[bytes, str]:
        await asyncio.to_thread(self._validator.execute, result, owner)
        if self._lock.locked():
            raise ApplicationError(
                409, "A PDF export is already running. Wait for it to finish."
            )
        async with self._lock:
            try:
                data = await asyncio.wait_for(
                    self._exporter(result.model_dump(mode="json")), timeout=90
                )
            except TimeoutError:
                raise ApplicationError(
                    504, "PDF export timed out. Try a smaller set."
                ) from None
        filename = quote(
            result.title.replace("/", "-").replace("\\", "-") + ".pdf", safe=""
        )
        return data, filename
