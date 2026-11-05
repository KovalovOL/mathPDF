import asyncio
from app.reports.models import ReportInput


class RecordIncident:
    def __init__(self, users, reports):
        self._users = users
        self._reports = reports

    async def execute(self, job, selection, exception, details):
        user = await asyncio.to_thread(self._users.user_identity, job.owner_id)
        report = ReportInput(
            origin="automatic",
            request_id=job.request_id,
            context={
                "server": {
                    "job_id": job.id,
                    "error": job.error,
                    "exception": exception,
                    "error_details": details,
                    "selection": selection.model_dump(mode="json"),
                }
            },
        )
        return await asyncio.to_thread(self._reports.record, user, report)
