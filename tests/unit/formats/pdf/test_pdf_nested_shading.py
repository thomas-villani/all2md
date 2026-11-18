"""Word's per-paragraph cell shading is not a cell grid.

Word paints a shaded cell once over the whole cell and again per paragraph, inset by
the cell padding, in the same color. find_tables() reads every filled rectangle's sides
as cell edges, so a 3x3 shaded table came out 6x9: a sliver column each side of every
cell and a row per paragraph. Fills nested in a same-colored fill are dropped first.
"""

from __future__ import annotations

import pymupdf
import pytest

from all2md.parsers._pdf_tables import find_tables_without_nested_shading, without_nested_shading

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]

GRAY = (0.88, 0.88, 0.88)


def _fill(x0: float, y0: float, x1: float, y1: float, color: tuple[float, ...] = GRAY) -> dict:
    return {"type": "f", "fill": color, "rect": pymupdf.Rect(x0, y0, x1, y1), "items": []}


def test_paragraph_shading_inside_a_cell_is_dropped() -> None:
    cell = _fill(72, 100, 200, 130)
    paragraphs = [_fill(77.4, 102, 194.6, 115), _fill(77.4, 115, 194.6, 128)]
    kept = without_nested_shading([cell, *paragraphs])
    assert kept == [cell]


def test_nothing_nested_leaves_the_drawings_alone() -> None:
    assert without_nested_shading([_fill(72, 100, 200, 130), _fill(200, 100, 330, 130)]) is None


def test_another_color_inside_is_an_edge() -> None:
    """A darker band inside a light cell is visible; its sides are real edges."""
    assert without_nested_shading([_fill(72, 100, 200, 130), _fill(77, 102, 195, 115, (0.5, 0.5, 0.5))]) is None


def test_a_page_background_does_not_swallow_its_cells() -> None:
    """A white page fill holds every white cell, far in from its sides: not a cell's shading."""
    white = (1.0, 1.0, 1.0)
    page = _fill(0, 0, 612, 792, white)
    cells = [_fill(72, 100, 200, 130, white), _fill(200, 100, 330, 130, white)]
    assert without_nested_shading([page, *cells]) is None


def test_rules_are_never_shading() -> None:
    """A border drawn as a thin fill inside a longer one is a rule, kept as the detector sees it."""
    black = (0.0, 0.0, 0.0)
    assert without_nested_shading([_fill(72, 100, 523, 100.5, black), _fill(80, 100, 520, 100.5, black)]) is None


def _word_shaded_table() -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    xs = [72, 200, 330, 460]
    top, row_h = 100, 30
    rows = [
        ["Name", "Phone", "City"],
        ["Boston office", "617 555", "Boston"],
        ["Hartford office", "860 555", "Hartford"],
    ]
    for i, row in enumerate(rows):
        y = top + i * row_h
        for j, text in enumerate(row):
            page.draw_rect(pymupdf.Rect(xs[j], y, xs[j + 1], y + row_h), color=None, fill=GRAY, width=0)
            for k in range(2):
                inset = pymupdf.Rect(xs[j] + 5.4, y + 2 + k * 13, xs[j + 1] - 5.4, y + 2 + (k + 1) * 13)
                page.draw_rect(inset, color=None, fill=GRAY, width=0)
            page.insert_text((xs[j] + 6, y + 12), text, fontsize=9)
            page.insert_text((xs[j] + 6, y + 25), "line two", fontsize=9)
    for x in xs:
        page.draw_line((x, top), (x, top + 3 * row_h))
    for i in range(4):
        page.draw_line((xs[0], top + i * row_h), (xs[-1], top + i * row_h))
    return doc


def test_a_word_shaded_table_keeps_its_shape() -> None:
    page = _word_shaded_table()[0]
    plain = page.find_tables().tables
    assert [(t.row_count, t.col_count) for t in plain] != [(3, 3)], "the fixture no longer shows the defect"
    tables = find_tables_without_nested_shading(page).tables
    assert [(t.row_count, t.col_count) for t in tables] == [(3, 3)]
    assert tables[0].extract()[1][0] == "Boston office\nline two"


def test_a_rotated_page_is_read_as_before() -> None:
    """find_tables() reads ``paths`` in the upright frame of a rotated page, so none are passed."""
    doc = _word_shaded_table()
    page = doc[0]
    page.set_rotation(90)
    plain = [(t.row_count, t.col_count) for t in page.find_tables().tables]
    assert [(t.row_count, t.col_count) for t in find_tables_without_nested_shading(page).tables] == plain
