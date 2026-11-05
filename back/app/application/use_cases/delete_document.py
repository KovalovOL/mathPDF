class DeleteDocument:
    def __init__(self, repository, cleanup):
        self._repository, self._cleanup = repository, cleanup

    def execute(self, kind: str, identifier: str, owner: str, revision: str) -> dict:
        if kind not in {"document", "study-set"}:
            raise ValueError("Unsupported deletion target.")
        result, stored_names = self._repository.delete(
            kind, identifier, owner, revision
        )
        self._cleanup.execute(stored_names)
        return result
