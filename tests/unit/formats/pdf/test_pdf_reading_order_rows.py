"""Two columns starting level must read left-to-right, not by a hairline (#290).

Blocks were ordered on ``y`` alone, so whichever column's top edge was a fraction
of a point higher was read first. On page 16 of ``PMC7500012.1`` the columns start
at ``y=89.708191`` and ``y=89.702942`` -- five thousandths of a point apart -- and
the right one won, so the references read 39-61 and then 19-38.

Note those values are *not* equal, which is why the obvious ``(y, x)`` sort key
does not fix it: the blocks have to be treated as level first.
"""

import fitz
import pytest

from all2md import to_markdown
from all2md.parsers.pdf import PdfToAstConverter

# Taken from the page in the report, so the test fails for the reason the bug did.
LEFT_Y = 89.708191
RIGHT_Y = 89.702942


def _block(x0: float, y0: float, text: str) -> dict:
    """A block whose lines give it a measurable height, as a real one has."""
    return {
        "bbox": [x0, y0, x0 + 230.0, y0 + 640.0],
        "lines": [{"bbox": [x0, y0, x0 + 230.0, y0 + 9.0], "spans": [{"text": text}]}],
    }


def _order(blocks: list[dict]) -> list[str]:
    converter = PdfToAstConverter()
    items = converter._build_sorted_column_items(blocks, [])
    return [item[2]["lines"][0]["spans"][0]["text"] for item in items]


@pytest.mark.unit
@pytest.mark.pdf
class TestLevelBlocksReadLeftToRight:
    """The reported geometry, and the general rule behind it."""

    def test_hairline_higher_right_column_does_not_win(self):
        right = _block(304.7, RIGHT_Y, "right")
        left = _block(56.7, LEFT_Y, "left")
        # Input order deliberately puts the right column first, so a stable sort
        # alone would leave it there.
        assert _order([right, left]) == ["left", "right"]

    def test_running_head_above_both_still_comes_first(self):
        head = _block(56.7, 32.6, "head")
        right = _block(304.7, RIGHT_Y, "right")
        left = _block(56.7, LEFT_Y, "left")
        assert _order([right, head, left]) == ["head", "left", "right"]

    def test_three_level_columns(self):
        blocks = [
            _block(400.0, 100.02, "c"),
            _block(60.0, 100.00, "a"),
            _block(230.0, 100.01, "b"),
        ]
        assert _order(blocks) == ["a", "b", "c"]


@pytest.mark.unit
@pytest.mark.pdf
class TestGenuineVerticalOffsetsAreLeftAlone:
    """Controls: the rule must not become a general left-to-right sort.

    These pass before and after the change. Without them the tolerance could be
    widened arbitrarily and the tests above would still be green.
    """

    def test_a_block_clearly_below_stays_below(self):
        upper = _block(304.7, 100.0, "upper-right")
        lower = _block(56.7, 140.0, "lower-left")
        assert _order([upper, lower]) == ["upper-right", "lower-left"]

    def test_a_margin_badge_below_a_title_does_not_overtake_it(self):
        """The case that ruled out a quarter-line tolerance.

        A left-margin badge sitting 2.2pt below a title is a real offset, not
        noise, and reading it first would demote the title.
        """
        title = _block(155.9, 128.3, "title")
        badge = _block(93.6, 130.5, "badge")
        assert _order([title, badge]) == ["title", "badge"]

    def test_consecutive_lines_of_running_text_keep_their_order(self):
        first = _block(56.7, 100.0, "first")
        second = _block(56.7, 109.0, "second")
        assert _order([second, first]) == ["first", "second"]


@pytest.mark.unit
@pytest.mark.pdf
class TestEmptyAndSingleInputs:
    """The grouping must not disturb the trivial cases."""

    def test_no_blocks(self):
        assert _order([]) == []

    def test_one_block(self):
        assert _order([_block(56.7, 100.0, "only")]) == ["only"]


@pytest.mark.unit
@pytest.mark.pdf
class TestEndToEnd:
    """A rendered two-column page reads down the left column first."""

    def test_two_column_page_with_a_gutter_too_narrow_to_detect(self, tmp_path):
        """The gutter has to be narrow, or the bug cannot happen.

        With a wide gutter ``detect_columns`` splits the page and orders the
        columns by their x centres, which is already correct -- the reported page
        fails precisely because its 14.3pt gutter is under ``column_gap_threshold``
        and both columns land in one column ordered by y. Padding the text makes
        the columns wide enough for the gap here to be similarly narrow.
        """
        padding = "filler text to widen the column " * 4
        doc = fitz.open()
        page = doc.new_page()
        # Right column drawn first and started a hair higher, reproducing the
        # shape of the reported page.
        for index in range(6):
            page.insert_text((300.0, 90.0 + index * 12), f"right{index} {padding}", fontsize=5)
        for index in range(6):
            page.insert_text((56.0, 90.05 + index * 12), f"left{index} {padding}", fontsize=5)
        path = tmp_path / "two_column.pdf"
        doc.save(str(path))
        doc.close()

        markdown = to_markdown(str(path))
        assert markdown.index("left0") < markdown.index("right0")
