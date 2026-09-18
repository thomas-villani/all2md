#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_split_number_list_marker.py
"""A number marker in its own span is a list marker when the line is indented (#503).

Word prints a numbered list as three spans -- the number, the tab after it, the text --
so the marker reader sees ``Text("1.")``, ``Text(" ")``, ``Text("First item")``. The
reader refuses to cross a node boundary for a number, because a reference list arrives
split exactly the same way (``Text("44.")``, ``Text(" Konema ...")``) and reading across
turned bibliographies into ordered lists renumbered from 1. Nothing on the line separates
the two: a Word-typeset bibliography in the PMC dev corpus has the same three spans in
the same fonts as a Word-typeset list.

What separates them is position. A list is indented from the body text around it; a
reference list hangs at the margin. Over the 128-article dev corpus every split number at
the margin was a reference or numbered heading, none of them more than the 4pt shift of a
right-aligned one-digit label, and every one 10pt or more past the body text was a list
item. So the walk crosses for a number only when the paragraph sits between 10pt and 120pt
past the last paragraph left as prose -- 120pt because a "body paragraph" further left
than that is the other column.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import Heading, List, ListItem, SourceLocation, Text
from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

BODY_X = 72.0
WORD_LIST_X = 108.0


@pytest.fixture
def converter():
    return PdfToAstConverter(options=PdfOptions())


def _para(*pieces: str, x: float | None, top: float = 100.0) -> AstParagraph:
    """A paragraph whose content is one Text node per piece, at a left edge of ``x``."""
    metadata = {"bbox": [x, top, x + 200.0, top + 12.0]} if x is not None else {}
    return AstParagraph(
        content=[Text(content=piece) for piece in pieces],
        source_location=SourceLocation(format="pdf", page=1, metadata=metadata),
    )


def _split_item(number: int, text: str, x: float) -> AstParagraph:
    """A numbered item as Word's PDF export prints it: number, tab, text -- three spans."""
    return _para(f"{number}.", " ", text, x=x)


def _items(converter, nodes) -> list[str]:
    grouped = converter._convert_paragraphs_to_lists(nodes)
    found: list[str] = []
    for node in grouped:
        if isinstance(node, List):
            for item in node.items:
                assert isinstance(item, ListItem)
                found.append(extract_text(item, joiner=""))
    return found


class TestAnIndentedSplitNumberStartsAList:
    def test_words_numbered_list_becomes_one_ordered_list(self, converter):
        # The golden fixture's shape: prose at the margin, three items 36pt in.
        nodes = [
            _para("And here's an ordered list:", x=BODY_X),
            _split_item(1, "First item on ordered list", WORD_LIST_X),
            _split_item(2, "Second item on ordered list", WORD_LIST_X),
            _split_item(3, "Third item on ordered list", WORD_LIST_X),
        ]

        grouped = converter._convert_paragraphs_to_lists(nodes)

        assert [type(node).__name__ for node in grouped] == ["Paragraph", "List"]
        assert grouped[1].ordered is True
        assert _items(converter, nodes) == [
            "First item on ordered list",
            "Second item on ordered list",
            "Third item on ordered list",
        ]

    def test_the_second_item_is_measured_against_the_prose_not_the_first_item(self, converter):
        # Were the reference the nearest paragraph, item 2 would sit 0pt past item 1 and
        # the list would stop after one item.
        nodes = [
            _para("Steps:", x=BODY_X),
            _split_item(1, "Prepare the sample", WORD_LIST_X),
            _split_item(2, "Measure the absorbance", WORD_LIST_X),
        ]

        assert _items(converter, nodes) == ["Prepare the sample", "Measure the absorbance"]

    def test_a_heading_between_the_prose_and_the_list_does_not_hide_the_prose(self, converter):
        # Headings carry no bbox. The prose above the heading is still the body text.
        nodes = [
            _para("Introductory prose.", x=BODY_X),
            Heading(level=2, content=[Text(content="Methods")]),
            _split_item(1, "Prepare the sample", WORD_LIST_X),
            _split_item(2, "Measure the absorbance", WORD_LIST_X),
        ]

        assert _items(converter, nodes) == ["Prepare the sample", "Measure the absorbance"]

    def test_the_marker_and_its_tab_are_both_stripped(self, converter):
        nodes = [_para("Prose.", x=BODY_X), _split_item(1, "First item", WORD_LIST_X)]

        (item,) = _items(converter, nodes)

        assert item == "First item"

    def test_a_modest_latex_indent_is_enough(self, converter):
        # LaTeX-set lists in the corpus sat 12-18pt past the body text.
        nodes = [_para("Prose.", x=BODY_X), _split_item(1, "Item", BODY_X + 12.0)]

        assert _items(converter, nodes) == ["Item"]


class TestASplitNumberAtTheMarginStaysProse:
    """The bibliography shape, which is what the boundary rule exists to protect."""

    def test_reference_entries_at_the_margin_are_not_a_list(self, converter):
        nodes = [
            _para("References", x=BODY_X),
            _split_item(44, "Konema. Nigeria - Youth literacy rate 2015.", BODY_X),
            _split_item(45, "Denny L. Prevention of cervical cancer.", BODY_X),
        ]

        grouped = converter._convert_paragraphs_to_lists(nodes)

        assert not any(isinstance(node, List) for node in grouped)
        assert extract_text(grouped[1], joiner="").startswith("44.")

    def test_a_right_aligned_one_digit_label_is_still_at_the_margin(self, converter):
        # "9." under "10." is shifted right by one digit, 3-4pt at body sizes. That is
        # not an indent.
        nodes = [
            _split_item(10, "Slater, J.C. The self consistent field.", BODY_X),
            _split_item(9, "Pople, J.A. Electron interaction.", BODY_X + 4.0),
        ]

        assert _items(converter, nodes) == []

    def test_the_other_column_is_not_the_body_text(self, converter):
        # A reference list opening at the top of the right column sits ~240pt past the
        # last paragraph of the left column. That is a column, not an indent.
        nodes = [
            _para("Last paragraph of the left column.", x=BODY_X),
            _split_item(1, "First reference.", BODY_X + 240.0),
            _split_item(2, "Second reference.", BODY_X + 240.0),
        ]

        assert _items(converter, nodes) == []

    def test_with_no_prose_yet_on_the_page_a_split_number_stays_prose(self, converter):
        # Unknown is answered conservatively, as it was before.
        nodes = [
            _split_item(1, "First entry.", WORD_LIST_X),
            _split_item(2, "Second entry.", WORD_LIST_X),
        ]

        assert _items(converter, nodes) == []

    def test_a_paragraph_without_a_bbox_stays_prose(self, converter):
        nodes = [_para("Prose.", x=BODY_X), _para("1.", " ", "No geometry here.", x=None)]

        assert _items(converter, nodes) == []

    def test_a_year_opening_a_wrapped_reference_line_is_not_a_marker(self, converter):
        # The one indented split number in the corpus that was not a list item: the
        # hanging-indent continuation of a reference, opening with its year.
        nodes = [
            _para("Prose.", x=BODY_X),
            _para("2. Smith AB. Title of the paper. Journal", x=BODY_X),
            _para("2020.", " ", "MMWR Morb Mortal Wkly Rep 2020;69(18):551-6.", x=BODY_X + 13.0),
        ]

        # The reference itself is a complete-in-one-node marker and was a list item before
        # this change; the point is that its wrapped line does not become a second one.
        assert _items(converter, nodes) == ["Smith AB. Title of the paper. Journal"]


class TestAListKeepsItsPrintedNumbers:
    """The harm in mistaking a reference for a list item was renumbering, so carry the number.

    In a double-spaced manuscript (PMC8500015) every wrapped line of a reference is its
    own paragraph, and the first reference on each page sits 18pt past the watermark
    the page opens with. It became a one-item list, and ``8. Mitchell KM`` printed as
    ``1. Mitchell KM``. With the printed number carried into ``List.start`` the same
    mistake prints ``8. Mitchell KM``, which is what the page says.
    """

    def test_a_list_opening_at_eight_starts_at_eight(self, converter):
        nodes = [_para("Prose.", x=BODY_X), _split_item(8, "Mitchell KM, Dimitrov D.", WORD_LIST_X)]

        (lst,) = [node for node in converter._convert_paragraphs_to_lists(nodes) if isinstance(node, List)]

        assert lst.ordered is True
        assert lst.start == 8

    def test_a_list_opening_at_one_keeps_the_default(self, converter):
        nodes = [_para("Prose.", x=BODY_X), _split_item(1, "First", WORD_LIST_X), _split_item(2, "Second", WORD_LIST_X)]

        (lst,) = [node for node in converter._convert_paragraphs_to_lists(nodes) if isinstance(node, List)]

        assert lst.start == 1

    def test_a_marker_complete_in_one_node_carries_its_number_too(self, converter):
        # The same list continued after a figure: "4." is printed, so "4." is rendered.
        nodes = [_para("4. Fourth step", x=BODY_X), _para("5. Fifth step", x=BODY_X)]

        (lst,) = [node for node in converter._convert_paragraphs_to_lists(nodes) if isinstance(node, List)]

        assert lst.start == 4
        assert _items(converter, nodes) == ["Fourth step", "Fifth step"]

    def test_a_nested_ordered_list_carries_its_own_number(self, converter):
        nodes = [
            _para("Prose.", x=BODY_X),
            _para("- Parent bullet", x=WORD_LIST_X),
            _para("3. Nested third", x=WORD_LIST_X + 36.0),
        ]

        (outer,) = [node for node in converter._convert_paragraphs_to_lists(nodes) if isinstance(node, List)]
        (nested,) = [child for child in outer.items[0].children if isinstance(child, List)]

        assert outer.ordered is False
        assert nested.ordered is True
        assert nested.start == 3


class TestTheRestOfTheReaderIsUnchanged:
    def test_a_marker_complete_in_one_node_needs_no_indent(self, converter):
        # Exactly what was accepted before: the whole marker in one span.
        nodes = [_para("1. Prepare the sample", x=BODY_X), _para("2. Measure the absorbance", x=BODY_X)]

        assert _items(converter, nodes) == ["Prepare the sample", "Measure the absorbance"]

    def test_a_bullet_in_its_own_span_needs_no_indent_either(self, converter):
        nodes = [_para("-", " ", "Konema. Nigeria - Youth literacy rate", x=BODY_X)]

        assert _items(converter, nodes) == ["Konema. Nigeria - Youth literacy rate"]

    def test_the_conservative_reader_is_the_default(self, converter):
        para = _split_item(1, "First item", WORD_LIST_X)

        assert converter._detect_list_marker(para) == (False, None)
        assert converter._detect_list_marker(para, split_number=True) == (True, "ordered")
