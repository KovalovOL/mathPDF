from pydantic import BaseModel, ConfigDict, Field


class DeletionChanged(Exception):
    """The user must review a changed deletion impact before confirming again."""


class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    expected_name: str | None = Field(default=None, max_length=200)


class RenameConflict(ValueError):
    pass


class Document(BaseModel):
    id: str
    filename: str
    sha256: str
    media_type: str
    page_count: int | None
    size: int
    original_document_id: str | None = None
    annotation_revision: int = 0
