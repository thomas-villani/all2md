#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_stacked_cell_runs.py
"""A column filled in several runs is a stack of cells only where those runs start rows.

``_groups_stack_column_cells`` refuses a row grouping when one of its columns is filled in
three or more separate runs, on the reasoning that a cell fills contiguous lines, so a
column inside one logical row is one run. That reasoning holds for the cell; it does not
hold for the grid of printed lines the cell is read out of. Where a table centres its
cells vertically, the cells of one logical row sit at different heights and the extractor
emits a line per distinct baseline, so a single wrapped cell's lines alternate with its
taller neighbours' and that one cell appears as several runs.

The two shapes are told apart by what the runs start on. A line holding one or two of the
grid's columns is a fragment of a row; a line holding nearly all of them is a row. Both
fixtures here are verbatim from the corpus drawn after the guard was written, which is
where the distinction first cost anything -- on the corpus the guard was measured against
it never changes an outcome at all.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_tables import (
    _groups_stack_column_cells,
    _line_fills_a_row,
    merge_continuation_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class TestACentredCellIsNotAStackOfCells:
    """One wrapped cell scattered down a column by its neighbours' heights."""

    # PMC12250033.1's gene/locus table, verbatim: 17 printed lines, 4 columns, 7 rows.
    # "SH2B3" and "[64]" are one cell printed on lines 1 and 3, with line 2 holding only
    # the middle columns -- so column 0 shows two runs there, and column 1 three of them
    # across the MTHFR row below.
    LINES = [
        ["Gene/Locus", "Function", "Associated with", "Implication"],
        ["SH2B3", "Immune and vascular", "", "Shared inflammatory and"],
        ["", "", "PE, HTN", ""],
        ["[64]", "regulation", "", "hypertensive pathways"],
        ["FTO", "Metabolic and vascular", "", ""],
        ["", "", "Obesity, HDP, HTN", "Metabolic–vascular interface"],
        ["[64]", "signaling", "", ""],
        ["eNOS (NOS3)", "NO production,", "HDP, endothelial", "Impaired vascular tone and"],
        ["[65]", "vasodilation", "dysfunction", "endothelial function"],
        ["", "Methylation,", "", ""],
        ["MTHFR", "", "", "Endothelial stress, oxidative"],
        ["", "homocysteine", "PE, HTN", ""],
        ["[66]", "", "", "damage"],
        ["", "metabolism", "", ""],
        ["Hypertension PRS", "Cumulative genetic", "", "Predictive of postpartum"],
        ["", "", "HDP, later-life HTN", ""],
        ["[67]", "burden", "", "risk"],
    ]

    EXTENTS = [
        (412.3195495605469, 420.2896423339844),
        (426.6610107421875, 434.631103515625),
        (431.3940124511719, 439.3641052246094),
        (436.1260070800781, 444.0960998535156),
        (450.3919982910156, 458.3620910644531),
        (455.1239929199219, 463.0940856933594),
        (459.8559875488281, 467.8260803222656),
        (474.12298583984375, 482.09307861328125),
        (483.58697509765625, 491.55706787109375),
        (497.8529968261719, 505.8230895996094),
        (502.5849914550781, 510.5550842285156),
        (507.3179931640625, 515.2880859375),
        (512.0499877929688, 520.0200805664062),
        (516.781982421875, 524.7520751953125),
        (531.0479736328125, 539.01806640625),
        (535.780029296875, 543.7501220703125),
        (540.5130004882812, 548.4830932617188),
    ]

    def test_the_wrapped_label_keeps_its_row(self) -> None:
        merged = merge_continuation_lines([list(row) for row in self.LINES], self.EXTENTS)

        assert len(merged) == 7
        assert merged[1][0].split("\n") == ["SH2B3", "[64]"]
        assert merged[1][2] == "PE, HTN"
        # Three printed lines of one cell, not three cells.
        assert merged[5][1].split("\n") == ["Methylation,", "homocysteine", "metabolism"]

    def test_the_grouping_is_not_read_as_a_stack(self) -> None:
        """The runs are real; what they start on is what makes them fragments."""
        groups = [[0], [1, 2, 3], [4, 5, 6]]

        assert _groups_stack_column_cells(self.LINES, groups) is False

        # Counting runs without asking what starts them sees column 1 filled three times
        # over the MTHFR row -- the count the guard used to refuse the whole grouping on.
        filled = [bool(self.LINES[index][1]) for index in (9, 10, 11, 12, 13)]
        runs = sum(1 for i, cell in enumerate(filled) if cell and not (i and filled[i - 1]))
        assert runs == 3


class TestAStackOfRealRowsIsStillRefused:
    """Lines that each fill the grid are rows, however the grouping wants to read them."""

    # PMC5250647.1's miRNA table, verbatim: every printed line is a complete data row,
    # empty only in the column where a repeated name is elided. Its gap structure invites
    # fusing the body into one row, which would interleave the whole table column-wise.
    LINES = [
        ["miRNA", "Delivery", "Compound", "Model", "Effectb", "Source"],
        ["mmu-miR-126a", "Intravitreal injection", "miR-mimic", "OIR", "; Retinal NV", "[114]"],
        ["mmu-miR-128a", "Intravitreal injection", "miR-mimic", "OIR", "; Retinal NV", "[105]"],
        ["mmu-miR-132a", "Intraocular injection", "anti-miR", "OIR", "; NV", "[106]"],
        ["mmu-miR-150a", "Intraocular injection", "pre-miR", "OIR", "; Retinal NV", "[90]"],
        ["", "Intraocular injection", "pre-miR", "Laser induced CNV", "; Choroidal NV", "[90]"],
        ["", "Intravitreal injection", "miR-mimic", "OIR", "; Retinal NV", "[108]"],
        ["", "Knockout mice", "miR-150-/-", "Laser induced CNV", ": Choroidal NV", "[108]"],
        ["mmu-miR-155a", "Knockout mice", "miR-155-/-", "OIR", ": Retinal NV", "[75]"],
        ["", "Knockout mice", "miR-155-/-", "Retinal development", "; Vascular area", "[75]"],
        ["", "Intravitreal injection", "miR-mimic", "Retinal development", "; Vascular area", "[75]"],
        ["mmu-miR-184a", "Intraocular injection", "pre-miR", "OIR", "; Retinal NV", "[90]"],
        ["mmu-miR-23/27a", "Intravitreal injection", "anti-miR", "Laser induced CNV", "; Choroidal NV", "[107]"],
        ["mmu-miR-24a", "Subretinal", "miR-mimic", "Laser induced CNV", "; Choroidal NV", "[109]"],
        ["mmu-miR-31a", "Intraocular injection", "pre-miR", "OIR", "; Retinal NV", "[90]"],
        ["", "Intraocular injection", "pre-miR", "Laser induced CNV", "; Choroidal NV", "[90]"],
    ]

    def test_complete_rows_are_not_fused_into_one(self) -> None:
        groups = [[0], list(range(1, 16))]

        assert _groups_stack_column_cells(self.LINES, groups) is True

    def test_an_elided_leading_column_does_not_disqualify_a_row(self) -> None:
        """Five columns of six is still a row, and the bar has to sit under that.

        Real rows do leave a column empty where a value repeats -- this table elides the
        miRNA name on every row after the first of a group. Were the bar set at every
        column, those rows would read as fragments and the guard would stop seeing them.
        """
        elided = self.LINES[5]

        assert not elided[0]
        assert sum(1 for cell in elided if cell) == 5
        assert _line_fills_a_row(elided, 6) is True

    def test_a_fragment_of_a_row_is_not_one(self) -> None:
        """The other side of the same bar, from the centred table above."""
        fragment = TestACentredCellIsNotAStackOfCells.LINES[2]

        assert sum(1 for cell in fragment if cell) == 1
        assert _line_fills_a_row(fragment, 4) is False
