from app.administration.ports import AdministrationReadPort
from app.usage.ports import UsageReadPort, AllowancePort


class GetAdminUser:
    def __init__(
        self,
        queries: AdministrationReadPort,
        usage: UsageReadPort,
        allowance: AllowancePort,
    ):
        self._queries, self._usage, self._allowance = queries, usage, allowance

    def execute(self, identifier: str) -> dict:
        result = self._queries.user_details(identifier)
        result["allowance"] = self._allowance.status(identifier)
        result["usage"] = {
            str(days): self._usage.dashboard(days, identifier) for days in (1, 7, 30)
        }
        return result
