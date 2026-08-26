#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_math.py
"""Recognising a display equation in a PDF's spans.

A display equation is typeset glyph by glyph: each variable, operator and bracket
piece is its own span, in its own font, positioned absolutely. PyMuPDF hands that
back as it finds it, so one equation arrives as dozens of one-word blocks -- and
because nothing marks them as mathematical, every rule downstream treats them as
prose. They are wrapped in emphasis one glyph at a time (an italic variable is
italic because it is a variable, not because it is stressed), and they interleave
with the paragraphs around them.

This module answers only the narrow question the rest of the parser needs: *is
this line part of a display equation?* It does not attempt to read the equation.
Reconstructing sub/superscripts and stacked constructs is a separate problem, and
until it is solved the honest thing is to keep the glyphs together and stop them
corrupting the text beside them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "MATH_BLOCK_MAX_WORDS",
    "MATH_BLOCK_MIN_LINE_SHARE",
    "MATH_LINE_MAX_WORDS",
    "MATH_LINE_MIN_FONT_SHARE",
    "is_equation_block",
    "is_equation_line",
]

# The font families a typesetter reaches for when it needs a glyph the text font
# does not carry: Adobe Symbol, TeX's math families, MathType's extras.
_MATH_FONT = re.compile(r"symbol|math|cmmi|cmsy|cmex|mtextra|msam|msbm", re.I)

# Enough of the line's spans in a math font that the line is being *set* as math,
# rather than a sentence reaching for one Greek letter.
MATH_LINE_MIN_FONT_SHARE = 0.30

# An equation line is a handful of glyphs, not a sentence. Measured over 9,417
# lines of three equation-heavy articles and two without: of the lines carrying
# math evidence, 99% hold two words or fewer, and the first prose line to carry
# it holds ten. Every cap between 3 and 8 admits the same 2,850-2,880 lines and
# no prose line at all, so this sits mid-plateau rather than on an edge.
MATH_LINE_MAX_WORDS = 6


def _private_use(text: str) -> bool:
    """Report whether the text carries a Private Use Area codepoint.

    A symbol font addresses its glyphs through the PUA, so ``0xF0B6`` reaches us
    where the page prints an operator. The character is unreadable as it stands --
    mapping it back through the font's encoding is its own problem -- but its
    presence is decisive evidence that the line is not ordinary prose.
    """
    return any(0xE000 <= ord(char) <= 0xF8FF for char in text)


def is_equation_line(spans: "Sequence[dict]") -> bool:
    """Decide whether these spans are a fragment of a display equation.

    Two things must hold together, because either alone claims real prose. The
    line must carry math evidence -- a substantial share of its spans set in a
    math font, or a Private Use codepoint anywhere in it -- and it must be short.
    Prose reaches for a Greek letter often enough ("in terms of electronic
    density ρ, momentum p") that evidence alone would strip the emphasis from,
    and refuse to join, sentences that are only *about* mathematics; on the
    corpus that is 36 lines of 11 to 24 words. Shortness alone is worse still,
    since a page is full of short lines.

    Neither test fires on an article without display equations: across 1,436
    control lines, this returned ``True`` for none of them.
    """
    if not spans:
        return False
    text = "".join(span.get("text", "") for span in spans)
    if len(text.split()) > MATH_LINE_MAX_WORDS:
        return False
    return _has_math_evidence(spans)


def _has_math_evidence(spans: "Sequence[dict]") -> bool:
    """Report whether these spans are set as mathematics, ignoring how long they are."""
    if not spans:
        return False
    if _private_use("".join(span.get("text", "") for span in spans)):
        return True
    in_math_font = sum(1 for span in spans if _MATH_FONT.search(span.get("font", "")))
    return in_math_font >= MATH_LINE_MIN_FONT_SHARE * len(spans)


# A display equation is a few lines of glyphs, not a section of prose. This bounds the
# block the share test below may claim, so a long paragraph that happens to quote one
# formula keeps its own typography.
MATH_BLOCK_MAX_WORDS = 24

# Half the block's lines carrying evidence is enough to call the block math, and with it
# the lines that carry none.
MATH_BLOCK_MIN_LINE_SHARE = 0.5


def is_equation_block(block: dict) -> bool:
    """Decide whether a whole block is a display equation.

    A line test alone is not enough, and the reason is worth stating. An equation is set
    glyph by glyph across several lines, and the evidence is not spread evenly over them:
    one line carries the operators and brackets in a symbol font, the next carries only
    the variables, set in the ordinary text italic. That second line is indistinguishable
    from prose *by itself* -- it is short, italic and says nothing else -- so a per-line
    test leaves it emphasised one letter at a time in the middle of an equation it plainly
    belongs to.

    What identifies it is its neighbours. When half a block's lines carry math evidence
    and the block is short enough not to be prose, the block is an equation and every line
    in it is part of it.
    """
    lines = [line for line in (block.get("lines") or []) if line.get("spans")]
    if not lines:
        return False
    text = "".join(span.get("text", "") for line in lines for span in line["spans"])
    if len(text.split()) > MATH_BLOCK_MAX_WORDS:
        return False
    # Counted on the full line test, not on the evidence alone: a paragraph that names
    # one Greek letter carries evidence on a line 22 words long, and letting that line
    # vote lets a sentence claim the block it sits in.
    equation_lines = sum(1 for line in lines if is_equation_line(line["spans"]))
    return equation_lines >= MATH_BLOCK_MIN_LINE_SHARE * len(lines)
