"""Versioned editable marks and portable vector PDF overlays."""
import io
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, FloatObject, NameObject, RectangleObject

Coordinate = Annotated[float, Field(ge=-10_000_000, le=10_000_000, allow_inf_nan=False)]
Point = tuple[Coordinate, Coordinate]


class AnnotationConflict(Exception):
    """Saving must not overwrite an edited copy changed in another tab."""


class Mark(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    page: int = Field(ge=1)
    color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')


class Ink(Mark):
    kind: Literal['ink']
    width: float = Field(ge=.000001, le=32, allow_inf_nan=False)
    points: list[Point] = Field(min_length=1, max_length=20_000)


class Highlight(Mark):
    kind: Literal['highlight']
    quads: list[tuple[Point, Point, Point, Point]] = Field(min_length=1, max_length=5000)


class AnnotationData(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    items: list[Annotated[Ink | Highlight, Field(discriminator='kind')]] = Field(default_factory=list, max_length=5000)

    @model_validator(mode='after')
    def bounded_unique_marks(self):
        if len({mark.id for mark in self.items}) != len(self.items):
            raise ValueError('Annotation identifiers must be unique.')
        if sum(len(mark.points) if isinstance(mark, Ink) else len(mark.quads)*4 for mark in self.items) > 200_000:
            raise ValueError('This annotation layer contains too many points.')
        return self


class AnnotationWrite(AnnotationData):
    expected_revision: int = Field(ge=0)


def annotated_pdf(source: Path, data: AnnotationData, identifier: str, revision: int) -> bytes:
    """Paint marks in the original, unrotated PDF coordinate space; retain page boxes."""
    reader = PdfReader(source)
    by_page = defaultdict(list)
    for mark in data.items:
        if mark.page > len(reader.pages):
            raise ValueError('An annotation refers to a page that does not exist.')
        page = reader.pages[mark.page-1]
        box = page.cropbox
        points = mark.points if isinstance(mark, Ink) else [point for quad in mark.quads for point in quad]
        if any(not (float(box.left)-.1 <= x <= float(box.right)+.1 and
                    float(box.bottom)-.1 <= y <= float(box.top)+.1) for x,y in points):
            raise ValueError('An annotation extends outside its source page.')
        by_page[mark.page].append(mark)
    writer = PdfWriter(clone_from=reader)
    for number, marks in by_page.items():
        page = writer.pages[number-1]
        overlay = PageObject.create_blank_page(width=float(page.mediabox.width), height=float(page.mediabox.height))
        overlay.mediabox = RectangleObject(page.mediabox)
        overlay.cropbox = RectangleObject(page.cropbox)
        overlay[NameObject('/Resources')] = DictionaryObject({NameObject('/ExtGState'): DictionaryObject({
            NameObject('/NoteHighlight'): DictionaryObject({NameObject('/ca'): FloatObject(.28),
                NameObject('/CA'): FloatObject(.28), NameObject('/BM'): NameObject('/Multiply')})})})
        commands = []
        for mark in marks:
            color = ' '.join(f'{int(mark.color[index:index+2],16)/255:.6f}' for index in (1,3,5))
            if isinstance(mark, Highlight):
                commands.append(f'q /NoteHighlight gs {color} rg')
                for quad in mark.quads:
                    commands.append(f'{quad[0][0]:.6f} {quad[0][1]:.6f} m ' +
                        ' '.join(f'{x:.6f} {y:.6f} l' for x,y in quad[1:]) + ' h f')
            else:
                commands.append(f'q {color} RG {color} rg {mark.width:.6f} w 1 J 1 j')
                x,y = mark.points[0]
                if len(mark.points) == 1:
                    r,k = mark.width/2,mark.width/2*.55228475
                    commands.append(f'{x+r} {y} m {x+r} {y+k} {x+k} {y+r} {x} {y+r} c '
                        f'{x-k} {y+r} {x-r} {y+k} {x-r} {y} c {x-r} {y-k} {x-k} {y-r} {x} {y-r} c '
                        f'{x+k} {y-r} {x+r} {y-k} {x+r} {y} c h f')
                else:
                    commands.append(f'{x:.6f} {y:.6f} m ' +
                        ' '.join(f'{x:.6f} {y:.6f} l' for x,y in mark.points[1:]) + ' S')
            commands.append('Q')
        stream = DecodedStreamObject(); stream.set_data(('\n'.join(commands)+'\n').encode('ascii'))
        overlay[NameObject('/Contents')] = stream
        page.merge_page(overlay)
    writer.add_metadata({'/MathPDFCopy':identifier, '/MathPDFRevision':str(revision)})
    output = io.BytesIO(); writer.write(output)
    return output.getvalue()
