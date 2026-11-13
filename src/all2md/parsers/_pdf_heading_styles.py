#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_heading_styles.py
"""How a PDF sets its headings, level by level: size, font, weight and color.

Word's built-in heading styles are 14pt and 13pt. A converted lease whose articles were
headed in 20pt Calibri Light came out with 14pt headings, so every page held more than
its source and the Word document ran a page short. Each heading's look is read from the
line it was printed on, and the look most of a level's headings share becomes that
level's style.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

#: PyMuPDF's span flag for a bold font.
_BOLD_FLAG = 16
#: Darkest channel value still read as black: print's "rich black" (``231F20``) is black.
_BLACK_CHANNEL = 0x40
#: Lightest luminance a heading color may have. A heading printed white sat on a shaded
#: band Word does not draw, and would be invisible on the page.
_MAX_LUMINANCE = 0.75


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
    return {"size": size, "font": font, "bold": bold, "color": color}


def measure_heading_styles(
    headings: Iterable[tuple[int, dict[str, Any]]],
    body_style: dict[str, Any] | None,
    family: Callable[[str], str],
) -> dict[str, dict[str, Any]]:
    """Return each heading level's style, for the ``heading_styles`` metadata.

    ``headings`` holds each heading's final level and the look recorded for it; a look
    without a size (a bold title at the body size) takes the body's size and font.
    ``family`` turns a PDF font name into the family Word knows it by.
    """
    looks: dict[int, Counter[tuple[float, str, bool, int]]] = {}
    for level, look in headings:
        size = look.get("size") or (body_style or {}).get("size")
        font = look.get("font")
        name = family(font) if font else (body_style or {}).get("font")
        if not size or not name:
            continue
        key = (float(size), str(name), bool(look.get("bold")), int(look.get("color") or 0))
        looks.setdefault(level, Counter())[key] += 1
    styles: dict[str, dict[str, Any]] = {}
    for level in sorted(looks):
        (size, name, bold, color), _ = looks[level].most_common(1)[0]
        style: dict[str, Any] = {"size": size, "font": name, "bold": bold}
        if _visible_color(color):
            style["color"] = f"{color:06X}"
        styles[str(level)] = style
    return styles


def _visible_color(color: int) -> bool:
    """Whether a heading color is worth naming: not black, and dark enough to read on white."""
    red, green, blue = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    if max(red, green, blue) <= _BLACK_CHANNEL:
        return False
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255 <= _MAX_LUMINANCE
