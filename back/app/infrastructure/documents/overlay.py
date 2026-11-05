import io
from collections import defaultdict
from pathlib import Path
from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    RectangleObject,
)
from app.annotations.models import AnnotationData, Ink, Highlight


def annotated_pdf(
    source: Path, data: AnnotationData, identifier: str, revision: int
) -> bytes:
    """Paint marks in the original, unrotated PDF coordinate space; retain page boxes."""
    reader = PdfReader(source)
    by_page = defaultdict(list)
    for mark in data.items:
        if mark.page > len(reader.pages):
            raise ValueError("An annotation refers to a page that does not exist.")
        page = reader.pages[mark.page - 1]
        box = page.cropbox
        points = (
            mark.points
            if isinstance(mark, Ink)
            else [point for quad in mark.quads for point in quad]
        )
        if any(
            (
                not (
                    float(box.left) - 0.1 <= x <= float(box.right) + 0.1
                    and float(box.bottom) - 0.1 <= y <= float(box.top) + 0.1
                )
                for x, y in points
            )
        ):
            raise ValueError("An annotation extends outside its source page.")
        by_page[mark.page].append(mark)
    writer = PdfWriter(clone_from=reader)
    for number, marks in by_page.items():
        _merge_page_marks(writer.pages[number - 1], marks)
    writer.add_metadata({"/MathPDFCopy": identifier, "/MathPDFRevision": str(revision)})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PdfAnnotationRenderer:

    def render(self, source, data, identifier, revision):
        return annotated_pdf(source, data, identifier, revision)


def _merge_page_marks(page, marks):
    overlay = _overlay_shell(page)
    commands = []
    for mark in marks:
        color = " ".join(
            (f"{int(mark.color[index:index + 2], 16) / 255:.6f}" for index in (1, 3, 5))
        )
        if isinstance(mark, Highlight):
            commands.append(f"q /NoteHighlight gs {color} rg")
            for quad in mark.quads:
                commands.append(
                    f"{quad[0][0]:.6f} {quad[0][1]:.6f} m "
                    + " ".join((f"{x:.6f} {y:.6f} l" for x, y in quad[1:]))
                    + " h f"
                )
        else:
            commands.append(f"q {color} RG {color} rg {mark.width:.6f} w 1 J 1 j")
            x, y = mark.points[0]
            if len(mark.points) == 1:
                r, k = (mark.width / 2, mark.width / 2 * 0.55228475)
                commands.append(
                    f"{x + r} {y} m {x + r} {y + k} {x + k} {y + r} {x} {y + r} c {x - k} {y + r} {x - r} {y + k} {x - r} {y} c {x - r} {y - k} {x - k} {y - r} {x} {y - r} c {x + k} {y - r} {x + r} {y - k} {x + r} {y} c h f"
                )
            else:
                commands.append(
                    f"{x:.6f} {y:.6f} m "
                    + " ".join((f"{x:.6f} {y:.6f} l" for x, y in mark.points[1:]))
                    + " S"
                )
        commands.append("Q")
    stream = DecodedStreamObject()
    stream.set_data(("\n".join(commands) + "\n").encode("ascii"))
    overlay[NameObject("/Contents")] = stream
    page.merge_page(overlay)


def _overlay_shell(page):
    overlay = PageObject.create_blank_page(
        width=float(page.mediabox.width), height=float(page.mediabox.height)
    )
    overlay.mediabox = RectangleObject(page.mediabox)
    overlay.cropbox = RectangleObject(page.cropbox)
    overlay[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/ExtGState"): DictionaryObject(
                {
                    NameObject("/NoteHighlight"): DictionaryObject(
                        {
                            NameObject("/ca"): FloatObject(0.28),
                            NameObject("/CA"): FloatObject(0.28),
                            NameObject("/BM"): NameObject("/Multiply"),
                        }
                    )
                }
            )
        }
    )
    return overlay
