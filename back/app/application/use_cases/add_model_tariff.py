from app.core.errors import ApplicationError
from app.identity.ports import RolesPort
from app.administration.ports import TariffRepositoryPort
from app.usage.models import PriceInput


class AddModelTariff:
    def __init__(self, roles: RolesPort, tariffs: TariffRepositoryPort):
        self._roles, self._tariffs = roles, tariffs

    def execute(self, actor, price: PriceInput) -> dict:
        if self._roles.role(actor.id) != "owner":
            raise ApplicationError(403, "Only the owner can add a tariff.")
        return self._tariffs.new_price(actor.id, price)
