"""Tables nested in table cells, and text boxes anchored in them.

A table cell holds inline content only, so a table nested in it cannot stay a table:
its cells are read in place as lines of the outer cell, row by row, as a cell's own
paragraphs are. A text box anchored in a cell is read the same way, after its anchor.
Before this, a cell read only its own paragraphs, and LibreOffice's Writer regression
corpus lost a nested table's words whole in 28 files.

Nesting is capped. Word gives up somewhere past thirty levels, but a hand-made file can
nest until the XML parser refuses it; past the cap a table's paragraphs are read flat,
without recursion, so every word is still read and the cost stays linear.
"""

import time
import zipfile
from io import BytesIO

import docx
import pytest

from all2md import to_markdown
from all2md.ast.nodes import Table, Text, get_node_children
from all2md.exceptions import MalformedFileError
from all2md.options import DocxOptions
from all2md.parsers.docx import _MAX_NESTED_TABLE_DEPTH, DocxToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.docx]

# The one namespace python-docx's template root does not declare.
A_URI = "http://schemas.openxmlformats.org/drawingml/2006/main"
WPS_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"


def para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def table(*rows: list[str]) -> str:
    """A table whose rows hold one cell per string, each string the cell's block XML."""
    columns = max(len(row) for row in rows)
    grid = "<w:tblGrid>" + "<w:gridCol/>" * columns + "</w:tblGrid>"
    body = "".join("<w:tr>" + "".join(f"<w:tc>{cell}</w:tc>" for cell in row) + "</w:tr>" for row in rows)
    return f"<w:tbl>{grid}{body}</w:tbl>"


def text_box(blocks: str) -> str:
    """A text box as Word writes it: DrawingML under mc:Choice, a VML copy under mc:Fallback."""
    dml = (
        '<w:drawing><wp:anchor><wp:docPr id="1" name="Text Box 1"/>'
        f'<a:graphic xmlns:a="{A_URI}"><a:graphicData uri="{WPS_URI}">'
        f"<wps:wsp><wps:txbx><w:txbxContent>{blocks}</w:txbxContent></wps:txbx></wps:wsp>"
        "</a:graphicData></a:graphic></wp:anchor></w:drawing>"
    )
    vml = f"<w:pict><v:rect><v:textbox><w:txbxContent>{blocks}</w:txbxContent></v:textbox></v:rect></w:pict>"
    return (
        f'<mc:AlternateContent><mc:Choice Requires="wps">{dml}</mc:Choice>'
        f"<mc:Fallback>{vml}</mc:Fallback></mc:AlternateContent>"
    )


def anchor(text: str, box: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r><w:r>{box}</w:r></w:p>"


def nested(levels: int) -> str:
    """``levels`` tables, each inside the single cell of the one before it."""
    xml = ""
    for level in range(levels, 0, -1):
        xml = table([para(f"level{level}start") + xml + para(f"level{level}end")])
    return xml


def document_with(body_xml: str) -> bytes:
    """A document whose body holds ``body_xml`` between two paragraphs.

    The XML is spliced into ``word/document.xml`` as text, so a document nested past
    what lxml will parse can still be written.
    """
    document = docx.Document()
    document.add_paragraph("Opening paragraph.")
    document.add_paragraph("PLACEHOLDER")
    document.add_paragraph("Closing paragraph.")
    buffer = BytesIO()
    document.save(buffer)
    placeholder = "<w:p><w:r><w:t>PLACEHOLDER</w:t></w:r></w:p>"
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(buffer.getvalue())) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "word/document.xml":
                xml = content.decode("utf8")
                # python-docx's template root declares every namespace the fragments use.
                assert xml.count(placeholder) == 1
                content = xml.replace(placeholder, body_xml).encode("utf8")
            target.writestr(item, content)
    return output.getvalue()


def parse(data: bytes, **options):
    return DocxToAstConverter(options=DocxOptions(**options)).parse(BytesIO(data))


def nodes_of_type(node, kind) -> list:
    found = [node] if isinstance(node, kind) else []
    for child in get_node_children(node):
        found.extend(nodes_of_type(child, kind))
    return found


def text_of(node) -> str:
    return " ".join(text.content for text in nodes_of_type(node, Text))


def test_a_nested_table_is_read_in_place_in_its_cell():
    inner = table([para("Inner A1"), para("Inner B1")], [para("Inner A2"), para("Inner B2")])
    data = document_with(table([para("Before inner.") + inner + para("After inner."), para("Right cell")]))

    ast = parse(data)
    tables = nodes_of_type(ast, Table)
    assert len(tables) == 1
    cell = tables[0].header.cells[0]
    words = text_of(cell)
    order = ["Before inner.", "Inner A1", "Inner B1", "Inner A2", "Inner B2", "After inner."]
    assert [words.index(item) for item in order] == sorted(words.index(item) for item in order)
    assert text_of(tables[0].header.cells[1]) == "Right cell"


def test_a_merged_cell_of_a_nested_table_is_read_once():
    restart = '<w:tcPr><w:vMerge w:val="restart"/></w:tcPr>'
    inner = (
        "<w:tbl><w:tblGrid><w:gridCol/></w:tblGrid>"
        f"<w:tr><w:tc>{restart}{para('Merged words')}</w:tc></w:tr>"
        f"<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr>{para('Merged words')}</w:tc></w:tr></w:tbl>"
    )
    markdown = to_markdown(document_with(table([para("Outer") + inner + "<w:p/>"])), source_format="docx")

    assert markdown.count("Merged words") == 1


def test_a_text_box_in_a_cell_is_read_once_after_its_anchor():
    cell = anchor("Anchor in cell.", text_box(para("Boxed in cell."))) + para("Cell tail.")
    markdown = to_markdown(document_with(table([cell])), source_format="docx")

    assert markdown.count("Boxed in cell.") == 1
    assert markdown.index("Anchor in cell.") < markdown.index("Boxed in cell.") < markdown.index("Cell tail.")


def test_a_table_in_a_text_box_in_a_cell_is_read():
    box = text_box(table([para("Deep one"), para("Deep two")]))
    markdown = to_markdown(document_with(table([anchor("Anchor.", box)])), source_format="docx")

    assert markdown.count("Deep one") == 1
    assert markdown.count("Deep two") == 1


def test_a_nested_table_is_read_when_tables_are_flattened():
    inner = table([para("Inner one"), para("Inner two")])
    ast = parse(document_with(table([para("Outer cell") + inner + "<w:p/>"])), preserve_tables=False)

    assert not nodes_of_type(ast, Table)
    words = text_of(ast)
    assert words.index("Outer cell") < words.index("Inner one") < words.index("Inner two")


def every_level_read_once(markdown: str, levels: int) -> None:
    for level in range(1, levels + 1):
        assert markdown.count(f"level{level}start") == 1, level
        assert markdown.count(f"level{level}end") == 1, level
    assert markdown.index(f"level{levels}start") < markdown.index(f"level{levels}end")


@pytest.mark.parametrize("levels", [_MAX_NESTED_TABLE_DEPTH, _MAX_NESTED_TABLE_DEPTH + 1])
def test_every_level_is_read_either_side_of_the_cap(levels):
    markdown = to_markdown(document_with(nested(levels)), source_format="docx")

    every_level_read_once(markdown, levels)


def test_a_box_past_the_cap_is_read_once():
    deepest = anchor("Deep anchor.", text_box(para("Deep boxed.")))
    xml = deepest
    for _ in range(_MAX_NESTED_TABLE_DEPTH + 2):
        xml = table([xml])

    markdown = to_markdown(document_with(xml), source_format="docx")

    assert markdown.count("Deep boxed.") == 1
    assert markdown.index("Deep anchor.") < markdown.index("Deep boxed.")


def test_nesting_to_the_xml_parser_limit_stays_bounded():
    # lxml refuses a document nested past 256 elements, a little over 60 tables deep
    # in the body. Everything short of that is read, in bounded time and size.
    levels = 60
    data = document_with(nested(levels))

    start = time.perf_counter()
    markdown = to_markdown(data, source_format="docx")
    elapsed = time.perf_counter() - start

    every_level_read_once(markdown, levels)
    assert elapsed < 10
    words = sum(len(f"level{level}start level{level}end") for level in range(1, levels + 1))
    assert len(markdown) < 4 * words + 500


def test_nesting_past_the_xml_parser_limit_is_a_malformed_file():
    with pytest.raises(MalformedFileError):
        to_markdown(document_with(nested(120)), source_format="docx")


def test_tables_past_the_cap_are_read_without_recursion(monkeypatch):
    from all2md.parsers import docx as docx_parser

    tables_read = []
    merged_table_rows = docx_parser._merged_table_rows

    def counting(table):
        tables_read.append(table)
        return merged_table_rows(table)

    monkeypatch.setattr(docx_parser, "_merged_table_rows", counting)
    markdown = to_markdown(document_with(nested(60)), source_format="docx")

    every_level_read_once(markdown, 60)
    assert len(tables_read) == _MAX_NESTED_TABLE_DEPTH
