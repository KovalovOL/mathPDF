import asyncio
from fastapi import Request
from fastapi.responses import Response
from app.reports.models import ReportUpdate
from app.identity.role_models import RoleChange
from app.usage.quotas import DefaultAllowance, UserAllowance
from app.infrastructure.http.frontend import html_page
from app.usage.models import PriceInput


class AdministrationHandler:
    def __init__(
        self,
        usage,
        reports,
        queries,
        dashboard,
        user_details,
        role_change,
        limit_change,
        tariff_add,
    ):
        self._usage, self._reports, self._queries = usage, reports, queries
        self._dashboard, self._user_details = dashboard, user_details
        self._role_change, self._limit_change, self._tariff_add = (
            role_change,
            limit_change,
            tariff_add,
        )

    def register(self, router):
        router.add_api_route("/admin", self.admin, methods=["GET"])
        router.add_api_route("/api/admin/overview", self.overview, methods=["GET"])
        router.add_api_route("/api/admin/users", self.users, methods=["GET"])
        router.add_api_route(
            "/api/admin/users/{identifier}", self.user_details, methods=["GET"]
        )
        router.add_api_route(
            "/api/admin/users/{identifier}/role", self.role, methods=["PATCH"]
        )
        router.add_api_route(
            "/api/admin/generation-limits", self.generation_limits, methods=["GET"]
        )
        router.add_api_route(
            "/api/admin/generation-limits", self.default_limit, methods=["PATCH"]
        )
        router.add_api_route(
            "/api/admin/users/{identifier}/generation-limit",
            self.individual_limit,
            methods=["PATCH"],
        )
        router.add_api_route("/api/admin/usage", self.metrics, methods=["GET"])
        router.add_api_route("/api/admin/prices", self.prices, methods=["GET"])
        router.add_api_route(
            "/api/admin/prices", self.new_price, methods=["POST"], status_code=201
        )
        router.add_api_route("/api/admin/reports", self.report_list, methods=["GET"])
        router.add_api_route(
            "/api/admin/reports/{identifier}", self.detail, methods=["GET"]
        )
        router.add_api_route(
            "/api/admin/reports/{identifier}", self.update, methods=["PATCH"]
        )
        router.add_api_route(
            "/api/admin/reports/{identifier}/bundle", self.download, methods=["GET"]
        )

    def admin(self):
        return html_page("admin.html")

    def overview(self):
        return self._dashboard.execute()

    def users(self, q: str = "", offset: int = 0):
        return self._queries.users(q, offset)

    def user_details(self, identifier: str):
        return self._user_details.execute(identifier)

    def role(self, request: Request, identifier: str, change: RoleChange):
        return self._role_change.execute(request.state.user, identifier, change.role)

    def generation_limits(self):
        return self._usage.quota.settings()

    def default_limit(self, request: Request, data: DefaultAllowance):
        return self._limit_change.execute(request.state.user, data.daily_tokens)

    def individual_limit(self, request: Request, identifier: str, data: UserAllowance):
        return self._limit_change.execute(
            request.state.user, data.daily_tokens, identifier
        )

    def metrics(self, days: int = 7, user_id: str | None = None):
        if days not in {1, 7, 30}:
            raise ValueError("Choose day, week or month.")
        return self._usage.dashboard(days, user_id)

    def prices(self):
        return self._queries.prices()

    def new_price(self, request: Request, price: PriceInput):
        return self._tariff_add.execute(request.state.user, price)

    def report_list(self, offset: int = 0, status: str | None = None):
        if offset < 0 or status not in {None, "new", "investigating", "resolved"}:
            raise ValueError("Invalid report page.")
        return self._reports.list(offset=offset, status=status)

    def detail(self, identifier: str):
        return self._reports.get(identifier)

    def update(self, request: Request, identifier: str, data: ReportUpdate):
        return self._reports.update(identifier, data, request.state.user)

    async def download(self, identifier: str):
        binary = await asyncio.to_thread(self._reports.bundle, identifier)
        return Response(
            binary,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="report-{identifier}.zip"'
            },
        )
