class ApplicationError(Exception):
    """A transport-independent, safe business error."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status_code = status
        self.detail = detail
