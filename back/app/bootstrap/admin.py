"""Explicit administration composition."""

from app.administration.handler import AdministrationHandler
from app.administration.repository import AdministrationQueries
from app.application.use_cases.get_admin_dashboard import GetAdminDashboard
from app.application.use_cases.get_admin_user import GetAdminUser
from app.application.use_cases.change_user_role import ChangeUserRole
from app.application.use_cases.change_generation_limit import ChangeGenerationLimit
from app.application.use_cases.add_model_tariff import AddModelTariff


def create_admin_handler(services):
    queries = AdministrationQueries(services.persistence)
    return AdministrationHandler(
        services.usage,
        services.reports,
        queries,
        GetAdminDashboard(queries),
        GetAdminUser(queries, services.usage, services.usage.quota),
        ChangeUserRole(services.auth.roles),
        ChangeGenerationLimit(services.usage.quota),
        AddModelTariff(services.auth.roles, queries),
    )
