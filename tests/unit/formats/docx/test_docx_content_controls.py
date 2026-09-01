"""Content controls (``w:sdt``), which hide their content one level down.

Every shape here is a wrapper Word writes around ordinary content -- a paragraph, a
run mid-sentence, a table, a row, a cell -- and each one used to make that content
invisible to a different reader. They are grouped in one file because they are one
defect: nobody descended through ``w:sdtContent``.
"""

import docx
import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from all2md import to_markdown
from all2md.parsers.docx import DocxToAstConverter
from all2md.parsers.docx_sdt import document_has_content_controls, unwrap_content_controls
from all2md.renderers.markdown import MarkdownRenderer

pytestmark = [pytest.mark.unit, pytest.mark.docx]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def sdt(*content, alias: str | None = None, showing_placeholder: bool = False):
    """Wrap ``content`` elements in a content control, properties and all."""
    element = OxmlElement("w:sdt")
    properties = OxmlElement("w:sdtPr")
    if alias is not None:
        alias_element = OxmlElement("w:alias")
        alias_element.set(qn("w:val"), alias)
        properties.append(alias_element)
    if showing_placeholder:
        properties.append(OxmlElement("w:showingPlcHdr"))
    element.append(properties)

    holder = OxmlElement("w:sdtContent")
    for child in content:
        holder.append(child)
    element.append(holder)
    return element


def wrap_in_place(element):
    """Replace ``element`` in its parent with a content control around it."""
    parent = element.getparent()
    index = parent.index(element)
    parent.remove(element)
    parent.insert(index, sdt(element, alias="Probe"))


def convert(doc, tmp_path, name="controlled.docx"):
    path = tmp_path / name
    doc.save(str(path))
    return to_markdown(str(path))


def test_a_block_control_does_not_swallow_its_paragraph(tmp_path):
    doc = docx.Document()
    doc.add_paragraph("Intro paragraph.")
    wrap_in_place(doc.add_paragraph("Author name goes here.")._p)

    markdown = convert(doc, tmp_path)
    assert "Intro paragraph." in markdown
    assert "Author name goes here." in markdown


def test_an_inline_control_keeps_its_place_in_the_sentence(tmp_path):
    doc = docx.Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("Before ")
    trailing = paragraph.add_run(" after.")

    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "CONTROLLED"
    run.append(text)
    trailing._r.addprevious(sdt(run, alias="Inline"))

    assert "Before CONTROLLED after." in convert(doc, tmp_path)


def test_nested_controls_unwrap_all_the_way_down(tmp_path):
    doc = docx.Document()
    wrap_in_place(doc.add_paragraph("Innermost text.")._p)
    # Wrap the control that now stands where the paragraph did.
    body = doc.element.body
    inner = body.findall(f"{{{W}}}sdt")[0]
    index = body.index(inner)
    body.remove(inner)
    body.insert(index, sdt(inner, alias="Outer"))

    assert "Innermost text." in convert(doc, tmp_path)


def test_a_controlled_table_survives(tmp_path):
    doc = docx.Document()
    table = doc.add_table(rows=2, cols=2)
    for row, values in zip(table.rows, (("H1", "H2"), ("A1", "B1")), strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    wrap_in_place(table._tbl)

    markdown = convert(doc, tmp_path)
    for value in ("H1", "H2", "A1", "B1"):
        assert value in markdown


def test_a_controlled_row_survives(tmp_path):
    doc = docx.Document()
    table = doc.add_table(rows=2, cols=2)
    for row, values in zip(table.rows, (("H1", "H2"), ("A1", "B1")), strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    wrap_in_place(table.rows[1]._tr)

    markdown = convert(doc, tmp_path)
    assert "A1" in markdown
    assert "B1" in markdown


def test_a_controlled_cell_paragraph_survives(tmp_path):
    doc = docx.Document()
    table = doc.add_table(rows=2, cols=2)
    for row, values in zip(table.rows, (("H1", "H2"), ("A1", "B1")), strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    wrap_in_place(table.rows[1].cells[0].paragraphs[0]._p)

    markdown = convert(doc, tmp_path)
    assert "A1" in markdown
    assert "B1" in markdown


def test_placeholder_text_is_what_the_page_prints(tmp_path):
    # An unfilled control shows Word's boilerplate, and a template's empty fields
    # are much of what makes the template worth reading.
    doc = docx.Document()
    paragraph = doc.add_paragraph("Click or tap here to enter text.")
    element = paragraph._p
    parent = element.getparent()
    index = parent.index(element)
    parent.remove(element)
    parent.insert(index, sdt(element, alias="Empty", showing_placeholder=True))

    assert "Click or tap here to enter text." in convert(doc, tmp_path)


def test_a_control_with_no_content_element_just_goes():
    doc = docx.Document()
    body = doc.element.body
    empty = OxmlElement("w:sdt")
    empty.append(OxmlElement("w:sdtPr"))
    body.insert(0, empty)

    assert unwrap_content_controls(body) == 1
    assert not document_has_content_controls(body)


def test_a_document_without_controls_is_left_alone():
    doc = docx.Document()
    doc.add_paragraph("Ordinary text.")

    assert document_has_content_controls(doc.element) is False
    assert unwrap_content_controls(doc.element) == 0


def test_the_caller_s_document_is_not_edited_underneath_them(tmp_path):
    # Converting a Document the caller opened must not strip the controls out of it.
    doc = docx.Document()
    wrap_in_place(doc.add_paragraph("Controlled text.")._p)
    path = tmp_path / "caller-owned.docx"
    doc.save(str(path))

    reopened = docx.Document(str(path))
    markdown = MarkdownRenderer().render_to_string(DocxToAstConverter().convert_to_ast(reopened))
    assert "Controlled text." in markdown
    assert document_has_content_controls(reopened.element) is True
