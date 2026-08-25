#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_wrapped_cell_rows.py
"""One printed line is not one table row, and the gap between lines is not the whole story.

``_gap_row_groups`` separates wrapped lines from row boundaries by the jump in their
inter-line gaps. A vertically centered multi-line cell prints *three* gap populations, not
two: lines from different columns interlace and go negative, a tall cell's own successive
lines merely abut, and real rows are separated by padding. Taking the first jump on faith
puts a cell's own wrap lines on the row-boundary side, and a single outlier gap can put the
threshold below every real gap at once (#438).

Geometry here is taken from the held-out corpus rather than invented: the header is
PMC5250635.1's, whose "Maximum bite force (mean+-standard deviation)" cell shredded into
three rows and pushed the real header labels down into the first body row.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_tables import merge_continuation_lines

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class TestWrappedCellsFoldIntoTheirRow:
    """A cell that wraps stays one cell."""

    # PMC5250635.1's Table 2, verbatim: 15 printed lines, 4 columns, 7 logical rows.
    LINES = [
        ["", "", "", "Maximum bite"],
        ["", "", "Number", "force"],
        ["Measurement", "Gender", "", ""],
        ["", "", "of patients", "(mean±standard"],
        ["", "", "", "deviation)"],
        ["", "Males", "14", "606.28±266.28"],
        ["Before", "", "", ""],
        ["", "Females", "10", "342.68±126.07"],
        ["surgery", "", "", ""],
        ["", "Total", "24", "496.45±252.82"],
        ["", "Males", "14", "611.75±260.28"],
        ["Eight weeks", "", "", ""],
        ["", "Females", "10", "277.68±90.42"],
        ["after surgery", "", "", ""],
        ["", "Total", "24", "472.55±264.19"],
    ]
    EXTENTS = [
        (507.3, 518.3),
        (518.8, 529.9),
        (524.6, 535.6),
        (530.4, 541.4),
        (541.9, 552.9),
        (555.9, 566.9),
        (564.0, 575.0),
        (570.6, 581.6),
        (577.2, 588.2),
        (585.1, 596.1),
        (603.8, 614.8),
        (611.7, 622.7),
        (618.3, 629.4),
        (625.1, 636.1),
        (633.0, 644.0),
    ]

    def test_a_wrapped_header_cell_keeps_its_labels_on_the_header_row(self) -> None:
        """The header's own wrap lines fold into it instead of displacing it downward.

        "Maximum bite" has no interlacing neighbour to overlap, so it abuts the line below
        by 0.49pt where every within-row gap is -3pt or lower -- the jump calls it a row of
        its own. It is the *first* printed line, which is the case the anchor rule
        structurally cannot reach: that rule only ever continues a row that has already
        started, so the fragment stood as row one and pushed the labels into row two.
        """
        rows = merge_continuation_lines([list(r) for r in self.LINES], self.EXTENTS)

        assert rows[0] == [
            "Measurement",
            "Gender",
            "Number\nof patients",
            "Maximum bite\nforce\n(mean±standard\ndeviation)",
        ]
        # And the six data rows are untouched -- three of them carry a wrapped row label
        # ("Before surgery"), which is the merge working as it already did.
        assert rows[1:] == [
            ["", "Males", "14", "606.28±266.28"],
            ["Before\nsurgery", "Females", "10", "342.68±126.07"],
            ["", "Total", "24", "496.45±252.82"],
            ["", "Males", "14", "611.75±260.28"],
            ["Eight weeks\nafter surgery", "Females", "10", "277.68±90.42"],
            ["", "Total", "24", "472.55±264.19"],
        ]

    def test_a_lone_outlier_gap_cannot_define_the_row_population(self) -> None:
        """A gap occurring once must not outweigh one occurring many times.

        The jump candidates are *distinct* gap values, so a single stray gap below the real
        population used to be peeled off as the jump -- putting the threshold beneath every
        genuine gap, so nothing merged. Measured on PMC7750019.1, the worst table on the
        held-out corpus: one -7.95pt gap below a cluster of 52 at -3.21pt turned 97 printed
        lines into 89 rows, 77 of them half-empty. The give-away is the *result*, so a
        grouping that leaves most rows half-empty is rejected and the next jump tried.
        """
        lines = [
            ["Smith", "Kenya", "Cost-effective"],
            ["2019", "", ""],
            ["", "", "analysis"],
            ["", "2015", ""],
            ["Jones", "Ghana", "Cost-benefit"],
            ["2020", "", ""],
            ["", "", "study"],
            ["Lee", "Peru", "Cost-utility"],
            ["2021", "", ""],
            ["", "", "model"],
        ]
        # One -8pt outlier, a -3pt within-row population, and +2pt row boundaries.
        extents = [
            (0.0, 8.0),
            (0.0, 8.0),
            (5.0, 13.0),
            (10.0, 18.0),
            (20.0, 28.0),
            (25.0, 33.0),
            (30.0, 38.0),
            (40.0, 48.0),
            (45.0, 53.0),
            (50.0, 58.0),
        ]

        rows = merge_continuation_lines([list(r) for r in lines], extents)

        assert rows == [
            ["Smith\n2019", "Kenya\n2015", "Cost-effective\nanalysis"],
            ["Jones\n2020", "Ghana", "Cost-benefit\nstudy"],
            ["Lee\n2021", "Peru", "Cost-utility\nmodel"],
        ]

    def test_a_data_row_is_not_folded_into_the_row_above_it(self) -> None:
        """Sharing your neighbour's columns is not the same as continuing its cell.

        The fold's tempting case: a data row whose leading label cell is empty fills a
        strict subset of the columns the row above fills, and sits close enough to it. What
        separates them is how *much* of the row they fill -- a wrapped fragment continues
        one cell while every other column stays empty, so a line filling half its
        neighbour's columns or more is carrying content of its own.
        """
        lines = [
            ["Region", "Cases", "Deaths", "Rate"],
            ["South", "", "", ""],
            ["", "12", "3", "0.25"],
            ["", "15", "4", "0.27"],
        ]
        extents = [(0.0, 8.0), (5.0, 13.0), (15.0, 23.0), (25.0, 33.0)]

        rows = merge_continuation_lines([list(r) for r in lines], extents)

        assert rows == [
            ["Region\nSouth", "Cases", "Deaths", "Rate"],
            ["", "12", "3", "0.25"],
            ["", "15", "4", "0.27"],
        ]
