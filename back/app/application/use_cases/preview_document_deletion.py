class PreviewDocumentDeletion:
    def __init__(self, repository):
        self._repository = repository

    def execute(self, kind: str, identifier: str, owner: str) -> dict:
        if kind not in {"document", "study-set"}:
            raise ValueError("Unsupported deletion target.")
        return self._repository.deletion_info(kind, identifier, owner)
