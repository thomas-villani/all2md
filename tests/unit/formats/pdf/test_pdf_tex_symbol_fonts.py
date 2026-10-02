#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_tex_symbol_fonts.py
"""TeX math fonts embedded without a ToUnicode map arrive as their raw codes.

TeX's math symbol (cmsy) and extension (cmex) fonts put glyphs at 0x00-0x1F, so
"Scoring ≥50%" reached the text as "Scoring \\x1550%" and the DOCX renderer then
dropped the code as XML-illegal. The codes are mapped through the published tables.
A document-specific subset (an Elsevier AdvP font, say) assigns its low codes per
document, so it is left alone, and so is everything outside 0x00-0x1F.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_math import decode_tex_symbol_fonts

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _blocks(*spans: tuple[str, str]) -> list[dict]:
    return [{"type": 0, "lines": [{"spans": [{"font": font, "text": text} for font, text in spans]}]}]


def _texts(blocks: list[dict]) -> list[str]:
    return [span["text"] for block in blocks for line in block["lines"] for span in line["spans"]]


@pytest.mark.parametrize(
    "font, raw, decoded",
    [
        ("TeX_CM_Maths_Symbols", "Scoring \x1550%", "Scoring ≥50%"),
        ("ABCDEF+CMSY10", "F \x00 Fmin", "F − Fmin"),
        ("CMSY7", "7\x037", "7∗7"),
        ("TeX_CM_Maths_Symbols", "\x0f COVID-19", "• COVID-19"),
        ("CMEX10", "\x10x\x11 \x14y\x15", "(x) [y]"),
    ],
)
def test_tex_fonts_decode_their_low_codes(font, raw, decoded):
    blocks = _blocks((font, raw))

    decode_tex_symbol_fonts(blocks)

    assert _texts(blocks) == [decoded]


def test_other_fonts_and_printable_codes_are_left_alone():
    blocks = _blocks(("AdvP4C4E74", "37\x03C"), ("CMSY10", "ð Þ ¼"), ("Times", "a\tb"))

    decode_tex_symbol_fonts(blocks)

    assert _texts(blocks) == ["37\x03C", "ð Þ ¼", "a\tb"]


def test_a_page_of_one_tex_font_gives_its_table_for_table_cells():
    # Tabs in a text font do not make the page ambiguous, and stay tabs in the table.
    table = decode_tex_symbol_fonts(_blocks(("CMSY10", "a \x15 b"), ("Times", "x\ty")))

    assert table is not None
    assert "Married\x03\x03\x03\t".translate(table) == "Married∗∗∗\t"


@pytest.mark.parametrize(
    "spans",
    [
        [("CMSY10", "\x15"), ("CMEX10", "\x10")],  # two kinds: a bare 0x10 could be either
        [("CMSY10", "\x15"), ("AdvP4C4E74", "\x03")],  # another font's low codes
        [("Times", "plain text")],  # no TeX font at all
    ],
)
def test_an_ambiguous_page_gives_no_table(spans):
    assert decode_tex_symbol_fonts(_blocks(*spans)) is None
