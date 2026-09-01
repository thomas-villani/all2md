"""Numbering whose definition lives behind a ``w:numStyleLink``.

Word writes a numbering style as a *pair* of ``w:abstractNum`` elements: one holds the
levels and carries ``w:styleLink``, the other holds none at all and carries
``w:numStyleLink`` back to the same style. Paragraphs point at the empty one, so a
reader that stops there finds no levels and the list demotes to bullets.
"""

import pytest
from lxml import etree

from all2md.parsers.docx import _collect_abstract_numbering_defs, _map_num_ids_to_abstract_nums

pytestmark = [pytest.mark.unit, pytest.mark.docx]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def numbering(*bodies: str):
    """Parse a ``w:numbering`` part built from the fragments given."""
    return etree.fromstring(f'<w:numbering xmlns:w="{W}">{"".join(bodies)}</w:numbering>'.encode())


def levelled(abstract_id: str, *, style_link: str | None = None, fmt: str = "decimal") -> str:
    link = f'<w:styleLink w:val="{style_link}"/>' if style_link else ""
    return (
        f'<w:abstractNum w:abstractNumId="{abstract_id}">{link}'
        f'<w:lvl w:ilvl="0"><w:numFmt w:val="{fmt}"/></w:lvl>'
        f'<w:lvl w:ilvl="1"><w:numFmt w:val="{fmt}"/></w:lvl>'
        f"</w:abstractNum>"
    )


def deferring(abstract_id: str, style: str) -> str:
    return f'<w:abstractNum w:abstractNumId="{abstract_id}"><w:numStyleLink w:val="{style}"/></w:abstractNum>'


def num(num_id: str, abstract_id: str) -> str:
    return f'<w:num w:numId="{num_id}"><w:abstractNumId w:val="{abstract_id}"/></w:num>'


def test_a_deferring_abstract_borrows_the_levels_of_its_pair():
    xml = numbering(levelled("0", style_link="CorpList"), deferring("1", "CorpList"))

    defs = _collect_abstract_numbering_defs(xml)
    assert defs["1"] == {"0": "number", "1": "number"}


def test_the_pair_resolves_in_either_written_order():
    xml = numbering(deferring("1", "CorpList"), levelled("0", style_link="CorpList"))

    assert _collect_abstract_numbering_defs(xml)["1"] == {"0": "number", "1": "number"}


def test_the_borrowed_format_is_the_pair_s_own():
    xml = numbering(levelled("0", style_link="Bulleted", fmt="bullet"), deferring("1", "Bulleted"))

    assert _collect_abstract_numbering_defs(xml)["1"] == {"0": "bullet", "1": "bullet"}


def test_a_link_naming_nothing_is_left_alone():
    # An orphan reference must not invent a definition, or an unnumbered paragraph
    # would start rendering as a list.
    xml = numbering(levelled("0", style_link="CorpList"), deferring("1", "Missing"))

    assert "1" not in _collect_abstract_numbering_defs(xml)


def test_the_numId_the_paragraphs_carry_reaches_the_borrowed_levels():
    # The shape Word actually writes: the paragraphs' numId points at the empty
    # abstract, and only the pairing gets them to a format.
    xml = numbering(
        levelled("0", style_link="CorpList"),
        deferring("1", "CorpList"),
        num("1", "0"),
        num("3", "1"),
    )

    defs = _map_num_ids_to_abstract_nums(xml, _collect_abstract_numbering_defs(xml))
    assert defs["3"] == {"0": "number", "1": "number"}


def test_a_style_link_inside_a_level_is_not_the_abstract_s_own():
    # Both elements can appear deeper in the tree; a descendant search would read
    # one of those as the abstract's link and pair the wrong two together.
    xml = numbering(
        levelled("0", style_link="CorpList"),
        '<w:abstractNum w:abstractNumId="1">'
        '<w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:styleLink w:val="CorpList"/></w:lvl>'
        "</w:abstractNum>",
        deferring("2", "CorpList"),
    )

    defs = _collect_abstract_numbering_defs(xml)
    # Abstract 0 is the one that declares the style at the top level, so its decimal
    # levels are what abstract 2 borrows -- not abstract 1's bullet.
    assert defs["2"] == {"0": "number", "1": "number"}
