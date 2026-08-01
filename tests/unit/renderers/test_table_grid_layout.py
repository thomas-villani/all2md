#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_table_grid_layout.py
"""Unit tests for the shared table grid layout in BaseRenderer.

Declared ``colspan``/``rowspan`` values are requests, not facts. Real documents
- HTML especially - routinely declare a span wider than the row it sits in, or
one that reaches into ground an earlier ``rowspan`` already claimed. These tests
pin the two rules that resolve those conflicts: spans truncate, and the grid
widens rather than dropping a cell.

"""

import pytest

from all2md import from_ast
from all2md.ast.nodes import Document, Table, TableCell, TableRow, Text
from all2md.renderers.base import BaseRenderer


def _cell(text: str = "", **kwargs: object) -> TableCell:
    """Build a table cell, empty when ``text`` is empty."""
    return TableCell(content=[Text(content=text)] if text else [], **kwargs)  # type: ignore[arg-type]


def _overflow_rows() -> list[TableRow]:
    """Rows whose spans both overflow the grid and collide with each other.

    Shrunk by Hypothesis from a generated counterexample; this is the shape that
    crashed the docx and pptx renderers (#207, #208).
    """
    return [
        TableRow(is_header=True, cells=[_cell("H1"), _cell("H2")]),
        TableRow(cells=[_cell("A", colspan=2, rowspan=2), _cell("B")]),
        TableRow(cells=[_cell("C", colspan=1, rowspan=2), _cell("D")]),
        TableRow(cells=[_cell("E"), _cell("F", colspan=2)]),
    ]


@pytest.mark.unit
class TestLayoutTableGrid:
    """The grid resolver places every cell without overlap."""

    def test_simple_table_is_unchanged(self) -> None:
        """A table with no spans lays out exactly as written."""
        rows = [
            TableRow(is_header=True, cells=[_cell("a"), _cell("b")]),
            TableRow(cells=[_cell("c"), _cell("d")]),
        ]

        grid = BaseRenderer._layout_table_grid(rows)

        assert (grid.num_rows, grid.num_cols) == (2, 2)
        assert [(p.row, p.col) for p in grid.placements] == [(0, 0), (0, 1), (1, 0), (1, 1)]
        assert all(p.rowspan == 1 and p.colspan == 1 for p in grid.placements)

    def test_rowspan_displaces_later_rows(self) -> None:
        """Cells step over the columns an earlier rowspan already claimed."""
        rows = [
            TableRow(cells=[_cell("tall", rowspan=2), _cell("x")]),
            TableRow(cells=[_cell("y")]),
        ]

        grid = BaseRenderer._layout_table_grid(rows)
        anchors = grid.anchors()

        # "y" cannot sit at column 0 - "tall" occupies it on this row.
        assert (1, 1) in anchors
        assert anchors[(1, 1)].cell.content[0].content == "y"

    def test_grid_widens_rather_than_dropping_a_cell(self) -> None:
        """A row displaced past the nominal width grows the table instead."""
        grid = BaseRenderer._layout_table_grid(_overflow_rows())

        # Summing colspans per row gives 3; the rowspans push row 2 out to 4.
        assert grid.num_cols == 4
        assert len(grid.placements) == 8

    def test_colliding_span_is_truncated(self) -> None:
        """A span stops at the first position an earlier cell claimed."""
        grid = BaseRenderer._layout_table_grid(_overflow_rows())

        by_label = {p.cell.content[0].content: p for p in grid.placements}

        # "F" asks for colspan 2, but "C" already holds the column to its right.
        assert by_label["F"].cell.colspan == 2
        assert by_label["F"].colspan == 1

        # Spans that collide with nothing are granted in full.
        assert (by_label["A"].rowspan, by_label["A"].colspan) == (2, 2)

    def test_no_two_cells_overlap(self) -> None:
        """Every grid position belongs to at most one cell."""
        grid = BaseRenderer._layout_table_grid(_overflow_rows())

        seen: set[tuple[int, int]] = set()
        for placement in grid.placements:
            for r in range(placement.row, placement.row + placement.rowspan):
                for c in range(placement.col, placement.col + placement.colspan):
                    assert (r, c) not in seen, f"cells overlap at {(r, c)}"
                    seen.add((r, c))

    def test_rowspan_cannot_exceed_the_table(self) -> None:
        """Rows cannot be added, so a vertical span stops at the last row."""
        rows = [TableRow(cells=[_cell("only", rowspan=9)])]

        grid = BaseRenderer._layout_table_grid(rows)

        assert grid.placements[0].rowspan == 1

    def test_occupancy_marks_covered_positions(self) -> None:
        """Positions no cell reaches stay False."""
        rows = [
            TableRow(cells=[_cell("wide", colspan=2)]),
            TableRow(cells=[_cell("narrow")]),
        ]

        assert BaseRenderer._layout_table_grid(rows).occupancy() == [
            [True, True],
            [True, False],
        ]


@pytest.mark.unit
@pytest.mark.table
class TestOverflowingSpansRender:
    """The overflow shape reaches every renderer without crashing or losing a cell."""

    LABELS = ("H1", "H2", "A", "B", "C", "D", "E", "F")

    def _doc(self) -> Document:
        rows = _overflow_rows()
        return Document(children=[Table(header=rows[0], rows=rows[1:])])

    @pytest.mark.parametrize("fmt", ["docx", "pptx"])
    def test_binary_renderer_does_not_crash(self, fmt: str) -> None:
        """Both renderers previously raised from their underlying library."""
        pytest.importorskip("docx" if fmt == "docx" else "pptx")

        assert from_ast(self._doc(), fmt)

    @pytest.mark.parametrize("fmt", ["markdown", "html", "latex", "org", "rst"])
    def test_text_renderer_keeps_every_cell(self, fmt: str) -> None:
        """Truncating a span is acceptable; dropping a cell is not."""
        output = from_ast(self._doc(), fmt)

        assert isinstance(output, str)
        missing = [label for label in self.LABELS if label not in output]
        assert not missing, f"{fmt} dropped {missing}"
