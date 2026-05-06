#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_numbering.py
"""PDF heading numbering-prefix detection.

Lightweight parser for the numbering schemes that document authors use to
mark heading hierarchy: Roman numerals (``I.``, ``II.``), decimals
(``1.``, ``1.1``, ``1.1.1``), letters (``A.``, ``B.``), and parenthesized
forms (``(a)``, ``(1)``). Used by the PDF parser to:

1. Recognize lines that contain *only* a numbering prefix and merge them
   with the next heading line — common when the PDF lays the numbering
   out on its own visual line above the heading text.
2. Optionally derive structural depth from nested decimal numbering
   (``1.1.1`` is one level deeper than ``1.1``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["NumberingMatch", "parse_numbering_prefix", "is_numbering_only"]


# Roman numeral matcher restricted to plausible heading values (1-39).
# Avoids matching "I" as a standalone pronoun or arbitrary letter sequences.
_ROMAN_RE = re.compile(r"^(?P<roman>(?=[IVX])X{0,3}(IX|IV|V?I{0,3}))\.\s*$", re.IGNORECASE)
# Decimal hierarchy: "1", "1.", "1.1", "1.1.1" — optional trailing period.
_DECIMAL_RE = re.compile(r"^(?P<decimal>\d+(?:\.\d+)*)\.?\s*$")
# Single uppercase letter followed by a period.
_LETTER_RE = re.compile(r"^(?P<letter>[A-Z])\.\s*$")
# Parenthesized letter or digit: "(a)", "(1)", "(iv)".
_PAREN_RE = re.compile(r"^\((?P<paren>[A-Za-z0-9]{1,4})\)\s*$")
# Section sign with optional decimal: "§", "§1", "§1.1".
_SECTION_RE = re.compile(r"^§\s*(?P<section>\d+(?:\.\d+)*)?\s*$")
# Standalone bullet glyph. Not a numbering scheme per se, but PDFs often
# split "- Item Name" across two visual lines (dash on one, name on the
# next), and merging them produces the right heading text.
_BULLET_RE = re.compile(r"^[-*•◦▪▫–—]\s*$")


@dataclass(frozen=True)
class NumberingMatch:
    """Result of parsing a numbering prefix.

    Attributes
    ----------
    kind : str
        One of "roman", "decimal", "letter", "paren", "section".
    raw : str
        The raw matched prefix text (without trailing whitespace).
    depth : int
        Best-effort hierarchical depth. 1 for top-level (Roman, "1.", "A.",
        "§"), 2 for "1.1" or paren letter under Roman, etc. Used as a hint
        for heading level — callers may map `depth` onto a heading level
        offset.

    """

    kind: str
    raw: str
    depth: int


def parse_numbering_prefix(text: str) -> NumberingMatch | None:
    """Return a :class:`NumberingMatch` if ``text`` is purely a numbering prefix.

    "Purely" means the entire stripped text is the prefix — e.g. ``"I."``,
    ``"1.1"``, ``"(a)"``. A line containing both a prefix and heading text
    (``"I. Background"``) does not match here; that case is handled by
    :func:`split_numbering_prefix` if/when needed.
    """
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None

    m = _ROMAN_RE.match(stripped)
    if m:
        return NumberingMatch(kind="roman", raw=stripped, depth=1)

    m = _PAREN_RE.match(stripped)
    if m:
        token = m.group("paren")
        # Distinguish parenthesized letter (depth 3) vs. digit (depth 4).
        depth = 4 if token.isdigit() else 3
        return NumberingMatch(kind="paren", raw=stripped, depth=depth)

    m = _DECIMAL_RE.match(stripped)
    if m:
        token = m.group("decimal")
        # Depth = number of dot-separated components: "1" → 1, "1.1" → 2.
        depth = token.count(".") + 1
        return NumberingMatch(kind="decimal", raw=stripped, depth=depth)

    m = _LETTER_RE.match(stripped)
    if m:
        return NumberingMatch(kind="letter", raw=stripped, depth=2)

    m = _SECTION_RE.match(stripped)
    if m:
        token = m.group("section") or ""
        depth = (token.count(".") + 1) if token else 1
        return NumberingMatch(kind="section", raw=stripped, depth=depth)

    if _BULLET_RE.match(stripped):
        # Bullet glyph alone — treat as a deeper structural marker so the
        # buffered heading level reflects "list item under section".
        return NumberingMatch(kind="bullet", raw=stripped, depth=3)

    return None


def is_numbering_only(text: str) -> bool:
    """Return True iff ``text`` consists entirely of a numbering prefix.

    Convenience wrapper for callers that don't need the structured match.
    """
    return parse_numbering_prefix(text) is not None
