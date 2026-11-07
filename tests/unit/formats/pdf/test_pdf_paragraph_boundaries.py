#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_paragraph_boundaries.py
"""Where a PDF paragraph ends.

Two defects the PDF to Word lane (`benchmarks/pdfword`) found on Word's own PDFs:

- **Prose split after an ordinary line.** The gap between two lines of a block was measured
  bottom to bottom, a whole line pitch, against half a line height. Every line ended a
  paragraph and `_merge_adjacent_paragraphs` glued them back below its 5pt bar, so any line
  followed by 5.1pt of leading instead of 4.9pt broke its paragraph in two.
- **Numbered clauses run together.** Word sets clause 1.2 2.3pt under the end of 1.1, the
  leading of a wrapped line, so only the hanging indent tells them apart: the number at the
  margin and the text at a tab stop past it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter, _caption_comparison_key, _hanging_marker_lines

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

SIZE = 11.0
HEIGHT = 12.2
CORPUS = Path(__file__).parents[4] / "benchmarks" / "pdfword" / "corpus"


@pytest.fixture
def converter():
    return PdfToAstConverter(options=PdfOptions())


def _span(x0: float, x1: float, top: float, text: str, size: float = SIZE) -> dict:
    return {"text": text, "size": size, "font": "Calibri", "flags": 0, "bbox": (x0, top, x1, top + HEIGHT)}


def _line(top: float, *spans: tuple[float, float, str]) -> dict:
    built = [_span(x0, x1, top, text) for x0, x1, text in spans]
    return {
        "bbox": (built[0]["bbox"][0], top, built[-1]["bbox"][2], top + HEIGHT),
        "dir": (1.0, 0.0),
        "spans": built,
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


def _paragraphs(converter, *blocks: dict) -> list[str]:
    """Block processing, then the paragraph merge, as the page pipeline runs them."""
    nodes = [node for block in blocks for node in converter._process_single_block_to_ast(block, [], 0)]
    merged = converter._merge_adjacent_paragraphs(nodes)
    return [" ".join(extract_text(node).split()) for node in merged if isinstance(node, AstParagraph)]


class TestTheLineGapIsWhiteSpace:
    def test_a_paragraph_holds_together_whatever_its_leading(self, converter):
        # plain-prose.pdf: 4.9pt between lines 1 and 2, 5.1pt between lines 2 and 3. The second
        # gap used to clear the merge's 5pt bar and split the paragraph after "the ground".
        block = _block(
            _line(158.9, (72.0, 511.7, "Work on the canal began in the spring of 1794, when a company")),
            _line(158.9 + HEIGHT + 4.9, (72.0, 530.9, "raised enough money. Progress was slow because the ground")),
            _line(158.9 + 2 * HEIGHT + 4.9 + 5.1, (72.0, 261.2, "was wet and the money ran out twice.")),
        )

        assert len(_paragraphs(converter, block)) == 1

    def test_a_wide_gap_inside_a_block_still_ends_a_paragraph(self, converter):
        block = _block(
            _line(100.0, (72.0, 400.0, "The first paragraph of the section.")),
            _line(130.0, (72.0, 400.0, "A second paragraph after a wide gap.")),
        )

        assert _paragraphs(converter, block) == [
            "The first paragraph of the section.",
            "A second paragraph after a wide gap.",
        ]


class TestHangingMarkers:
    def test_numbered_clauses_set_on_a_hanging_indent_stay_apart(self, converter):
        # msa-auto-numbered.pdf: each clause number is a line of its own at the margin, and
        # its text is the next line, on the same baseline, at the 108pt tab stop.
        block = _block(
            _line(227.4, (72.0, 88.9, "1.1 ")),
            _line(227.6, (108.0, 514.6, "In this Agreement, Services means the hosting described in")),
            _line(242.2, (108.0, 408.2, "Schedule 1, and Fees means the amounts payable.")),
            _line(256.7, (72.0, 88.9, "1.2 ")),
            _line(256.9, (108.0, 536.3, "Confidential Information means all non-public information,")),
            _line(271.6, (108.0, 155.4, "including:")),
            _line(286.1, (108.0, 123.3, "(a) ")),
            _line(286.3, (144.0, 332.0, "business plans, pricing and customer lists;")),
        )

        assert _paragraphs(converter, block) == [
            "1.1 In this Agreement, Services means the hosting described in Schedule 1, and Fees means the "
            "amounts payable.",
            "1.2 Confidential Information means all non-public information, including:",
            "(a) business plans, pricing and customer lists;",
        ]

    def test_a_marker_span_followed_by_a_tab_starts_a_paragraph(self, converter):
        # memo-findings.pdf: "1." ends at 98.4, a space span runs to 101.5, the text starts at
        # 108 -- 6.5pt past the space, where a word space would be about 2.8pt.
        block = _block(
            _line(560.0, (72.0, 500.0, "We recommend that management act on these findings")),
            _line(574.8, (72.0, 200.0, "before the year end:")),
            _line(589.6, (90.0, 98.4, "1."), (98.4, 101.5, " "), (108.0, 421.7, "Merge duplicate vendor records")),
            _line(604.4, (90.0, 98.4, "2."), (98.4, 101.5, " "), (108.0, 412.7, "Enforce approval limits")),
        )

        paragraphs = _paragraphs(converter, block)

        assert paragraphs[0] == "We recommend that management act on these findings before the year end:"
        assert [p.split()[0] for p in paragraphs[1:]] == ["1.", "2."]

    def test_a_dash_set_with_a_word_space_is_prose(self, converter):
        block = _block(
            _line(100.0, (72.0, 500.0, "Values were compared across the two arms")),
            _line(114.6, (72.0, 400.0, "- 12 patients in each - using a paired test.")),
        )

        assert len(_paragraphs(converter, block)) == 1


class TestWhatIsNotAHangingMarker:
    def test_a_row_of_numbers_on_one_baseline(self):
        # A table row or a chart axis: numbers side by side, as a clause number sits by its text.
        lines = [_line(545.0, (153.1, 171.3, "2023")), _line(545.0, (285.4, 303.7, "2024"))]

        assert _hanging_marker_lines(lines) == set()

    def test_a_bare_integer_beside_text(self):
        lines = [_line(497.2, (190.5, 199.0, "4 ")), _line(497.2, (240.0, 300.0, "Widgets"))]

        assert _hanging_marker_lines(lines) == set()

    def test_an_equation_number_at_the_right_margin(self):
        lines = [_line(300.0, (120.0, 400.0, "E = mc")), _line(300.0, (520.0, 540.0, "(12)"))]

        assert _hanging_marker_lines(lines) == set()

    def test_a_footnote_number_run_into_its_text(self):
        line = {
            "bbox": (72.0, 758.3, 325.7, 770.0),
            "dir": (1.0, 0.0),
            "spans": [
                _span(72.0, 75.6, 758.3, "1", 6.5),
                _span(75.6, 325.7, 758.3, " Our scope excluded Dublin.", 10.0),
            ],
        }

        assert _hanging_marker_lines([line]) == set()

    def test_a_marker_on_a_line_of_its_own_counts(self):
        lines = [_line(227.4, (72.0, 88.9, "1.1 ")), _line(227.6, (108.0, 500.0, "In this Agreement"))]

        assert _hanging_marker_lines(lines) == {0}


class TestCaptionsNowArriveWhole:
    """Caption de-duplication was built on the old split, which handed it one line at a time.

    Every line it was handed sat inside a caption cut short by its search band and was
    dropped, and the lines past the band were stranded in the body. A whole paragraph is now
    handed over instead, which no cut-short caption contains, so the PMC dev corpus printed
    123 words of one caption twice until these were added.
    """

    CUT = "Fig 2. User interface of the XYTEventDetector. The line above the main window"
    WHOLE = CUT + " provides the current frame number and the number of LCRs found."

    def test_a_paragraph_opening_with_a_cut_caption_becomes_the_caption(self):
        from all2md.ast.nodes import Figure

        figure = Figure(children=[], caption=self.CUT)
        plan = [{"images": [], "caption": self.CUT}]
        key = _caption_comparison_key(self.WHOLE)

        assert PdfToAstConverter._complete_cut_caption(key, self.WHOLE, plan, [figure]) is True
        assert figure.caption == self.WHOLE
        assert plan[0]["caption"] == self.WHOLE

    def test_prose_that_merely_mentions_the_figure_is_left_alone(self):

        text = "As Fig 2 shows, the detector reports the frame number."
        plan = [{"images": [], "caption": self.CUT}]

        assert PdfToAstConverter._complete_cut_caption(_caption_comparison_key(text), text, plan, []) is False
        assert plan[0]["caption"] == self.CUT

    def test_a_paragraph_opening_partway_into_a_caption_trims_the_caption(self):
        from all2md.ast.nodes import Figure

        # PMC10000015.1: a title line, then a paragraph the band cut partway through. The
        # body holds that paragraph whole, opening on the caption's last words. The caption
        # gives those words back; the paragraph keeps its place.
        title = "FIGURE 1: Sagittal (left) and axial (right) MRI of the patient"
        cut = f"{title} A. T2-weighted and B. T1 fat saturation MRI sequences demonstrating C1 lateral mass lesion"
        paragraph = (
            "A. T2-weighted and B. T1 fat saturation MRI sequences demonstrating C1 lateral mass lesion "
            "(red arrow) and displacement of the vertebral artery."
        )
        figure = Figure(children=[], caption=cut)
        plan = [{"images": [], "caption": cut}]

        kept_out = PdfToAstConverter._complete_cut_caption(
            _caption_comparison_key(paragraph), paragraph, plan, [figure]
        )

        assert kept_out is False  # the paragraph stays in the body
        assert figure.caption == title
        assert plan[0]["caption"] == title

    def test_body_prose_the_band_reached_is_given_back_not_swallowed(self):
        from all2md.ast.nodes import Figure

        # PMC7000152.1: the band ran past the caption into the body, so the caption ended on
        # the opening of the next body paragraph. Moving that paragraph onto the figure put
        # 202 words of prose into the caption.
        title = "Figure 1. Network map of TFs from Table 1 showing the documented regulations."
        prose = (
            "Furthermore, HMS1 deletion results in both temperature-dependent filamentation defects "
            "and attenuation of virulence in a Galleria mellonella model of infection."
        )
        cut = f"{title} Furthermore, HMS1 deletion results in both temperature-dependent filamen-"
        figure = Figure(children=[], caption=cut)

        assert not PdfToAstConverter._complete_cut_caption(
            _caption_comparison_key(prose), prose, [{"images": [], "caption": cut}], [figure]
        )
        assert figure.caption == title

    def test_a_short_shared_phrase_does_not_join_prose_to_a_caption(self):
        cut = "Figure 3. Survival of the patients in each arm of the trial"
        prose = "of the trial was twelve months, and every patient was followed up."
        plan = [{"images": [], "caption": cut}]

        assert not PdfToAstConverter._complete_cut_caption(_caption_comparison_key(prose), prose, plan, [])
        assert plan[0]["caption"] == cut

    def test_a_soft_hyphen_does_not_hide_a_body_copy(self):
        # PMC11000000.1: the caption route kept a soft hyphen in "intensity", the body route
        # dropped it, and the whole 157-word body copy escaped the de-duplication.
        assert _caption_comparison_key("High signal in" + chr(0xAD) + "tensity") == _caption_comparison_key(
            "High signal intensity"
        )


@pytest.mark.skipif(not (CORPUS / "control").is_dir(), reason="PDF to Word lane corpus not present")
class TestOnWordsOwnPdfs:
    def _body(self, pdf: Path) -> list[str]:
        from all2md import to_ast

        document = to_ast(pdf, parser_options=PdfOptions(layout_analysis_mode="disabled"))
        return [" ".join(extract_text(node).split()) for node in document.children if isinstance(node, AstParagraph)]

    def test_plain_prose_paragraphs_come_out_whole(self):
        body = self._body(CORPUS / "control" / "plain-prose.untagged.pdf")
        prose = [p for p in body if len(p.split()) > 5]

        assert len(prose) == 5
        assert any(p.endswith("because the ground was wet and the money ran out twice.") for p in prose)

    def test_auto_numbered_clauses_come_out_one_per_paragraph(self):
        body = self._body(CORPUS / "contract" / "msa-auto-numbered.untagged.pdf")
        openers = [p.split()[0] for p in body if p.split()]

        for clause in ("1.1", "1.2", "(a)", "(b)", "(c)", "2.1", "2.2", "2.3", "3.1", "3.2", "3.3"):
            assert clause in openers, clause
