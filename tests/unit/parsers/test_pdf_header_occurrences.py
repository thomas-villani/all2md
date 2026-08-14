#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_header_occurrences.py
"""``header_min_occurrences`` counts lines, not characters.

``fontsizes`` used to accumulate ``len(text)`` per span, so the filter dropped a font size
only if it rendered fewer than ``header_min_occurrences`` *characters* -- a bar so low that
almost every size cleared it regardless of how many times it actually appeared, silently
defeating the documented "minimum occurrences of a font size" behaviour.

The fix tracks real line occurrences in a separate statistic, used only to decide which
sizes survive the filter; the single largest size is exempt, since it is, by convention, a
document's title, which renders once by design and should not need to repeat to be found.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_headers import IdentifyHeaders

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _one_page_pdf(tmp_path: Path, lines: list[tuple[float, str, float]], name: str = "page.pdf") -> str:
    """A one-page PDF with each ``(y, text, fontsize)`` triple on its own line."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=500)
    writer = pymupdf.TextWriter(page.rect)
    font = pymupdf.Font("helv")
    for y, text, fontsize in lines:
        writer.append((40, y), text, font=font, fontsize=fontsize)
    writer.write_text(page)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


class TestOccurrencesAreLinesNotCharacters:
    """A font size needs enough *lines*, not enough *characters*, to pass the filter."""

    def test_a_long_but_rare_size_is_filtered(self, tmp_path: Path) -> None:
        """One long line at a subordinate size does not meet occurrences=5 on its own.

        Body text (size 9) recurs on ten lines, comfortably clearing the bar. A single
        long line at size 11 -- between body and the confidently-larger title -- used to
        pass because its character count alone exceeded 5; it must now be filtered
        because it renders on only one line and is not the document's largest size.
        """
        lines = [(40.0, "A big title that stands alone", 24.0)]
        lines += [
            (
                70.0,
                "A single subordinate-size line long enough that its old character count "
                "cleared the threshold on its own, even though it occurs exactly once.",
                11.0,
            )
        ]
        y = 100.0
        for i in range(10):
            lines.append((y, f"Body paragraph line {i} of the article.", 9.0))
            y += 12.0

        path = _one_page_pdf(tmp_path, lines)
        import pymupdf

        doc = pymupdf.open(path)
        options = PdfOptions(header_debug_output=True, header_min_occurrences=5)
        hdr = IdentifyHeaders(doc, options=options)
        doc.close()

        info = hdr.get_debug_info()
        assert info is not None
        # The rare 11pt line is gone from the post-filter distribution ...
        assert 11 not in info["font_size_distribution"]
        # ... despite having far more characters than the ten-line, nine-point body text.
        assert info["font_size_occurrences"][11] == 1

    def test_a_short_but_frequent_size_survives(self, tmp_path: Path) -> None:
        """A size repeated often enough passes even if each occurrence is short.

        Six short section-heading lines at size 14 clear ``header_min_occurrences=5`` on
        line count; the old character-count filter would have made this an easy pass too
        (rendering it untestable as a regression), so this pins the *line*-counting
        behaviour specifically by using text too short to clear 5 characters on any
        single line while still clearing 5 *occurrences*.
        """
        lines = [(40.0, "Report", 24.0)]
        y = 80.0
        for i in range(6):
            lines.append((y, "S" + str(i), 14.0))  # 2 characters per line
            y += 14.0
            lines.append((y, f"Body text paragraph {i} explaining the section.", 9.0))
            y += 24.0

        path = _one_page_pdf(tmp_path, lines)
        import pymupdf

        doc = pymupdf.open(path)
        options = PdfOptions(header_debug_output=True, header_min_occurrences=5, header_percentile_threshold=0)
        hdr = IdentifyHeaders(doc, options=options)
        doc.close()

        info = hdr.get_debug_info()
        assert info is not None
        assert info["font_size_occurrences"][14] == 6
        assert 14 in info["font_size_distribution"]
        assert hdr.header_id.get(14) is not None


class TestTheLargestSizeIsExemptFromTheOccurrenceFilter:
    """A rare title-sized font is still detected, even though it fails the raw count."""

    def test_a_title_on_two_lines_is_still_a_heading(self, tmp_path: Path) -> None:
        """Regression pin for the case the fix would otherwise break.

        A wrapped title occupies only two lines -- below ``header_min_occurrences=5`` on
        a literal reading -- but is the largest size on the page, so it is exempt and
        still becomes a heading.
        """
        lines = [
            (40.0, "Long-term outcomes of an", 20.0),
            (64.0, "intervention in older adults", 20.0),
        ]
        y = 100.0
        for i in range(12):
            lines.append((y, f"body line {i} of the article", 9.0))
            y += 12.0

        path = _one_page_pdf(tmp_path, lines)
        import pymupdf

        doc = pymupdf.open(path)
        options = PdfOptions()
        hdr = IdentifyHeaders(doc, options=options)
        doc.close()

        assert hdr.header_id.get(20) == 1

    def test_body_text_is_still_correctly_identified_when_it_ties_on_occurrences(self, tmp_path: Path) -> None:
        """A tie in line count does not make a short heading outrank a long paragraph.

        Body-limit detection uses characters, not occurrences. Two lines share one
        occurrence count each here (one heading-sized, one body-sized
        line), but the body line carries far more text -- exactly the ambiguity the
        character-based body-limit statistic exists to resolve independently of the
        occurrence-based header filter.
        """
        lines = [
            (40.0, "H", 20.0),
            (70.0, "This single line carries the bulk of the page's actual prose content.", 12.0),
        ]

        path = _one_page_pdf(tmp_path, lines)
        import pymupdf

        doc = pymupdf.open(path)
        options = PdfOptions(header_debug_output=True, header_min_occurrences=1)
        hdr = IdentifyHeaders(doc, options=options)
        doc.close()

        info = hdr.get_debug_info()
        assert info is not None
        assert info["body_text_size"] == 12.0
