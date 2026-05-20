#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/ast/test_line_map.py
"""Tests for all2md.ast.line_map (output line-number mapping)."""

import pytest

from all2md.ast.line_map import find_heading_lines, map_sections_to_lines, number_text_lines
from all2md.ast.nodes import Document, Heading, Text
from all2md.ast.sections import get_all_sections

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# find_heading_lines
# ---------------------------------------------------------------------------


def test_find_heading_lines_atx() -> None:
    """ATX headings are located by 1-based line number and level."""
    md = "# Title\n\nIntro.\n\n## Sub\n\nText.\n\n# Second"
    assert find_heading_lines(md) == [(1, 1), (5, 2), (9, 1)]


def test_find_heading_lines_skips_code_fences() -> None:
    """Hash lines inside fenced code blocks are not treated as headings."""
    md = "# Real\n\n```python\n# not a heading\n## also not\n```\n\n## After"
    assert find_heading_lines(md) == [(1, 1), (8, 2)]


def test_find_heading_lines_skips_tilde_fences() -> None:
    """Tilde-fenced code blocks are skipped just like backtick fences."""
    md = "# Real\n\n~~~\n# nope\n~~~\n\n# After"
    assert find_heading_lines(md) == [(1, 1), (7, 1)]


def test_find_heading_lines_setext() -> None:
    """Setext headings report the text line, not the underline."""
    md = "Title\n=====\n\nText.\n\nSub\n---\n\nMore."
    assert find_heading_lines(md) == [(1, 1), (6, 2)]


def test_find_heading_lines_setext_not_after_blank() -> None:
    """A rule preceded by a blank line (thematic break) is not a heading."""
    md = "Some text.\n\n---\n\nMore text."
    assert find_heading_lines(md) == []


def test_find_heading_lines_indented_not_detected() -> None:
    """Indented heading-like lines (nested constructs) are ignored."""
    md = "# Top\n\n   # indented, not top-level\n\n> # quoted"
    assert find_heading_lines(md) == [(1, 1)]


# ---------------------------------------------------------------------------
# map_sections_to_lines
# ---------------------------------------------------------------------------


def _doc() -> Document:
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Heading(level=2, content=[Text(content="Background")]),
            Heading(level=1, content=[Text(content="Methods")]),
        ],
        metadata={},
    )


def test_map_sections_to_lines_matching_counts() -> None:
    """When detected headings match sections one-to-one, lines come straight through."""
    md = "# Introduction\n\nText.\n\n## Background\n\nMore.\n\n# Methods"
    sections = get_all_sections(_doc(), min_level=1, max_level=6)
    assert map_sections_to_lines(sections, md) == [1, 5, 9]


def test_map_sections_to_lines_fallback_by_level() -> None:
    """On a count mismatch, mapping aligns greedily by heading level."""
    sections = get_all_sections(_doc(), min_level=1, max_level=6)
    # An extra detected heading (count mismatch) forces the fallback path.
    detected_md = "# Introduction\n\n## Background\n\n## Extra\n\n# Methods"
    result = map_sections_to_lines(sections, detected_md)
    # levels [1, 2, 1] align to lines 1 (h1), 3 (first h2), 7 (next h1).
    assert result == [1, 3, 7]


# ---------------------------------------------------------------------------
# number_text_lines
# ---------------------------------------------------------------------------


def test_number_text_lines_sequential() -> None:
    """Lines are numbered sequentially with an aligned gutter."""
    text = "alpha\nbeta\ngamma"
    assert number_text_lines(text) == "1: alpha\n2: beta\n3: gamma"


def test_number_text_lines_alignment() -> None:
    """The number column is right-aligned to the widest number."""
    text = "\n".join(str(i) for i in range(1, 11))  # 10 lines -> width 2
    out = number_text_lines(text).splitlines()
    assert out[0] == " 1: 1"
    assert out[9] == "10: 10"


def test_number_text_lines_explicit_numbers_with_gap() -> None:
    """Explicit numbers display original positions; None leaves a line unnumbered."""
    text = "first\n\nsecond"
    out = number_text_lines(text, [10, None, 25])
    assert out == "10: first\n\n25: second"


def test_number_text_lines_empty() -> None:
    """Empty input is returned unchanged."""
    assert number_text_lines("") == ""
