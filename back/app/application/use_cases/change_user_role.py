from app.identity.ports import RolesPort


class ChangeUserRole:
    def __init__(self, roles: RolesPort):
        self._roles = roles

    def execute(self, actor, target: str, role: str) -> dict:
        return self._roles.change(actor, target, role)
