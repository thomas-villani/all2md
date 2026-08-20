#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_find_tables_repair.py
"""A ``find_tables()`` grid is trusted for its geometry, not for its text assembly.

``Table.extract()`` builds cell text from the characters its cell rects clip, so a
glyph straddling a boundary is cut mid-character ("Contro", "perce ntage") inside a
grid whose columns the rulings corroborate; and where the rulings mark only columns,
PyMuPDF snaps its rows to printed lines, so a wrapped cell shreds into two rows. Both
were measured on the PMC dev corpus (#417): eight tables below the recall bar for
truncation, six for row shred, every word of them present whole on the page.

The repair rebuilds cell text from the page's own word boxes (each word lands whole in
the cell holding its center) and folds wrapped lines with the same guarded merge the
word-gutter path uses (#416). Tables that need neither must come through byte-identical.
"""

from __future__ import annotations

import pytest

from all2md.ast import Table as AstTable
from all2md.ast.nodes import Text, get_node_children
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class _FakeRow:
    def __init__(self, bbox, cells):
        self.bbox = bbox
        self.cells = cells


class _FakeTable:
    """A PyMuPDF table with the geometry the repair reads: ``rows[].bbox`` and ``rows[].cells``."""

    def __init__(self, grid, row_extents, column_edges):
        self._grid = grid
        self.rows = []
        for (top, bottom), _row in zip(row_extents, grid, strict=True):
            cells = [
                (column_edges[index], top, column_edges[index + 1], bottom) for index in range(len(column_edges) - 1)
            ]
            self.rows.append(_FakeRow((column_edges[0], top, column_edges[-1], bottom), cells))
        self.bbox = (column_edges[0], row_extents[0][0], column_edges[-1], row_extents[-1][1])

    def extract(self):
        return self._grid


class _FakePage:
    """A page whose words are placed by the test; ``get_text('words')`` is the only thing read."""

    def __init__(self, words):
        # (x0, y0, x1, y1, text, block, line, word) as PyMuPDF returns them.
        self._words = [(*box, text, 0, line, index) for index, (box, text, line) in enumerate(words)]

    def get_text(self, kind):
        assert kind == "words"
        return list(self._words)

    def get_textbox(self, rect):
        return " ".join(word[4] for word in self._words)


def _cells(node: AstTable) -> list[list[str]]:
    def text_of(cell) -> str:
        parts: list[str] = []

        def walk(current) -> None:
            if isinstance(current, Text):
                parts.append(current.content)
                return
            for child in get_node_children(current):
                walk(child)

        walk(cell)
        return "".join(parts)

    rows = [node.header, *node.rows]
    return [[text_of(cell) for cell in row.cells] for row in rows]


def _word(x0, top, text, line):
    """A word box 6pt per character wide, sitting on the printed line at *top*."""
    return ((x0, top + 1, x0 + 6 * len(text), top + 9), text, line)


EDGES = [0.0, 60.0, 120.0]


def test_clipped_cell_text_is_rebuilt_from_whole_words():
    """A grid whose extract() cut words at cell edges comes back spelled as the page spells them."""
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    # What the page says ...
    page = _FakePage(
        [
            _word(2, 0, "Group", 0),
            _word(62, 0, "Percentage", 0),
            _word(2, 14, "Control", 1),
            _word(62, 14, "12.5", 1),
            _word(2, 28, "Treated", 2),
            _word(62, 28, "40.0", 2),
        ]
    )
    # ... and what extract() clipped it to.
    grid = [["Group", "Perce ntage"], ["Contro", "12.5"], ["Treate", "40.0"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [["Group", "Percentage"], ["Control", "12.5"], ["Treated", "40.0"]]


def test_a_clean_grid_keeps_its_extracted_text_verbatim():
    """No fragments and no wraps: the table is exactly what extract() returned, whitespace and all."""
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    page = _FakePage(
        [
            _word(2, 0, "Model", 0),
            _word(62, 0, "Score", 0),
            _word(2, 14, "baseline", 1),
            _word(62, 14, "0.62", 1),
            _word(2, 28, "ours", 2),
            _word(62, 28, "0.81", 2),
        ]
    )
    grid = [["Model", "Score"], ["baseline", "0.62"], ["ours", "0.81"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == grid


def test_printed_line_rows_fold_into_logical_rows_and_repair_the_hyphen():
    """Rows snapped to printed lines merge on the gap jump, and the wrap's hyphen heals across the join."""
    # Wraps sit 1.5pt below their row; the next row sits 4-4.5pt below.
    extents = [(0.0, 10.0), (14.0, 24.0), (25.5, 35.5), (40.0, 50.0), (51.5, 61.5), (66.0, 76.0)]
    page = _FakePage(
        [
            _word(2, 0, "Drug", 0),
            _word(62, 0, "Effect", 0),
            _word(2, 14, "Aspirin", 1),
            _word(62, 14, "reduces", 1),
            _word(62, 25.5, "inflammation", 2),
            _word(2, 40, "Ibuprofen", 3),
            _word(62, 40, "eases", 3),
            _word(62, 51.5, "fever", 4),
            _word(2, 66, "Statin", 5),
            _word(62, 66, "lipids", 5),
        ]
    )
    grid = [
        ["Drug", "Effect"],
        ["Aspirin", "reduces inflam-"],
        ["", "mation"],
        ["Ibuprofen", "eases"],
        ["", "fever"],
        ["Statin", "lipids"],
    ]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [
        ["Drug", "Effect"],
        ["Aspirin", "reduces inflammation"],
        ["Ibuprofen", "eases fever"],
        ["Statin", "lipids"],
    ]


def test_a_table_without_row_geometry_is_not_merged():
    """Without ``rows`` to read extents from, the grid is emitted as extracted -- never merged blind."""

    class _Bare:
        bbox = (0, 0, 120, 40)

        def extract(self):
            return [["Drug", "Effect"], ["Aspirin", "reduces"], ["", "inflammation"]]

    page = _FakePage(
        [
            _word(2, 0, "Drug", 0),
            _word(62, 0, "Effect", 0),
            _word(2, 14, "Aspirin", 1),
            _word(62, 14, "reduces", 1),
            _word(62, 28, "inflammation", 2),
        ]
    )
    node = PdfToAstConverter()._process_table_to_ast(_Bare(), page, page_num=0)

    assert isinstance(node, AstTable)
    assert len(node.rows) == 2


def test_overlapping_row_boxes_disable_the_merge():
    """A rowspan table's overlapping row bboxes are not line geometry: nothing merges.

    find_tables() hands back overlapping row boxes when a spanning cell stretches
    one row's bbox over its neighbours; every gap statistic computed over those is
    garbage, and a row with an empty first cell would fold into the span above.
    extract() already understands the spans, so its rows stand.
    """
    # Row 1's box swallows row 2 entirely -- and row 2's leading cell is empty,
    # exactly the shape the anchor rule would otherwise merge.
    extents = [(0.0, 10.0), (14.0, 60.0), (24.0, 40.0), (64.0, 74.0)]
    page = _FakePage(
        [
            _word(2, 0, "Site", 0),
            _word(62, 0, "Count", 0),
            _word(2, 14, "Liver", 1),
            _word(62, 14, "four", 1),
            _word(62, 24, "seven", 2),
            _word(2, 64, "Lung", 3),
            _word(62, 64, "two", 3),
        ]
    )
    grid = [["Site", "Count"], ["Liver", "four"], ["", "seven"], ["Lung", "two"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == grid


def test_a_rebuild_that_loses_text_is_discarded():
    """When the cell rects miss the page's words, the gutted rebuild must not replace the extract.

    On rotated pages find_tables() cell rects and the word boxes do not share a
    coordinate frame, so the rebuild comes back nearly empty. Measured before the
    char-mass guard: three intact landscape tables were gutted, died at the
    mostly-empty guard, and were destroyed outright (1.00 -> 0.00).
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    # The words sit far outside every cell rect, as a rotated frame would put them.
    page = _FakePage(
        [
            _word(402, 0, "Group", 0),
            _word(462, 0, "Percentage", 0),
            _word(402, 14, "Control", 1),
            _word(462, 14, "12.5", 1),
            _word(402, 28, "Treated", 2),
            _word(462, 28, "40.0", 2),
        ]
    )
    # Extract text is damaged enough to fire the trigger (fragments + lost words).
    grid = [["Group", "Perce ntage"], ["Contro", "12.5"], ["Treate", "40.0"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    # The damaged extract survives -- worse than the page, better than nothing.
    assert _cells(node) == grid


def test_a_second_header_tier_with_an_empty_label_cell_stays_its_own_row():
    """A "# | Acc" sub-header fills columns the tier above left empty: it must not fold up.

    find_tables() row bboxes tile the grid -- every gap is zero -- so the anchor rule
    carries the merge alone, and an empty label cell is its whole test. Measured: a
    two-tier header fused (0.87 -> 0.79) because the second tier's filled columns were
    exactly the ones the first tier left empty. Empty separator lines (no columns at
    all) still fold away.
    """
    extents = [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 40.0)]
    edges = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    page = _FakePage(
        [
            _word(2, 0, "modalities", 0),
            _word(62, 0, "visual", 0),
            _word(182, 0, "audio", 0),
            _word(122, 10, "Acc", 1),
            _word(242, 10, "Acc", 1),
            _word(2, 20, "one", 2),
            _word(62, 20, "1", 2),
            _word(122, 20, "70", 2),
            _word(182, 20, "2", 2),
            _word(242, 20, "60", 2),
        ]
    )
    # The top tier spans column pairs, so the sub-header's "Acc" cells sit in
    # columns the top tier leaves empty -- the real two-tier geometry.
    grid = [
        ["modalities", "visual", "", "audio", ""],
        ["", "", "Acc", "", "Acc"],
        ["", "", "", "", ""],
        ["one", "1", "70", "2", "60"],
    ]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, edges), page, page_num=0)

    assert isinstance(node, AstTable)
    # The sub-header keeps its row; only the fully-empty separator line folds.
    assert _cells(node) == [
        ["modalities", "visual", "", "audio", ""],
        ["", "", "Acc", "", "Acc"],
        ["one", "1", "70", "2", "60"],
    ]
