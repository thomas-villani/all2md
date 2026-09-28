"""Characters XML cannot carry must not fail a whole DOCX or EPUB render.

PDF text layers routinely hold C0 control characters -- a glyph whose font encoding maps
nowhere, such as the U+0002 a publisher's PDF carries where it prints a copyright sign.
lxml refuses any string holding one, and before this fix a single such character failed
the whole document: PDF -> DOCX failed on 18 of the 66 articles in the PMC development
corpus (``python -m benchmarks.pmc docx``).
"""

from __future__ import annotations

import logging
from io import BytesIO

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Table, TableCell, TableRow, Text
from all2md.ast.nodes import Figure
from all2md.ast.transforms import XML_ILLEGAL_CHARACTERS, remove_xml_illegal_characters
from all2md.ast.utils import extract_text

pytestmark = pytest.mark.unit


def _dirty() -> Document:
    return Document(
        children=[
            Heading(level=1, content=[Text("Title\x03")]),
            Paragraph(
                content=[
                    Text("S. Acharya \x02 B. Aggarwal\x08, tab\tand\nnewline kept"),
                    Link(url="https://example.org/\x01a", content=[Text("li\x04nk")]),
                ]
            ),
            Table(
                header=TableRow(cells=[TableCell(content=[Text("head\x05")])], is_header=True),
                rows=[TableRow(cells=[TableCell(content=[Text("cell\x06")])])],
            ),
            Figure(
                children=[Paragraph(content=[Image(url="", alt_text="alt\x07")])],
                caption="Figure 1\x1f caption",
            ),
        ],
        metadata={"title": "t\x02itle", "keywords": ["k\x0bey"]},
    )


def _clean() -> Document:
    return Document(children=[Paragraph(content=[Text("nothing to remove\there\n")])])


def test_a_clean_tree_is_returned_as_is_and_uncopied() -> None:
    document = _clean()
    cleaned, removed = remove_xml_illegal_characters(document)
    assert removed == 0
    assert cleaned is document


def test_every_string_field_is_cleaned_and_the_input_is_not_mutated() -> None:
    document = _dirty()
    cleaned, removed = remove_xml_illegal_characters(document)

    assert removed == 11
    assert cleaned is not document
    assert isinstance(cleaned, Document)
    heading, paragraph, table, figure = cleaned.children
    assert extract_text(heading) == "Title"
    assert paragraph.content[0].content == "S. Acharya  B. Aggarwal, tab\tand\nnewline kept"
    assert paragraph.content[1].url == "https://example.org/a"
    assert extract_text(paragraph.content[1]) == "link"
    assert extract_text(table) == "head cell"
    assert figure.caption == "Figure 1 caption"
    assert figure.children[0].content[0].alt_text == "alt"
    assert cleaned.metadata == {"title": "title", "keywords": ["key"]}

    # The caller's tree still holds exactly what it held.
    assert document.children[0].content[0].content == "Title\x03"
    assert document.metadata["keywords"] == ["k\x0bey"]


def test_the_pattern_is_exactly_the_complement_of_xml_char() -> None:
    """Every code point, against XML 1.0's own ``Char`` production.

    CodeQL flags the U+000E to U+001F range as possibly over-broad. It is not, and this is
    the proof: the pattern matches no character XML allows and misses none it forbids.
    """

    def xml_char(code: int) -> bool:
        return (
            code in (0x9, 0xA, 0xD) or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
        )

    disagreements = [
        hex(code) for code in range(0x110000) if bool(XML_ILLEGAL_CHARACTERS.match(chr(code))) == xml_char(code)
    ]
    assert disagreements == []


def test_unpaired_surrogates_and_noncharacters_are_removed() -> None:
    document = Document(children=[Paragraph(content=[Text("a\ud800b\ufffec\uffffd")])])
    cleaned, removed = remove_xml_illegal_characters(document)
    assert removed == 3
    assert extract_text(cleaned) == "abcd"


@pytest.mark.docx
def test_docx_renders_a_document_holding_control_characters(caplog: pytest.LogCaptureFixture) -> None:
    pytest.importorskip("docx")
    from all2md import from_ast, to_ast

    with caplog.at_level(logging.WARNING, logger="all2md.renderers.docx"):
        rendered = from_ast(_dirty(), "docx")
    assert isinstance(rendered, bytes)
    assert any("Removed 11 control character(s) DOCX cannot store" in record.message for record in caplog.records)

    text = extract_text(to_ast(BytesIO(rendered), source_format="docx"))
    assert "S. Acharya  B. Aggarwal" in text
    assert "head" in text and "cell" in text


def test_epub_renders_a_document_holding_control_characters(caplog: pytest.LogCaptureFixture) -> None:
    pytest.importorskip("ebooklib")
    from all2md import from_ast

    with caplog.at_level(logging.WARNING, logger="all2md.renderers.epub"):
        rendered = from_ast(_dirty(), "epub")
    assert isinstance(rendered, bytes)
    assert rendered[:2] == b"PK"
    assert any("control character(s) EPUB cannot store" in record.message for record in caplog.records)
