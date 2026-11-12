#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_running_furniture.py
"""Running headers and footers leave the body and are kept in the metadata.

Word prints a document's header and footer on every page; read page by page they became
body paragraphs above each page's text. A line repeated at the same place in the page
margin on two or more pages is now taken out of the body and kept as ``page_header`` /
``page_footer``, page numbers as ``{page}``, and the DOCX renderer writes it back as a
real Word header and footer.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Paragraph, Text
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_furniture import detect_running_furniture, running_template, running_templates

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

HEADER = "Kestrel Ridge Manufacturing"
BODY = [
    "The plant ran three shifts through the winter and met every delivery date.",
    "Maintenance moved to the weekend, which cut unplanned stops by a third.",
    "Energy use per unit fell again, for the fourth year running.",
]


def _pdf(
    tmp_path: Path, pages: int = 3, *, header: str = HEADER, footer: str = "Annual report, page {n} of {total}"
) -> str:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 40), header, fontsize=9)
        for i, line in enumerate(BODY):
            page.insert_text((72, 140 + 60 * i + 7 * n), f"{line} ({n})", fontsize=11)
        page.insert_text((72, 760), footer.format(n=n, total=pages), fontsize=9)
    path = tmp_path / "report.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _texts(doc: Document) -> list[str]:
    return [" ".join(extract_text(node).split()) for node in doc.children if isinstance(node, Paragraph)]


def _convert(path: str, **options) -> Document:
    return to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled", **options))


def test_running_header_and_footer_leave_the_body_for_the_metadata(tmp_path: Path) -> None:
    doc = _convert(_pdf(tmp_path))
    texts = _texts(doc)
    assert not any(HEADER in text or "Annual report" in text for text in texts)
    assert sum(BODY[0] in text for text in texts) == 3
    assert doc.metadata["page_header"] == HEADER
    assert doc.metadata["page_footer"] == "Annual report, page {page} of {pages}"


def test_a_single_page_keeps_its_margin_text(tmp_path: Path) -> None:
    doc = _convert(_pdf(tmp_path, pages=1))
    texts = _texts(doc)
    assert any(HEADER in text for text in texts)
    assert any("Annual report, page 1 of 1" in text for text in texts)
    assert "page_header" not in doc.metadata


def test_extraction_can_be_turned_off(tmp_path: Path) -> None:
    doc = _convert(_pdf(tmp_path), extract_running_headers_footers=False)
    assert sum(HEADER in text for text in _texts(doc)) == 3
    assert "page_header" not in doc.metadata


def test_trimming_still_deletes_instead(tmp_path: Path) -> None:
    doc = _convert(_pdf(tmp_path), auto_trim_headers_footers=True)
    assert not any(HEADER in text for text in _texts(doc))
    assert "page_header" not in doc.metadata


def _block(text: str, bbox: tuple[float, float, float, float]) -> dict:
    return {"type": 0, "bbox": bbox, "lines": [{"bbox": bbox, "spans": [{"text": text}]}]}


def test_a_line_that_moves_with_the_text_is_not_running() -> None:
    pages = [([_block("Results", (72, 60 + 30 * n, 200, 72 + 30 * n))], 792.0) for n in range(3)]
    assert detect_running_furniture(pages, min_occurrences=2) is None


def test_a_repeated_table_header_row_below_the_running_header_stays_in_the_body() -> None:
    header = _block(HEADER, (72, 30, 300, 42))
    # Inside the top tenth of the page, as a table carried onto the next page sits.
    row = _block("Site Electricity Gas", (72, 50, 500, 64))
    body = _block("Body text", (72, 300, 500, 320))
    furniture = detect_running_furniture([([header, row, body], 792.0)] * 2, min_occurrences=2)
    assert furniture is not None
    # The row repeats at the same place too, but it lies in a table: only the header goes.
    kept = furniture.take([header, row, body], 1, 792.0, keep_out=[(70, 48, 510, 200)])
    assert kept == [row, body]
    # Text above a candidate means it is not the outermost line, so it is not furniture.
    stamp = _block("DRAFT", (72, 10, 120, 20))
    furniture = detect_running_furniture([([row, body], 792.0)] * 2, min_occurrences=2)
    assert furniture is not None
    assert furniture.take([stamp, row, body], 1, 792.0) == [stamp, row, body]


def test_a_line_below_the_top_tenth_of_the_page_is_not_running() -> None:
    # A table's caption repeated at the top of each continuation page sits about an
    # eighth of the way down, under the running head: body, however anchored it is.
    caption = _block("Table 1. Continued", (72, 95, 300, 108))
    assert detect_running_furniture([([caption], 792.0)] * 3, min_occurrences=2) is None


@pytest.mark.parametrize(
    ("occurrences", "total", "expected"),
    [
        ([(1, "Page 1 of 3"), (2, "Page 2 of 3"), (3, "Page 3 of 3")], 3, ("Page {page} of {pages}", 1)),
        ([(2, "Invoice 20648, page 2"), (3, "Invoice 20648, page 3")], 3, ("Invoice 20648, page {page}", 1)),
        (
            [(1, "Form PR-104 (Rev. 03/2026)"), (2, "Form PR-104 (Rev. 03/2026)")],
            2,
            ("Form PR-104 (Rev. 03/2026)", None),
        ),
        # A report whose first page is numbered 131 keeps that as the start.
        ([(1, "131"), (2, "132"), (5, "135")], 9, ("{page}", 131)),
        # Numbers that change but do not follow the page stay as page 1 printed them.
        ([(1, "Draft 7"), (2, "Draft 9")], 2, ("Draft 7", None)),
        # Numbering that would give page 1 a negative number is kept as printed.
        ([(4, "1"), (5, "2")], 9, ("1", None)),
    ],
)
def test_page_numbers_become_placeholders_and_other_digits_stay(occurrences, total, expected) -> None:
    assert running_template(occurrences, total) == expected


def test_every_distinct_running_line_is_kept() -> None:
    # Odd and even pages carry different running heads; neither may be lost.
    occurrences = [
        (1, "Outlook, page 1"),
        (2, "Commodity Spotlight"),
        (3, "Outlook, page 3"),
        (4, "Commodity Spotlight"),
    ]
    assert running_templates(occurrences, 4) == [("Outlook, page {page}", 1), ("Commodity Spotlight", None)]


def test_the_docx_renderer_writes_a_word_header_and_footer_with_page_fields() -> None:
    pytest.importorskip("docx")
    from all2md.renderers.docx import DocxRenderer

    doc = Document(
        children=[Paragraph(content=[Text(content="Body")])],
        metadata={"page_header": "Suite 310 Lease", "page_footer": "Lease, page {page} of {pages}"},
    )
    out = io.BytesIO()
    DocxRenderer().render(doc, out)
    parts = zipfile.ZipFile(out)
    header = next(n for n in parts.namelist() if re.match(r"word/header\d*\.xml", n))
    footer = next(n for n in parts.namelist() if re.match(r"word/footer\d*\.xml", n))
    assert "Suite 310 Lease" in parts.read(header).decode("utf-8")
    footer_xml = parts.read(footer).decode("utf-8")
    assert "Lease, page " in footer_xml
    assert re.search(r'w:instr=" PAGE ', footer_xml)
    assert re.search(r'w:instr=" NUMPAGES ', footer_xml)
    assert "Suite 310 Lease" not in parts.read("word/document.xml").decode("utf-8")


def test_the_docx_renderer_starts_page_numbering_where_the_pdf_did() -> None:
    pytest.importorskip("docx")
    from all2md.renderers.docx import DocxRenderer

    doc = Document(
        children=[Paragraph(content=[Text(content="Body")])],
        metadata={"page_footer": "{page}", "page_number_start": 131},
    )
    out = io.BytesIO()
    DocxRenderer().render(doc, out)
    body = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
    section = re.search(r"<w:sectPr.*?</w:sectPr>", body, re.S)
    assert section is not None
    assert 'w:pgNumType w:start="131"' in section.group()
    # Schema order: pgNumType precedes cols and docGrid.
    tags = re.findall(r"<w:(pgNumType|cols|docGrid)[ />]", section.group())
    assert tags.index("pgNumType") < min(tags.index(t) for t in ("cols", "docGrid") if t in tags)


def test_small_capitals_split_into_spans_are_read_as_one_word() -> None:
    from all2md.parsers._pdf_furniture import block_text

    line = {
        "spans": [
            {"text": "FY05 E", "bbox": (72, 30, 110, 40), "size": 9.0},
            {"text": "NGINEERING", "bbox": (110.2, 31, 170, 40), "size": 7.0},
            {"text": "Report", "bbox": (180, 30, 210, 40), "size": 9.0},
        ]
    }
    assert block_text({"type": 0, "bbox": (72, 30, 210, 40), "lines": [line]}) == "FY05 ENGINEERING Report"
