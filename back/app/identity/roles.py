"""Explicit role policy service; persistence is supplied through a port."""

from app.core.errors import ApplicationError
from app.identity.role_ports import RoleRepositoryPort


class Roles:
    def __init__(self, repository: RoleRepositoryPort):
        self._repository = repository

    def verified_login(self, identifier: str, email: str) -> None:
        self._repository.verified_login(identifier, email)

    def role(self, identifier: str) -> str:
        return self._repository.role(identifier)

    def require_admin(self, user) -> None:
        if not user or self.role(user.id) not in {"admin", "owner"}:
            raise ApplicationError(403, "Administrator access is required.")

    def change(self, actor, target: str, new_role: str) -> dict:
        return self._repository.change(actor, target, new_role)
