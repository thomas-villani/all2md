#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_page_setup.py
"""A PDF's page setup: paper size, orientation, margins, header and footer distance.

A PDF converted to Word came out on US Letter with one-inch margins whatever it was
printed on: an A4 lease ran three pages in the PDF and two in Word, and a landscape
financial summary came out portrait. The size is exact in the PDF. The margins are
not recorded anywhere, but where the body's text starts and stops says where they are,
and Word sets the first line of each page at the top margin and every line at the
left one.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from all2md.parsers._pdf_furniture import RunningFurniture, block_text, running_key

#: Margin values documents are actually set with, in points: eighth-inch steps from a
#: quarter inch to an inch and a half, and the whole and half centimetres in between.
COMMON_MARGINS = sorted({*(9.0 * n for n in range(2, 13)), *(28.3465 * cm for cm in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5))})
#: How close, in points, a measured margin must be to a common value to be read as it.
MARGIN_SNAP_TOLERANCE = 2.5


def _snap(value: float, tolerance: float = MARGIN_SNAP_TOLERANCE) -> float:
    """Read a measured margin as the common value it was set with.

    Text never crosses a margin, so a measurement is an upper bound: the first line's
    glyphs start a little below the top margin, the more so the larger the type. The
    measurement snaps *down* to the largest common value within ``tolerance`` of it.
    """
    below = [common for common in COMMON_MARGINS if common <= value + 0.5 and value - common <= tolerance]
    if below:
        return round(max(below), 2)
    return round(value * 2) / 2


#: Share of the first line's font size its glyphs may start below the top margin.
TOP_GLYPH_INSET = 0.3


def _quartile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def page_size(sizes: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """Return the commonest (width, height) among the pages, in points."""
    if not sizes:
        return None
    (width, height), _ = Counter((round(w, 1), round(h, 1)) for w, h in sizes).most_common(1)[0]
    return width, height


def measure_page_setup(
    sizes: Sequence[tuple[float, float]],
    pages: Sequence[tuple[list[dict], float, float]],
    furniture: RunningFurniture | None,
) -> dict[str, Any] | None:
    """Return the document's page setup, for the ``page_setup`` metadata.

    ``sizes`` holds every page's (width, height); ``pages`` holds a sample of pages as
    (text blocks, width, height). Margins are measured only on two or more sampled pages
    of the commonest size: on a single page a running header cannot be told from the
    body, and the top margin would land on it.
    """
    size = page_size(sizes)
    if size is None:
        return None
    width, height = size
    setup: dict[str, Any] = {"width": width, "height": height}
    if width > height:
        setup["orientation"] = "landscape"
    running = {key for zone in furniture.lines.values() for key in zone} if furniture else set()

    lefts: list[float] = []
    rights: list[float] = []
    tops: list[tuple[float, float]] = []
    bottoms: list[float] = []
    same_size = [page for page in pages if (round(page[1], 1), round(page[2], 1)) == size]
    for index, (blocks, page_width, page_height) in enumerate(same_size):
        body = [
            block
            for block in blocks
            if block.get("bbox") and (text := block_text(block)) and running_key(text) not in running
        ]
        if not body:
            continue
        lefts.append(min(block["bbox"][0] for block in body))
        rights.append(page_width - max(block["bbox"][2] for block in body))
        first = min(body, key=lambda block: block["bbox"][1])
        tops.append((first["bbox"][1], _first_size(first)))
        if index < len(same_size) - 1:
            bottoms.append(page_height - max(block["bbox"][3] for block in body))
    if len(lefts) >= 2:
        left = _snap(_quartile(lefts, 0.25))
        top_at, top_size = sorted(tops)[min(len(tops) - 1, len(tops) // 4)]
        top = _snap(top_at, max(MARGIN_SNAP_TOLERANCE, TOP_GLYPH_INSET * top_size))
        # The right margin mirrors the left unless text demonstrably runs further right.
        # Text that stops short proves nothing: ragged lines, a form's short fields and a
        # list's items all end well inside the margin. Text that runs past the mirror
        # does, and is then read to the nearest common value, either way, since a
        # justified line ends in a space whose box overshoots the margin by a point or two.
        right_measured = _quartile(rights, 0.25)
        if right_measured >= left - MARGIN_SNAP_TOLERANCE - 1.0:
            right = left
        else:
            nearest = min(COMMON_MARGINS, key=lambda common: abs(common - right_measured))
            right = round(nearest, 2) if abs(nearest - right_measured) <= 3.0 else round(right_measured * 2) / 2
        # The bottom mirrors the top unless text demonstrably runs lower. A page's text
        # stops short of the bottom margin by up to a line (a row or paragraph that did
        # not fit moves to the next page), so a measured bottom above the top margin's
        # mirror cannot be told from a larger margin, and is not taken for one.
        fullest = min(bottoms) if bottoms else None
        bottom = _snap(fullest) if fullest is not None and fullest < top - MARGIN_SNAP_TOLERANCE else top
        setup.update({"margin_top": top, "margin_bottom": bottom, "margin_left": left, "margin_right": right})
    if furniture is not None:
        header = [low for low, _ in furniture.lines["header"].values()]
        footer = [low for low, _ in furniture.lines["footer"].values()]
        if header:
            setup["header_distance"] = _snap(min(header))
        if footer:
            setup["footer_distance"] = _snap(min(footer))
    return setup


def _first_size(block: dict) -> float:
    """Font size of a block's first span, or a body size when it has none."""
    for line in block.get("lines") or []:
        for span in line.get("spans") or []:
            if span.get("size"):
                return float(span["size"])
    return 11.0
