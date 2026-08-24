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

The geometry in these tests is the real thing, taken from page 13 of
PMC7250011.1 in the held-out corpus: 260pt columns at x 28-288 and x 309-569, a
20.7pt gutter, and a footer 312pt below the last line of text.
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
