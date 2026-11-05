from app.reports.ports import ReportRepositoryPort, ReportBundlePort

"""Public report operations and the cancellable collection lifecycle."""

import asyncio
import logging
from app.core.observability.diagnostics import error_identity
from app.reports.models import ReportInput, ReportUpdate


class Reports:
    def __init__(
        self, repository: ReportRepositoryPort, collector, bundles: ReportBundlePort
    ):
        self._repository, self._collector, self._bundles = (
            repository,
            collector,
            bundles,
        )

    @property
    def spool(self):
        return self._repository.spool

    def event(self, user, event) -> None:
        self._repository.event(user, event)

    def record(
        self, user, request: ReportInput, spool_on_failure=True, **options
    ) -> dict:
        return self._repository.record(user, request, spool_on_failure, **options)

    def flush_spool(self) -> None:
        self._repository.flush_spool()

    def collect_one(self) -> bool:
        return self._collector.execute()

    def list(self, limit=100, offset=0, status=None) -> list[dict]:
        return self._repository.list(limit, offset, status)

    def get(self, identifier: str) -> dict:
        return self._repository.get(identifier)

    def update(self, identifier: str, request: ReportUpdate, actor) -> dict:
        return self._repository.update(identifier, request, actor)

    def bundle(self, identifier: str) -> bytes:
        return self._bundles.export(self._repository.get(identifier))

    async def worker(self) -> None:
        while True:
            try:
                if not await asyncio.to_thread(self.collect_one):
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "Report worker unavailable",
                    extra={
                        "event": "report.worker_unavailable",
                        **error_identity(error),
                    },
                )
                await asyncio.sleep(5)
