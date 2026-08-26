"""One block printed across the gutter must not erase the whole channel (#440).

``_detect_columns_by_channel`` merges the blocks' x-intervals and reads the
complement as the gutter. That test is all-or-nothing: a *single* block bridging
the gutter fuses the two runs, the page has no channel at all, and it is read
line-by-line in y -- so both columns interleave and every adjacency dies, even
though dozens of blocks on each side agree where the gutter is.

Page furniture was the common culprit and #445 handles it by trimming bands off
the ends of the page. A block in the middle of the body is not reachable that
way: no band trim will ever discard it. A wide figure label, or a formula set
across the measure, still erases the channel.

The tolerant search asks the question the other way round -- for each candidate
x, how many blocks does it cut? -- which survives a crosser. What keeps that
honest is uniqueness: several admissible gutters on one page is the signature of
an undetected table, not a layout, and one held-out reference page offers twelve.

The geometry is the real thing, from page 6 of PMC7250022.1 in the held-out
corpus: a 569pt page with its gutter at x=297.6.
"""

import pytest

from all2md.constants import PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS
from all2md.parsers._pdf_columns import _tolerant_boundaries, detect_columns

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

GUTTER_LEFT, GUTTER_RIGHT = 288.0, 307.0
PAGE_RIGHT = 569.0


def _two_columns(rows: int = 8) -> list[dict]:
    """A two-column page: ``rows`` stacked blocks each side of a 19pt gutter."""
    blocks = []
    for i in range(rows):
        top = 50.0 + i * 36.0
        blocks.append({"bbox": [28.0, top, GUTTER_LEFT, top + 35.0]})
        blocks.append({"bbox": [GUTTER_RIGHT, top, PAGE_RIGHT, top + 35.0]})
    return blocks


def _crossing_block(top: float = 200.0) -> dict:
    """A body block printed across the gutter -- a wide figure label."""
    return {"bbox": [180.0, top, 420.0, top + 12.0]}


def _boxes(blocks: list[dict]) -> list[tuple[float, float, float, float]]:
    return [tuple(block["bbox"]) for block in blocks]


class TestOneCrossingBlock:
    def test_a_clean_two_column_page_splits(self) -> None:
        """The control: without a crosser this page always split."""
        assert len(detect_columns(_two_columns(), 20)) == 2

    def test_a_single_crossing_block_no_longer_erases_the_channel(self) -> None:
        blocks = [*_two_columns(), _crossing_block()]

        assert len(detect_columns(blocks, 20)) == 2

    def test_the_crossing_block_is_still_emitted(self) -> None:
        """Tolerating it must not mean dropping it."""
        crosser = _crossing_block()
        columns = detect_columns([*_two_columns(), crosser], 20)

        assert any(crosser in column for column in columns)

    def test_the_columns_keep_their_own_blocks(self) -> None:
        """Every left block lands left of every right block, which is the whole point."""
        columns = detect_columns([*_two_columns(), _crossing_block()], 20)
        left, right = columns[0], columns[-1]

        assert all(block["bbox"][2] <= GUTTER_LEFT for block in left if block["bbox"][0] < 100)
        assert all(block["bbox"][0] >= GUTTER_RIGHT for block in right if block["bbox"][0] > 300)


class TestWhatTheToleranceRefuses:
    def test_more_crossers_than_allowed_still_veto(self) -> None:
        crossers = [_crossing_block(200.0 + 40 * i) for i in range(PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS + 1)]

        assert _tolerant_boundaries(_boxes([*_two_columns(), *crossers]), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_a_page_naming_several_gutters_is_refused_outright(self) -> None:
        """An undetected table offers many admissible gutters; a layout offers one.

        Refused rather than split on the best of them -- picking a winner among
        several is how a table's column structure becomes the page's.
        """
        grid = []
        for row in range(8):
            top = 50.0 + row * 36.0
            for x0 in (28.0, 150.0, 280.0, 410.0):
                grid.append({"bbox": [x0, top, x0 + 100.0, top + 35.0]})

        assert _tolerant_boundaries(_boxes(grid), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_too_few_blocks_a_side_is_refused(self) -> None:
        """A crossing allowance does not lower the evidence bar the sides must clear."""
        thin = _two_columns(rows=1)

        assert _tolerant_boundaries(_boxes([*thin, _crossing_block()]), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_sides_that_do_not_overlap_in_y_are_refused(self) -> None:
        """Stacked, not side by side.

        A y-sort cannot interleave these, so there is nothing for a channel to repair.
        """
        stacked = []
        for i in range(6):
            stacked.append({"bbox": [28.0, 50.0 + i * 36.0, GUTTER_LEFT, 85.0 + i * 36.0]})
        for i in range(6):
            stacked.append({"bbox": [GUTTER_RIGHT, 600.0 + i * 36.0, PAGE_RIGHT, 635.0 + i * 36.0]})

        assert _tolerant_boundaries(_boxes(stacked), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_an_indented_quotation_does_not_make_a_gutter(self) -> None:
        """It overlaps the body in x, so no candidate x separates the two sides."""
        body = [{"bbox": [28.0, 50.0 + i * 36.0, PAGE_RIGHT, 85.0 + i * 36.0]} for i in range(6)]
        quote = [{"bbox": [80.0, 300.0 + i * 20.0, 500.0, 318.0 + i * 20.0]} for i in range(3)]

        assert _tolerant_boundaries(_boxes([*body, *quote]), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_no_blocks_names_no_gutter(self) -> None:
        assert _tolerant_boundaries([], PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []


class TestTheSidesMustBeColumns:
    """Tolerating a crosser exposes gutters the strict test never had to judge.

    One of them is not a layout at all. A journal title page sets its affiliations
    in a narrow band beside a wide abstract, and reading that as two columns hoists
    the introduction above the article's own title -- which is what PMC8250095.2
    did before this guard, at 123pt against 317pt.
    """

    def _lopsided(self) -> list[dict]:
        """A narrow affiliation sidebar beside a wide abstract, as on a title page."""
        blocks = [{"bbox": [28.0, 100.0 + i * 30.0, 151.0, 128.0 + i * 30.0]} for i in range(5)]
        blocks += [{"bbox": [175.0, 100.0 + i * 30.0, 492.0, 128.0 + i * 30.0]} for i in range(5)]
        return blocks

    def test_a_narrow_sidebar_beside_a_wide_body_is_not_two_columns(self) -> None:
        assert _tolerant_boundaries(_boxes(self._lopsided()), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS) == []

    def test_two_columns_of_one_measure_still_qualify(self) -> None:
        """The control for the guard above: equal columns are what a journal sets."""
        found = _tolerant_boundaries(
            _boxes([*_two_columns(), _crossing_block()]), PDF_COLUMN_CHANNEL_MAX_CROSSING_BLOCKS
        )

        assert len(found) == 1
        assert GUTTER_LEFT < found[0] < GUTTER_RIGHT
