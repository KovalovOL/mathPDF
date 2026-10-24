"""Reuse embedded Type 1 fonts as text fonts, with real Unicode and GSUB variants."""

import hashlib
import json
import unicodedata
from pathlib import Path

from fontTools import agl, t1Lib
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from pdfminer.pdftypes import dict_value, resolve1, stream_value
from .models import Font, Glyph


# Standard TeX construction glyphs frequently lack a PDF ToUnicode mapping.
ALIASES = {
    "parenleft": "(", "parenright": ")", "braceleft": "{", "braceright": "}",
    "bracketleft": "[", "bracketright": "]", "angleleft": "⟨", "angleright": "⟩",
    "floorleft": "⌊", "floorright": "⌋", "ceilingleft": "⌈", "ceilingright": "⌉",
    "union": "⋃", "intersection": "⋂", "product": "∏", "summation": "∑",
    "coproduct": "∐", "integral": "∫", "radical": "√", "arrowvertex": "|",
    "barex": "⏐", "bracehext": "⎯",
}


def _unicode(font, cid: int, name: str) -> str | None:
    try:
        text = font.to_unichr(cid)
    except Exception:
        text = ""
    if not text or text.startswith("(cid:") or "\ufffd" in text:
        text = agl.toUnicode(name)
    if not text:
        for prefix, value in sorted(ALIASES.items(), key=lambda pair: -len(pair[0])):
            if name.startswith(prefix):
                text = value
                break
    if len(text) > 1:
        text = "".join(c for c in text if not 0xFE00 <= ord(c) <= 0xFE0F)
        composed = unicodedata.normalize("NFKC", text)
        ligatures = {"ff": "ﬀ", "fi": "ﬁ", "fl": "ﬂ", "ffi": "ﬃ", "ffl": "ﬄ"}
        text = ligatures.get(text, composed)
    if len(text) != 1 or unicodedata.category(text) in {"Cc", "Cs"}:
        return None
    return text


def _encoding(font, program) -> dict[int, str]:
    result = dict(enumerate(program["Encoding"]))
    encoding = resolve1(font.spec.get("Encoding"))
    if isinstance(encoding, dict):
        code = 0
        for entry in resolve1(encoding.get("Differences", [])):
            if isinstance(entry, int):
                code = entry
            else:
                result[code] = entry.name
                code += 1
    return result


class FontRegistry:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self._cache: dict[object, Font] = {}

    def register(self, font) -> Font:
        key = font
        if key in self._cache:
            return self._cache[key]
        identifier = "unsupported-" + hashlib.sha256(font.fontname.encode()).hexdigest()[:12]
        try:
            if font.spec.get("Subtype").name != "Type1":
                raise ValueError("This experiment supports embedded Type 1 fonts only")
            descriptor = dict_value(font.spec.get("FontDescriptor", {}))
            if "FontFile" not in descriptor:
                raise ValueError("The source font is not embedded as Type 1")
            data = stream_value(descriptor["FontFile"]).get_data()
            program = object.__new__(t1Lib.T1Font)
            program.data, program.encoding = data, "ascii"
            glyph_set = program.getGlyphSet()
            matrix = program["FontMatrix"]
            transform = tuple(v*1000 for v in matrix)
            encoding = _encoding(font, program)
            signature = b"formula-font-v3" + data + json.dumps(encoding, sort_keys=True).encode()
            signature += json.dumps(font.cid2unicode, sort_keys=True, ensure_ascii=False).encode()
            identifier = "pdf_" + hashlib.sha256(signature).hexdigest()[:20]
            entries: list[Glyph] = []
            cmap: dict[int, str] = {}
            features = []
            unknown = {}
            for cid, name in sorted(encoding.items()):
                if name == ".notdef" or name not in glyph_set:
                    continue
                text = _unicode(font, cid, name)
                if text is None:
                    unknown[cid] = name
                    continue
                glyph = glyph_set[name]
                bounds = BoundsPen(glyph_set)
                glyph.draw(TransformPen(bounds, transform))
                feature = None
                cp = ord(text)
                if cp in cmap and cmap[cp] != name:
                    feature = f"f{len(features):03d}"
                    features.append(f"feature {feature} {{ sub {cmap[cp]} by {name}; }} {feature};")
                else:
                    cmap[cp] = name
                entries.append(Glyph(cid=cid, text=text, glyph_name=name, feature=feature,
                                     advance=font.char_width(cid) * 1000,
                                     bbox=bounds.bounds or (0, 0, 0, 0)))

            target = self.directory / f"{identifier}.otf"
            if not target.exists():
                order = [".notdef"] + [n for n in glyph_set if n != ".notdef"]
                strings, metrics = {}, {}
                for name in order:
                    glyph = glyph_set[name]
                    glyph.draw(BoundsPen(glyph_set))
                    width = round(glyph.width*transform[0])
                    pen = T2CharStringPen(width, glyph_set, roundTolerance=0)
                    glyph.draw(TransformPen(pen, transform))
                    strings[name] = pen.getCharString()
                    metrics[name] = (width, 0)
                builder = FontBuilder(1000, isTTF=False)
                builder.setupGlyphOrder(order)
                builder.setupCharacterMap(cmap)
                builder.setupCFF(identifier, {"FullName": identifier, "FamilyName": identifier,
                                             "Weight": "Regular"}, strings, {})
                builder.setupHorizontalMetrics(metrics)
                # Nominal 0.8em ascent; the renderer also measures browser rounding.
                builder.setupHorizontalHeader(ascent=800, descent=-200, lineGap=0)
                builder.setupNameTable({"familyName": identifier, "styleName": "Regular",
                                        "uniqueFontIdentifier": identifier, "fullName": identifier,
                                        "psName": identifier})
                builder.setupOS2(version=4, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=0,
                                 usWinAscent=3000, usWinDescent=2000, fsSelection=0x80)
                builder.setupPost()
                if features:
                    addOpenTypeFeaturesFromString(builder.font, "\n".join(features))
                builder.save(target)
            asset = Font(id=identifier, name=font.fontname, url=f"/fonts/{identifier}.otf",
                         glyphs=entries,unmapped_codes=unknown)
        except Exception as error:
            asset = Font(id=identifier, name=font.fontname, warning=str(error))
        self._cache[key] = asset
        return asset
