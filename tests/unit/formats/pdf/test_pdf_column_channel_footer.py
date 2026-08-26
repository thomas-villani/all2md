"""A footer must not veto a column channel it cannot interleave (#440).

``_detect_columns_by_channel`` admits a tight-gutter two-column page on
structural evidence: an x-interval no non-spanning block touches, with enough
blocks and enough mutual y-overlap on each side that a y-sort would provably
interleave them. Any single block crossing that interval merges the two x-runs
into one and the channel disappears, so the page is read line-by-line in y and
both columns interleave -- every word survives, every adjacency dies.

The prune that guarded against this dropped blocks that y-overlap *nothing*,
which is enough for a lone stray page number but not for a real journal footer.
On the mycology reference pages the footer has two elements on one baseline --
a copyright line crossing the gutter and a page number -- so each vouches for
the other, both survive, and the copyright line erases a channel that twenty
blocks a side support.

What makes that footer discardable is not how far below the body it sits. The
pages #445 was measured on separate the two by 40-312pt; ten more separate them
by 8.6-11.5pt, tighter than the gap above many a table row. Height is the
discriminator instead: furniture prints a line or two, the body prints the page.

The geometry in these tests is the real thing, taken from page 13 of
PMC7250011.1 in the held-out corpus: 260pt columns at x 28-288 and x 309-569 and
a 20.7pt gutter, with the footer printed at both distances.
"""

import pytest

from all2md.parsers._pdf_columns import detect_columns

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

GUTTER_LEFT, GUTTER_RIGHT = 288.3, 309.0
PAGE_RIGHT = 569.0


def _two_columns(rows: int = 13) -> list[dict]:
    """Build a reference page: ``rows`` stacked blocks in each of two columns."""
    blocks = []
    for i in range(rows):
        top = 50.0 + i * 36.0
        blocks.append({"bbox": [28.3, top, GUTTER_LEFT, top + 35.5]})
        blocks.append({"bbox": [GUTTER_RIGHT, top, PAGE_RIGHT, top + 35.5]})
    return blocks


def _footer() -> list[dict]:
    """The copyright line, which crosses the gutter, and the page number."""
    return [
        {"bbox": [211.5, 808.0, 383.7, 819.5]},
        {"bbox": [550.2, 806.6, 566.9, 820.6]},
    ]


def _column_of(columns: list[list[dict]], block: dict) -> int:
    for i, column in enumerate(columns):
        if block in column:
            return i
    raise AssertionError("block was assigned to no column")


class TestFooterDoesNotVetoTheChannel:
    def test_clean_page_splits(self) -> None:
        """The control: without furniture the channel has always been found."""
        assert len(detect_columns(_two_columns())) == 2

    def test_gutter_crossing_footer_pair_still_splits(self) -> None:
        """The regression: two footer elements on one baseline vouched for each other."""
        assert len(detect_columns(_two_columns() + _footer())) == 2

    def test_lone_gutter_crossing_footer_still_splits(self) -> None:
        """The case the original prune already handled stays handled."""
        assert len(detect_columns(_two_columns() + _footer()[:1])) == 2

    def test_footer_reads_after_both_columns(self) -> None:
        """Furniture below the body belongs after it, not spliced into a column.

        Excluding the footer from the *evidence* must not exclude it from the
        *output*: it is still assigned a column, and being below all body text
        it goes to the last one so a reader reaches it after both columns.
        """
        body, footer = _two_columns(), _footer()
        columns = detect_columns(body + footer)
        emitted = [block for column in columns for block in column]
        assert len(emitted) == len(body) + len(footer)
        for block in footer:
            assert _column_of(columns, block) == len(columns) - 1

    def test_columns_are_not_interleaved(self) -> None:
        """The point of the whole exercise: each side stays contiguous."""
        columns = detect_columns(_two_columns() + _footer())
        left, right = columns[0], columns[1]
        assert all(block["bbox"][2] <= GUTTER_LEFT for block in left)
        assert all(block["bbox"][0] >= GUTTER_RIGHT for block in right[: len(right) - 2])


class TestOnlyFurnitureIsDiscarded:
    """A band big enough to be a column is body, and body never gets dropped."""

    def test_a_figure_split_body_is_left_alone(self) -> None:
        """Two substantial bands with a bridging block: no guess about which half.

        Dropping the smaller band here would admit a channel on half a page's
        evidence. Measured on the held-out corpus, every page this rejects would
        have discarded 6, 17, 27 or 39 blocks, against exactly 2 for every page
        it accepts.
        """
        upper = [{"bbox": [28.3, 50.0 + i * 30.0, GUTTER_LEFT, 78.0 + i * 30.0]} for i in range(4)]
        upper += [{"bbox": [GUTTER_RIGHT, 50.0 + i * 30.0, PAGE_RIGHT, 78.0 + i * 30.0]} for i in range(4)]
        lower = [{"bbox": [28.3, 400.0 + i * 30.0, GUTTER_LEFT, 428.0 + i * 30.0]} for i in range(4)]
        lower += [{"bbox": [GUTTER_RIGHT, 400.0 + i * 30.0, PAGE_RIGHT, 428.0 + i * 30.0]} for i in range(4)]
        bridge = [{"bbox": [211.5, 404.0, 383.7, 415.0]}]

        assert len(detect_columns(upper + lower + bridge)) == 1

    def test_a_single_column_page_is_not_split_by_stripping_its_footer(self) -> None:
        """Removing furniture must not manufacture a channel out of nothing."""
        body = [{"bbox": [28.3, 50.0 + i * 30.0, 520.0, 78.0 + i * 30.0]} for i in range(12)]
        assert len(detect_columns(body + _footer())) == 1


def _tight_footer(rows: int = 13) -> list[dict]:
    """The same footer, printed a single line below the last line of text.

    PMC7250011.1 p6 and nine pages like it in the held-out corpus set their
    footer 8.6-11.5pt below the body -- tighter than the gap above many a table
    row, so no measure of clear space can tell the two apart.
    """
    body_bottom = 50.0 + (rows - 1) * 36.0 + 35.5
    return [
        {"bbox": [211.5, body_bottom + 11.5, 383.7, body_bottom + 23.0]},
        {"bbox": [550.2, body_bottom + 10.1, 566.9, body_bottom + 24.1]},
    ]


class TestFurnitureIsMeasuredByHeightNotDistance:
    """What makes a band furniture is that it prints a line, not that it sits far off."""

    def test_a_footer_one_line_below_the_body_still_splits(self) -> None:
        """The regression: a footer too close to the body to clear a gap threshold.

        The trim that #445 shipped banded the page at 24pt of clear space, which
        these pages never reach. Ten of them read line-by-line in y as a result,
        seven in the two articles that between them own 44 of the reading's lost
        blocks.
        """
        assert len(detect_columns(_two_columns() + _tight_footer())) == 2

    def test_the_tight_footer_still_reads_after_both_columns(self) -> None:
        """Trimming furniture from the evidence must not move it in the output."""
        body, footer = _two_columns(), _tight_footer()
        columns = detect_columns(body + footer)
        assert len([block for column in columns for block in column]) == len(body) + len(footer)
        for block in footer:
            assert _column_of(columns, block) == len(columns) - 1

    def test_a_tall_end_band_is_not_furniture(self) -> None:
        """A band that prints paragraphs is body, however few blocks it holds.

        PMC8250041.1 p0 prints a correspondence sidebar beside an abstract whose
        narrower lines cross the gutter. An end trim does unlock a channel there,
        but only by discarding 19.4% of the page's printed text; every trim on
        the corpus that unlocks a *real* channel discards 1.4-2.3%. Counting
        blocks cannot see the difference -- the band here holds two, fewer than
        a column needs -- so the bar is height.
        """
        tight_left, tight_right = 290.0, 306.0  # a 16pt gutter: only the channel can admit it
        intro = [
            {"bbox": [44.8, 50.0, 188.4, 300.0]},  # the sidebar
            {"bbox": [207.1, 50.0, 464.9, 300.0]},  # the abstract, crossing the gutter
        ]
        body = []
        for i in range(4):
            top = 400.0 + i * 36.0
            body.append({"bbox": [28.3, top, tight_left, top + 35.5]})
            body.append({"bbox": [tight_right, top, PAGE_RIGHT, top + 35.5]})
        assert len(detect_columns(body)) == 2, "control: the body alone is a channel"
        assert len(detect_columns(intro + body)) == 1
