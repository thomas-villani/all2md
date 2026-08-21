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


def test_a_boundary_cutting_words_on_edge_bearing_rows_is_dissolved():
    """A column boundary the page's words contradict on two rows merges its cell pair (#419).

    The grid claims three columns, but the middle boundary at x=60 runs through
    "B12," and "(B1)," on the two data rows -- the page wrote one word where the grid
    drew two cells. Neither existing guard can see it: no character is lost, and the
    fragment tokenizer is digit-blind. The rebuilt table reunites the pair.
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    page = _FakePage(
        [
            _word(2, 0, "Nutrient", 0),
            _word(92, 0, "Amt", 0),
            # "B12," spans x=32..56... make it straddle x=60: start at 44, 6pt/char * 4 = 44..68.
            _word(2, 14, "Vitamin", 1),
            _word(44, 14, "B12,", 1),
            _word(92, 14, "2.8", 1),
            _word(2, 28, "Thiamine", 2),
            _word(50, 28, "(B1),", 2),
            _word(92, 28, "800", 2),
        ]
    )
    # extract() clipped the straddling words at the x=60 boundary.
    grid = [
        ["Nutrient", "", "Amt"],
        ["Vitamin B1", "2,", "2.8"],
        ["Thiamine (B", "1),", "800"],
    ]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, [0.0, 60.0, 90.0, 120.0]), page, 0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [
        ["Nutrient", "Amt"],
        ["Vitamin B12,", "2.8"],
        ["Thiamine (B1),", "800"],
    ]


def test_words_crossing_under_a_spanning_header_do_not_dissolve_the_boundary():
    """A two-tier header spanning two columns crosses their boundary legitimately.

    The span row omits the edge, so its crossing words are no contradiction; the data
    rows bear the edge and their words fall inside their cells. The grid keeps all
    three columns and its extracted text verbatim.
    """
    top = _FakeRow(
        (0.0, 0.0, 120.0, 10.0),
        # First cell spans x=0..90 across the interior boundary at x=60.
        [(0.0, 0.0, 90.0, 10.0), (90.0, 0.0, 120.0, 10.0)],
    )
    body_edges = [0.0, 60.0, 90.0, 120.0]
    body_rows = []
    grid = [
        ["Interobserver variability", "p"],
        ["mean", "sd", "0.05"],
        ["1.2", "0.4", "0.01"],
    ]
    for (t, b), _row in zip([(14.0, 24.0), (28.0, 38.0)], grid[1:], strict=True):
        cells = [(body_edges[i], t, body_edges[i + 1], b) for i in range(3)]
        body_rows.append(_FakeRow((0.0, t, 120.0, b), cells))

    class _SpanTable:
        rows = [top, *body_rows]
        bbox = (0.0, 0.0, 120.0, 38.0)

        def extract(self):
            return grid

    page = _FakePage(
        [
            # Header words straddle x=60 -- inside the spanning cell.
            _word(30, 0, "Interobserver", 0),
            _word(56, 0, "variability", 0),
            _word(94, 0, "p", 0),
            _word(2, 14, "mean", 1),
            _word(62, 14, "sd", 1),
            _word(94, 14, "0.05", 1),
            _word(2, 28, "1.2", 2),
            _word(62, 28, "0.4", 2),
            _word(94, 28, "0.01", 2),
        ]
    )

    node = PdfToAstConverter()._process_table_to_ast(_SpanTable(), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == grid


def test_a_single_contradicted_row_does_not_dissolve_the_boundary():
    """One crossing word is not evidence of a mis-split column: both columns survive.

    The extract-loss guard may still rebuild the cell *text* from word boxes (here the
    clipped "B12," is missing from the grid, so it does) -- but the boundary itself
    stays, where a dissolve would have collapsed the grid to one column and demoted it
    to a paragraph.
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    page = _FakePage(
        [
            _word(2, 0, "Name", 0),
            _word(62, 0, "Value", 0),
            # Only this row's word straddles x=60 (44..68).
            _word(44, 14, "B12,", 1),
            _word(92, 14, "2.8", 1),
            _word(2, 28, "iron", 2),
            _word(62, 28, "20", 2),
        ]
    )
    grid = [["Name", "Value"], ["B1", "2, 2.8"], ["iron", "20"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, EDGES), page, page_num=0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [["Name", "Value"], ["B12,", "2.8"], ["iron", "20"]]


def test_an_overhanging_value_delivered_whole_does_not_dissolve_the_boundary():
    """A wide value protruding past a correct boundary is not a mis-split (#419).

    "<0.001" physically overhangs the boundary at x=60 on both data rows, but
    extract() delivered it whole in its own cell -- nothing was cut, so the grid
    keeps all three columns and its text verbatim. This is the case that separates
    overhang from mis-split: dissolving here would fuse two real columns.
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    page = _FakePage(
        [
            _word(2, 0, "Metric", 0),
            _word(62, 0, "P", 0),
            _word(92, 0, "Q", 0),
            # 6pt/char * 6 chars from x=40: box 40..76, straddling x=60 by >1pt each side.
            _word(2, 14, "Knowledge", 1),
            _word(40, 14, "<0.001", 1),
            _word(92, 14, "0.4", 1),
            _word(2, 28, "Attitude", 2),
            _word(40, 28, "<0.001", 2),
            _word(92, 28, "0.7", 2),
        ]
    )
    grid = [
        ["Metric", "P", "Q"],
        ["Knowledge", "<0.001", "0.4"],
        ["Attitude", "<0.001", "0.7"],
    ]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, [0.0, 60.0, 90.0, 120.0]), page, 0)

    assert isinstance(node, AstTable)
    assert _cells(node) == grid


def test_a_cut_value_in_a_real_gutter_keeps_the_boundary_and_heals_the_word():
    """A wide value cut by a real boundary is healed in place, not fused (#419).

    extract() clipped "<0.001" across the boundary at x=60 on two rows, so the
    boundary is contradicted -- but on the uncut rows the words on either side sit a
    gutter apart, which is what a real column boundary looks like. The repair keeps
    both columns and the rebuild lands "<0.001" whole in the cell holding its
    center.
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0), (42.0, 52.0)]
    page = _FakePage(
        [
            _word(2, 0, "Metric", 0),
            _word(80, 0, "P", 0),
            # 6pt/char * 6 chars from x=52: box 52..88, straddling x=60 by >1pt each side.
            _word(2, 14, "Knowledge", 1),
            _word(52, 14, "<0.001", 1),
            _word(2, 28, "Attitude", 2),
            _word(52, 28, "<0.001", 2),
            _word(2, 42, "Practice", 3),
            _word(80, 42, "0.20", 3),
        ]
    )
    # extract() split "<0.001" at the boundary on the two cut rows.
    grid = [
        ["Metric", "P"],
        ["Knowledge <0.0", "01"],
        ["Attitude <0.0", "01"],
        ["Practice", "0.20"],
    ]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, [0.0, 60.0, 120.0]), page, 0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [
        ["Metric", "P"],
        ["Knowledge", "<0.001"],
        ["Attitude", "<0.001"],
        ["Practice", "0.20"],
    ]


def test_a_word_clipped_by_the_table_bbox_joins_the_outer_cell():
    """A word beginning inside the last cell survives even when its center leaks past the edge (#419).

    find_tables() drew its bbox through the middle of "0.024": extract() clipped it
    to "0", and the center-assignment rule alone would have dropped the word into no
    cell at all. Beginning inside the outer cell is the evidence that it belongs
    there.
    """
    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    page = _FakePage(
        [
            _word(2, 0, "Method", 0),
            _word(62, 0, "mAP", 0),
            _word(2, 14, "Image", 1),
            # 6pt/char * 5 chars from x=86: box 86..116 -- starts inside the last
            # cell (ends at x=90) but its center (101) leaks past the table edge.
            _word(86, 14, "0.024", 1),
            _word(2, 28, "Video", 2),
            _word(86, 28, "0.090", 2),
        ]
    )
    # extract() kept only what its cell rects clip.
    grid = [["Method", "mAP"], ["Image", "0"], ["Video", "0"]]

    node = PdfToAstConverter()._process_table_to_ast(_FakeTable(grid, extents, [0.0, 60.0, 90.0]), page, 0)

    assert isinstance(node, AstTable)
    assert _cells(node) == [["Method", "mAP"], ["Image", "0.024"], ["Video", "0.090"]]


def test_a_whole_column_outside_the_bbox_is_detected_and_admitted():
    """A column the bbox excluded entirely is found by its three signals and joins the grid (#419).

    The words sit a column gutter away (5pt), align with every grid row, and nothing
    continues beyond them -- a prose neighbour or caption fails at least one of the
    three. Admitted through clip_extension, they become the last cell of every row.
    """
    from all2md.parsers._pdf_tables import adjacent_clipped_column

    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    words = [
        _word(2, 0, "Group", 0),
        _word(62, 0, "Mean", 0),
        _word(125, 0, "SD", 0),  # x=125..137: 5pt past the bbox edge at 120
        _word(2, 14, "Control", 1),
        _word(62, 14, "4.1", 1),
        _word(125, 14, "0.7", 1),
        _word(2, 28, "Treated", 2),
        _word(62, 28, "5.9", 2),
        _word(125, 28, "0.9", 2),
    ]
    page = _FakePage(words)
    grid = [["Group", "Mean"], ["Control", "4.1"], ["Treated", "5.9"]]
    table = _FakeTable(grid, extents, EDGES)

    found = adjacent_clipped_column(page, table)
    assert found is not None
    rect, side = found
    assert side == "right"

    node = PdfToAstConverter()._process_table_to_ast(table, page, 0, clip_extension=(rect, side))
    assert isinstance(node, AstTable)
    assert _cells(node) == [
        ["Group", "Mean", "SD"],
        ["Control", "4.1", "0.7"],
        ["Treated", "5.9", "0.9"],
    ]


def test_a_prose_neighbour_is_not_admitted_as_a_column():
    """Words that keep going past the near band are a prose column, not a clipped one."""
    from all2md.parsers._pdf_tables import adjacent_clipped_column

    extents = [(0.0, 10.0), (14.0, 24.0), (28.0, 38.0)]
    words = [
        _word(2, 0, "Group", 0),
        _word(62, 0, "Mean", 0),
        _word(2, 14, "Control", 1),
        _word(62, 14, "4.1", 1),
        _word(2, 28, "Treated", 2),
        _word(62, 28, "5.9", 2),
    ]
    # A neighbouring prose column: near words on every row, but text runs on far
    # past them, which no clipped table column does.
    for row, top in enumerate((0, 14, 28)):
        for k in range(6):
            words.append(_word(126 + 24 * k, top, "word", row))
    page = _FakePage(words)
    grid = [["Group", "Mean"], ["Control", "4.1"], ["Treated", "5.9"]]

    assert adjacent_clipped_column(page, _FakeTable(grid, extents, EDGES)) is None
