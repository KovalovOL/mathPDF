from app.administration.ports import AdministrationReadPort


class GetAdminDashboard:
    def __init__(self, queries: AdministrationReadPort):
        self._queries = queries

    def execute(self) -> dict:
        return self._queries.overview()
