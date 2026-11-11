#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_shaded_cells.py
"""Shaded table cells do not add columns.

Word shades a cell twice, over the whole cell and again inset by its padding, and
``find_tables()`` takes the edges of both rectangles as column boundaries. A vendor form's
4x4 grid of shaded labels arrived as 4x8, which the empty-cell guard then rejected, and an
annual report's 6x4 table with a shaded header and banded rows as 6x12. The strips a
cell's padding leaves are folded back into the column they belong to.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Table
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LEFT, WIDTH, ROW, PAD, RULE = 72.0, 117.0, 12.0, 5.4, 0.5
GRAY, BLUE = (0.9, 0.9, 0.9), (0.27, 0.45, 0.77)


def _grid_pdf(tmp_path: Path, rows: list[list[str]], shade: list[list[tuple[float, float, float] | None]]) -> str:
    """Draw a ruled grid the way Word draws one.

    Borders are thin filled rectangles; each shaded cell is filled once over the cell and
    once inset by its padding.
    """
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    top = 100.0
    n_cols = len(rows[0])
    for r, row in enumerate(rows):
        y0, y1 = top + r * ROW, top + (r + 1) * ROW
        for c, text in enumerate(row):
            x0, x1 = LEFT + c * WIDTH, LEFT + (c + 1) * WIDTH
            fill = shade[r][c]
            if fill is not None:
                page.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=None, fill=fill, width=0)
                page.draw_rect(pymupdf.Rect(x0 + PAD, y0, x1 - PAD, y1), color=None, fill=fill, width=0)
            if text:
                page.insert_text((x0 + PAD, y1 - 3), text, fontsize=9)
    right = LEFT + n_cols * WIDTH
    bottom = top + len(rows) * ROW
    for r in range(len(rows) + 1):
        y = top + r * ROW
        page.draw_rect(pymupdf.Rect(LEFT, y - RULE, right, y), color=None, fill=(0, 0, 0), width=0)
    for c in range(n_cols + 1):
        x = LEFT + c * WIDTH
        page.draw_rect(pymupdf.Rect(x - RULE, top, x, bottom), color=None, fill=(0, 0, 0), width=0)
    path = tmp_path / "grid.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _tables(path: str) -> list[list[list[str]]]:
    doc = to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled"))
    tables = []
    for node in doc.children:
        if isinstance(node, Table):
            rows = ([node.header] if node.header else []) + list(node.rows)
            tables.append([[" ".join(extract_text(cell).split()) for cell in row.cells] for row in rows])
    return tables


def test_a_form_with_shaded_labels_keeps_its_columns(tmp_path: Path) -> None:
    rows = [
        ["Legal name", "", "Trading name", ""],
        ["Registered address", "", "City", ""],
        ["Tax ID", "", "Phone", ""],
    ]
    shade = [[GRAY, None, GRAY, None] for _ in rows]
    assert _tables(_grid_pdf(tmp_path, rows, shade)) == [rows]


def test_banded_rows_keep_their_text_in_its_column(tmp_path: Path) -> None:
    """An unshaded row draws one cell across the strips; its text stays in its column."""
    rows = [
        ["Site", "Electricity", "Change", "Share"],
        ["Tilbury", "18,450", "-6.2%", "41%"],
        ["Hull", "12,310", "-3.8%", "37%"],
        ["Leeds", "9,870", "-1.1%", "52%"],
    ]
    shade = [[BLUE] * 4, [GRAY] * 4, [None] * 4, [GRAY] * 4]
    assert _tables(_grid_pdf(tmp_path, rows, shade)) == [rows]


def test_an_unshaded_grid_is_unchanged(tmp_path: Path) -> None:
    rows = [["Phase", "Scope", "Start"], ["One", "Design", "May"], ["Two", "Build", "June"]]
    assert _tables(_grid_pdf(tmp_path, rows, [[None] * 3 for _ in rows])) == [rows]


def test_a_cell_read_as_full_and_inset_rectangles_is_left_alone() -> None:
    """Both rectangles of one cell read its words; folding them together would print them twice."""
    from types import SimpleNamespace

    from all2md.parsers._pdf_tables import collapse_phantom_columns

    header = [
        (72, 0, 126, 1),
        (126, 0, 131, 1),
        (131, 0, 211, 1),
        (211, 0, 216, 1),
        (216, 0, 221, 1),
        (221, 0, 535, 1),
        (535, 0, 540, 1),
    ]
    doubled = [
        (72, 1, 126, 2),
        (126, 1, 131, 2),
        (131, 1, 211, 2),
        (211, 1, 216, 2),
        (216, 1, 540, 2),
        (221, 1, 535, 2),
        None,
    ]
    table = SimpleNamespace(rows=[SimpleNamespace(cells=header), SimpleNamespace(cells=doubled)])
    data = [
        ["", "", "NME", "", "", "LASA Names", ""],
        ["1", "", "Vidaza", "", "Videx, Vitrase", "Videx, Vitrase", ""],
    ]
    assert collapse_phantom_columns(table, data) is None
