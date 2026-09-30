"""XML comments and processing instructions inside a DOCX's parts.

Word ignores ``<!-- ... -->`` and ``<?pi ...?>`` nodes wherever they sit. lxml hands
them back from ``iter()`` and ``iterchildren()`` alongside the elements, with a
function, not a string, as their ``tag``, so a reader that calls a string method on
every child's tag crashes. Three files in LibreOffice's Writer regression corpus that
Word opens fine (n758883, tdf129353, tdf95777) failed that way.
"""

from io import BytesIO

import docx
import pytest
from docx.oxml.ns import qn
from lxml import etree

from all2md import to_markdown
from all2md.parsers.docx import _collect_abstract_numbering_defs, _map_num_ids_to_abstract_nums

pytestmark = [pytest.mark.unit, pytest.mark.docx]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _stray_nodes():
    return [etree.Comment(" generator note "), etree.ProcessingInstruction("mso-hint", "x")]


def _save(document) -> bytes:
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_comments_between_body_blocks_are_skipped():
    document = docx.Document()
    document.add_paragraph("Before the table.")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Cell text"
    document.add_paragraph("After the table.")
    body = document.element.body
    for index in (2, 1, 0):
        for node in _stray_nodes():
            body.insert(index, node)

    markdown = to_markdown(_save(document), source_format="docx")

    assert "Before the table." in markdown
    assert "Cell text" in markdown
    assert "After the table." in markdown
    assert "generator note" not in markdown


def test_comments_inside_a_paragraph_and_its_runs_are_skipped():
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("First run. ")
    paragraph.add_run("Second run.")
    paragraph._p.insert(0, etree.Comment(" paragraph comment "))
    paragraph._p.append(etree.ProcessingInstruction("mso-hint", "x"))
    first_run = paragraph.runs[0]._r
    first_run.insert(0, etree.Comment(" run comment "))
    first_run.find(qn("w:t")).append(etree.Comment(" text comment "))

    markdown = to_markdown(_save(document), source_format="docx")

    assert "First run. Second run." in markdown
    assert "comment" not in markdown


def test_comments_inside_table_cells_are_skipped():
    document = docx.Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Left"
    table.cell(0, 1).text = "Right"
    table.cell(0, 0)._tc.insert(0, etree.Comment(" cell comment "))
    table.rows[0]._tr.append(etree.Comment(" row comment "))

    markdown = to_markdown(_save(document), source_format="docx")

    assert "Left" in markdown
    assert "Right" in markdown
    assert "comment" not in markdown


def test_numbering_definitions_read_past_comments():
    xml = etree.fromstring(
        (
            f'<w:numbering xmlns:w="{W}"><!-- abstract definitions -->'
            '<w:abstractNum w:abstractNumId="0"><!-- levels -->'
            '<w:lvl w:ilvl="0"><?mso-hint x?><w:numFmt w:val="decimal"/></w:lvl>'
            "</w:abstractNum><!-- instances -->"
            '<w:num w:numId="1"><!-- link --><w:abstractNumId w:val="0"/></w:num>'
            "</w:numbering>"
        ).encode()
    )

    abstracts = _collect_abstract_numbering_defs(xml)
    assert abstracts == {"0": {"0": "number"}}
    assert _map_num_ids_to_abstract_nums(xml, abstracts) == {"1": {"0": "number"}}
