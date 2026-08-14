#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_list_nesting_levels.py
"""A PDF list item's nesting level comes from its indent, not from when it was seen.

``_determine_list_level_from_x`` used to hand out levels in arrival order --
``len(x_levels)`` -- with no comparison of the x-coordinates themselves. The first list
item of a run became level 0 whatever its indent, and each new indent after it became one
level deeper whether it was further right or further left.

That inverts a very ordinary shape. A nested list continuing at the top of a column or a
page starts on a *sub*-bullet, so the sub-bullet was recorded as level 0 and the genuine
top-level bullet after it as level 1. The caller reads a larger level as deeper and calls
``_handle_deeper_nesting``, so the parent list ended up nested inside its own child.

The requirement pinned here is an ordering one -- larger indent, larger level -- and not
any particular numbering, so these tests assert the ordering and never the numbers. The
levels are deliberately neither 0-based nor contiguous: renumbering them to keep either
property would strand the level numbers the caller has already recorded on its list
stack, so a shallower indent takes a lower number instead, and one arriving between two
known indents takes a number between theirs.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import List, ListItem, SourceLocation, Text
from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

TOP_LEVEL_X = 72.0
SUB_LEVEL_X = 100.0
SUB_SUB_LEVEL_X = 128.0


@pytest.fixture
def converter() -> PdfToAstConverter:
    return PdfToAstConverter(options=PdfOptions())


def _levels(converter: PdfToAstConverter, *xs: float) -> list[int]:
    """The level assigned to each x, in the order the items were seen."""
    x_levels: dict[int, float] = {}
    return [converter._determine_list_level_from_x(x, x_levels) for x in xs]


class TestTheLevelFollowsTheIndent:
    def test_a_plain_nested_list_still_deepens(self, converter):
        """The ordinary case, and the only thing the numbers themselves have to satisfy."""
        top, sub, sub_sub = _levels(converter, TOP_LEVEL_X, SUB_LEVEL_X, SUB_SUB_LEVEL_X)

        assert top < sub < sub_sub

    def test_a_sub_bullet_seen_first_is_still_the_deeper_one(self, converter):
        """The whole bug: the sub-bullet arrives first, so arrival order said it was level 0."""
        sub, top = _levels(converter, SUB_LEVEL_X, TOP_LEVEL_X)

        assert sub > top, "the item further right must be the deeper level, whichever was seen first"

    def test_returning_to_the_first_indent_returns_the_first_level(self, converter):
        sub, top, sub_again = _levels(converter, SUB_LEVEL_X, TOP_LEVEL_X, SUB_LEVEL_X)

        assert sub_again == sub
        assert sub_again > top

    def test_three_indents_arriving_in_the_worst_order(self, converter):
        levels = _levels(converter, SUB_SUB_LEVEL_X, SUB_LEVEL_X, TOP_LEVEL_X)

        assert levels[0] > levels[1] > levels[2]

    @pytest.mark.parametrize(
        "order",
        [
            pytest.param((0, 1, 2), id="outside-in"),
            pytest.param((2, 1, 0), id="inside-out"),
            pytest.param((1, 0, 2), id="middle-first"),
            pytest.param((1, 2, 0), id="middle-then-deepest"),
            pytest.param((2, 0, 1), id="deepest-then-shallowest"),
            pytest.param((0, 2, 1), id="shallowest-then-deepest"),
        ],
    )
    def test_the_level_order_matches_the_indent_order_whatever_the_arrival_order(self, converter, order):
        """The invariant, over every arrival order of the same three indents."""
        indents = [TOP_LEVEL_X, SUB_LEVEL_X, SUB_SUB_LEVEL_X]
        seen = [indents[i] for i in order]

        levels = dict(zip(seen, _levels(converter, *seen), strict=True))

        assert levels[TOP_LEVEL_X] < levels[SUB_LEVEL_X] < levels[SUB_SUB_LEVEL_X]

    def test_distinct_indents_get_distinct_levels(self, converter):
        levels = _levels(converter, SUB_LEVEL_X, SUB_SUB_LEVEL_X, TOP_LEVEL_X)

        assert len(set(levels)) == 3


class TestIndentsCloseTogetherAreOneLevel:
    def test_a_couple_of_points_of_jitter_is_the_same_level(self, converter):
        assert _levels(converter, TOP_LEVEL_X, TOP_LEVEL_X + 2.0) == [0, 0]

    def test_it_matches_the_nearest_indent_not_the_first_one_within_tolerance(self, converter):
        """With several levels established, "first match wins" is arrival order again."""
        levels = _levels(converter, TOP_LEVEL_X, TOP_LEVEL_X + 6.0, TOP_LEVEL_X + 5.5)

        assert levels[2] == levels[1], "5.5 is nearer to 6.0 than to 0.0"

    def test_an_indent_arriving_between_two_levels_lands_between_them(self, converter):
        """Levels are spaced out precisely so a later, middle indent has somewhere to go."""
        outer, inner, middle = _levels(converter, TOP_LEVEL_X, SUB_SUB_LEVEL_X, SUB_LEVEL_X)

        assert outer < middle < inner


# --- through the list builder ------------------------------------------------------


def _bullet(text: str, x: float) -> AstParagraph:
    return AstParagraph(
        content=[Text(content=f"• {text}")],
        source_location=SourceLocation(format="pdf", page=1, metadata={"bbox": (x, 100.0, 400.0, 110.0)}),
    )


def _item_texts(node) -> list[str]:
    """Every list item at or under ``node``, each by its *own* text.

    An item's own text excludes any nested list's, so that a parent and its child are
    two entries rather than one concatenation.
    """
    found: list[str] = []

    def visit(current) -> None:
        if isinstance(current, ListItem):
            own = " ".join(extract_text(child, joiner="") for child in current.children if not isinstance(child, List))
            found.append(" ".join(own.split()))
            for child in current.children:
                if isinstance(child, List):
                    visit(child)
            return
        for item in getattr(current, "items", None) or []:
            visit(item)

    visit(node)
    return found


class TestTheListBuilderNestsTheRightWayRound:
    def test_a_normal_nested_list_is_unchanged(self, converter):
        nodes = converter._convert_paragraphs_to_lists(
            [
                _bullet("parent", TOP_LEVEL_X),
                _bullet("child", SUB_LEVEL_X),
                _bullet("parent again", TOP_LEVEL_X),
            ]
        )

        assert len(nodes) == 1
        outer = nodes[0]
        assert isinstance(outer, List)
        assert _item_texts(outer.items[0]) == ["parent", "child"], "the child belongs under the parent"

    def test_a_parent_is_never_nested_under_its_own_child(self, converter):
        """A nested list continuing at the top of a column: the sub-bullet comes first."""
        nodes = converter._convert_paragraphs_to_lists(
            [
                _bullet("continued sub-item", SUB_LEVEL_X),
                _bullet("a top-level item", TOP_LEVEL_X),
                _bullet("another top-level item", TOP_LEVEL_X),
            ]
        )

        for node in nodes:
            if isinstance(node, List):
                for item in node.items:
                    nested = _item_texts(item)
                    if nested and nested[0] == "continued sub-item":
                        assert "a top-level item" not in nested, "the parent was nested under its own child"

    def test_no_item_is_lost_when_the_run_starts_on_a_sub_bullet(self, converter):
        """Re-anchoring pops the stack empty, and the popped list has to go somewhere."""
        nodes = converter._convert_paragraphs_to_lists(
            [
                _bullet("continued sub-item", SUB_LEVEL_X),
                _bullet("a top-level item", TOP_LEVEL_X),
                _bullet("another top-level item", TOP_LEVEL_X),
            ]
        )

        emitted = [text for node in nodes for text in _item_texts(node)]
        assert sorted(emitted) == sorted(["continued sub-item", "a top-level item", "another top-level item"])

    def test_the_two_top_level_items_stay_siblings(self, converter):
        nodes = converter._convert_paragraphs_to_lists(
            [
                _bullet("continued sub-item", SUB_LEVEL_X),
                _bullet("a top-level item", TOP_LEVEL_X),
                _bullet("another top-level item", TOP_LEVEL_X),
            ]
        )

        top_level_lists = [node for node in nodes if isinstance(node, List) and "a top-level item" in _item_texts(node)]
        assert len(top_level_lists) == 1
        assert _item_texts(top_level_lists[0]) == ["a top-level item", "another top-level item"]
