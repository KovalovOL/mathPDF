from app.usage.ports import UsageRepositoryPort, AllowancePort
from app.core.ports import ObservationJournalPort

"""Provider observations are durable; admission and settlement remain atomic."""

from app.core.ports import ClockPort


class Usage:
    def __init__(
        self,
        repository: UsageRepositoryPort,
        allowance: AllowancePort,
        journal: ObservationJournalPort,
        clock: ClockPort,
    ):
        self._repository, self._allowance, self._journal = (
            repository,
            allowance,
            journal,
        )

        self._clock = clock

    @property
    def quota(self):
        return self._allowance

    @property
    def spool(self):
        return self._journal.directory

    def start(self, user_id, provider, model, context):
        return self._repository.start(user_id, provider, model, context)

    def finish(
        self,
        identifier,
        status,
        usage=None,
        duration_ms=None,
        provider_request_id=None,
        finished_at=None,
        unbilled=False,
    ):
        return self._journal.execute(
            "finish",
            self._repository.finish,
            (identifier, status),
            {
                "usage": usage,
                "duration_ms": duration_ms,
                "provider_request_id": provider_request_id,
                "finished_at": finished_at or self._clock.now().isoformat(),
                "unbilled": unbilled,
            },
        )

    def response(self, identifier, model, status, text):
        return self._journal.execute(
            "response", self._repository.response, (identifier, model, status, text), {}
        )

    def outcome(self, identifier, status):
        return self._journal.execute(
            "outcome", self._repository.outcome, (identifier, status), {}
        )

    def flush_spool(self):
        self._journal.replay(
            {
                "finish": self._repository.finish,
                "response": self._repository.response,
                "outcome": self._repository.outcome,
            }
        )

    def dashboard(self, days=7, user_id=None):
        return self._repository.dashboard(days, user_id)
