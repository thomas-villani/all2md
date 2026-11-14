#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_heading_styles.py
"""How a PDF sets its headings, level by level: size, font, weight and color.

Word's built-in heading styles are 14pt and 13pt. A converted lease whose articles were
headed in 20pt Calibri Light came out with 14pt headings, so every page held more than
its source and the Word document ran a page short. Each heading's look is read from the
line it was printed on, and the look most of a level's headings share becomes that
level's style.

The space around a heading is part of its style too. Word's Heading 1 opens 24pt above
itself and its Title leaves 15pt below; a contract that set 4pt under its title and 18pt
above each article came out taller in Word than in print. The space is read from the
baselines of the body lines just above and below each heading, less what Word's own
line boxes already span. Word, measured on its own PDFs, sets a line's ascent above
its baseline and its descent below, puts a line spacing's extra under the text, and
leaves the larger of one paragraph's space after and the next one's space before
between them, not their sum.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Protocol

#: PyMuPDF's span flag for a bold font.
_BOLD_FLAG = 16
#: Darkest channel value still read as black: print's "rich black" (``231F20``) is black.
_BLACK_CHANNEL = 0x40
#: Lightest luminance a heading color may have. A heading printed white sat on a shaded
#: band Word does not draw, and would be invisible on the page.
_MAX_LUMINANCE = 0.75
#: Font sizes within this many points of the body size are body text.
_BODY_SIZE_TOLERANCE = 0.25
#: Most space, in points, read as a heading's own: more is a figure or table between.
_MAX_SPACE = 72.0
#: Least space, in points, a measurement may come to before it is read as none. A little
#: below zero is rounding between two fonts' metrics; much below is a misread neighbor.
_MIN_SPACE = -3.0
#: Word's own paragraph defaults, which the body keeps when the PDF's was not measured:
#: 1.15 lines and 10pt after.
_WORD_LINE_SPACING = 1.15
_WORD_SPACE_AFTER = 10.0


class _Line(Protocol):
    """A line of text as the body style sampler records it."""

    @property
    def size(self) -> float: ...

    @property
    def font(self) -> str: ...

    @property
    def baseline(self) -> float: ...

    @property
    def x0(self) -> float: ...

    @property
    def x1(self) -> float: ...


def heading_font(spans: Iterable[dict]) -> dict[str, Any] | None:
    """Return the look of a heading's line: its commonest span's size, font, weight and color."""
    weights: Counter[tuple[float, str, bool, int]] = Counter()
    for span in spans:
        text = (span.get("text") or "").strip()
        if not text or not span.get("size"):
            continue
        font = span.get("font") or ""
        bold = bool(int(span.get("flags") or 0) & _BOLD_FLAG) or "bold" in font.lower()
        weights[(round(float(span["size"]) * 2) / 2, font, bold, int(span.get("color") or 0))] += len(text)
    if not weights:
        return None
    (size, font, bold, color), _ = weights.most_common(1)[0]
    look: dict[str, Any] = {"size": size, "font": font, "bold": bold, "color": color}
    placed = [span for span in spans if (span.get("text") or "").strip() and span.get("origin") and span.get("bbox")]
    if placed:
        look["baseline"] = round(float(placed[0]["origin"][1]), 2)
        look["x0"] = round(min(float(span["bbox"][0]) for span in placed), 2)
        look["x1"] = round(max(float(span["bbox"][2]) for span in placed), 2)
    return look


def measure_heading_styles(
    headings: Iterable[tuple[int, dict[str, Any]] | tuple[int, dict[str, Any], Sequence[_Line]]],
    body_style: dict[str, Any] | None,
    family: Callable[[str], str],
    metrics: Callable[[str], tuple[float, float] | None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return each heading level's style, for the ``heading_styles`` metadata.

    ``headings`` holds each heading's final level, the look recorded for it and,
    optionally, the lines of its page; a look without a size (a bold title at the body
    size) takes the body's size and font. ``family`` turns a PDF font name into the
    family Word knows it by, and ``metrics`` into the shares of the size its lines take
    above and below the baseline, which the space around each heading is read with.
    """
    looks: dict[int, Counter[tuple[float, str, bool, int]]] = {}
    spaces: dict[int, tuple[list[float], list[float]]] = {}
    for level, look, *rest in headings:
        size = look.get("size") or (body_style or {}).get("size")
        font = look.get("font")
        name = family(font) if font else (body_style or {}).get("font")
        if not size or not name:
            continue
        key = (float(size), str(name), bool(look.get("bold")), int(look.get("color") or 0))
        looks.setdefault(level, Counter())[key] += 1
        if rest and metrics is not None and font and body_style:
            before, after = _space_around(look, rest[0], body_style, metrics)
            befores, afters = spaces.setdefault(level, ([], []))
            if before is not None:
                befores.append(before)
            if after is not None:
                afters.append(after)
    styles: dict[str, dict[str, Any]] = {}
    for level in sorted(looks):
        (size, name, bold, color), _ = looks[level].most_common(1)[0]
        style: dict[str, Any] = {"size": size, "font": name, "bold": bold}
        if _visible_color(color):
            style["color"] = f"{color:06X}"
        befores, afters = spaces.get(level, ([], []))
        if befores:
            style["space_before"] = _settle(befores)
        if afters:
            style["space_after"] = _settle(afters)
        styles[str(level)] = style
    return styles


def _space_around(
    look: dict[str, Any],
    lines: Sequence[_Line],
    body_style: dict[str, Any],
    metrics: Callable[[str], tuple[float, float] | None],
) -> tuple[float | None, float | None]:
    """Return the space a heading's style must set above and below it to sit where it was printed.

    Between two baselines Word leaves the upper line's descent, the extra its line
    spacing adds under it, the larger of its space after and the lower line's space
    before, and the lower line's ascent. The heading is set single-spaced, and the body
    has no space before. A space before no larger than the body's space after does not
    show, and is read as the body's. A neighbor that is not body text (another heading,
    a caption) says nothing.
    """
    baseline, left, right = look.get("baseline"), look.get("x0"), look.get("x1")
    size, font = look.get("size"), look.get("font")
    body_size = body_style.get("size")
    if baseline is None or left is None or right is None or not size or not font or not body_size:
        return None, None
    own = metrics(font)
    if own is None:
        return None, None

    def beside(line: _Line) -> bool:
        return min(line.x1, right) - max(line.x0, left) > 0

    def body(line: _Line) -> bool:
        return abs(line.size - body_size) <= _BODY_SIZE_TOLERANCE

    multiple = body_style.get("line_spacing") or _WORD_LINE_SPACING
    space_after_body = body_style.get("space_after")
    if space_after_body is None:
        space_after_body = _WORD_SPACE_AFTER

    before = after = None
    above = [line for line in lines if line.baseline < baseline - 0.5 * size and beside(line)]
    if above:
        line = max(above, key=lambda each: each.baseline)
        fit = metrics(line.font)
        if body(line) and fit is not None:
            extra = (multiple - 1) * (fit[0] + fit[1]) * line.size
            before = (baseline - line.baseline) - fit[1] * line.size - extra - own[0] * size
            if before is not None and before < space_after_body + 1.0:
                before = space_after_body
    # A heading set on two lines: its second line sits below its first.
    last = baseline
    below = sorted(
        (line for line in lines if line.baseline > baseline + 0.3 * size and beside(line)),
        key=lambda line: line.baseline,
    )
    for line in below:
        if abs(line.size - size) <= _BODY_SIZE_TOLERANCE and line.font == font and line.baseline - last <= 2 * size:
            last = line.baseline
            continue
        fit = metrics(line.font)
        if body(line) and fit is not None:
            after = (line.baseline - last) - own[1] * size - fit[0] * line.size
        break
    return _sane(before), _sane(after)


def _sane(space: float | None) -> float | None:
    if space is None or not _MIN_SPACE <= space <= _MAX_SPACE:
        return None
    return max(space, 0.0)


def _settle(spaces: list[float]) -> float:
    """Return the space most of a level's headings share, as a whole or half point."""
    buckets = Counter(round(space) for space in spaces)
    mode = buckets.most_common(1)[0][0]
    space = statistics.median(each for each in spaces if abs(each - mode) <= 1.5)
    return float(round(space)) if abs(space - round(space)) <= 0.3 else round(space * 2) / 2


def _visible_color(color: int) -> bool:
    """Whether a heading color is worth naming: not black, and dark enough to read on white."""
    red, green, blue = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    if max(red, green, blue) <= _BLACK_CHANNEL:
        return False
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255 <= _MAX_LUMINANCE
