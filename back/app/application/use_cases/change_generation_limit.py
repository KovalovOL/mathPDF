from app.usage.ports import AllowancePort


class ChangeGenerationLimit:
    def __init__(self, allowance: AllowancePort):
        self._allowance = allowance

    def execute(self, actor, tokens: int | None, target: str | None = None) -> dict:
        return self._allowance.update(actor, tokens, target)
