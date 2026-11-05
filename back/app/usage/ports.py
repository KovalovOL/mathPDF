from typing import Protocol


class AllowancePort(Protocol):
    def check(self, owner_id: str) -> dict: ...
    def status(self, owner_id: str) -> dict: ...
    def settings(self) -> dict: ...
    def update(self, actor, tokens: int | None, target: str | None = None) -> dict: ...


class UsageReadPort(Protocol):
    def dashboard(self, days: int, user_id: str | None = None) -> dict: ...


class UsageAttemptPort(Protocol):
    def start(self, user_id: str, provider: str, model: str, context: dict) -> str: ...
    def finish(
        self,
        identifier: str,
        status: str,
        usage=None,
        duration_ms=None,
        provider_request_id=None,
        finished_at=None,
        unbilled=False,
    ) -> None: ...
    def response(self, identifier: str, model: str, status: str, text: str) -> None: ...
    def outcome(self, identifier: str, status: str) -> None: ...


class UsageRepositoryPort(UsageAttemptPort, UsageReadPort, Protocol):
    pass
