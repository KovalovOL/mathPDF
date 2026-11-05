"""Versioned editable marks and portable vector PDF overlays."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Coordinate = Annotated[float, Field(ge=-10000000, le=10000000, allow_inf_nan=False)]
Point = tuple[Coordinate, Coordinate]


class AnnotationConflict(Exception):
    """Saving must not overwrite an edited copy changed in another tab."""


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern="^[a-zA-Z0-9_-]{1,64}$")
    page: int = Field(ge=1)
    color: str = Field(pattern="^#[0-9a-fA-F]{6}$")


class Ink(Mark):
    kind: Literal["ink"]
    width: float = Field(ge=1e-06, le=32, allow_inf_nan=False)
    points: list[Point] = Field(min_length=1, max_length=20000)


class Highlight(Mark):
    kind: Literal["highlight"]
    quads: list[tuple[Point, Point, Point, Point]] = Field(
        min_length=1, max_length=5000
    )


class AnnotationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    items: list[Annotated[Ink | Highlight, Field(discriminator="kind")]] = Field(
        default_factory=list, max_length=5000
    )

    @model_validator(mode="after")
    def bounded_unique_marks(self):
        if len({mark.id for mark in self.items}) != len(self.items):
            raise ValueError("Annotation identifiers must be unique.")
        if (
            sum(
                (
                    len(mark.points) if isinstance(mark, Ink) else len(mark.quads) * 4
                    for mark in self.items
                )
            )
            > 200000
        ):
            raise ValueError("This annotation layer contains too many points.")
        return self


class AnnotationWrite(AnnotationData):
    expected_revision: int = Field(ge=0)
