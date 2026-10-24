"""Versioned presentation data. Coordinates and sizes are PDF points (1/72 in)."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field


class Source(BaseModel):
    document_sha256: str
    filename: str
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float]


class Glyph(BaseModel):
    cid: int
    text: str
    glyph_name: str
    feature: str | None = None
    advance: float
    bbox: tuple[float, float, float, float] = (0, -200, 1000, 800)


class Font(BaseModel):
    id: str
    name: str
    url: str | None = None
    glyphs: list[Glyph] = Field(default_factory=list)
    warning: str | None = None
    unmapped_codes: dict[int,str] = Field(default_factory=dict)


class TextNode(BaseModel):
    kind: Literal["text"] = "text"
    id: str
    text: str
    font_id: str
    feature: str | None = None
    glyph_name: str
    cid: int
    x: float
    y: float  # baseline, measured downwards from the formula's top
    size: float
    advance: float
    x_scale: float = 1
    color: str = "#000000"
    ink_bbox: tuple[float, float, float, float]


class RuleNode(BaseModel):
    kind: Literal["rule"] = "rule"
    id: str
    x: float
    y: float
    width: float
    height: float
    color: str = "#000000"


Node = Annotated[TextNode | RuleNode, Field(discriminator="kind")]


class Review(BaseModel):
    state: Literal["unverified", "accepted", "needs_correction"] = "unverified"
    notes: str = Field(default="",max_length=4000)


class Transformation(BaseModel):
    operation: Literal["replace_sign"] = "replace_sign"
    node_id: str
    before: str
    after: str


class Formula(BaseModel):
    schema_version: Literal[1] = 1
    id: str
    title: str
    source: Source
    width: float
    height: float
    nodes: list[Node]
    fonts: list[Font]
    warnings: list[str] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)
    original_id: str | None = None
    transformation: Transformation | None = None


class Candidate(BaseModel):
    id: str
    bbox: tuple[float, float, float, float]
    text: str


class UnsupportedRegion(BaseModel):
    bbox: tuple[float,float,float,float]
    reason: str


class Page(BaseModel):
    page: int
    width: float
    height: float
    nodes: list[Node]
    fonts: list[Font]
    candidates: list[Candidate]
    warnings: list[str]
    unsupported_regions: list[UnsupportedRegion] = Field(default_factory=list)
