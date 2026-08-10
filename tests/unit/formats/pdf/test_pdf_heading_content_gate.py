#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_heading_content_gate.py
"""A heading names something, so it has to contain at least one alphanumeric character.

``IdentifyHeaders.classify_line_style`` validated a candidate by font size, bold/all-caps
requirements, maximum length and an internal-sentence-boundary check -- and never asked
whether the text held a letter. Large math delimiters are set in a symbol font at a size
well above body text, so they cleared the size gate and passed every remaining one: short,
non-empty, no sentence boundary.

On one chemistry paper in the born-digital corpus that produced **179 headings for 9
sections**, 122 of them a single Private Use Area glyph -- sigma, integral, large
parentheses -- lifted out of displayed equations and emitted as `### `.

The gate uses ``str.isalnum`` rather than an ASCII character class, which is the whole
point: it is Unicode-aware, so a heading in any script still qualifies, while PUA
codepoints (category Co, where symbol fonts keep their glyphs) do not. An ASCII test would
have rejected every CJK, Cyrillic, Arabic and Devanagari heading in the process of fixing
this.
"""

from __future__ import annotations

import pytest

from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_headers import IdentifyHeaders

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


@pytest.fixture
def identifier() -> IdentifyHeaders:
    """A classifier with one heading size registered, and no style requirement on it."""
    ident = IdentifyHeaders.__new__(IdentifyHeaders)
    ident.header_id = {20: 1, 16: 2}
    ident.bold_header_sizes = set()
    ident.allcaps_header_sizes = set()
    ident.options = PdfOptions()
    ident.debug_info = None
    return ident


def _classify(ident: IdentifyHeaders, text: str, size: int = 20) -> int:
    return ident.classify_line_style(size=size, text=text, is_bold=False, is_allcaps=False)


class TestGlyphOnlyLinesAreNotHeadings:
    @pytest.mark.parametrize(
        "glyph,name",
        [
            ("", "summation"),
            ("", "large opening parenthesis"),
            ("", "large closing parenthesis"),
            ("", "integral"),
            ("", "large bracket"),
        ],
    )
    def test_a_lone_symbol_font_glyph_is_rejected(self, identifier, glyph, name):
        assert _classify(identifier, glyph) == 0, name

    def test_a_run_of_glyphs_is_rejected(self, identifier):
        assert _classify(identifier, "") == 0

    def test_punctuation_alone_is_rejected(self, identifier):
        assert _classify(identifier, "— :") == 0

    def test_whitespace_around_a_glyph_does_not_rescue_it(self, identifier):
        assert _classify(identifier, "    ") == 0


class TestRealHeadingsStillQualify:
    def test_ordinary_text(self, identifier):
        assert _classify(identifier, "Introduction") == 1

    def test_a_numbered_heading(self, identifier):
        assert _classify(identifier, "3.1. Non-Relativistic Bondons") == 1

    def test_a_number_alone(self, identifier):
        # A chapter number is a legitimate heading; the gate asks for alphanumeric, not
        # alphabetic, so digits carry it.
        assert _classify(identifier, "7") == 1

    @pytest.mark.parametrize(
        "text,script",
        [
            ("第一章", "CJK"),
            ("Введение", "Cyrillic"),
            ("المقدمة", "Arabic"),
            ("परिचय", "Devanagari"),
            ("Εισαγωγή", "Greek"),
            ("서론", "Hangul"),
        ],
    )
    def test_non_latin_headings_are_kept(self, identifier, text, script):
        # The reason the gate is `str.isalnum` and not `[A-Za-z0-9]`. An ASCII test would
        # silently delete every heading in these scripts.
        assert _classify(identifier, text) == 1, script

    def test_a_heading_mixing_text_and_a_glyph_is_kept(self, identifier):
        assert _classify(identifier, "Method: Identification of Bondons (B)") == 1


class TestTheGateRunsAfterTheOtherChecks:
    def test_a_size_that_is_not_a_heading_size_is_still_rejected(self, identifier):
        assert _classify(identifier, "Introduction", size=11) == 0

    def test_an_overlong_line_is_still_rejected(self, identifier):
        assert _classify(identifier, "word " * 200) == 0
