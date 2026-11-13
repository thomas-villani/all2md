#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_page_breaks.py
"""Pages a PDF's author ended on purpose: the page breaks to keep in Word.

A lease's signature block closed its first page and Article 2 opened the next, because
its author put a page break there. Converted to Word, the article ran on below the
signatures, the document came out a page short, and every later page broke in a
different place.

A page that ends early is not always a page break. A word processor moves to the next
page whatever does not fit: a figure or table row that does not fit, a paragraph's last
line that would be left alone (widow control), a heading that would be parted from the
first lines of its section (keep with next). So a page ends early *on purpose* only when
what opens the next page would have fit in the space left: the first three lines of text
(a heading and the two lines Word keeps with it, or a paragraph's opening that would not
leave one line behind), or a figure or table that opens the page, whole.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

#: Least room, as a share of the page height, a page must end with to have ended on purpose.
#: Less is within the ragged ends of pages broken by a print engine without widow control.
MIN_ROOM_SHARE = 0.1
#: Lines of text a word processor would move together to the next page: a heading and the
#: two lines it is kept with, or the first lines of a paragraph that cannot leave one behind.
KEPT_TOGETHER_LINES = 3


@dataclass(frozen=True)
class PageExtent:
    """Where a page's body content starts and stops, and how tall its opening is."""

    top: float
    bottom: float
    #: Height from ``top`` that would have to move as one: see :data:`KEPT_TOGETHER_LINES`.
    opening: float
    #: Typical distance between two lines of text on the page.
    line_pitch: float


def page_extent(
    blocks: Sequence[dict],
    regions: Sequence[tuple[float, float, float, float]] = (),
    page_height: float | None = None,
) -> PageExtent | None:
    """Measure a page's body from its text blocks and its image, figure and table regions.

    ``blocks`` are the page's body text blocks (running headers and footers already
    taken out); ``regions`` are the boxes of whatever does not split across a page.
    Anything outside ``page_height`` is off the page, and not measured.
    """

    def on_page(top: float, bottom: float) -> bool:
        return bottom > top and top >= 0 and (page_height is None or bottom <= page_height)

    lines: list[tuple[float, float]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            bbox = line.get("bbox")
            if bbox and any((span.get("text") or "").strip() for span in line.get("spans") or []):
                if on_page(float(bbox[1]), float(bbox[3])):
                    lines.append((float(bbox[1]), float(bbox[3])))
    boxes = [(float(region[1]), float(region[3])) for region in regions if on_page(region[1], region[3])]
    if not lines and not boxes:
        return None
    # Lines that share a baseline (a list marker beside its text, table-like columns)
    # count once.
    rows: list[tuple[float, float]] = []
    for top, bottom in sorted(lines):
        if rows and top < rows[-1][1] - 0.5 * (rows[-1][1] - rows[-1][0]):
            rows[-1] = (rows[-1][0], max(rows[-1][1], bottom))
        else:
            rows.append((top, bottom))
    top = min([row[0] for row in rows] + [box[0] for box in boxes])
    bottom = max([row[1] for row in rows] + [box[1] for box in boxes])

    first_box = min(boxes, default=None)
    if first_box is not None and (not rows or first_box[0] <= rows[0][0]):
        # A figure or table opens the page: it moves whole, and alone.
        opening = first_box[1]
    else:
        opening = rows[min(KEPT_TOGETHER_LINES, len(rows)) - 1][1]
        # A figure or table that starts before the opening lines end moves with them, whole.
        for box_top, box_bottom in boxes:
            if box_top <= opening:
                opening = max(opening, box_bottom)
    pitches = sorted(later[0] - earlier[0] for earlier, later in pairwise(rows) if later[0] > earlier[0])
    pitch = pitches[len(pitches) // 2] if pitches else (rows[0][1] - rows[0][0] if rows else 12.0)
    return PageExtent(top=top, bottom=bottom, opening=opening - top, line_pitch=pitch)


def body_bottom(extents: Sequence[PageExtent]) -> float | None:
    """Where the body runs down to: the upper median of the pages' bottoms.

    Not the lowest: one page whose text runs into the footer, or a print engine's ragged
    page ends, would make every other page look short. On a document whose pages mostly
    run full, the upper median is the bottom margin.
    """
    if not extents:
        return None
    bottoms = sorted(extent.bottom for extent in extents)
    return bottoms[len(bottoms) // 2]


def ends_on_purpose(previous: PageExtent, following: PageExtent, body_bottom: float, page_height: float) -> bool:
    """Whether ``previous`` ended early with room for ``following``'s opening: a page break.

    ``body_bottom`` is where the body may run to on the previous page (the bottom margin).
    The opening needs its own height and the line pitch for the gap above it; one more
    line of room is asked for, so that measuring slack never reads as a break, and never
    less than a tenth of the page.
    """
    room = body_bottom - previous.bottom
    needed = following.opening + 2 * max(previous.line_pitch, following.line_pitch)
    return room > max(needed, MIN_ROOM_SHARE * page_height)
