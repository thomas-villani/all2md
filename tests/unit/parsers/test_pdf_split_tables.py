#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_split_tables.py
"""A table the page break splits is one table.

Word carries a long table over to the next page at the same x positions, often repeating
its header row there. Read page by page it became two tables, with the page's footer and
the next page's running header between them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Paragraph, Table
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

ROW, PAD = 16.0, 4.0
HEADER = ["Site", "Electricity", "Gas", "Change"]
FIRST = [
    ["Tilbury", "18,450", "6,210", "-6.2%"],
    ["Hull", "12,310", "4,980", "-3.8%"],
    ["Leeds", "9,870", "3,115", "-1.1%"],
]
SECOND = [["York", "7,640", "2,870", "-0.4%"], ["Derby", "6,105", "2,230", "+1.2%"]]


def _grid(page, top: float, left: float, widths: list[float], rows: list[list[str]]) -> None:
    edges = [left]
    for width in widths:
        edges.append(edges[-1] + width)
    bottom = top + ROW * len(rows)
    for r in range(len(rows) + 1):
        page.draw_line((edges[0], top + r * ROW), (edges[-1], top + r * ROW), width=0.5)
    for x in edges:
        page.draw_line((x, top), (x, bottom), width=0.5)
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            page.insert_text((edges[c] + PAD, top + (r + 1) * ROW - PAD), text, fontsize=9)


def _two_pages(
    tmp_path: Path,
    *,
    repeat_header: bool = True,
    second_left: float = 72.0,
    between: str | None = None,
) -> str:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    widths = [140.0, 110.0, 110.0, 90.0]
    first = doc.new_page(width=612, height=792)
    first.insert_text((72, 90), "Energy use by site, in megawatt hours.", fontsize=10)
    top = 792 - 90 - ROW * (len(FIRST) + 1)
    _grid(first, top, 72.0, widths, [HEADER, *FIRST])
    first.insert_text((72, 760), "Energy report, page 1", fontsize=8)
    second = doc.new_page(width=612, height=792)
    second.insert_text((72, 40), "Kestrel Ridge Manufacturing", fontsize=8)
    start = 72.0
    if between:
        second.insert_text((72, start + 10), between, fontsize=10)
        start += 30
    _grid(second, start, second_left, widths, ([HEADER] if repeat_header else []) + SECOND)
    second.insert_text((72, 400), "Figures are unaudited.", fontsize=10)
    path = tmp_path / "split.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _convert(path: str, **options) -> list:
    return to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled", **options)).children


def _rows(table: Table) -> list[list[str]]:
    rows = ([table.header] if table.header else []) + list(table.rows)
    return [[" ".join(extract_text(cell).split()) for cell in row.cells] for row in rows]


def _tables(nodes: list) -> list[list[list[str]]]:
    return [_rows(node) for node in nodes if isinstance(node, Table)]


def test_a_table_split_by_a_page_break_is_joined_and_its_repeated_header_dropped(tmp_path: Path) -> None:
    nodes = _convert(_two_pages(tmp_path))
    assert _tables(nodes) == [[HEADER, *FIRST, *SECOND]]
    texts = [" ".join(extract_text(node).split()) for node in nodes if isinstance(node, Paragraph)]
    # The margin text is kept, after the joined table, and the prose after it follows.
    table_at = next(i for i, node in enumerate(nodes) if isinstance(node, Table))
    after = [" ".join(extract_text(node).split()) for node in nodes[table_at + 1 :] if isinstance(node, Paragraph)]
    assert "Energy report, page 1" in after
    assert "Kestrel Ridge Manufacturing" in after
    assert texts[-1] == "Figures are unaudited."


def test_a_continuation_without_a_repeated_header_keeps_its_first_row(tmp_path: Path) -> None:
    assert _tables(_convert(_two_pages(tmp_path, repeat_header=False))) == [[HEADER, *FIRST, *SECOND]]


def test_tables_at_different_edges_stay_apart(tmp_path: Path) -> None:
    assert len(_tables(_convert(_two_pages(tmp_path, second_left=110.0)))) == 2


def test_tables_with_body_text_between_them_stay_apart(tmp_path: Path) -> None:
    path = _two_pages(tmp_path, between="Table 2 reports the remaining sites.")
    assert len(_tables(_convert(path))) == 2


def test_joining_can_be_turned_off(tmp_path: Path) -> None:
    assert len(_tables(_convert(_two_pages(tmp_path), join_split_tables=False))) == 2


def _line(bbox: tuple[float, float, float, float], text: str) -> dict:
    return {"bbox": bbox, "spans": [{"text": text}]}


def _block(*lines: dict) -> dict:
    xs0, ys0, xs1, ys1 = zip(*(line["bbox"] for line in lines), strict=True)
    return {"bbox": (min(xs0), min(ys0), max(xs1), max(ys1)), "lines": list(lines)}


TABLE = (72.0, 100.0, 540.0, 300.0)


def test_a_last_row_with_words_trailing_blank_line_belongs_to_the_table() -> None:
    from all2md.parsers.pdf import _block_in_table_region

    pymupdf = pytest.importorskip("pymupdf")
    # The row lies inside the table and the blank paragraph below it outside, so the block
    # as a whole is under half inside (16 of 34pt).
    block = _block(_line((80, 284, 300, 298), "Sites 412 398"), _line((80, 298, 300, 318), " "))
    assert _block_in_table_region(block, [pymupdf.Rect(TABLE)])
    trailing_text = _block(_line((80, 284, 300, 298), "Sites 412 398"), _line((80, 298, 300, 318), "Note"))
    assert not _block_in_table_region(trailing_text, [pymupdf.Rect(TABLE)])


def test_text_straddling_a_table_edge_is_not_taken_by_trimming_blank_lines() -> None:
    from all2md.parsers.pdf import _block_in_table_region

    pymupdf = pytest.importorskip("pymupdf")
    # A rotated heading half in the table, with a blank line far below it: kept as text.
    heading = _block(_line((40, 200, 52, 420), "ATTACHMENT II"), _line((40, 700, 52, 703), " "))
    assert not _block_in_table_region(heading, [pymupdf.Rect(TABLE)])
    # A blank line above the text does not count as Word's trailing paragraph.
    caption = _block(_line((80, 60, 90, 110), " "), _line((80, 104, 300, 116), "Top insulated wall"))
    assert not _block_in_table_region(caption, [pymupdf.Rect(TABLE)])
