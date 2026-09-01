"""Numbering that lives on a paragraph style rather than on the paragraph.

The corporate-template shape: the paragraphs carry only ``w:pStyle`` and the
``w:numPr`` sits in ``styles.xml``, so reading the paragraph alone finds no
numbering at all.
"""

import docx
import pytest
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

from all2md import to_markdown
from all2md.parsers.docx import (
    _detect_list_from_numbering_props,
    _get_numbering_definitions,
)

pytestmark = [pytest.mark.unit, pytest.mark.docx]

# numId -> level -> type, standing in for the document's numbering part.
DECIMAL = {"1": {"0": "number", "1": "number"}}

# The default python-docx template already defines these.
TEMPLATE_ORDERED_NUM_ID = "5"


def num_pr(*, num_id: str | None = None, ilvl: str | None = None):
    """Build a ``w:numPr`` carrying either half of the numbering properties."""
    element = OxmlElement("w:numPr")
    if ilvl is not None:
        level = OxmlElement("w:ilvl")
        level.set(qn("w:val"), ilvl)
        element.append(level)
    if num_id is not None:
        identifier = OxmlElement("w:numId")
        identifier.set(qn("w:val"), num_id)
        element.append(identifier)
    return element


def numbered_style(doc, name, *, num_id=None, ilvl=None, based_on=None):
    """Add a paragraph style whose own properties carry the numbering."""
    style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    if based_on is not None:
        style.base_style = based_on
    if num_id is not None or ilvl is not None:
        style.element.get_or_add_pPr().append(num_pr(num_id=num_id, ilvl=ilvl))
    return style


def test_numbering_carried_by_the_style_is_found():
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id="1")
    paragraph = doc.add_paragraph("Alpha item", style="CorpList")

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 1)


def test_numbering_is_inherited_through_based_on():
    doc = docx.Document()
    base = numbered_style(doc, "CorpBase", num_id="1")
    numbered_style(doc, "CorpChild", based_on=base)
    paragraph = doc.add_paragraph("Alpha item", style="CorpChild")

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 1)


def test_a_level_without_a_num_id_is_not_a_list():
    # Word's built-in Subtitle style really does carry <w:numPr><w:ilvl w:val="1"/></w:numPr>
    # and is emphatically not a list, so numId is what has to switch numbering on.
    doc = docx.Document()
    numbered_style(doc, "PseudoSubtitle", ilvl="1")
    paragraph = doc.add_paragraph("A subtitle", style="PseudoSubtitle")

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) is None


def test_num_id_zero_means_no_numbering():
    doc = docx.Document()
    numbered_style(doc, "Unnumbered", num_id="0")
    paragraph = doc.add_paragraph("Plain prose", style="Unnumbered")

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) is None


def test_direct_properties_beat_the_style():
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id="1", ilvl="0")
    paragraph = doc.add_paragraph("Alpha item", style="CorpList")
    paragraph._p.get_or_add_pPr().append(num_pr(num_id="1", ilvl="2"))

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 3)


def test_the_level_and_the_id_can_come_from_different_places():
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id="1")
    paragraph = doc.add_paragraph("Alpha item", style="CorpList")
    paragraph._p.get_or_add_pPr().append(num_pr(ilvl="1"))

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 2)


def test_a_based_on_cycle_terminates():
    doc = docx.Document()
    first = numbered_style(doc, "CycleA")
    second = numbered_style(doc, "CycleB", based_on=first)
    first.base_style = second
    paragraph = doc.add_paragraph("Alpha item", style="CycleA")

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) is None


def test_indentation_still_nests_when_the_level_comes_from_a_style():
    # A style's ilvl is the same for every paragraph using it, so writers that
    # cannot vary it nest by indenting instead.
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id="1")
    paragraph = doc.add_paragraph("Nested item", style="CorpList")
    paragraph.paragraph_format.left_indent = Inches(0.5)

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 2)


def test_a_direct_level_makes_indentation_mere_formatting():
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id="1")
    paragraph = doc.add_paragraph("Top-level item", style="CorpList")
    paragraph._p.get_or_add_pPr().append(num_pr(ilvl="0"))
    paragraph.paragraph_format.left_indent = Inches(0.5)

    assert _detect_list_from_numbering_props(paragraph, doc, DECIMAL) == ("number", 1)


def test_a_missing_numbering_part_is_not_a_crash():
    # python-docx raises NotImplementedError -- not AttributeError -- for a part
    # the document does not have, so hasattr() does not screen it out.
    class _Part:
        @property
        def numbering_part(self):
            raise NotImplementedError("part not implemented yet")

    class _Doc:
        _part = _Part()

    assert _get_numbering_definitions(_Doc()) == {}


def test_a_style_numbered_list_reaches_the_markdown(tmp_path):
    doc = docx.Document()
    numbered_style(doc, "CorpList", num_id=TEMPLATE_ORDERED_NUM_ID)
    doc.add_paragraph("Intro paragraph.")
    for item in ("Alpha item", "Beta item", "Gamma item"):
        doc.add_paragraph(item, style="CorpList")

    path = tmp_path / "style-numbered.docx"
    doc.save(str(path))

    markdown = to_markdown(str(path))
    assert "1. Alpha item" in markdown
    assert "2. Beta item" in markdown
    assert "3. Gamma item" in markdown
