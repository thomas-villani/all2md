"""A grid's merged-cell positions are not empty cells.

find_tables() lays every row of a table on one grid of all the column edges any row
draws and leaves ``None`` where a row has no cell. A Word register whose rows are cut
at different widths came out more than half ``None``, failed the empty-cell guard and
lost its table. The guard now judges a grid with text in most rows on its real cells.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_tables import MAX_TABLE_EMPTY_RATIO, is_mostly_empty_grid

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def test_a_full_grid_is_a_table() -> None:
    assert not is_mostly_empty_grid([["Name", "Phone"], ["Boston", "617"], ["Hartford", "860"]])


def test_a_register_cut_at_different_widths_is_a_table() -> None:
    """Every row holds text; most positions are spans; the real cells are mostly filled."""
    rows = [
        ["Category", None, None, None, "Method", None, None, None],
        ["Executes safety", None, None, "Daily", None, None, "", None],
        ["Reviews", None, None, None, None, "Weekly", None, None],
        ["Approves", None, "Monthly", None, None, None, None, ""],
    ]
    cells = [cell for row in rows for cell in row]
    assert sum(1 for cell in cells if cell is None or not str(cell).strip()) / len(cells) > MAX_TABLE_EMPTY_RATIO
    assert not is_mostly_empty_grid(rows)


def test_a_chart_is_still_rejected() -> None:
    """Gridlines around a plot: no spans, and the real cells are blank but for the axis values."""
    rows = [["0.10", "", "", "", "", ""], ["", "", "", "", "", ""], ["0.05", "", "", "", "", ""]]
    rows += [["", "", "", "", "", ""] for _ in range(4)]
    assert is_mostly_empty_grid(rows)


def test_spans_do_not_save_a_grid_whose_rows_are_mostly_blank() -> None:
    """A frame around a running head: one line of text, the rest spans and blanks."""
    rows = [["VOLUME 3: NO. 1", None, None], [None, None, ""], [None, "", None]]
    assert is_mostly_empty_grid(rows)


def test_spans_do_not_save_a_grid_whose_real_cells_are_blank() -> None:
    rows = [["Label", None, "", ""], ["", None, "", ""], ["x", None, "", ""]]
    assert is_mostly_empty_grid(rows)


def test_no_cells_is_empty() -> None:
    assert is_mostly_empty_grid([])
