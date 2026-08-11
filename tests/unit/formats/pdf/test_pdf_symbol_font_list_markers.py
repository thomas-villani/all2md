#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_symbol_font_list_markers.py
"""A list marker is whatever the line opens with, not whatever the first Text node holds.

Three places asked "does this start with a marker?" and each answered by finding the first
top-level ``Text`` node. That gets the question wrong in both directions:

* A bullet set in a symbol font carries that font's flags, so it arrives wrapped -- italic
  flags make ``Emphasis(Text("-"))`` -- and the line has no top-level ``Text`` at all. It
  read as empty and never started a list. On the PMC corpus one article's sixteen bullets
  came out as fourteen plain paragraphs each beginning with a literal "- ".
* A marker and the space that disambiguates it are often *separate spans*. The rule that
  the letter "o" must be followed by a space (so "office" is not a bullet) could therefore
  never fire, because the space was in the next node. Word's second-level Courier "o"
  bullets escaped list detection entirely and landed as loose paragraphs.
* Reading past the first node to find a ``Text`` answers for the *middle* of the line. A
  citation opening with a styled journal name -- ``Nature 12. 45-67`` -- reported an
  ordered marker and became a list item.

Reading the raw spans instead does not work either, and that is worth stating because it
looks like the obvious fix: ``_process_text_spans_to_inline`` rewrites four bullet glyphs
to "-", and three of those four are not markers in their printed form. The conversion is
what makes a symbol-font bullet recognisable, so detection has to run after it.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import Emphasis, Link, List, ListItem, Strong, Text
from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LINE_HEIGHT = 10.0

ITALIC, MONO, BOLD = 2, 8, 16


@pytest.fixture
def converter():
    return PdfToAstConverter(options=PdfOptions())


def _spans(*parts: tuple[str, int], x0: float = 50.0, top: float = 100.0) -> list[dict]:
    """Build the spans of one line from (text, font-flags) pairs."""
    spans = []
    for text, flags in parts:
        width = max(len(text) * 5.0, 3.0)
        spans.append(
            {
                "text": text,
                "size": 9.0,
                "font": "Helvetica",
                "flags": flags,
                "bbox": (x0, top, x0 + width, top + LINE_HEIGHT),
            }
        )
        x0 += width
    return spans


def _line(top: float, *parts: tuple[str, int]) -> dict:
    spans = _spans(*parts, top=top)
    return {
        "bbox": (spans[0]["bbox"][0], top, spans[-1]["bbox"][2], top + LINE_HEIGHT),
        "dir": (1.0, 0.0),
        "spans": spans,
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


class TestAMarkerPrintedInASymbolFontStartsAList:
    def test_an_italic_flagged_bullet_is_still_a_bullet(self, converter):
        # CMSY10 and friends mark their bullet italic, so it converts to Emphasis(Text("-"))
        # and the line has no top-level Text node to find.
        block = _block(
            _line(100, ("•", ITALIC), (" ", 0), ("First point about the study", 0)),
            _line(112, ("•", ITALIC), (" ", 0), ("Second point about the study", 0)),
        )

        assert _items(converter, block) == [
            "First point about the study",
            "Second point about the study",
        ]

    def test_a_numbered_marker_inside_a_wrapper_is_still_a_marker(self, converter):
        # Wrapped, but complete within the one span -- which is the condition below.
        block = _block(
            _line(100, ("1. Prepare the sample", BOLD)),
            _line(112, ("2. Measure the absorbance", BOLD)),
        )

        assert _items(converter, block) == ["Prepare the sample", "Measure the absorbance"]

    def test_a_marker_inside_a_link_is_still_a_marker(self, converter):
        para = AstParagraph(
            content=[Link(url="https://example.com", content=[Text(content="- ")]), Text(content="Item")]
        )

        assert converter._detect_list_marker(para) == (True, "unordered")


class TestAMarkerSplitAcrossSpans:
    def test_the_letter_o_bullet_finds_the_space_in_the_next_span(self, converter):
        # Word sets its second-level bullet as a Courier "o", and the space after it is a
        # separate span in a different font. "o" only counts as a marker when a space
        # follows, so a reader that stopped at the first node could never accept one.
        block = _block(
            _line(100, ("o", MONO), (" ", 0), ("Second level 1", 0)),
            _line(112, ("o", MONO), (" ", 0), ("Second level 2", 0)),
        )

        assert _items(converter, block) == ["Second level 1", "Second level 2"]

    def test_the_letter_o_still_needs_a_space_after_it(self, converter):
        # The disambiguation the rule exists for: "office" is not a bullet. Now that the
        # reader crosses spans, the word being split across two of them must not create one.
        block = _block(_line(100, ("off", 0), ("ice hours are posted weekly", 0)))

        assert _items(converter, block) == []

    def test_the_markers_own_trailing_space_does_not_leak_into_the_item(self, converter):
        # The bullet is its own span, so the space after it lived in the next node and
        # survived stripping -- every item used to begin with a stray leading space.
        block = _block(_line(100, ("•", 0), (" ", 0), ("First item", 0)))

        nodes = converter._process_single_block_to_ast(block, [], 0)
        grouped = converter._convert_paragraphs_to_lists(nodes)
        item = next(n for n in grouped if isinstance(n, List)).items[0]

        assert extract_text(item, joiner="") == "First item"


class TestANumberedMarkerMustBeCompleteWithinOneSpan:
    """The one place the walk deliberately stops short, and the reason it has to.

    A reference number is typeset exactly like a list marker -- ``Text("44.")`` then
    ``Text(" Konema, Nigeria ...")`` -- and nothing in the PDF says which is which. Reading
    across that boundary turned a 60-entry bibliography into an ordered list, and because
    nothing carries the start number through, the renderer printed it from 1: reference 44
    came out as item 1, so no citation in the body could be matched to its reference.
    """

    def test_a_reference_number_in_its_own_span_does_not_start_a_list(self, converter):
        block = _block(
            _line(100, ("44.", 0), (" Konema. Nigeria - Youth literacy rate 2015. Available from", 0)),
            _line(112, ("45.", 0), (" Denny L. Prevention of cervical cancer. Reprod Health Matters", 0)),
        )

        assert _items(converter, block) == []

    def test_the_reference_keeps_its_printed_number(self, converter):
        block = _block(_line(100, ("44.", 0), (" Konema. Nigeria - Youth literacy rate 2015", 0)))

        nodes = converter._process_single_block_to_ast(block, [], 0)
        grouped = converter._convert_paragraphs_to_lists(nodes)

        assert "44." in extract_text(grouped[0], joiner="")

    def test_a_bullet_in_its_own_span_still_reaches_across_for_its_space(self, converter):
        # The asymmetry is the point: a bullet may look ahead one node, a number may not.
        block = _block(_line(100, ("•", 0), (" ", 0), ("Konema. Nigeria - Youth literacy rate", 0)))

        assert _items(converter, block) == ["Konema. Nigeria - Youth literacy rate"]


class TestTheReaderDoesNotAnswerForTheMiddleOfTheLine:
    @pytest.mark.parametrize(
        "opening",
        [
            pytest.param(Emphasis(content=[Text(content="Nature ")]), id="styled-journal-name"),
            pytest.param(Link(url="https://doi.org/x", content=[Text(content="Nature ")]), id="linked-journal-name"),
            pytest.param(Strong(content=[Text(content="Nature ")]), id="bold-journal-name"),
        ],
    )
    def test_a_citation_is_not_an_ordered_list_item(self, converter, opening):
        # The first top-level Text node is "12. 45-67, 2019", which reads as a numbered
        # marker only because the reader skipped the journal name in front of it.
        para = AstParagraph(content=[opening, Text(content="12. 45-67, 2019")])

        assert converter._detect_list_marker(para) == (False, None)
        assert converter._strip_list_marker(para) == para.content

    def test_a_dash_after_a_bold_lead_in_is_not_a_bullet(self, converter):
        para = AstParagraph(content=[Strong(content=[Text(content="Note ")]), Text(content="- see appendix")])

        assert converter._detect_list_marker(para) == (False, None)

    def test_a_line_opening_with_inline_code_is_not_a_list_item(self, converter):
        # Code stops the walk rather than being read through, so the prose after it cannot
        # supply a marker. (A one-character "-" span is exempt from monospace treatment
        # precisely so that a bullet in a Courier list survives as a bullet, which is why
        # this needs a multi-character run to be inline code at all.)
        block = _block(_line(100, ("--flag", MONO), (" enables the check", 0)))

        assert _items(converter, block) == []


class TestTheMarkerIsRemovedFromWhereverItSits:
    def test_a_wrapper_emptied_by_stripping_is_dropped(self, converter):
        para = AstParagraph(content=[Emphasis(content=[Text(content="-")]), Text(content=" Item body")])

        stripped = converter._strip_list_marker(para)

        assert extract_text(stripped, joiner="") == "Item body"
        assert not any(isinstance(node, Emphasis) for node in stripped)

    def test_a_wrapper_that_survives_keeps_its_formatting(self, converter):
        # Only the marker comes off; the bold run it shared a node with stays bold.
        para = AstParagraph(content=[Strong(content=[Text(content="- Background")]), Text(content=" of the study")])

        stripped = converter._strip_list_marker(para)

        assert extract_text(stripped, joiner="") == "Background of the study"
        assert isinstance(stripped[0], Strong)

    def test_a_marker_straddling_two_nodes_is_fully_removed(self, converter):
        # Bullet in the first node, the space that follows it in the second.
        para = AstParagraph(content=[Emphasis(content=[Text(content="-")]), Text(content=" Item body")])

        assert extract_text(converter._strip_list_marker(para), joiner="").startswith("Item")
