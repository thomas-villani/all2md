#  Copyright (c) 2025 Tom Villani, Ph.D.
"""A passage of prose the detector fenced is not a table (#451).

A journal first page prints its keywords beside its abstract, a peer-review page
prints a reviewer's comments beside an author's response, and a magazine prints a
figure between two columns of body text. The whitespace separating them is a real
gutter, so the grid a detector builds is sound -- only the *content* says the
region is not a table. The abstract arrives as a cell, which reads wrong for a
human, and where the region spans two columns they interleave line by line inside
that cell, so every word survives and every adjacency dies.

Three signals must agree before a grid is condemned, because no two of them separate
the corpus. Censused over the 411 tables emitted across the 66-article dev corpus and
the 110-article held-out corpus, twelve grids hold a 60-word cell of three or more
sentences, and dominance alone orders two of them backwards: a real 6x5 data grid that
absorbed a figure caption dominates *more* (70%) than an abstract printed beside its
author affiliations (69%). The median cell length separates that pair -- values are one
word, an affiliation list is forty-nine -- and dominance separates both from a real
clinical table whose three parallel case descriptions leave no single cell dominant.

Ten defects, none of the 401 other grids, and the verdict holds across every threshold
combination tried. The cell text here is the real thing, taken from the census.
"""

import pytest

from all2md.parsers._pdf_tables import looks_like_gridded_prose

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]

# PMC10750033.1 p1: the abstract printed beside the keywords box, 354 words of it.
ABSTRACT = (
    "Objectives: Antimicrobial resistance (AMR), a growing global menace, poses a significant "
    "threat to maternal and fetal health. Asymptomatic bacteriuria in pregnancy is a recognised "
    "risk factor for pyelonephritis and preterm delivery. This study set out to describe the "
    "resistance profile of the organisms recovered. Methods: Urine samples were collected at the "
    "booking visit and cultured by standard technique. Isolates were identified to species level. "
    "Results: Escherichia coli predominated among the isolates recovered. Resistance to ampicillin "
    "was near universal across the series. Conclusions: Empirical therapy should be guided by local "
    "surveillance rather than by national guidance alone."
)
KEYWORDS = "Keywords: Asymptomatic Bacteriuria Antimicrobial resistance Multidrug Pregnancy"


class TestTheKeywordsBoxBesideAnAbstract:
    """The shape four of the eight regions take, on four different journals."""

    def test_an_abstract_beside_its_keywords_is_condemned(self) -> None:
        assert looks_like_gridded_prose([[KEYWORDS, ABSTRACT]])

    def test_the_article_info_header_does_not_save_it(self) -> None:
        """PMC11750000.1 p1 prints ``A R T I C L E | I N F O | A B S T R A C T`` above it.

        A header row of short labels adds cells without adding words, so the
        passage still holds the grid.
        """
        grid = [["A R T I C L E", "I N F O", "A B S T R A C T"], [KEYWORDS, "carcinoma", ABSTRACT]]

        assert looks_like_gridded_prose(grid)


class TestRealTablesSurvive:
    """Either signal alone describes plenty of real tables, so both must agree."""

    def test_a_long_cell_among_many_short_ones_is_a_table(self) -> None:
        """PMC3750033.1 p8: a 48x8 table whose caption cell runs 90 words over 7 sentences.

        The sentences are there; the dominance is not -- the cell is 28% of the
        grid's words. A footnote or a caption inside a real table looks exactly
        like this, and condemning it would cost the table.
        """
        caption = ABSTRACT  # long, many sentences -- the point is what surrounds it
        grid = [[caption, "", "", ""]] + [["TP53", "0.901", "1.37", "significant"] for _ in range(60)]

        assert not looks_like_gridded_prose(grid)

    def test_a_dominant_cell_of_values_is_a_table(self) -> None:
        """PMC3250033.1 p4: a shredded data row, 62 words at 65% of the grid.

        The dominance is there; the sentences are not. Decimal points do not
        count -- a terminator must meet whitespace or the end of the cell -- so
        a row of measurements reads as 0 sentences however long it runs.
        """
        values = " ".join(f"{n / 100:.2f} ± 0.0{n % 9}" for n in range(30, 60))
        grid = [["Table 5: Effects of black tea decoction on rat paw edema", "", ""], [values, "", ""]]

        assert not looks_like_gridded_prose(grid)

    def test_a_short_prose_cell_is_not_a_passage(self) -> None:
        """Three terse sentences are a comment column, not a fenced abstract."""
        grid = [["ACE2", "Up. Confirmed. Replicated."], ["TP53", "Down. Confirmed. Replicated."]]

        assert not looks_like_gridded_prose(grid)

    def test_a_data_grid_that_absorbed_a_caption_is_a_table(self) -> None:
        """PMC2000230.1 p7: a 6x5 grid of values with a figure caption stuck on as a row.

        This is the case dominance gets *backwards*. The caption is 79 of the grid's
        113 words -- 70%, more than the defect below -- because the table's own cells
        are single numbers. What says "table" is exactly that: the median filled cell
        is one word long.
        """
        header = ["Element/gene type", "50-kb upstream", "50-kb downstream", "Coding", "Total"]
        values = [[f"TR/kb row{n}", "0.120", "0.100", "0.151", "0.113"] for n in range(4)]
        caption = "Fig. 2 Distribution of CpG islands in imprinted genes. " + "region " * 70

        assert not looks_like_gridded_prose([header, *values, [caption, "", "", "", ""]])

    def test_parallel_case_descriptions_are_a_table(self) -> None:
        """PMC6500022.1 p8: three stages of care, each a paragraph, under three headers.

        Every cell is prose and the longest runs 303 words over 23 sentences, so both
        the passage test and the median test say prose. It is still a table, and what
        says so is that no one cell dominates -- three parallel descriptions share the
        grid at 51%.
        """
        stages = ["At the hospital", "At the rehab clinic", "At home with the neurology team"]
        bodies = ["Admission cause. " + "detail. " * n for n in (60, 20, 90)]

        assert not looks_like_gridded_prose([stages, bodies])

    def test_an_abstract_beside_its_affiliations_is_condemned(self) -> None:
        """PMC8500047.2 p1: the case that fixed the dominance bar below 70%.

        At 69% it sits *under* the real data grid above, so no share alone divides
        them. Its cells are an abstract and two author lists -- prose-length every one,
        which is what the median sees and the data grid does not have.
        """
        abstract = "ABSTRACT Background. " + "word " * 200 + "Conclusion. Results. Methods."
        grid = [[abstract, "", ""], ["Sahar Samy, Program Director " + "name " * 45, "", "Hashaam Akhtar " + "x " * 44]]

        assert looks_like_gridded_prose(grid)

    def test_an_empty_grid_is_not_condemned(self) -> None:
        assert not looks_like_gridded_prose([["", ""], ["", ""]])

    def test_none_cells_are_tolerated(self) -> None:
        """``find_tables()`` reports an unfilled cell as ``None``, not ``""``."""
        assert not looks_like_gridded_prose([[None, None], [None, "value"]])

    def test_one_long_caption_is_not_a_passage(self) -> None:
        """A single unpunctuated title, however long, is a caption and stays one."""
        title = " ".join(["Magnetic Resonance guided High Intensity Focused Ultrasound ablation"] * 3)
        grid = [["", title]]

        assert not looks_like_gridded_prose(grid)
