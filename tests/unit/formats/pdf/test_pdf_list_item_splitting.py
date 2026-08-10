#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_list_item_splitting.py
"""A bulleted list is more than one list item.

The vertical gap between two bullets is the same gap that separates two paragraphs, so
the paragraph-break rule is suspended once a list has started -- otherwise every item
that wrapped would be split at its own second line. With nothing put in its place, an
item could only ever end when the block did, and a whole list arrived as one item. On the
PMC born-digital corpus one article emitted a single list item for its sixteen bullets,
and list-item recall over the corpus was 0.059.

A line carrying its own marker starts the next item, whatever the spacing says. That is
narrow on purpose: it can only re-split text already inside a list, so it cannot make
anything a list that was not one before.

The awkward real-world shape these are built around is a bullet on a *line of its own*,
with the item's text on the following line -- common in two-column journal typesetting,
and invisible to any rule that looks for a marker at the start of a text line.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import List, ListItem
from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LINE_HEIGHT = 10.0


@pytest.fixture
def converter():
    return PdfToAstConverter(options=PdfOptions())


def _line(top: float, text: str, x0: float = 50.0, x1: float = 300.0) -> dict:
    return {
        "bbox": (x0, top, x1, top + LINE_HEIGHT),
        "dir": (1.0, 0.0),
        "spans": [
            {"text": text, "size": 9.0, "font": "Helvetica", "flags": 0, "bbox": (x0, top, x1, top + LINE_HEIGHT)}
        ],
    }


def _block(*lines: dict) -> dict:
    return {
        "bbox": (
            min(line["bbox"][0] for line in lines),
            min(line["bbox"][1] for line in lines),
            max(line["bbox"][2] for line in lines),
            max(line["bbox"][3] for line in lines),
        ),
        "lines": list(lines),
        "type": 0,
    }


def _items(converter, block) -> list[str]:
    """Run a block through block processing and list grouping, returning item texts."""
    nodes = converter._process_single_block_to_ast(block, [], 0)
    grouped = converter._convert_paragraphs_to_lists(nodes)
    found: list[str] = []

    def visit(node) -> None:
        if isinstance(node, ListItem):
            found.append(" ".join(extract_text(node, joiner="").split()))
            return
        for child in getattr(node, "items", []) or []:
            visit(child)

    for node in grouped:
        if isinstance(node, List):
            for item in node.items:
                visit(item)
    return found


def _paragraphs(converter, block) -> list[str]:
    nodes = converter._process_single_block_to_ast(block, [], 0)
    return [" ".join(extract_text(n, joiner="").split()) for n in nodes if isinstance(n, AstParagraph)]


class TestEachBulletIsItsOwnItem:
    def test_three_inline_bullets_become_three_items(self, converter):
        block = _block(
            _line(100, "• First point about the study"),
            _line(112, "• Second point about the study"),
            _line(124, "• Third point about the study"),
        )

        assert _items(converter, block) == [
            "First point about the study",
            "Second point about the study",
            "Third point about the study",
        ]

    def test_a_bullet_on_its_own_line_still_starts_an_item(self, converter):
        # The shape that motivated this: the bullet glyph is a line of its own, and the
        # item's text is the line after it.
        block = _block(
            _line(100, "•", x1=55),
            _line(102, "To the best of our knowledge, this is the first", x0=64),
            _line(114, "approach to integrate real-time usage patterns.", x0=64),
            _line(126, "•", x1=55),
            _line(128, "Creation of a novel tri-modality dataset.", x0=64),
        )

        assert _items(converter, block) == [
            "To the best of our knowledge, this is the first approach to integrate real-time usage patterns.",
            "Creation of a novel tri-modality dataset.",
        ]

    def test_a_wrapped_item_is_not_split_at_its_own_second_line(self, converter):
        # The reason the gap rule is suspended for lists in the first place.
        block = _block(
            _line(100, "• An item long enough that it wraps onto"),
            _line(112, "a second line of its own."),
            _line(124, "• A second item."),
        )

        assert _items(converter, block) == [
            "An item long enough that it wraps onto a second line of its own.",
            "A second item.",
        ]

    def test_numbered_items_split_too(self, converter):
        block = _block(
            _line(100, "1. Prepare the sample"),
            _line(112, "2. Incubate for one hour"),
            _line(124, "3. Measure the absorbance"),
        )

        assert _items(converter, block) == [
            "Prepare the sample",
            "Incubate for one hour",
            "Measure the absorbance",
        ]


class TestTheSplitDoesNotReachOutsideLists:
    def test_ordinary_paragraphs_are_unaffected(self, converter):
        block = _block(
            _line(100, "The first paragraph of the section."),
            _line(130, "A second paragraph after a wide gap."),
        )

        assert _paragraphs(converter, block) == [
            "The first paragraph of the section.",
            "A second paragraph after a wide gap.",
        ]

    def test_a_marker_line_does_not_split_a_paragraph_that_is_not_a_list(self, converter):
        # The split is conditioned on the paragraph already being a list, so a line of
        # prose that happens to open with a dash cannot start an item. Driven at the
        # accumulator with the gap held below the break threshold, because that isolates
        # the new rule from the pre-existing one: block processing sits below the
        # paragraph merge, so at this layer the gap rule splits nearly every line.
        from all2md.parsers.pdf import _BlockProcessingState

        state = _BlockProcessingState()
        first = _line(100, "Values were compared across the two arms")
        second = _line(110, "- 12 patients in each - using a paired test.")

        converter._accumulate_paragraph_line(first, first["spans"], [], 0.0, 5.0, state, 0, None)
        converter._accumulate_paragraph_line(second, second["spans"], [], 1.0, 5.0, state, 0, None)

        assert state.paragraph_is_list is False
        assert not [n for n in state.nodes if isinstance(n, AstParagraph)]  # nothing flushed: one paragraph

    def test_a_continuation_line_that_is_not_a_marker_stays_in_its_item(self, converter):
        block = _block(
            _line(100, "• Dose was escalated weekly"),
            _line(112, "until the maximum was reached."),
        )

        assert _items(converter, block) == ["Dose was escalated weekly until the maximum was reached."]
