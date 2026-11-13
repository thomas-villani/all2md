#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_body_style.py
"""A PDF's body text style: font, size, line spacing and the space between paragraphs.

A PDF converted to Word came out in Calibri 11 with 1.15 line spacing and 10pt between
paragraphs whatever it was set in, so a lease set in Garamond 12 ran a page shorter in
Word than in the PDF, and a 10pt Arial report a page longer. All four are recoverable:

* the font and size are on every span, and the commonest by character count is the body;
* the line spacing is the distance between two lines' baselines in one paragraph, read
  as a multiple of the font's own line height, which is in the embedded font's ``hhea``
  table, as Word sets a "multiple" from it;
* the space after a paragraph is the extra distance between the last line of one
  paragraph and the first of the next.

Only text the converter keeps as body is sampled: table cells (Word's tables are
single-spaced), running headers and footers, and OCR pages are left out.
"""

from __future__ import annotations

import re
import statistics
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Any

#: Line spacings Word offers or sets by default, in 240ths of a line: single, Word
#: 2013's 1.08, 1.1, 1.15, Word 2024's 1.16, 1.2, 1.5 and double.
COMMON_LINE_SPACINGS = (240, 259, 264, 276, 278, 288, 360, 480)
#: How close, in 240ths of a line, a measured spacing must be to a common one to be read as it.
LINE_SPACING_SNAP = 2.5
#: Fewest same-paragraph line pairs a line spacing is read from.
MIN_LINE_PAIRS = 3
#: Fewest paragraph boundaries a space between paragraphs is read from.
MIN_PARAGRAPH_GAPS = 2
#: Fewest characters of body text a font and size are read from.
MIN_BODY_CHARACTERS = 200
#: Font sizes within this many points of the body size are body text.
SIZE_TOLERANCE = 0.25

#: Words in a PostScript name's style suffix that name a style, not a family.
_STYLE_WORDS = {"Bold", "Italic", "Oblique", "Regular", "Roman", "Book", "Normal", "It", "Bd", "Regu", "Ital"}
#: A table of contents' dot leaders and a form's fill-in rules: such lines are never body text.
_LEADER = re.compile(r"(?:\.\s?){5,}|\u2026{3,}|_{5,}")
#: Natural line heights (ascender + descender + line gap, from ``hhea``) of fonts Word
#: documents are commonly set in, as a share of the font size. A PDF that does not embed
#: its font leaves only PyMuPDF's ascender and descender, which leave out the line gap
#: Word adds: Times New Roman reads as 1.107 against the 1.150 Word sets lines from.
KNOWN_LINE_HEIGHTS = {
    "Arial": 1.1499,
    "Arial Black": 1.4102,
    "Arial Narrow": 1.1475,
    "Book Antiqua": 1.2056,
    "Bookman Old Style": 1.1738,
    "Calibri": 1.2207,
    "Calibri Light": 1.2207,
    "Cambria": 1.1724,
    "Candara": 1.2207,
    "Century": 1.2021,
    "Century Gothic": 1.2261,
    "Century Schoolbook": 1.2021,
    "Consolas": 1.1709,
    "Constantia": 1.2207,
    "Corbel": 1.2075,
    "Courier New": 1.1328,
    "Franklin Gothic Book": 1.1338,
    "Garamond": 1.125,
    "Georgia": 1.1362,
    "Gill Sans MT": 1.1597,
    "Lucida Console": 1.0,
    "Lucida Sans": 1.1777,
    "Palatino Linotype": 1.3491,
    "Segoe UI": 1.3301,
    "Tahoma": 1.207,
    "Times New Roman": 1.1499,
    "Trebuchet MS": 1.1611,
    "Verdana": 1.2153,
}
_BASE_14 = {"Times": "Times New Roman", "Helvetica": "Arial", "Courier": "Courier New"}


@dataclass(frozen=True)
class _Line:
    block: int
    characters: int
    size: float
    font: str
    baseline: float
    x0: float
    x1: float
    #: Holds a span in another font family (a checkbox or bullet glyph), whose own
    #: line height can open the line up: it says what the font is, not the spacing.
    mixed: bool = False


def _strip_subset(name: str) -> str:
    prefix, plus, rest = name.partition("+")
    return rest if plus and len(prefix) == 6 and prefix.isupper() else name


def family_from_postscript(name: str) -> str:
    """Read a font family from a PostScript font name: ``TimesNewRomanPS-BoldMT`` is Times New Roman."""
    name = _strip_subset(name)
    base, _, suffix = name.replace(",", "-").partition("-")
    base = re.sub(r"(?:PSMT|PS|MT)$", "", base) or base
    words = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", base).split()
    # A style run into the name itself (``FreeMonoBold``) is not part of the family.
    while len(words) > 1 and words[-1] in _STYLE_WORDS - {"Roman", "Book", "Normal"}:
        words.pop()
    family = " ".join(words) or name
    suffix = re.sub(r"(?:PSMT|MT)$", "", suffix)
    extra = [word for word in re.findall(r"[A-Z][a-z]*|[0-9]+", suffix) if word not in _STYLE_WORDS]
    if extra:
        family = f"{family} {' '.join(extra)}"
    return _BASE_14.get(family, family)


def _font_tables(buffer: bytes) -> dict[str, tuple[int, int]] | None:
    if len(buffer) < 12 or buffer[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
        return None
    (count,) = struct.unpack(">H", buffer[4:6])
    tables = {}
    for index in range(count):
        start = 12 + 16 * index
        if start + 16 > len(buffer):
            return None
        tag, _, offset, length = struct.unpack(">4sIII", buffer[start : start + 16])
        tables[tag.decode("latin-1")] = (offset, length)
    return tables


def font_line_height(buffer: bytes) -> float | None:
    """Return a font's natural line height as a share of its size, from its ``hhea`` table.

    Word's "multiple" line spacing multiplies this: ascender plus descender plus line gap.
    """
    tables = _font_tables(buffer)
    if not tables or "hhea" not in tables or "head" not in tables:
        return None
    head, hhea = tables["head"][0], tables["hhea"][0]
    try:
        (units,) = struct.unpack(">H", buffer[head + 18 : head + 20])
        ascender, descender, gap = struct.unpack(">hhh", buffer[hhea + 4 : hhea + 10])
    except struct.error:
        return None
    if not units:
        return None
    height = (ascender - descender + gap) / units
    return height if 0.8 <= height <= 2.0 else None


def font_family(buffer: bytes) -> str | None:
    """Return the family name (``name`` table ID 1) a font file gives itself."""
    tables = _font_tables(buffer)
    if not tables or "name" not in tables:
        return None
    offset = tables["name"][0]
    try:
        _, count, strings = struct.unpack(">HHH", buffer[offset : offset + 6])
        for index in range(count):
            start = offset + 6 + 12 * index
            platform, _, _, name_id, length, at = struct.unpack(">HHHHHH", buffer[start : start + 12])
            if name_id == 1 and platform == 3:
                raw = buffer[offset + strings + at : offset + strings + at + length]
                family = raw.decode("utf-16-be", "replace").strip()
                return family or None
    except struct.error:
        return None
    return None


class BodyStyleSampler:
    """Collect body text lines page by page, then read the body style from them."""

    def __init__(self) -> None:
        self._pages: list[list[_Line]] = []
        self._fonts: dict[str, int] = {}
        self._metrics: dict[str, float] = {}

    def add(self, blocks: list[dict], fonts: list[tuple[Any, ...]] | None = None) -> None:
        """Record one page's body blocks and, from ``page.get_fonts()``, its fonts' xrefs."""
        for entry in fonts if isinstance(fonts, (list, tuple)) else []:
            if len(entry) > 3 and isinstance(entry[3], str):
                self._fonts.setdefault(_strip_subset(entry[3]), entry[0])
        lines: list[_Line] = []
        for index, block in enumerate(blocks):
            if block.get("type") != 0:
                continue
            for line in block.get("lines") or []:
                if tuple(line.get("dir") or (1.0, 0.0)) != (1.0, 0.0):
                    continue
                weights: Counter[tuple[float, str]] = Counter()
                for span in line.get("spans") or []:
                    text = (span.get("text") or "").strip()
                    if text and span.get("size"):
                        weights[(round(float(span["size"]) * 2) / 2, span.get("font") or "")] += len(text)
                        if span.get("font") and "ascender" in span and "descender" in span:
                            self._metrics.setdefault(span["font"], span["ascender"] - span["descender"])
                if not weights or _LEADER.search("".join(span.get("text") or "" for span in line.get("spans") or [])):
                    continue
                (size, font), _ = weights.most_common(1)[0]
                family = family_from_postscript(font)
                mixed = any(family_from_postscript(other) != family for _, other in weights)
                spans = line["spans"]
                bbox = line.get("bbox") or (0, 0, 0, 0)
                origin = spans[0].get("origin")
                baseline = float(origin[1]) if origin else float(bbox[3])
                lines.append(_Line(index, sum(weights.values()), size, font, baseline, bbox[0], bbox[2], mixed))
        self._pages.append(lines)

    def measure(self, doc: Any) -> dict[str, Any] | None:
        """Return the body style, for the ``body_style`` metadata, or None when too little body text."""
        characters: Counter[tuple[float, str]] = Counter()
        for lines in self._pages:
            for line in lines:
                characters[(line.size, line.font)] += line.characters
        sizes: Counter[float] = Counter()
        for (size, _), count in characters.items():
            sizes[size] += count
        if sum(sizes.values()) < MIN_BODY_CHARACTERS:
            return None
        size = sizes.most_common(1)[0][0]
        fonts = Counter({font: count for (each, font), count in characters.items() if each == size})
        font = fonts.most_common(1)[0][0]

        buffer = self._font_buffer(doc, font)
        family = self.family(doc, font)
        style: dict[str, Any] = {"font": family, "size": size}

        # Each pair counts by its characters: a borderless table's narrow cells, often
        # set single-spaced, must not outvote the prose around it, nor a bullet glyph
        # on a line of its own the text beside it.
        same_paragraph: list[tuple[float, int]] = []
        across: list[tuple[float, int]] = []
        for lines in self._pages:
            for below, above in _vertical_neighbours(lines):
                if abs(below.size - size) > SIZE_TOLERANCE or abs(above.size - size) > SIZE_TOLERANCE:
                    continue
                if below.mixed or above.mixed:
                    continue
                distance = below.baseline - above.baseline
                weight = min(below.characters, above.characters)
                (same_paragraph if below.block == above.block else across).append((distance, weight))
        if len(same_paragraph) < MIN_LINE_PAIRS:
            return style
        pitch = _central(same_paragraph, 0.1, 0.3)
        height = (font_line_height(buffer) if buffer else None) or KNOWN_LINE_HEIGHTS.get(family)
        if height is None:
            height = self._metrics.get(font)
        if height:
            spacing = _snap_line_spacing(pitch / (height * size) * 240)
            if spacing is not None:
                style["line_spacing"] = round(spacing / 240, 4)
        # A block is not a paragraph: two paragraphs can share one, so the gap is looked
        # for between any two body lines, and no line pair inside a paragraph is that far apart.
        gaps = [
            (distance - pitch, weight)
            for distance, weight in same_paragraph + across
            if pitch + 1.0 < distance <= pitch + 2.5 * size
        ]
        flush = [(distance, weight) for distance, weight in across if abs(distance - pitch) <= 0.5]
        if len(gaps) >= MIN_PARAGRAPH_GAPS and sum(w for _, w in gaps) >= sum(w for _, w in flush):
            gap = _central(gaps, 1.0, 0.75)
            style["space_after"] = float(round(gap)) if abs(gap - round(gap)) <= 0.3 else round(gap * 2) / 2
        elif len(flush) >= MIN_LINE_PAIRS:
            style["space_after"] = 0.0
        return style

    def family(self, doc: Any, font: str) -> str:
        """Return the family Word knows a PDF font by: the embedded font's own, else its PostScript name's."""
        buffer = self._font_buffer(doc, font)
        family = font_family(buffer) if buffer else None
        # A subset font's name table can hold its PostScript name, prefix and all.
        if not family or "+" in family or " " not in family and re.search(r"[a-z][A-Z]|-", family):
            family = family_from_postscript(family or font)
        return family

    def _font_buffer(self, doc: Any, font: str) -> bytes | None:
        xref = self._fonts.get(font)
        if xref is None or doc is None:
            return None
        try:
            buffer = doc.extract_font(xref)[3]
        except Exception:
            return None
        return buffer or None


def _vertical_neighbours(lines: list[_Line]) -> list[tuple[_Line, _Line]]:
    """Pair each line with the nearest line above it that shares some of its width."""
    ordered = sorted(lines, key=lambda line: line.baseline)
    pairs = []
    for index, line in enumerate(ordered):
        for above in reversed(ordered[:index]):
            if above.baseline > line.baseline - 0.5 * line.size:
                continue
            if min(above.x1, line.x1) - max(above.x0, line.x0) > 0:
                pairs.append((line, above))
                break
    return pairs


def _central(values: list[tuple[float, int]], bucket: float, spread: float) -> float:
    """Return the median of the values near the heaviest, by weight, rounded to ``bucket``."""
    weights: Counter[float] = Counter()
    for value, weight in values:
        weights[round(value / bucket) * bucket] += weight
    mode = weights.most_common(1)[0][0]
    return statistics.median(value for value, _ in values if abs(value - mode) <= spread)


def _snap_line_spacing(value: float) -> float | None:
    """Read a measured spacing (240ths of a line) as the Word setting it was made with."""
    if not 200 <= value <= 720:
        return None
    # A tie goes to Word's current default.
    nearest = min(COMMON_LINE_SPACINGS, key=lambda common: (abs(common - value), common != 278))
    return float(nearest) if abs(nearest - value) <= LINE_SPACING_SNAP else float(round(value))
