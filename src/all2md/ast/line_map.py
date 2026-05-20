#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/line_map.py
"""Map document headings to line numbers in rendered Markdown output.

These utilities back the CLI features that reference *output* line numbers:

- ``--outline --line-numbers`` annotates each heading with the line it occupies
  in the full Markdown rendering, giving callers (humans or LLMs) a
  heading -> line map.
- ``--extract line:X-Y`` selects content by that same line range.
- ``--line-numbers`` on full/extract output prefixes lines with their numbers.

All functions operate on already-rendered Markdown *text* so they stay
decoupled from the renderer (no import cycle) and describe exactly what the
caller sees on stdout.

Functions
---------
find_heading_lines : Locate heading lines in rendered Markdown
map_sections_to_lines : Assign a 1-based line number to each section
number_text_lines : Prefix lines with right-aligned line numbers

"""

from __future__ import annotations

import re

from all2md.ast.sections import Section

# ATX heading at column 0 (top-level headings are emitted flush-left). Leading
# whitespace is intentionally *not* allowed so indented/nested heading-like
# lines (list items, blockquotes) are not mistaken for top-level headings,
# matching the set of headings get_all_sections() returns.
_ATX_RE = re.compile(r"^(#{1,6})[ \t]")

# Opening/closing fence of a fenced code block.
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")

# Setext underline: a run of '=' (level 1) or '-' (level 2) on its own line.
_SETEXT_RE = re.compile(r"^(=+|-+)[ \t]*$")


def find_heading_lines(markdown_text: str) -> list[tuple[int, int]]:
    """Locate top-level headings in rendered Markdown.

    Parameters
    ----------
    markdown_text : str
        Rendered Markdown to scan.

    Returns
    -------
    list of (int, int)
        ``(line_number, level)`` for each heading, in document order.
        Line numbers are 1-based.

    Notes
    -----
    Detects both ATX (``# Heading``) and setext (text underlined with ``=`` or
    ``-``) headings at column 0. Fenced code blocks are skipped so that ``#``
    comments inside code are not mistaken for headings. For setext headings the
    reported line is the text line, not the underline.

    """
    lines = markdown_text.split("\n")
    results: list[tuple[int, int]] = []
    in_fence = False
    fence_char = ""
    prev_blank = True  # start of document behaves like a preceding blank line

    for idx, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)

        if in_fence:
            # Close on a fence line using the same character (``` vs ~~~).
            if fence_match and fence_match.group(1)[0] == fence_char:
                in_fence = False
            prev_blank = not line.strip()
            continue

        if fence_match:
            in_fence = True
            fence_char = fence_match.group(1)[0]
            prev_blank = False
            continue

        atx = _ATX_RE.match(line)
        if atx:
            results.append((idx + 1, len(atx.group(1))))
            prev_blank = False
            continue

        # Setext underline closes the (non-blank) text line immediately above.
        # Requiring a non-blank predecessor avoids treating a thematic break
        # (``---``), which the renderer surrounds with blank lines, as a heading.
        if not prev_blank and _SETEXT_RE.match(line):
            level = 1 if line.lstrip()[0] == "=" else 2
            results.append((idx, level))  # idx == 1-based number of previous line
            prev_blank = False
            continue

        prev_blank = not line.strip()

    return results


def map_sections_to_lines(sections: list[Section], markdown_text: str) -> list[int | None]:
    """Assign a 1-based output line number to each section's heading.

    Parameters
    ----------
    sections : list of Section
        Sections to map. Pass the full-range list
        (``get_all_sections(doc, min_level=1, max_level=6)``) so there is one
        section per heading, matching the rendered output one-to-one.
    markdown_text : str
        Markdown rendering of the same document.

    Returns
    -------
    list of (int or None)
        Parallel to ``sections``; the heading's 1-based line number, or ``None``
        when it cannot be located unambiguously.

    """
    detected = find_heading_lines(markdown_text)

    # Fast path: the renderer emits exactly one heading construct per Heading
    # node, so counts normally match and ordering is authoritative.
    if len(detected) == len(sections):
        return [line for line, _level in detected]

    # Fallback: counts diverged (e.g. setext ambiguity or an unexpected
    # detection). Align greedily by the heading-level sequence; unmatched
    # sections get None rather than a wrong number.
    return _align_by_level([s.level for s in sections], detected)


def _align_by_level(section_levels: list[int], detected: list[tuple[int, int]]) -> list[int | None]:
    """Greedily align section levels to detected (line, level) pairs in order."""
    result: list[int | None] = [None] * len(section_levels)
    cursor = 0
    for i, level in enumerate(section_levels):
        j = cursor
        while j < len(detected) and detected[j][1] != level:
            j += 1
        if j < len(detected):
            result[i] = detected[j][0]
            cursor = j + 1
    return result


def number_text_lines(text: str, numbers: list[int | None] | None = None, *, sep: str = ": ") -> str:
    """Prefix each line of ``text`` with a right-aligned line number.

    Parameters
    ----------
    text : str
        Text whose lines should be numbered.
    numbers : list of (int or None), optional
        Explicit line numbers, one per line of ``text``. When omitted, lines are
        numbered sequentially starting at 1. Supplying numbers lets callers show
        the *original* document line numbers for a non-contiguous selection; a
        ``None`` entry leaves that line unnumbered (e.g. a gap separator).
    sep : str, default ": "
        Separator placed between the number and the line content.

    Returns
    -------
    str
        Numbered text. The number column is padded so separators align.

    """
    if not text:
        return text

    lines = text.split("\n")
    if numbers is None:
        numbers = list(range(1, len(lines) + 1))

    width = max((len(str(n)) for n in numbers if n is not None), default=1)
    out: list[str] = []
    for line, number in zip(lines, numbers, strict=False):
        if number is None:
            out.append(line)
        else:
            out.append(f"{number:>{width}}{sep}{line}")
    return "\n".join(out)


__all__ = [
    "find_heading_lines",
    "map_sections_to_lines",
    "number_text_lines",
]
