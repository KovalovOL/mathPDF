"""Explicit presentation-tree edits; no formula-wide string replacement."""

from uuid import uuid4
from .models import Formula, Review, TextNode, Transformation


def replace_sign(original: Formula, node_id: str, replacement: str) -> Formula:
    if original.original_id:
        raise ValueError("Select an original formula; chaining variants is outside this experiment")
    replacement = "−" if replacement == "-" else replacement
    if replacement not in {"+", "−"}:
        raise ValueError("This experiment supports plus/minus replacements only")
    source_node = next((n for n in original.nodes if n.id == node_id), None)
    if not isinstance(source_node, TextNode) or source_node.text not in {"+", "−", "-"}:
        raise ValueError("Select a plus or minus text node")
    if source_node.text == replacement:
        raise ValueError("The requested sign is unchanged")
    choices = [(f, g) for f in original.fonts if f.url
               for g in f.glyphs if g.text == replacement]
    choices.sort(key=lambda pair: pair[0].id != source_node.font_id)
    if not choices:
        raise ValueError("The replacement sign is not available in the embedded source fonts")
    face, glyph = choices[0]
    result = original.model_copy(deep=True)
    result.id = str(uuid4())
    result.title = original.title + f" · {source_node.text} → {replacement}"
    result.original_id = original.id
    result.transformation = Transformation(node_id=node_id,before=source_node.text,after=replacement)
    result.review = Review()
    node = next(n for n in result.nodes if n.id == node_id)
    new_advance = glyph.advance/1000*node.size*node.x_scale
    # Preserve the original sign cell and all other nodes; center the new glyph.
    node.x += (node.advance-new_advance)/2
    node.text, node.font_id, node.feature = glyph.text, face.id, glyph.feature
    node.cid, node.glyph_name = glyph.cid, glyph.glyph_name
    a,b,c,d=glyph.bbox
    node.ink_bbox = (node.x+a*node.size*node.x_scale/1000,node.y-d*node.size/1000,
                     node.x+c*node.size*node.x_scale/1000,node.y-b*node.size/1000)
    return result
