class RenameLibraryItem:
    def __init__(self, repository):
        self._repository = repository

    def execute(self, kind: str, identifier: str, owner: str, request):
        return self._repository.rename_item(kind, identifier, owner, request)
