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

Geometry here is taken from the corpora rather than invented: the gap populations are
PMC5250635.1's, and the section-heading table is PMC4500011.1's.

The other half of #438 -- folding a half-empty group into a neighbour it abuts -- was
removed after it was measured against ground truth rather than against a half-empty-row
count. A section-heading row is legitimately half-empty, and no gap tolerance separates
the two: PMC4500011.1 prints *one* body gap value, 1.56pt, for headings and data rows
alike. See ``ROW_GROUP_MAX_SPARSE_SHARE``.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_tables import merge_continuation_lines

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class TestGapGroupsSeparateRowsFromWraps:
    """A gap jump is believed only when the grouping it produces looks like rows."""

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


class TestSectionHeadingRowsSurvive:
    """A row that fills one column may be a heading, not a wrapped fragment."""

    # PMC4500011.1's Table 1, verbatim: 33 printed lines, 3 columns. Five of its rows are
    # section headings ("Gender", "Height (cm)", ...) whose data columns are empty by
    # design, each followed by the indented rows it governs.
    LINES = [
        ["", "The", "Blind"],
        ["Variable", "", ""],
        ["", "Text reading group", "Braille reading group"],
        ["Age (yrs)", "16.0 ± 0.8", "13.6 ± 0.8"],
        ["Gender", "", ""],
        ["Male (%)", "9 (64.3)", "5 (35.7)"],
        ["Female (%)", "5 (35.7)", "9 (64.3)"],
        ["Height (cm)", "", ""],
        ["Male", "160.6 ± 4.9", "163.9 ± 2.2"],
        ["Female", "153.1 ± 3.6", "148.4 ± 3.6"],
        ["Gender total", "158.0 ± 3.4", "154.0 ± 3.1"],
    ]
    # y-extents as printed: the header tier interlaces (-4.80pt), and every body gap that
    # follows is +1.56pt -- one value, shared by the headings and the data rows they head.
    EXTENTS = [
        (107.87, 119.04),
        (114.23, 125.40),
        (120.60, 131.77),
        (133.46, 144.63),
        (146.19, 157.36),
        (158.93, 170.09),
        (171.66, 182.83),
        (184.39, 195.56),
        (197.12, 208.29),
        (209.86, 221.03),
        (222.59, 233.76),
    ]

    def test_a_section_heading_is_not_folded_onto_the_row_above_it(self) -> None:
        """A heading must not join the row above it, or values land under the wrong label.

        This is the regression #438 shipped: the heading fills one of the three columns its
        neighbour fills, which is exactly the shape of a wrapped fragment, so a fold rule
        keyed on that shape swallowed it. The printed page offers nothing to tell them
        apart -- the gap above "Gender" is 1.56pt, the same as the gap above "Male (%)"
        and above every other row in the table.
        """
        rows = merge_continuation_lines([list(r) for r in self.LINES], self.EXTENTS)

        assert ["Gender", "", ""] in rows, rows
        assert ["Height (cm)", "", ""] in rows, rows
        # The heading kept its own row, so the Age row still owns its own numbers.
        age = [row for row in rows if row[0].startswith("Age")]
        assert age == [["Age (yrs)", "16.0 ± 0.8", "13.6 ± 0.8"]], rows

    def test_every_data_row_keeps_the_label_it_was_printed_with(self) -> None:
        """No row may carry two labels: that is what mislabelling looks like structurally."""
        rows = merge_continuation_lines([list(r) for r in self.LINES], self.EXTENTS)

        for row in rows:
            assert (
                "\n" not in row[0] or not row[1]
            ), f"row label {row[0]!r} fused two printed labels onto data {row[1]!r}"
