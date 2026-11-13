#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_furniture.py
"""Running headers and footers: find them, take them out of the body, keep their text.

Word prints a document's header and footer on every page, in the margin, at the same
place each time. Read page by page they became body paragraphs -- the header above
page 1's title, a header and a footer between every two pages of text. The functions
here pick that furniture out by repetition and position alone (a line on one page is
never furniture, however much it looks like a page number), so the parser can move
it out of the body and into the document metadata, where a renderer that knows about
page headers -- DOCX -- can put it back in one.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

#: Fractions of the page height inside which a running header (top) or footer (bottom)
#: must lie entirely. Word's header and footer, and a journal's running heads, sit within
#: the outer 6-8% of the page. A fifth of the page (the zone ``auto_trim_headers_footers``
#: uses) reached the caption and header row of a table continued at the top of each page,
#: which repeat in place just as a running head does.
RUNNING_HEADER_ZONE_FRACTION = 0.1
RUNNING_FOOTER_ZONE_FRACTION = 0.9

#: How far, in points, a running line may drift between pages and still be the same.
#: Real furniture is anchored to the page edge; body text that recurs moves with the flow.
RUNNING_LINE_TOLERANCE = 5.0

#: Placeholders a running-line template uses for the page number and the page count.
PAGE_PLACEHOLDER = "{page}"
PAGES_PLACEHOLDER = "{pages}"

_DIGITS = re.compile(r"\d+")


#: Gap between two spans, as a share of the font size, that reads as a word space.
SPAN_SPACE_FRACTION = 0.15


def _line_text(line: dict) -> str:
    """Join a line's spans as printed: a space only where the spans stand apart.

    Small capitals set each capital as its own span ("E" + "NGINEERING"); joining every
    span with a space split the word, and the running text kept in the metadata no
    longer matched what the body extraction prints.
    """
    out = ""
    previous: dict | None = None
    for span in line.get("spans") or []:
        text = span.get("text", "")
        if previous is not None and out and not out[-1].isspace() and text[:1] and not text[0].isspace():
            gap = span.get("bbox", (0, 0, 0, 0))[0] - previous.get("bbox", (0, 0, 0, 0))[2]
            size = max(float(span.get("size") or 0), float(previous.get("size") or 0), 1.0)
            if gap > SPAN_SPACE_FRACTION * size:
                out += " "
        out += text
        previous = span
    return out


def block_text(block: dict) -> str:
    """Return a text block's text, its lines joined by single spaces."""
    if block.get("type", 0) != 0:
        return ""
    return " ".join(" ".join(_line_text(line) for line in block.get("lines") or []).split())


def running_key(text: str) -> str:
    """Key a running line by what stays the same from page to page (digit runs collapsed)."""
    return _DIGITS.sub("#", text).strip()


def _edge_offset(bbox: Sequence[float], zone: str, page_height: float) -> float:
    """Distance of a block from the page edge its zone hangs from.

    A footer is measured up from the bottom edge, not down from the top, so a landscape
    page among portrait ones still sets its footer at the same offset.
    """
    return bbox[1] if zone == "header" else page_height - bbox[3]


def _zone_of(bbox: Sequence[float], page_height: float) -> str | None:
    if bbox[3] <= page_height * RUNNING_HEADER_ZONE_FRACTION:
        return "header"
    if bbox[1] >= page_height * RUNNING_FOOTER_ZONE_FRACTION:
        return "footer"
    return None


@dataclass
class RunningFurniture:
    """The running lines a document repeats, by zone: key -> (min offset, max offset)."""

    lines: dict[str, dict[str, tuple[float, float]]]
    removed: dict[str, list[tuple[int, str]]] = field(default_factory=lambda: {"header": [], "footer": []})

    def _matches(self, block: dict, zone: str, page_height: float) -> bool:
        text = block_text(block)
        span = self.lines[zone].get(running_key(text)) if text else None
        if span is None:
            return False
        offset = _edge_offset(block["bbox"], zone, page_height)
        return span[0] - RUNNING_LINE_TOLERANCE <= offset <= span[1] + RUNNING_LINE_TOLERANCE

    def take(
        self, blocks: list[dict], page_number: int, page_height: float, keep_out: Iterable[Sequence[float]] = ()
    ) -> list[dict]:
        """Return ``blocks`` without this page's running lines, recording the lines taken.

        A matching block is taken only when it is outermost -- nothing but other running
        lines between it and the page edge -- and lies in no ``keep_out`` region (a
        table's): Word repeats a split table's header row at the same place on every
        page, and that row is body, not furniture.
        """
        regions = [tuple(region) for region in keep_out]
        taken: dict[int, str] = {}
        for zone in ("header", "footer"):
            candidates = []
            for i, block in enumerate(blocks):
                bbox = block.get("bbox")
                if not bbox or not block_text(block) or _zone_of(bbox, page_height) != zone:
                    continue
                if any(_overlaps(bbox, region) for region in regions):
                    continue
                if self._matches(block, zone, page_height):
                    candidates.append(i)
            for i in candidates:
                if self._has_text_toward_edge(blocks, i, zone, set(candidates)):
                    continue
                taken[i] = zone
        if not taken:
            return blocks
        for zone in ("header", "footer"):
            picked = sorted(
                (i for i, z in taken.items() if z == zone), key=lambda i: (blocks[i]["bbox"][1], blocks[i]["bbox"][0])
            )
            if picked:
                self.removed[zone].append((page_number, " ".join(block_text(blocks[i]) for i in picked)))
        return [block for i, block in enumerate(blocks) if i not in taken]

    @staticmethod
    def _has_text_toward_edge(blocks: list[dict], index: int, zone: str, running: set[int]) -> bool:
        bbox = blocks[index]["bbox"]
        for j, other in enumerate(blocks):
            if j == index or j in running or not other.get("bbox") or not block_text(other):
                continue
            if zone == "header" and other["bbox"][3] <= bbox[1]:
                return True
            if zone == "footer" and other["bbox"][1] >= bbox[3]:
                return True
        return False

    def metadata(self, total_pages: int) -> dict[str, object]:
        """Return the running lines taken, as document metadata.

        ``page_header`` / ``page_footer`` hold the commonest line of each zone, page
        numbers as placeholders; any other distinct line taken from that zone (an even
        page's running head beside an odd page's) is kept in ``page_header_alternates`` /
        ``page_footer_alternates``, so no text taken from the body is dropped.
        ``page_number_start`` is the number printed on page 1 when the page numbers run
        from something other than 1.
        """
        out: dict[str, object] = {}
        start: int | None = None
        for zone in ("footer", "header"):
            found = running_templates(self.removed[zone], total_pages)
            if not found:
                continue
            out[f"page_{zone}"] = found[0][0]
            if len(found) > 1:
                out[f"page_{zone}_alternates"] = [template for template, _ in found[1:]]
            if start is None:
                start = next((first for _, first in found if first is not None), None)
        if start is not None and start != 1:
            out["page_number_start"] = start
        return out


def _overlaps(bbox: Sequence[float], region: Sequence[float]) -> bool:
    width = min(bbox[2], region[2]) - max(bbox[0], region[0])
    height = min(bbox[3], region[3]) - max(bbox[1], region[1])
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    return width > 0 and height > 0 and area > 0 and width * height > 0.5 * area


def _inner_offset(bbox: Sequence[float], zone: str, page_height: float) -> float:
    """Distance from the zone's page edge to the block's far side (its body-facing edge)."""
    return bbox[3] if zone == "header" else page_height - bbox[1]


#: Clearance, in points, a running line must keep from where the body starts.
BODY_CLEARANCE = 1.0


def detect_running_furniture(
    pages: Sequence[tuple[list[dict], float]], min_occurrences: int
) -> RunningFurniture | None:
    """Find the lines a document repeats at the same place in its top or bottom margin.

    ``pages`` holds each sampled page's text blocks and height. A line is running when
    its digit-collapsed text sits in the same zone, at the same offset from that zone's
    page edge (within :data:`RUNNING_LINE_TOLERANCE`), on at least ``min_occurrences``
    of the pages, at most once per page -- and lies wholly outside the body.

    Where the body starts is measured, not assumed: on each page, the first text that
    is not itself a repeated line, from the top (or the last, from the bottom), and the
    lower quartile of that across the pages. A table carried onto the next page repeats
    its "Table 1. Continued" caption in place on every continuation page, which is
    repetition and anchoring both; what gives it away is that it starts where the body
    starts, while the running head above it ends well clear.
    """
    seen: dict[str, dict[str, list[tuple[float, float]]]] = {"header": {}, "footer": {}}
    for blocks, height in pages:
        on_page: set[tuple[str, str]] = set()
        for block in blocks:
            bbox = block.get("bbox")
            text = block_text(block) if bbox else ""
            zone = _zone_of(bbox, height) if bbox and text else None
            if bbox is None or zone is None:
                continue
            key = running_key(text)
            if not key or (zone, key) in on_page:
                continue
            on_page.add((zone, key))
            seen[zone].setdefault(key, []).append((_edge_offset(bbox, zone, height), _inner_offset(bbox, zone, height)))

    def anchored(spots: list[tuple[float, float]], floor: int) -> bool:
        offsets = [o for o, _ in spots]
        return len(spots) >= floor and max(offsets) - min(offsets) <= RUNNING_LINE_TOLERANCE

    lines: dict[str, dict[str, tuple[float, float]]] = {"header": {}, "footer": {}}
    for zone, keys in seen.items():
        # Anything repeated in place on two pages is left out of the body edge, even if
        # too rare to be taken: an odd page's running head, absent from the cover page,
        # can fall one short of the floor, and counted as body it put the body's top
        # edge above every running line, so the even page's head was kept in too.
        body_edge = _body_edge(pages, zone, {key for key, spots in keys.items() if anchored(spots, 2)})
        for key, spots in keys.items():
            if not anchored(spots, min_occurrences):
                continue
            if body_edge is not None and max(inner for _, inner in spots) > body_edge - BODY_CLEARANCE:
                continue
            offsets = [o for o, _ in spots]
            lines[zone][key] = (min(offsets), max(offsets))
    if not lines["header"] and not lines["footer"]:
        return None
    return RunningFurniture(lines)


def _body_edge(pages: Sequence[tuple[list[dict], float]], zone: str, running: set[str]) -> float | None:
    """Where the body starts, as an offset from ``zone``'s page edge (lower quartile)."""
    edges = []
    for blocks, height in pages:
        offsets = [
            _edge_offset(block["bbox"], zone, height)
            for block in blocks
            if block.get("bbox") and (text := block_text(block)) and running_key(text) not in running
        ]
        if offsets:
            edges.append(min(offsets))
    if not edges:
        return None
    edges.sort()
    return edges[len(edges) // 4]


def running_templates(occurrences: Sequence[tuple[int, str]], total_pages: int) -> list[tuple[str, int | None]]:
    """Return each distinct running line in ``occurrences``, commonest first.

    Occurrences are grouped by their digit-collapsed text; each group gives one
    ``(template, page_number_start)`` pair (see :func:`running_template`).
    """
    groups: dict[str, list[tuple[int, str]]] = {}
    for page, text in occurrences:
        groups.setdefault(running_key(text), []).append((page, text))
    out: list[tuple[str, int | None]] = []
    for group in sorted(groups.values(), key=len, reverse=True):
        found = running_template(group, total_pages)
        if found is not None and found[0] not in (template for template, _ in out):
            out.append(found)
    return out


def running_template(occurrences: Sequence[tuple[int, str]], total_pages: int) -> tuple[str, int | None] | None:
    """Return the running text ``occurrences`` share, page numbers as placeholders.

    ``occurrences`` holds (1-based page number, text) pairs; the commonest
    digit-collapsed form is used. In it, a digit run that steps with the page -- the
    page number plus the same offset on every page it was taken from -- becomes
    ``{page}``, and the second value returned is the number it gives page 1 (a report
    printed 131 on its first page starts at 131); one that equals the page count on
    every page becomes ``{pages}``. Any other digits are kept as printed on the first
    page. A run that would number page 1 below zero is kept as printed too.
    """
    if not occurrences:
        return None
    key, _ = Counter(running_key(text) for _, text in occurrences).most_common(1)[0]
    chosen = [(page, text) for page, text in occurrences if running_key(text) == key]
    runs = [[int(m.group()) for m in _DIGITS.finditer(text)] for _, text in chosen]
    pages = [page for page, _ in chosen]
    several = len(set(pages)) > 1
    first = chosen[0][1]
    pieces: list[str] = []
    start: int | None = None
    last = 0
    for i, match in enumerate(_DIGITS.finditer(first)):
        values = [run[i] for run in runs]
        offsets = {value - page for value, page in zip(values, pages, strict=True)}
        pieces.append(first[last : match.start()])
        if several and len(offsets) == 1 and 1 + next(iter(offsets)) >= 0 and start is None:
            pieces.append(PAGE_PLACEHOLDER)
            start = 1 + next(iter(offsets))
        elif several and total_pages > 1 and all(value == total_pages for value in values):
            pieces.append(PAGES_PLACEHOLDER)
        else:
            pieces.append(match.group())
        last = match.end()
    pieces.append(first[last:])
    template = "".join(pieces).strip()
    return (template, start) if template else None
