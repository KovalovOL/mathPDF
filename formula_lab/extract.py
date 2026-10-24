"""Read source glyph operations, then select presentation groups in PDF coordinates."""

import hashlib
import math
import re
import threading
from pathlib import Path
from uuid import uuid4

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LTLine, LTRect, LTContainer, LTCurve, LTImage
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from .fonts import FontRegistry
from .models import Candidate, Formula, Page, RuleNode, Source, TextNode, UnsupportedRegion


def color(value) -> str:
    values = list(value) if isinstance(value, (list, tuple)) else [value or 0]
    if len(values) == 4:
        c, m, y, k = values
        values = [1-min(1, v+k) for v in (c, m, y)]
    elif len(values) == 1:
        values *= 3
    return "#" + "".join(f"{round(max(0,min(1,v))*255):02x}" for v in values[:3])


class Resources(PDFResourceManager):
    def get_font(self, objid, spec):
        font = super().get_font(objid, spec)
        font.spec = spec
        return font


class Collector(PDFPageAggregator):
    def __init__(self, resources, registry):
        super().__init__(resources)
        self.registry = registry
        self.text_nodes = []
        self.fonts = {}
        self.warnings = set()

    def render_char(self, matrix, font, fontsize, scaling, rise, cid, ncs, graphicstate):
        advance = super().render_char(matrix, font, fontsize, scaling, rise, cid, ncs, graphicstate)
        asset = self.registry.register(font)
        self.fonts[asset.id] = asset
        glyph = next((g for g in asset.glyphs if g.cid == cid), None)
        if glyph is None:
            text = self.cur_item._objs[-1].get_text()
            if text.isspace():
                return advance
            name=asset.unmapped_codes.get(cid,"unknown")
            self.warnings.add(f"Unsupported source glyph {cid} ({name}) in {asset.name}")
        a, b, c, d, x, y = matrix
        if abs(b) > 1e-5 or abs(c) > 1e-5 or a <= 0 or d <= 0:
            self.warnings.add("Rotated or mirrored text is not supported in this prototype")
            return advance
        size = fontsize*d
        xscale = a*scaling/d
        baseline = y + rise*d
        if glyph:
            gx0, gy0, gx1, gy1 = glyph.bbox
            box = (x + gx0*size*xscale/1000, baseline + gy0*size/1000,
                   x + gx1*size*xscale/1000, baseline + gy1*size/1000)
        else:
            box = self.cur_item._objs[-1].bbox
        self.text_nodes.append((TextNode(
            id=f"t{len(self.text_nodes)}", text=glyph.text if glyph else text,
            font_id=asset.id, feature=glyph.feature if glyph else None,
            glyph_name=glyph.glyph_name if glyph else "unsupported", cid=cid,
            x=x, y=baseline, size=size, x_scale=xscale,
            advance=advance*a, color=color(graphicstate.ncolor), ink_bbox=box), box))
        return advance


def _objects(item):
    if isinstance(item, (LTCurve, LTImage)):
        yield item
    elif isinstance(item, LTContainer):
        for child in item:
            yield from _objects(child)


def candidates(page: Page) -> list[Candidate]:
    fonts = {f.id: f.name for f in page.fonts}
    rows = []
    for node in sorted((n for n in page.nodes if isinstance(n, TextNode)), key=lambda n: n.y):
        if not rows or abs(rows[-1][0]-node.y) > 2:
            rows.append((node.y, [node]))
        else:
            rows[-1][1].append(node)
    kinds = []
    for y, nodes in rows:
        if all(n.text in {"⋄", "□", "◻", "∎"} for n in nodes):
            kinds.append("prose")
            continue
        math_count = sum(bool(re.search(r"Math|txmi|txsy|txex|Symbol|cmmi|cmsy|cmex|Boondox", fonts[n.font_id])) for n in nodes)
        prose = sum(sum(ch.isascii() and ch.isalpha() for ch in n.text)
                    for n in nodes if not re.search(r"Math|txmi|txsy|txex|Symbol|cmmi|cmsy|cmex|Boondox", fonts[n.font_id]))
        kinds.append("math" if math_count and (prose <= 4 or prose <= 10 and math_count > 2*prose)
                     else "short" if prose == 0 and len(nodes)<12 else "prose")
    # An accent belonging to a prose line must not extend a nearby display formula.
    prose_rows=[i for i,k in enumerate(kinds) if k=="prose"]
    main_rows=[i for i,k in enumerate(kinds) if k=="math" and len(rows[i][1])>=3]
    for i,k in enumerate(kinds):
        if k in {"math","short"} and len(rows[i][1])<=2:
            prose_distance=min((abs(rows[i][0]-rows[j][0]) for j in prose_rows),default=math.inf)
            math_distance=min((abs(rows[i][0]-rows[j][0]) for j in main_rows),default=math.inf)
            if prose_distance<7 and prose_distance<math_distance:
                kinds[i]="prose"
    selected = set(i for i, kind in enumerate(kinds) if kind == "math")
    for i, kind in enumerate(kinds):
        if kind == "short" and any(abs(rows[i][0]-rows[j][0]) < 15 for j in selected):
            selected.add(i)
    groups = []
    for i in sorted(selected):
        if groups and i == groups[-1][-1]+1 and rows[i][0]-rows[groups[-1][-1]][0]<25:
            groups[-1].append(i)
        else:
            groups.append([i])
    result = []
    for group in groups:
        nodes = [n for i in group for n in rows[i][1] if not n.text.isspace()]
        if not nodes:
            continue
        x0=min(n.ink_bbox[0] for n in nodes)-2
        y0=min(n.ink_bbox[1] for n in nodes)-2
        x1=max(n.ink_bbox[2] for n in nodes)+2
        y1=max(n.ink_bbox[3] for n in nodes)+2
        if y0 < 30 or y1 > page.height-30:
            continue
        text="\n".join("".join(n.text for n in sorted(rows[i][1], key=lambda n:n.x)) for i in group)
        result.append(Candidate(id=f"c{len(result)+1}", bbox=(x0,y0,x1,y1), text=text))
    return result


class PdfSource:
    def __init__(self, path: Path, directory: Path):
        self.path = path.resolve(strict=True)
        with self.path.open("rb") as stream:
            self.sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        with self.path.open("rb") as stream:
            self.page_count = sum(1 for _ in PDFPage.get_pages(stream, check_extractable=True))
        self.registry = FontRegistry(directory / self.sha256 / "fonts")
        self._cache: dict[int, Page] = {}
        self._lock = threading.RLock()

    def page(self, number: int) -> Page:
        if not 1 <= number <= self.page_count:
            raise ValueError(f"Page must be between 1 and {self.page_count}")
        with self._lock:
            if number in self._cache:
                return self._cache[number].model_copy(deep=True)
            resources = Resources()
            collector = Collector(resources, self.registry)
            with self.path.open("rb") as stream:
                page = next(PDFPage.get_pages(stream, pagenos={number-1}, check_extractable=True))
                PDFPageInterpreter(resources, collector).process_page(page)
                layout = collector.get_result()
                width, height = layout.width, layout.height
                nodes = []
                unsupported = []
                for node, (x0,y0,x1,y1) in collector.text_nodes:
                    node.y = height-node.y
                    node.ink_bbox = (x0, height-y1, x1, height-y0)
                    nodes.append(node)
                for obj in _objects(layout):
                    x0,y0,x1,y1=obj.bbox
                    w,h=x1-x0,y1-y0
                    is_rule = (isinstance(obj,LTLine) and (w<.01 or h<.01)) or (
                        isinstance(obj,LTRect) and obj.fill and not obj.stroke and ((w>2 and h<2) or (h>2 and w<2)))
                    if is_rule:
                        thickness=max(getattr(obj,"linewidth",0),.1)
                        if w<.01: x0-=thickness/2;w=thickness
                        if h<.01: y1+=thickness/2;h=thickness
                        nodes.append(RuleNode(id=f"r{len(nodes)}",x=x0,y=height-y1,width=w,height=h,
                                              color=color(getattr(obj,"non_stroking_color",None) if obj.fill else getattr(obj,"stroking_color",None))))
                    else:
                        unsupported.append(UnsupportedRegion(bbox=(x0,height-y1,x1,height-y0),
                            reason="Source image is not editable text" if isinstance(obj,LTImage)
                            else "Source graphic cannot be represented by this prototype's text/rule model"))
                warnings=sorted(collector.warnings)
                if not collector.text_nodes:
                    warnings.append("This page has no extractable text; OCR is outside this prototype")
                result=Page(page=number,width=width,height=height,nodes=nodes,
                            fonts=list(collector.fonts.values()),candidates=[],warnings=warnings,
                            unsupported_regions=unsupported)
                result.candidates=candidates(result)
                self._cache[number]=result
                return result.model_copy(deep=True)

    def select(self, number: int, bbox, title="Source formula") -> Formula:
        page=self.page(number)
        if len(bbox)!=4 or not all(math.isfinite(v) for v in bbox):
            raise ValueError("Bounding box must contain four finite coordinates")
        x0,y0,x1,y1=bbox
        if not (0<=x0<x1<=page.width and 0<=y0<y1<=page.height):
            raise ValueError("Bounding box must be inside the page with positive dimensions")
        chosen=[]
        for original in page.nodes:
            if isinstance(original,TextNode):
                box=original.ink_bbox
                cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
            else:
                cx,cy=original.x+original.width/2,original.y+original.height/2
            if x0<=cx<=x1 and y0<=cy<=y1:
                node=original.model_copy(deep=True)
                node.x-=x0;node.y-=y0
                if isinstance(node,TextNode):
                    a,b,c,d=node.ink_bbox;node.ink_bbox=(a-x0,b-y0,c-x0,d-y0)
                chosen.append(node)
        if not any(isinstance(n,TextNode) for n in chosen):
            raise ValueError("The selected region contains no text nodes")
        used={n.font_id for n in chosen if isinstance(n,TextNode)}
        warnings=[w for w in page.warnings if not w.startswith("Unsupported source glyph")]
        warnings.extend(f"Unsupported glyph {n.cid} in {n.font_id}" for n in chosen
                        if isinstance(n,TextNode) and n.glyph_name == "unsupported")
        warnings.extend(f.warning for f in page.fonts if f.id in used and f.warning)
        for region in page.unsupported_regions:
            a,b,c,d=region.bbox
            if a<x1 and c>x0 and b<y1 and d>y0:
                warnings.append(region.reason)
        for node in chosen:
            if isinstance(node,TextNode):
                a,b,c,d=node.ink_bbox
                if a<-.01 or b<-.01 or c>x1-x0+.01 or d>y1-y0+.01:
                    warnings.append("The selection clips a source glyph; enlarge the source region")
                    break
        return Formula(id=str(uuid4()),title=title,source=Source(document_sha256=self.sha256,
                       filename=self.path.name,page=number,bbox=bbox),width=x1-x0,height=y1-y0,
                       nodes=chosen,fonts=page.fonts,warnings=list(dict.fromkeys(warnings)))
