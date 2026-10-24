from types import SimpleNamespace
from fontTools.ttLib import TTFont
from pdfminer.psparser import LIT
import pytest
from formula_lab.fonts import FontRegistry
from formula_lab.models import TextNode, RuleNode


@pytest.mark.parametrize("number",[4,7,15])
def test_source_fonts_and_unicode_are_recovered(pdf_source,number):
    page=pdf_source.page(number)
    assert page.nodes and page.candidates
    assert page.warnings == []
    assert all(f.url and not f.warning for f in page.fonts)
    assert all("(cid:" not in n.text for n in page.nodes if isinstance(n,TextNode))
    for f in page.fonts:
        with TTFont(pdf_source.registry.directory/f"{f.id}.otf") as webfont:
            assert webfont["OS/2"].fsSelection & 0x80
            assert webfont["hhea"].ascent == 800
            for glyph in f.glyphs:
                assert ord(glyph.text) in webfont.getBestCmap()


def test_fraction_and_source_coordinates(pdf_source):
    page=pdf_source.page(4)
    candidate=next(c for c in page.candidates if "ℚ" in c.text)
    formula=pdf_source.select(4,candidate.bbox)
    assert formula.source.page==4
    assert formula.source.document_sha256==pdf_source.sha256
    assert formula.review.state=="unverified"
    assert any(isinstance(n,RuleNode) for n in formula.nodes)
    text={n.id:n for n in page.nodes if isinstance(n,TextNode)}
    for node in formula.nodes:
        if isinstance(node,TextNode):
            assert node.x+candidate.bbox[0]==pytest.approx(text[node.id].x)
            assert node.y+candidate.bbox[1]==pytest.approx(text[node.id].y)
    assert pdf_source.page(4)==page  # selection did not mutate cached page data


def test_prose_accents_do_not_expand_display_candidate(pdf_source):
    page=pdf_source.page(7)
    formula=pdf_source.select(7,page.candidates[0].bbox)
    text="".join(n.text for n in formula.nodes if isinstance(n,TextNode))
    assert "𝑐" in text and "𝑈" in text
    assert "′" not in text and "¯" not in text


def test_graphics_and_clipped_glyphs_are_not_silently_accepted(pdf_source):
    page=pdf_source.page(38)
    assert page.unsupported_regions
    diagram=pdf_source.select(38,(0,0,page.width,page.height))
    assert any("graphic" in warning for warning in diagram.warnings)
    page=pdf_source.page(4)
    candidate=page.candidates[0]
    x0,y0,x1,y1=candidate.bbox
    clipped=pdf_source.select(4,(x0+3,y0,x1,y1))
    assert any("clips" in warning for warning in clipped.warnings)


@pytest.mark.parametrize("number,bbox",[(0,(0,0,1,1)),(4,(-1,0,10,10)),
                                        (4,(0,0,float('nan'),10)),(4,(0,0,10000,10)),
                                        (4,(0,0,1,1))])
def test_invalid_or_empty_selection_is_rejected(pdf_source,number,bbox):
    with pytest.raises(ValueError):
        pdf_source.select(number,bbox)


def test_unembedded_font_is_explicit(tmp_path):
    font=SimpleNamespace(fontname="Missing",spec={"Subtype":LIT("Type1")})
    # PDF font objects are identity-hashable.
    class MissingFont:
        fontname="Missing"
        spec=font.spec
    result=FontRegistry(tmp_path).register(MissingFont())
    assert result.url is None
    assert "not embedded" in result.warning
