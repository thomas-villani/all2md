"""Weight that lives in a style rather than on the run.

The legal-template shape: the run carries only ``w:rStyle`` and the ``<w:b/>`` sits in
``styles.xml``, so reading the run alone finds no formatting at all.

The cases that pin the toggle rule down are Word's measured behaviour, not the spec's
prose -- see :mod:`all2md.parsers.docx_styles`.
"""

from pathlib import Path

import docx
import pytest
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

from all2md import to_markdown

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def bold_style(doc, name, kind=WD_STYLE_TYPE.CHARACTER, *, bold=True, based_on=None):
    """Define a style whose own ``w:rPr`` carries the weight."""
    style = doc.styles.add_style(name, kind)
    if based_on is not None:
        style.base_style = based_on
    style.font.bold = bold
    return style


def render(doc, tmp_path: Path) -> str:
    out = tmp_path / "sample.docx"
    doc.save(str(out))
    return to_markdown(str(out))


def test_bold_carried_by_a_character_style_is_emitted(tmp_path):
    doc = docx.Document()
    bold_style(doc, "StrongLabel")
    paragraph = doc.add_paragraph("Body with a ")
    paragraph.add_run("LABEL").style = doc.styles["StrongLabel"]
    paragraph.add_run(" word inside it.")

    assert "**LABEL**" in render(doc, tmp_path)


def test_direct_bold_still_wins_when_no_style_is_involved(tmp_path):
    doc = docx.Document()
    paragraph = doc.add_paragraph("Body with a ")
    paragraph.add_run("LABEL").bold = True
    paragraph.add_run(" word inside it.")

    assert "**LABEL**" in render(doc, tmp_path)


def test_style_carried_italic_and_strike_are_emitted(tmp_path):
    doc = docx.Document()
    style = doc.styles.add_style("Defined", WD_STYLE_TYPE.CHARACTER)
    style.font.italic = True
    struck = doc.styles.add_style("Removed", WD_STYLE_TYPE.CHARACTER)
    struck.font.strike = True

    paragraph = doc.add_paragraph()
    paragraph.add_run("term").style = style
    paragraph.add_run(" and ")
    paragraph.add_run("gone").style = struck

    output = render(doc, tmp_path)
    assert "*term*" in output
    assert "~~gone~~" in output


def test_weight_inherited_through_based_on_is_emitted(tmp_path):
    doc = docx.Document()
    base = bold_style(doc, "StrongBase")
    child = doc.styles.add_style("StrongChild", WD_STYLE_TYPE.CHARACTER)
    child.base_style = base

    paragraph = doc.add_paragraph("A ")
    paragraph.add_run("LABEL").style = child

    assert "**LABEL**" in render(doc, tmp_path)


def test_a_based_on_chain_is_one_level_so_restating_bold_does_not_cancel(tmp_path):
    """Measured: inheritance is not a toggle-rule level boundary."""
    doc = docx.Document()
    base = bold_style(doc, "StrongBase")
    bold_style(doc, "StrongRestated", based_on=base)

    paragraph = doc.add_paragraph("A ")
    paragraph.add_run("LABEL").style = doc.styles["StrongRestated"]

    assert "**LABEL**" in render(doc, tmp_path)


def test_a_child_style_can_turn_its_parents_bold_off(tmp_path):
    doc = docx.Document()
    base = bold_style(doc, "StrongBase")
    bold_style(doc, "PlainChild", based_on=base, bold=False)

    paragraph = doc.add_paragraph("A ")
    paragraph.add_run("LABEL").style = doc.styles["PlainChild"]

    assert "**LABEL**" not in render(doc, tmp_path)


def test_a_uniformly_bold_paragraph_style_earns_no_markers(tmp_path):
    """The regression guard: `Heading 1` carries its own ``<w:b/>``.

    Nothing in the paragraph is heavier than anything else, so there is nothing for
    ``**`` to distinguish -- and wrapping a heading's own text in it would be wrong.
    """
    doc = docx.Document()
    bold_style(doc, "BoldBody", WD_STYLE_TYPE.PARAGRAPH)
    doc.add_paragraph("Every word here is bold.", style="BoldBody")

    output = render(doc, tmp_path)
    assert "Every word here is bold." in output
    assert "**" not in output


def test_direct_bold_is_marked_even_inside_a_bold_paragraph_style(tmp_path):
    """Typing bold onto a word is an explicit act, and Word's `Heading 1` is bold.

    The relative rule governs weight a run *inherits*; weight it states itself is the
    author's, and all2md has always emitted it.
    """
    doc = docx.Document()
    heading = doc.add_heading(level=1)
    heading.add_run("Bold Title").bold = True

    assert "**Bold Title**" in render(doc, tmp_path)


def test_a_bold_paragraph_style_and_a_bold_character_style_cancel(tmp_path):
    """Measured: two style levels differing from the base flip it twice."""
    doc = docx.Document()
    bold_style(doc, "BoldBody", WD_STYLE_TYPE.PARAGRAPH)
    bold_style(doc, "StrongLabel")

    paragraph = doc.add_paragraph("Bold body with a ", style="BoldBody")
    paragraph.add_run("LABEL").style = doc.styles["StrongLabel"]

    assert "**LABEL**" not in render(doc, tmp_path)


def test_direct_bold_off_beats_a_bold_character_style(tmp_path):
    doc = docx.Document()
    bold_style(doc, "StrongLabel")

    paragraph = doc.add_paragraph("A ")
    run = paragraph.add_run("LABEL")
    run.style = doc.styles["StrongLabel"]
    run.bold = False

    assert "**LABEL**" not in render(doc, tmp_path)


def test_a_based_on_cycle_does_not_raise(tmp_path):
    """A converter must render a self-contradicting document, not refuse it."""
    doc = docx.Document()
    style = bold_style(doc, "StrongLoop")
    based_on = style.element.makeelement(qn("w:basedOn"), {qn("w:val"): "StrongLoop"})
    style.element.insert(0, based_on)

    paragraph = doc.add_paragraph("A ")
    paragraph.add_run("LABEL").style = doc.styles["StrongLoop"]

    assert "LABEL" in render(doc, tmp_path)
