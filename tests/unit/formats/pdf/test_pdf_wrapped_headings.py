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

    def test_headings_in_different_blocks_do_not_join_as_they_are_read(self, converter):
        # State is per block, so this is really a guard against the bookkeeping leaking;
        # a wrap across blocks is joined afterwards (TestAWrapAcrossBlocks).
        first, second = _BlockProcessingState(), _BlockProcessingState()

        _emit(converter, first, "Methods", bottom=100)
        _emit(converter, second, "Results", bottom=100 + LINE_HEIGHT)

        assert _headings(first) == ["Methods"]
        assert _headings(second) == ["Results"]


class TestASubsectionUnderItsSectionStaysItsOwnHeading:
    """The wrap-width test (#400).

    A line only wraps because it filled its measure, so a "continuation" that
    extends past the line above it is a different heading. Before this test a
    section title with its subsection printed directly beneath -- `Methods` /
    `Study design` -- fused into one heading, and both JATS titles went
    missing; measured at ~30% of the heading residual on the PMC corpus.
    """

    def test_a_wider_second_line_is_a_new_heading(self, converter):
        state = _BlockProcessingState()

        _emit(converter, state, "Methods", bottom=100, bbox=_bbox(100, x1=95.0))
        _emit(converter, state, "Study design", bottom=100 + LINE_HEIGHT, bbox=_bbox(100 + LINE_HEIGHT, x1=140.0))

        assert _headings(state) == ["Methods", "Study design"]

    def test_a_first_line_nearly_at_the_measure_still_wraps(self, converter):
        # Ragged-right wraps rarely end exactly at the measure; 0.96 fill is a wrap.
        state = _BlockProcessingState()

        _emit(converter, state, "Effects of long-term exposure on", bottom=100, bbox=_bbox(100, x1=290.0))
        _emit(
            converter,
            state,
            "cardiovascular outcomes",
            bottom=100 + LINE_HEIGHT,
            bbox=_bbox(100 + LINE_HEIGHT, x1=300.0),
        )

        assert _headings(state) == ["Effects of long-term exposure on cardiovascular outcomes"]

    def test_the_fill_boundary_separates(self, converter):
        # Just under HEADING_WRAP_MIN_FILL: (247 - 50) / (300 - 50) = 0.788.
        state = _BlockProcessingState()

        _emit(converter, state, "Results", bottom=100, bbox=_bbox(100, x1=247.0))
        _emit(
            converter,
            state,
            "Dynamic regulation of miRNAs",
            bottom=100 + LINE_HEIGHT,
            bbox=_bbox(100 + LINE_HEIGHT, x1=300.0),
        )

        assert _headings(state) == ["Results", "Dynamic regulation of miRNAs"]

    def test_a_wider_first_line_still_merges(self, converter):
        # The known residual: when the section title is the wider line
        # (`Methods and Design` over `Study design`), width cannot separate the
        # pair and the merge stands. Pinned so a future fix has to change this
        # test deliberately rather than by side effect.
        state = _BlockProcessingState()

        _emit(converter, state, "Methods and Design", bottom=100, bbox=_bbox(100, x1=200.0))
        _emit(converter, state, "Study design", bottom=100 + LINE_HEIGHT, bbox=_bbox(100 + LINE_HEIGHT, x1=150.0))

        assert _headings(state) == ["Methods and Design Study design"]


def _across_blocks(converter, lines) -> list[str]:
    """Emit each (text, bottom, level, bbox) line in a block of its own, then join the page."""
    converter._heading_lines.clear()
    nodes = []
    for text, bottom, level, bbox in lines:
        state = _BlockProcessingState()
        _emit(converter, state, text, level=level, bottom=bottom, bbox=bbox)
        nodes.extend(state.nodes)
    return [extract_text(n, joiner="") for n in converter._join_wrapped_headings(nodes) if isinstance(n, Heading)]


class TestAWrapAcrossBlocks:
    """Word writes each line of a centered title as a PyMuPDF block of its own.

    The join made as lines are read never saw the second line, so a two-line title read
    as two headings: 331 such pairs in 93 documents of the Word tier.
    """

    def test_a_title_split_over_two_blocks_is_one_heading(self, converter):
        lines = [
            ("Childhood: The Roles of Cognitive Development and", 100, 1, _bbox(100, x0=107.0, x1=512.0)),
            ("Educational and Social Environmental Variables", 100 + LINE_HEIGHT, 1, _bbox(112, x0=124.0, x1=495.0)),
        ]

        assert _across_blocks(converter, lines) == [
            "Childhood: The Roles of Cognitive Development and Educational and Social Environmental Variables"
        ]

    def test_three_blocks_join_into_one(self, converter):
        lines = [(text, 100 + i * LINE_HEIGHT, 1, None) for i, text in enumerate(["A very", "long", "title"])]

        assert _across_blocks(converter, lines) == ["A very long title"]

    def test_the_tests_made_as_lines_are_read_still_apply(self, converter):
        lines = [
            ("Methods", 100, 2, None),
            ("Results", 100 + LINE_HEIGHT * (HEADING_WRAP_GAP_RATIO + 0.5), 2, None),
            ("1. Introduction", 200, 2, None),
            ("2. Methods", 200 + LINE_HEIGHT, 2, None),
            ("Results", 300, 2, None),
            ("Gene expression", 300 + LINE_HEIGHT, 3, None),
        ]

        assert _across_blocks(converter, lines) == [
            "Methods",
            "Results",
            "1. Introduction",
            "2. Methods",
            "Results",
            "Gene expression",
        ]

    def test_a_paragraph_between_stops_the_join(self, converter):
        converter._heading_lines.clear()
        first, second, third = _BlockProcessingState(), _BlockProcessingState(), _BlockProcessingState()
        _emit(converter, first, "Methods", bottom=100)
        second.paragraph_content = [Text(content="Body text.")]
        converter._flush_state_paragraph(second, 0)
        _emit(converter, third, "Results", bottom=100 + LINE_HEIGHT)

        joined = converter._join_wrapped_headings([*first.nodes, *second.nodes, *third.nodes])

        assert [extract_text(n, joiner="") for n in joined if isinstance(n, Heading)] == ["Methods", "Results"]

    def test_two_bold_lines_join_into_one_bold_run(self, converter):
        from all2md.ast.nodes import Strong

        converter._heading_lines.clear()
        nodes = []
        for index, text in enumerate(["Development of Reading", "in Early Childhood"]):
            state = _BlockProcessingState()
            converter._emit_heading(state, 1, text, [Strong(content=[Text(content=text)])], 0, _bbox(100 + index * 12))
            nodes.extend(state.nodes)

        (heading,) = converter._join_wrapped_headings(nodes)

        assert len(heading.content) == 1
        assert isinstance(heading.content[0], Strong)
        assert extract_text(heading, joiner="") == "Development of Reading in Early Childhood"


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
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=400)
        writer = pymupdf.TextWriter(page.rect)
        font = pymupdf.Font("helv")
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
        import pymupdf

        from all2md.ast.transforms import NodeCollector
        from all2md.parsers._pdf_headers import IdentifyHeaders

        path = self._page_with_a_wrapped_title(tmp_path)
        doc = pymupdf.open(path)
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
