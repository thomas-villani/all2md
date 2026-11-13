#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_page_breaks.py
"""Pages a PDF's author ended on purpose start a new page in Word too.

A page that ends early is a page break only when what opens the next page would have
fit in the space left; otherwise the word processor moved it on because it did not fit.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Heading, Paragraph, Table, TableCell, TableRow, Text
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_page_breaks import PageExtent, ends_on_purpose, page_extent

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LINE = "The plant ran three shifts through the winter and met every delivery date on time."


def _block(top: float, lines: int, pitch: float = 14.0) -> dict:
    return {
        "type": 0,
        "lines": [
            {"bbox": (72, top + n * pitch, 540, top + n * pitch + 11), "spans": [{"text": LINE}]} for n in range(lines)
        ],
    }


def test_the_opening_is_three_lines_of_text() -> None:
    extent = page_extent([_block(72, 10)])
    assert extent is not None
    assert (extent.top, extent.bottom) == (72, 72 + 9 * 14 + 11)
    assert extent.opening == 2 * 14 + 11
    assert extent.line_pitch == 14


def test_a_figure_opening_the_page_moves_whole() -> None:
    extent = page_extent([_block(400, 5)], regions=[(72, 72, 540, 380)])
    assert extent is not None
    assert extent.top == 72
    assert extent.opening == 380 - 72


def test_a_page_with_room_for_the_next_opening_was_ended_on_purpose() -> None:
    following = PageExtent(top=72, bottom=700, opening=39, line_pitch=14)
    assert ends_on_purpose(PageExtent(72, 400, 39, 14), following, body_bottom=720, page_height=792)
    # Room for two lines: the next page's opening could not have fit.
    assert not ends_on_purpose(PageExtent(72, 692, 39, 14), following, body_bottom=720, page_height=792)


def _pdf(tmp_path: Path, pages: list[tuple[str | None, int]]) -> str:
    """Pages of ``(heading, lines)``; a page is filled from the top margin down."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for number, (heading, lines) in enumerate(pages, 1):
        page = doc.new_page(width=612, height=792)
        baseline = 84.0
        if heading:
            page.insert_text((72, baseline + 6), heading, fontsize=18)
            baseline += 30
        for n in range(lines):
            page.insert_text((72, baseline), f"{LINE} ({number}.{n})", fontsize=11)
            baseline += 14.0
    path = tmp_path / "breaks.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


FULL = 45  # lines that reach the bottom margin


def _marked(path: str, **options) -> list[str]:
    doc = to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled", **options))
    return [
        "".join(getattr(part, "content", "") for part in getattr(node, "content", []))
        for node in doc.children
        if node.metadata.get("page_break_before")
    ]


def test_a_section_started_on_a_new_page_is_marked(tmp_path: Path) -> None:
    path = _pdf(tmp_path, [("Terms", FULL), (None, 12), ("Exhibit A", 20)])
    assert [text.strip() for text in _marked(path)] == ["Exhibit A"]


def test_a_page_that_ran_full_is_not_marked(tmp_path: Path) -> None:
    path = _pdf(tmp_path, [("Terms", FULL), ("Renewal", FULL), ("Exhibit A", 20)])
    assert _marked(path) == []


def test_marking_can_be_turned_off(tmp_path: Path) -> None:
    path = _pdf(tmp_path, [("Terms", FULL), (None, 12), ("Exhibit A", 20)])
    assert _marked(path, keep_page_breaks=False) == []


def _document_xml(*children) -> str:
    pytest.importorskip("docx")
    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    out = io.BytesIO()
    DocxRenderer(DocxRendererOptions()).render(Document(children=list(children)), out)
    return zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")


def _paragraphs(xml: str) -> list[str]:
    return re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)


def test_the_docx_renderer_starts_a_new_page_before_the_marked_block() -> None:
    xml = _document_xml(
        Paragraph(content=[Text(content="Signatures")]),
        Heading(level=1, content=[Text(content="Exhibit A")], metadata={"page_break_before": True}),
        Paragraph(content=[Text(content="Floor plan")]),
    )
    flagged = [p for p in _paragraphs(xml) if "<w:pageBreakBefore/>" in p]
    assert len(flagged) == 1 and "Exhibit A" in flagged[0]


def test_a_marked_table_breaks_before_its_first_cell() -> None:
    table = Table(
        header=TableRow(cells=[TableCell(content=[Text(content="Site")]), TableCell(content=[Text(content="kWh")])]),
        rows=[TableRow(cells=[TableCell(content=[Text(content="North")]), TableCell(content=[Text(content="120")])])],
        metadata={"page_break_before": True},
    )
    xml = _document_xml(Paragraph(content=[Text(content="Summary")]), table)
    flagged = [p for p in _paragraphs(xml) if "<w:pageBreakBefore/>" in p]
    assert len(flagged) == 1 and "Site" in flagged[0]
