#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_header_footer_trim.py
"""Running header/footer removal, on a stock install.

``auto_trim_headers_footers`` had no tests at all, and had quietly stopped working in
the two cases that matter most:

* it did nothing on a two-page document (detection required three pages), and
* it never removed a footer containing a page number -- which is very nearly every
  running footer there is -- because candidates were keyed on their exact text, so
  ``Page 1 of 12`` and ``Page 2 of 12`` looked like two unrelated blocks and neither
  ever repeated.

Both failures were invisible in development because the optional layout model labels
headers and footers directly, so the text-based path never ran. These tests force the
layout model **off**, which is what a stock install and CI actually have.
"""

from __future__ import annotations

import fitz
import pytest

from all2md import to_markdown
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter, _running_text_key

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


class _StubPage:
    """Just enough page for the zone filter: it only reads ``rect.height``."""

    def __init__(self, height: float) -> None:
        self.rect = fitz.Rect(0, 0, 612, height)


HEADER = "ACME CONFIDENTIAL -- INTERNAL USE ONLY"

#: Distinct prose per page. Body text that were *identical* on every page, in the same
#: place, would be indistinguishable from a running header by any repetition rule --
#: which is a statement about that document, not about the detector.
BODIES = [
    "The northern depot absorbed most of the seasonal surge without extra headcount.",
    "Regulatory filings went in a fortnight early and cleared without comment.",
    "Shipping delays pushed three launches into the following quarter.",
    "Office consolidation freed an entire floor of the building.",
    "A currency swing wiped out most of the overseas gain this period.",
    "The legacy billing system was finally decommissioned in full.",
]


@pytest.fixture(autouse=True)
def _no_layout_model(monkeypatch):
    """A stock install has no ``pdf_layout`` extra, so the text-based path must work."""
    monkeypatch.setattr("all2md.parsers.pdf.is_layout_available", lambda: False)


def _make_pdf(tmp_path, n_pages: int, *, footer: str = "Page {n} of {total}") -> str:
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 40), HEADER, fontsize=8)
        page.insert_text((72, 760), footer.format(n=i + 1, total=n_pages), fontsize=8)
        # Body sits clear of the header zone (the top 20% of the page).
        page.insert_textbox(
            fitz.Rect(72, 220, 540, 520), f"Section {i + 1} opens here. {BODIES[i % len(BODIES)]}", fontsize=11
        )
    path = tmp_path / f"doc{n_pages}.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


class TestRunningTextKey:
    """Page numbers are the thing that makes a running footer look non-repeating."""

    def test_page_numbers_collapse_to_one_key(self):
        assert _running_text_key("Page 1 of 12") == _running_text_key("Page 2 of 12")

    def test_different_text_keeps_different_keys(self):
        assert _running_text_key("Chapter One") != _running_text_key("Appendix")

    def test_prose_is_untouched(self):
        assert _running_text_key("no digits here") == "no digits here"


class TestAutoTrim:
    @pytest.mark.parametrize("n_pages", [2, 3, 6])
    def test_removes_the_running_header(self, tmp_path, n_pages):
        md = to_markdown(_make_pdf(tmp_path, n_pages), parser_options=PdfOptions(auto_trim_headers_footers=True))
        assert "INTERNAL USE ONLY" not in md

    @pytest.mark.parametrize("n_pages", [2, 3, 6])
    def test_removes_a_footer_that_carries_a_page_number(self, tmp_path, n_pages):
        """The common case, and the one that never worked: the footer differs on every page."""
        md = to_markdown(_make_pdf(tmp_path, n_pages), parser_options=PdfOptions(auto_trim_headers_footers=True))
        assert "Page 1 of" not in md

    @pytest.mark.parametrize("n_pages", [2, 3, 6])
    def test_body_text_survives(self, tmp_path, n_pages):
        """Trimming furniture must not cost body text.

        The zone boundary comes from the innermost matching block, so an over-eager
        detector does not lose one line, it loses everything outside that line.
        """
        md = to_markdown(_make_pdf(tmp_path, n_pages), parser_options=PdfOptions(auto_trim_headers_footers=True))
        assert "seasonal surge" in md
        for i in range(1, n_pages + 1):
            assert f"Section {i} opens here" in md, "auto_trim ate a page's body text"

    def test_two_pages_are_enough(self, tmp_path):
        """A two-page document used to be ignored outright."""
        md = to_markdown(_make_pdf(tmp_path, 2), parser_options=PdfOptions(auto_trim_headers_footers=True))
        assert "INTERNAL USE ONLY" not in md

    def test_a_single_page_is_left_alone(self, tmp_path):
        """One page cannot show repetition, so nothing may be presumed furniture."""
        md = to_markdown(_make_pdf(tmp_path, 1), parser_options=PdfOptions(auto_trim_headers_footers=True))
        assert "INTERNAL USE ONLY" in md

    def test_defaults_keep_everything(self, tmp_path):
        """Trimming is opt-in: the default conversion is unchanged."""
        md = to_markdown(_make_pdf(tmp_path, 3))
        assert "INTERNAL USE ONLY" in md
        assert "Page 1 of 3" in md


class TestNonFurnitureIsSafe:
    """What must *not* be trimmed. Digit-collapsing keys make this the live risk."""

    def test_body_that_starts_inside_the_zone_survives(self):
        """A paragraph that merely *begins* inside the header zone must not be eaten.

        Taken from a real FCC filing: the running head's lower edge sat at y=73 and the
        body opened at y=74.1, so the detected zone (furniture, plus a small margin)
        reached a few points past the top of the body block. The filter tested only a
        block's near edge -- does it *start* above ``header_height`` -- and so dropped
        the opening paragraph of every page in its entirety, all the way down the page.

        Furniture is always *fully* contained in the zone, because the zone is derived
        from furniture's own far edge. Body text merely pokes into it.
        """
        page = _StubPage(height=792)
        converter = PdfToAstConverter(PdfOptions(trim_headers_footers=True, header_height=78, footer_height=53))

        running_head = {"bbox": (72, 36, 540, 73)}  # entirely inside the zone: furniture
        body = {"bbox": (72, 74, 540, 700)}  # starts inside it, runs the page: content
        page_number = {"bbox": (72, 743, 540, 755)}  # entirely inside the footer zone

        kept = converter._filter_headers_footers([running_head, body, page_number], page)

        assert body in kept, "a body block was trimmed because it began inside the header zone"
        assert running_head not in kept, "the running head survived"
        assert page_number not in kept, "the page number survived"

    def test_a_heading_that_moves_down_the_page_is_not_furniture(self, tmp_path):
        """``Section 1`` / ``Section 2`` share a digit-collapsed key -- position saves them.

        Real furniture is anchored to the page. A heading that merely recurs is anchored
        to the text flow, so it lands somewhere different on each page. Without the
        position check these headings key alike, repeat often enough, and get trimmed --
        taking every line above them with them.
        """
        doc = fitz.open()
        for i in range(4):
            page = doc.new_page(width=612, height=792)
            # Same text shape, but it drifts down the page: not anchored, not furniture.
            page.insert_text((72, 60 + i * 12), f"Section {i + 1}", fontsize=14)
            page.insert_textbox(fitz.Rect(72, 200, 540, 400), f"Body of section {i + 1}.", fontsize=11)
        path = tmp_path / "sections.pdf"
        doc.save(str(path))
        doc.close()

        md = to_markdown(str(path), parser_options=PdfOptions(auto_trim_headers_footers=True))

        for i in range(1, 5):
            assert f"Section {i}" in md, "a drifting heading was mistaken for a running header"
