from dataclasses import dataclass
from pydantic import BaseModel, ConfigDict, Field
from app.documents.models import Document


class LibraryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FolderCreate(LibraryInput):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None


class FolderUpdate(LibraryInput):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: str | None = None


class ItemUpdate(LibraryInput):
    folder_id: str | None = None
    archived: bool | None = Field(default=None, strict=True)


@dataclass(frozen=True, slots=True)
class LibrarySnapshot:
    files: list[Document]
    sets: list[dict]
    metadata: dict
    folders: list[dict]
