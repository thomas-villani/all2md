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

import io
import zipfile

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


def _collision_rows() -> list[TableRow]:
    """Rows where a declared colspan runs into an earlier rowspan's ground.

    "CCC" asks for three columns but "BBB" already holds the one to its right,
    so the span truncates to one and "DDD" lands in the last column. Renderers
    that placed cells with the *declared* span instead pushed "DDD" past the
    grid's width and dropped it (finding #26).
    """
    return [
        TableRow(cells=[_cell("AAA"), _cell("BBB", rowspan=2)]),
        TableRow(cells=[_cell("CCC", colspan=3), _cell("DDD")]),
    ]


def _odf_text(data: bytes) -> str:
    """Pull the body XML out of an ODF package."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("content.xml").decode("utf-8")


def _pdf_text(data: bytes) -> str:
    """Pull the rendered text out of a PDF."""
    pymupdf = pytest.importorskip("pymupdf")
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        return "".join(page.get_text() for page in pdf)


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


@pytest.mark.unit
@pytest.mark.table
class TestCollidingSpanKeepsTrailingCells:
    """A span that collides with an earlier rowspan must not cost a cell.

    Every renderer here used to take its width from the (truncating) shared
    layout but place cells with their declared spans, so the last cell of the
    row fell off the end of the grid and was silently discarded.
    """

    LABELS = ("AAA", "BBB", "CCC", "DDD")

    def _doc(self) -> Document:
        return Document(children=[Table(rows=_collision_rows())])

    @pytest.mark.parametrize("fmt", ["rst", "org", "latex"])
    def test_text_renderer_keeps_the_trailing_cell(self, fmt: str) -> None:
        """The text renderers write straight to a string."""
        output = from_ast(self._doc(), fmt)

        assert isinstance(output, str)
        missing = [label for label in self.LABELS if label not in output]
        assert not missing, f"{fmt} dropped {missing}"

    @pytest.mark.parametrize("fmt", ["odt", "odp"])
    def test_odf_renderer_keeps_the_trailing_cell(self, fmt: str) -> None:
        """ODT and ODP carry their cells in the package's ``content.xml``."""
        pytest.importorskip("odf")

        output = from_ast(self._doc(), fmt)

        assert isinstance(output, bytes)
        content = _odf_text(output)
        missing = [label for label in self.LABELS if label not in content]
        assert not missing, f"{fmt} dropped {missing}"

    def test_pdf_renderer_keeps_the_trailing_cell(self) -> None:
        """The PDF renderer lays cells into a ReportLab table."""
        pytest.importorskip("reportlab")

        output = from_ast(self._doc(), "pdf")

        assert isinstance(output, bytes)
        text = _pdf_text(output)
        missing = [label for label in self.LABELS if label not in text]
        assert not missing, f"pdf dropped {missing}"

    def test_grid_truncates_the_colliding_span(self) -> None:
        """The recovered cell exists because the collision truncated a span."""
        grid = BaseRenderer._layout_table_grid(_collision_rows())
        by_label = {p.cell.content[0].content: p for p in grid.placements}

        assert grid.num_cols == 3
        assert by_label["CCC"].colspan == 1
        assert (by_label["DDD"].row, by_label["DDD"].col) == (1, 2)
