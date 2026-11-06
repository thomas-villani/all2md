# Copyright (c) 2025 Tom Villani, Ph.D.
"""CSV merged cells occupy their resolved columns across the entire table."""

import csv
import io

import pytest

from all2md import from_ast
from all2md.ast import Document, Table, TableCell, TableRow, Text
from all2md.constants import MergedCellHandling
from all2md.options.csv import CsvRendererOptions

pytestmark = [pytest.mark.unit, pytest.mark.table]


def _cell(text: str = "", *, colspan: int = 1, rowspan: int = 1) -> TableCell:
    """Build a synthetic cell, including genuinely empty content."""
    return TableCell(content=[Text(content=text)] if text else [], colspan=colspan, rowspan=rowspan)


def _render(table: Table, mode: MergedCellHandling) -> list[list[str]]:
    """Read actual CSV records instead of splitting on commas or newlines."""
    output = from_ast(Document(children=[table]), "csv", renderer_options=CsvRendererOptions(handle_merged_cells=mode))
    assert isinstance(output, str)
    return list(csv.reader(io.StringIO(output)))


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_rowspan_preserves_later_columns(mode: MergedCellHandling) -> None:
    """A body cell remains in its column on each row covered by a rowspan."""
    table = Table(
        rows=[
            TableRow(cells=[_cell("group", rowspan=2), _cell("first")]),
            TableRow(cells=[_cell("second")]),
        ]
    )
    continuation = {"repeat": "group", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["group", "first"], [continuation, "second"]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_header_rowspan_and_colspan(mode: MergedCellHandling) -> None:
    """A combined header span also covers the following body row."""
    table = Table(
        header=TableRow(cells=[_cell("group", colspan=2, rowspan=2), _cell("value")]),
        rows=[TableRow(cells=[_cell("first")]), TableRow(cells=[_cell("a"), _cell("b"), _cell("last")])],
    )
    continuation = {"repeat": "group", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [
        ["group", continuation, "value"],
        [continuation, continuation, "first"],
        ["a", "b", "last"],
    ]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_multiple_spans_displace_cells_and_widen_rows(mode: MergedCellHandling) -> None:
    """Independent active spans never drop the later source cells."""
    table = Table(
        rows=[
            TableRow(cells=[_cell("left", rowspan=3), _cell("middle"), _cell("right", rowspan=2)]),
            TableRow(cells=[_cell("new", rowspan=2), _cell("displaced")]),
            TableRow(cells=[_cell("last")]),
        ]
    )

    def merged(text: str) -> str:
        return {"repeat": text, "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [
        ["left", "middle", "right"],
        [merged("left"), "new", merged("right"), "displaced"],
        [merged("left"), merged("new"), "last"],
    ]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_conflicting_colspan_uses_effective_span(mode: MergedCellHandling) -> None:
    """A colspan stops at occupied ground, then the next cell steps over it."""
    table = Table(
        rows=[
            TableRow(cells=[_cell("a"), _cell("tall", rowspan=2)]),
            TableRow(cells=[_cell("wide", colspan=3), _cell("end")]),
        ]
    )
    continuation = {"repeat": "tall", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["a", "tall"], ["wide", continuation, "end"]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_empty_spanning_cell_and_covered_empty_row(mode: MergedCellHandling) -> None:
    """Empty anchors are retained and covered empty rows contain merged positions."""
    table = Table(rows=[TableRow(cells=[_cell(colspan=2, rowspan=2), _cell("tail", rowspan=2)]), TableRow(cells=[])])
    empty = "[merged]" if mode == "placeholder" else ""
    tail = {"repeat": "tail", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["", empty, "tail"], [empty, empty, tail]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_holes_before_later_rowspan_are_empty(mode: MergedCellHandling) -> None:
    """Unoccupied slots are empty even when merged positions use placeholders."""
    table = Table(rows=[TableRow(cells=[_cell("a"), _cell("tall", rowspan=2)]), TableRow(cells=[])])
    continuation = {"repeat": "tall", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["a", "tall"], ["", continuation]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_truncated_rowspan_does_not_add_rows(mode: MergedCellHandling) -> None:
    """A span beyond the table ends at the final source row."""
    table = Table(rows=[TableRow(cells=[_cell("tall", rowspan=9)]), TableRow(cells=[_cell("last")])])
    continuation = {"repeat": "tall", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["tall"], [continuation, "last"]]


@pytest.mark.parametrize("mode", ["repeat", "blank", "placeholder"])
def test_ragged_rows_and_colspan_only_output_are_unchanged(mode: MergedCellHandling) -> None:
    """Existing unmerged row lengths and horizontal merge values stay intact."""
    table = Table(
        header=TableRow(cells=[_cell("h1"), _cell("h2"), _cell("h3")]),
        rows=[
            TableRow(cells=[_cell("short")]),
            TableRow(cells=[]),
            TableRow(cells=[_cell(), _cell("wide", colspan=2)]),
        ],
    )
    continuation = {"repeat": "wide", "blank": "", "placeholder": "[merged]"}[mode]

    assert _render(table, mode) == [["h1", "h2", "h3"], ["short"], [], ["", "wide", continuation]]


@pytest.mark.parametrize("table", [Table(), Table(rows=[TableRow(cells=[])]), Table(rows=[TableRow(cells=[_cell()])])])
def test_empty_tables_and_cells_keep_existing_records(table: Table) -> None:
    """No table rows, an empty row and an empty cell remain distinct."""
    expected = [] if not table.rows else ([[]] if not table.rows[0].cells else [[""]])
    assert _render(table, "repeat") == expected
