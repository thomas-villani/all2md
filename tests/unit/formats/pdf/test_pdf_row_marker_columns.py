#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_row_marker_columns.py
"""Rows are named by the columns that agree, and headers fold only where a cell wrapped.

The anchor rule reads one column and asks whether it is filled, which fails outright when
the column naming the rows is the one that wraps: a reference column printing "Suleiman",
"et al.", "[8]" down three lines is filled on all of them, so nothing reads as a
continuation and every wrap is left standing as a row. The columns that *do* mark the rows
give themselves away by agreement -- several hold one short value per row and are filled on
nearly the same lines. Nearly is the operative word, and the first test here is why: under
exact equality this table's four markers count as four distinct sets, because a multi-line
header perturbs each of them by whichever header line that column's own label sits on.

The header fold is the other half. A header whose cells wrap sets each of them at its own
height, so its printed lines fill disjoint columns; a data row refills the columns above
it. Chaining while that holds ends where the body starts. Disjointness alone is not enough,
though, and that is the trap this file exists to pin down: a two-tier header whose top tier
spans column pairs is *also* disjoint, and folding it interleaves both tiers. Wrapping is
what tells them apart -- a continued cell fills its column twice, a tiered header once.

Geometry is taken from the dev corpus verbatim: PMC11000000.1 (case reports, three-line
references), PMC8000011.1 and PMC9000011.1 (headers wrapping to four and five lines).
Measured over its 100 truth tables, the three signals here move n-gram containment against
JATS ground truth from 0.823 to 0.846, ten tables better and none worse; on the
110-article tuned corpus, 0.760 to 0.778.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_tables import _header_fold, merge_continuation_lines

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class TestAgreeingColumnsNameTheRows:
    """Where several columns are filled on the same lines, those lines are the row starts."""

    # PMC11000000.1's Table 1, verbatim: 19 printed lines, 9 columns, 7 logical rows.
    # Gender, Age, Blood cultures and Brucella serology all fire on the same seven lines;
    # Reference wraps across 15 of the 19 and names nothing.
    LINES = [
        [
            "Reference",
            "Gender",
            "Age",
            "Country of",
            "Epidemiol-ogical antecedent",
            "Blood",
            "Brucella",
            "Tests to confirm",
            "Antibiotics",
        ],
        ["", "", "(years)", "exposure", "for brucellosis", "cultures", "serology", "diagnosis of", "regimen and"],
        ["", "", "", "", "", "", "titer", "myositis", "duration"],
        ["", "", "", "", "", "", "", "", ""],
        [
            "Suleiman",
            "M",
            "16",
            "Saudi",
            "Ingestion of unpasteuri-zed",
            "Negative",
            "1:5210",
            "Biopsy of the left",
            "G/1w",
        ],
        ["et al.", "", "", "Arabia", "camel milk", "", "", "deltoid muscle", "S/1w"],
        ["[8]", "", "", "", "", "", "", "EMG", "C -D/3 m"],
        ["Faris et al.", "F", "22", "Jordan", "Ingestion of unpasteuri-zed", "Positive", "1:640", "Pelvic MRI", "G/1w"],
        ["[9]", "", "", "", "milk", "", "", "", "R-D/3 m"],
        ["Aygul et al.", "M", "25", "Turkey", "Contact with infected", "Positive", "1:640", "EMG", "S/4 w"],
        ["[10]", "", "", "", "animal", "", "", "", "R-D/3 m"],
        ["Pantelis", "M", "19", "Greece", "NR", "Positive", ">1:1280", "Pelvic MRI", "D-R- C/6 m"],
        ["et al.", "", "", "", "", "", "", "", ""],
        ["[11]", "", "", "", "", "", "", "", ""],
        ["Dafni et al.", "F", "58", "Greece", "NR", "Positive", "NR", "Pelvic MRI", "D-C -Ra/6w"],
        ["[12]", "", "", "", "", "", "", "", ""],
        ["Kushal et al.", "M", "35", "India", "Contact with infected", "Negative", "1:640", "EMG", "D-R/6w"],
        ["[13]", "", "", "", "animal and ingestion of", "", "", "", ""],
        ["", "", "", "", "unpasteuri-zed milk.", "", "", "", ""],
    ]

    def test_a_wrapping_reference_column_no_longer_leaves_every_wrap_a_row(self) -> None:
        """The anchor rule saw 15 filled label cells and merged nothing; agreement sees six reports."""
        merged = merge_continuation_lines([list(row) for row in self.LINES], continuation_within_start_columns=True)

        # One header row plus the six case reports, not the 15 lines the anchor rule left
        # standing. This is the table the agreement bar has to be loose enough to see: its
        # four markers differ over the header lines and agree on every row start.
        assert len(merged) == 7
        # Each reference is whole rather than split down three printed lines.
        assert merged[1][0].split("\n") == ["Suleiman", "et al.", "[8]"]
        # And its row keeps the values that were printed beside it.
        assert merged[1][1] == "M"
        assert merged[1][2] == "16"

    def test_the_columns_that_agree_are_the_sparse_ones(self) -> None:
        """A column filled on most of a wrapping table's lines cannot be marking its rows.

        Reference is filled on 15 of 19 lines. Believing it is how a province column fused
        nine yak breeds into one column-major row, so the fill share is capped at half.
        """
        filled = sum(1 for row in self.LINES if row[0])
        assert filled / len(self.LINES) > 0.5

        merged = merge_continuation_lines([list(row) for row in self.LINES], continuation_within_start_columns=True)

        # Rows are named by Gender/Age/cultures/serology, so no row holds two genders.
        assert [row[1] for row in merged[1:]] == ["M", "F", "M", "M", "F", "M"]

    def test_one_sparse_column_alone_is_not_believed(self) -> None:
        """A single sparse column is indistinguishable from a sparse data column."""
        lines = [
            ["Total", "12", "4"],
            ["", "13", "5"],
            ["", "14", "6"],
            ["", "15", "7"],
        ]

        assert merge_continuation_lines([list(row) for row in lines]) == lines


class TestTheHeaderFold:
    """A header whose cells wrap is one row; a header whose tiers span columns is not."""

    # PMC9000011.1's Table 2, verbatim: a five-line header over a single data row, with
    # "Parts" and "The Shear"/"Cogging" set at three different heights.
    WRAPPED_HEADER = [
        ["", "The Box Girder, the", "The Interface", "", ""],
        ["", "", "", "", "The Shear"],
        ["Parts", "Track Slab, the Base", "between CA Mortar", "Rebar", ""],
        ["", "", "", "", "Cogging"],
        ["", "Plate, and CA Mortar", "and the Track Slab", "", ""],
        ["Elements", "C3D8I", "COH3D8", "T3D2", "Spring"],
    ]

    def test_a_header_wrapping_to_five_lines_becomes_one_row(self) -> None:
        merged = merge_continuation_lines([list(row) for row in self.WRAPPED_HEADER])

        assert len(merged) == 2
        assert merged[0][0] == "Parts"
        assert merged[0][1].split("\n") == [
            "The Box Girder, the",
            "Track Slab, the Base",
            "Plate, and CA Mortar",
        ]
        assert merged[0][4].split("\n") == ["The Shear", "Cogging"]
        assert merged[1] == ["Elements", "C3D8I", "COH3D8", "T3D2", "Spring"]

    def test_blank_lines_inside_the_header_are_crossed_not_believed(self) -> None:
        """PMC8000011.1's header carries blank lines between its tiers of wrapped cells.

        Stopping the fold on them left the header half folded (0.70 against ground truth);
        crossing them takes it to 1.00.
        """
        lines = [
            ["", "Microcrystalline", "Nano-Bentonite (B)", "", ""],
            ["", "", "", "", ""],
            ["TPS (wt%)", "", "", "Acronym", ""],
            ["", "Cellulose (C) (wt%)", "(wt%)", "", ""],
            ["", "", "", "", ""],
            ["100", "-", "-", "TPS", ""],
            ["95", "5", "-", "TPS/5C *", ""],
        ]

        assert _header_fold(lines) == 5
        merged = merge_continuation_lines([list(row) for row in lines], continuation_within_start_columns=True)
        assert merged[0][1].split("\n") == ["Microcrystalline", "Cellulose (C) (wt%)"]
        assert merged[0][0] == "TPS (wt%)"
        assert merged[1] == ["100", "-", "-", "TPS", ""]

    def test_a_tiered_header_is_disjoint_too_and_must_not_fold(self) -> None:
        """The top tier spans column pairs, so its sub-header fills the columns it left empty.

        Geometrically identical to a wrapped header, semantically the opposite: folding
        interleaves both tiers' grams (measured 0.87 -> 0.79). No column is filled twice
        across the two lines, and that is the whole difference.
        """
        lines = [
            ["modalities", "visual", "", "audio", ""],
            ["", "", "Acc", "", "Acc"],
            ["one", "1", "70", "2", "60"],
        ]

        assert _header_fold(lines) == 1
        assert merge_continuation_lines([list(row) for row in lines], continuation_within_start_columns=True) == lines

    def test_a_dense_grid_folds_nothing(self) -> None:
        """Two data rows refill the same columns, so the chain ends on the first line."""
        lines = [
            ["Group", "Mean", "SD"],
            ["Control", "12.5", "1.1"],
            ["Treated", "40.0", "2.4"],
        ]

        assert _header_fold(lines) == 1
        assert merge_continuation_lines([list(row) for row in lines]) == lines


class TestBlankLinesSeparateRows:
    """A blank printed line inside a grid is a row boundary, and carries no cell of its own."""

    def test_a_blank_line_stops_a_continuation_without_becoming_a_row(self) -> None:
        lines = [
            ["Variable", "Value"],
            ["", "continued"],
            ["", ""],
            ["", "not a continuation of Variable"],
        ]

        merged = merge_continuation_lines([list(row) for row in lines])

        assert merged == [
            ["Variable", "Value\ncontinued"],
            ["", "not a continuation of Variable"],
        ]
