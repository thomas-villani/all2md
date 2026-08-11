#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_wrapped_headings.py
"""A heading too long for one printed line is still one heading.

Issue #295. A PDF has no notion of a heading that wraps -- it has two lines of type, and
each reaches the emitter separately, so an article title set on three lines came out as
three sibling ``#`` headings. The join asks whether this line sits directly under the
heading just emitted, at the same level, with nothing between them.

The interesting tests are the ones that must *not* join: two headings of the same level
can legitimately follow one another, and the only thing separating that case from a wrap
is the space above a new section, so these pin the boundary from both sides.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import Heading, Text
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import HEADING_WRAP_GAP_RATIO, PdfToAstConverter, _BlockProcessingState

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LINE_HEIGHT = 12.0


@pytest.fixture
def converter():
    return PdfToAstConverter(options=PdfOptions())


def _bbox(bottom: float, x0: float = 50.0, x1: float = 300.0) -> tuple[float, float, float, float]:
    return (x0, bottom - LINE_HEIGHT, x1, bottom)


def _emit(converter, state, text: str, *, level: int = 2, bottom: float, bbox=None) -> None:
    converter._emit_heading(state, level, text, [Text(content=text)], 0, bbox or _bbox(bottom))


def _headings(state) -> list[str]:
    # joiner="" because the separator between the two halves has to come from the join
    # itself. `extract_text`'s default inserts a space between every sibling node, which
    # would make a heading that lost its space look correct here.
    return [extract_text(n, joiner="") for n in state.nodes if isinstance(n, Heading)]


class TestAWrappedHeadingBecomesOneHeading:
    def test_two_lines_a_line_apart_join(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "Effects of long-term exposure on", bottom=100)
        _emit(converter, state, "cardiovascular outcomes", bottom=100 + LINE_HEIGHT)

        assert _headings(state) == ["Effects of long-term exposure on cardiovascular outcomes"]

    def test_three_lines_join_into_one(self, converter):
        state = _BlockProcessingState()

        for index, text in enumerate(["A very long", "article title set", "across three lines"]):
            _emit(converter, state, text, level=1, bottom=100 + index * LINE_HEIGHT)

        assert _headings(state) == ["A very long article title set across three lines"]

    def test_the_joined_heading_keeps_the_first_line_s_level(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "First half", level=3, bottom=100)
        _emit(converter, state, "second half", level=3, bottom=100 + LINE_HEIGHT)

        headings = [n for n in state.nodes if isinstance(n, Heading)]
        assert len(headings) == 1
        assert headings[0].level == 3

    def test_a_gap_at_the_limit_still_joins(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "First half", bottom=100)
        _emit(converter, state, "second half", bottom=100 + LINE_HEIGHT * HEADING_WRAP_GAP_RATIO)

        assert _headings(state) == ["First half second half"]


class TestAdjacentHeadingsStayApart:
    def test_a_wider_gap_starts_a_new_heading(self, converter):
        # The space above a new section, not the leading inside one heading.
        state = _BlockProcessingState()

        _emit(converter, state, "Methods", bottom=100)
        _emit(converter, state, "Results", bottom=100 + LINE_HEIGHT * (HEADING_WRAP_GAP_RATIO + 0.5))

        assert _headings(state) == ["Methods", "Results"]

    def test_a_different_level_starts_a_new_heading(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "Results", level=2, bottom=100)
        _emit(converter, state, "Gene expression", level=3, bottom=100 + LINE_HEIGHT)

        assert _headings(state) == ["Results", "Gene expression"]

    def test_a_numbered_second_line_starts_a_new_heading(self, converter):
        # Tightly set numbered sections are common, and the number announces a new one
        # however little space is above it.
        state = _BlockProcessingState()

        _emit(converter, state, "1. Introduction", bottom=100)
        _emit(converter, state, "2. Methods", bottom=100 + LINE_HEIGHT)

        assert _headings(state) == ["1. Introduction", "2. Methods"]

    def test_a_paragraph_between_two_headings_stops_the_join(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "Methods", bottom=100)
        state.paragraph_content = [Text(content="Body text.")]
        converter._flush_state_paragraph(state, 0)
        _emit(converter, state, "Results", bottom=100 + LINE_HEIGHT)

        assert _headings(state) == ["Methods", "Results"]

    def test_a_line_above_the_previous_one_does_not_join(self, converter):
        # A second column read after the first: same level, small distance, wrong direction.
        state = _BlockProcessingState()

        _emit(converter, state, "Discussion", bottom=400)
        _emit(converter, state, "Conclusion", bottom=400 - LINE_HEIGHT)

        assert _headings(state) == ["Discussion", "Conclusion"]

    def test_headings_in_different_blocks_do_not_join(self, converter):
        # State is per block, so this is really a guard against the bookkeeping leaking.
        first, second = _BlockProcessingState(), _BlockProcessingState()

        _emit(converter, first, "Methods", bottom=100)
        _emit(converter, second, "Results", bottom=100 + LINE_HEIGHT)

        assert _headings(first) == ["Methods"]
        assert _headings(second) == ["Results"]


class TestTheJoinNeedsGeometry:
    def test_without_a_bbox_nothing_joins(self, converter):
        # Callers that cannot supply a line box keep the old behaviour rather than
        # joining on level alone.
        state = _BlockProcessingState()

        converter._emit_heading(state, 2, "First half", [Text(content="First half")], 0)
        converter._emit_heading(state, 2, "second half", [Text(content="second half")], 0)

        assert _headings(state) == ["First half", "second half"]

    def test_a_degenerate_bbox_does_not_join(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "First half", bottom=100, bbox=(50.0, 100.0, 300.0, 100.0))
        _emit(converter, state, "second half", bottom=100, bbox=(50.0, 100.0, 300.0, 100.0))

        assert _headings(state) == ["First half", "second half"]

    def test_a_numbering_prefix_line_still_merges_into_the_next_heading(self, converter):
        # The pre-existing prefix buffer has to keep working: "II." on its own line is
        # absorbed by the heading below it rather than being treated as a wrap anchor.
        state = _BlockProcessingState()

        _emit(converter, state, "II.", bottom=100)
        _emit(converter, state, "Background", bottom=100 + LINE_HEIGHT)

        assert _headings(state) == ["II. Background"]


class TestWrappedHeadingOnAPage:
    """End to end, so the geometry really comes from a rendered page."""

    @staticmethod
    def _page_with_a_wrapped_title(tmp_path):
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=300, height=400)
        writer = fitz.TextWriter(page.rect)
        font = fitz.Font("helv")
        # A two-line title at a size the font heuristic promotes, over body text that it
        # does not.
        writer.append((40, 60), "Long-term outcomes of an", font=font, fontsize=20)
        writer.append((40, 84), "intervention in older adults", font=font, fontsize=20)
        for idx in range(12):
            writer.append((40, 120 + idx * 12), f"body line {idx} of the article", font=font, fontsize=9)
        writer.write_text(page)
        path = tmp_path / "wrapped.pdf"
        doc.save(str(path))
        doc.close()
        return str(path)

    def test_the_title_is_one_heading(self, tmp_path):
        import fitz

        from all2md.ast.transforms import NodeCollector
        from all2md.parsers._pdf_headers import IdentifyHeaders

        path = self._page_with_a_wrapped_title(tmp_path)
        doc = fitz.open(path)
        page = doc[0]

        options = PdfOptions()
        converter = PdfToAstConverter(options=options)
        converter._hdr_identifier = IdentifyHeaders(doc, options=options)
        nodes = converter._process_page_to_ast(page, 0, "doc", lambda a, b: (a, 0), doc.page_count)
        doc.close()

        collector = NodeCollector(lambda n: isinstance(n, Heading))
        for node in nodes:
            node.accept(collector)

        assert [extract_text(h, joiner="").strip() for h in collector.collected] == [
            "Long-term outcomes of an intervention in older adults"
        ]
