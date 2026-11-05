from app.library.projection import LibraryProjection


class GetLibrarySnapshot:
    def __init__(self, repository):
        self._repository = repository
        self._projection = LibraryProjection()

    def execute(self, owner_id: str) -> dict:
        return self._projection.render(self._repository.read_snapshot(owner_id))
