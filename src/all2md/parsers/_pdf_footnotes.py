#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_footnotes.py
"""Footnotes in a PDF: the area below the separator rule, its notes, and their labels.

Word sets a page's footnotes below a short rule at the left margin (two inches, 144pt on any
paper), in a smaller size, each opening with its number set as a superscript; the reference in
the text is the same number, raised and small. Nothing in the PDF says "footnote", so all three
are read from the page: the rule, the notes below it, and the labels that open them.

The test is strict on purpose. A short rule low on a page with smaller text beneath it, every
line of which belongs to a note opened by a small label, is a footnote area; anything less is
left in the body, where it was before this module existed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median
from typing import Any

#: The separator is short: Word draws 144pt, a quarter of a Letter page's width. A rule this
#: share of the text width or less, and at least this long, can be one.
_SEPARATOR_MAX_SHARE = 0.45
_SEPARATOR_MIN_WIDTH = 36.0
#: A rule is a stroke or a hairline rectangle.
_SEPARATOR_MAX_HEIGHT = 2.0
#: How far the rule's left end may sit from the text's left margin.
_SEPARATOR_MARGIN_SLACK = 6.0
#: Footnotes live in the lower part of the page.
_SEPARATOR_MIN_DEPTH = 0.4
#: A label is a short token: a number, a letter or two, or a reference mark.
_LABEL = re.compile(r"^(?:\d{1,3}|[a-z]{1,2}|[ivx]{1,4}|[*\u2020\u2021\u00a7\u00b6#]{1,3})$")
#: A label is raised and small: at most this share of the note text's size.
_LABEL_MAX_SIZE_SHARE = 0.85
#: A line further than this many line heights below the note above it is not part of it.
_CONTINUATION_GAP = 1.0
#: A note's next line starts at the margin, give or take an indent.
_CONTINUATION_INDENT = 36.0


@dataclass
class Note:
    """One footnote: the label that opens it and the spans of each of its lines, label removed."""

    label: str
    lines: list[list[dict]] = field(default_factory=list)


@dataclass
class FootnoteArea:
    """A page's footnote area: where it starts and the notes in it, in order."""

    top: float
    notes: list[Note]
    #: Lines at the top of the area before any label: the end of a note begun on the page before.
    continued: list[list[dict]] = field(default_factory=list)


def _rows(lines: list[tuple[dict, list[dict]]]) -> list[tuple[list[dict], dict, list[dict]]]:
    """Join lines set side by side into rows: (member lines, a combined line, their inked spans).

    Word sets a footnote's label at an indent, raised, and its text at a tab stop, which PyMuPDF
    returns as two lines that overlap in height but share neither top nor bottom. A row's members
    are ordered left to right.
    """
    groups: list[list[tuple[dict, list[dict]]]] = []
    for item in lines:
        top, bottom = item[0]["bbox"][1], item[0]["bbox"][3]
        if groups:
            row_top = min(line["bbox"][1] for line, _ in groups[-1])
            row_bottom = max(line["bbox"][3] for line, _ in groups[-1])
            overlap = min(bottom, row_bottom) - max(top, row_top)
            if overlap > 0.5 * min(bottom - top, row_bottom - row_top):
                groups[-1].append(item)
                continue
        groups.append([item])
    rows: list[tuple[list[dict], dict, list[dict]]] = []
    for group in groups:
        group.sort(key=lambda item: item[0]["bbox"][0])
        members = [line for line, _ in group]
        box = (
            min(line["bbox"][0] for line in members),
            min(line["bbox"][1] for line in members),
            max(line["bbox"][2] for line in members),
            max(line["bbox"][3] for line in members),
        )
        rows.append((members, {**members[0], "bbox": box}, [span for _, spans in group for span in spans]))
    return rows


def _full_spans(members: list[dict]) -> list[dict]:
    """Return every span of a row's lines, in order, with a word space where two lines meet."""
    spans: list[dict] = []
    for line in members:
        own = list(line.get("spans", []))
        if spans and own and not spans[-1]["text"].endswith((" ", "\t")) and not own[0]["text"].startswith((" ", "\t")):
            spans.append({**own[0], "text": " "})
        spans.extend(own)
    return spans


def _inked(spans: list[dict]) -> list[dict]:
    return [span for span in spans if span.get("text", "").strip()]


def _text_lines(blocks: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Return every horizontal line with ink in it, as (line, its inked spans), top to bottom."""
    lines = []
    for block in blocks:
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            if tuple(line.get("dir", (1, 0))) != (1, 0):
                continue
            inked = _inked(line.get("spans", []))
            if inked:
                lines.append((line, inked))
    lines.sort(key=lambda item: (item[0]["bbox"][1], item[0]["bbox"][0]))
    return lines


def _ink_top(block: dict) -> float | None:
    """Return the top of a text block's highest inked line, or None for a block with no ink."""
    tops = [line["bbox"][1] for line, _ in _text_lines([block])]
    return min(tops) if tops else None


def find_separator(drawings: list[Any], blocks: list[dict], page_height: float) -> Any | None:
    """Return the footnote separator's rect, or None.

    ``drawings`` are ``page.get_drawings()`` (anything with a ``rect`` having x0, y0, x1, y1).
    The rule must start at the text's left margin, be short against the text width, sit in the
    lower part of the page, and have text below it.
    """
    lines = _text_lines(blocks)
    if not lines:
        return None
    left = min(line["bbox"][0] for line, _ in lines)
    right = max(line["bbox"][2] for line, _ in lines)
    width = right - left
    if width <= 0:
        return None
    candidates = []
    for drawing in drawings:
        rect = drawing["rect"] if isinstance(drawing, dict) else drawing.rect
        if rect.y1 - rect.y0 > _SEPARATOR_MAX_HEIGHT:
            continue
        length = rect.x1 - rect.x0
        if not (_SEPARATOR_MIN_WIDTH <= length <= _SEPARATOR_MAX_SHARE * width):
            continue
        if abs(rect.x0 - left) > _SEPARATOR_MARGIN_SLACK or rect.y0 < _SEPARATOR_MIN_DEPTH * page_height:
            continue
        if not any(line["bbox"][1] >= rect.y1 - 1.0 for line, _ in lines):
            continue
        candidates.append(rect)
    # The lowest rule with notes under it: a short rule higher up is more likely part of the body.
    return max(candidates, key=lambda rect: rect.y0) if candidates else None


def _label_of(spans: list[dict], note_size: float) -> str | None:
    """Return the label a line opens with, when its first inked span is one, else None."""
    first = spans[0]
    token = first["text"].strip()
    if not _LABEL.match(token):
        return None
    raised = bool(first.get("flags", 0) & 1)
    small = first.get("size", 0.0) <= _LABEL_MAX_SIZE_SHARE * note_size
    return token if (raised or small) and len(spans) > 1 else None


def take_footnote_area(
    drawings: list[Any], blocks: list[dict], page_height: float, note_open: bool = False
) -> tuple[list[dict], FootnoteArea | None]:
    """Split a page's blocks into the body and its footnote area.

    Returns the blocks that stay in the body, and the area (None when the page has none, in
    which case the blocks come back untouched). The notes must be set no larger than the body
    above them. A line set apart from the notes, or away from the margin, ends the area and
    stays in the body (a page number, for the running-line filter). ``note_open`` says the page
    before ended with a note, which unlabelled text at the top of this page's area may finish.
    """
    rule = find_separator(drawings, blocks, page_height)
    if rule is None:
        return blocks, None
    # A block is below the rule when all its ink is: its box can take in an empty line above.
    below = [block for block in blocks if _ink_top(block) is not None and _ink_top(block) >= rule.y1 - 1.0]
    above = [block for block in blocks if block not in below]
    if not below:
        return blocks, None
    # Text that starts above the rule and runs below it straddles it: not a clean area. Only
    # inked lines count, since the empty paragraph Word sets above a rule often overlaps it.
    if any(line["bbox"][1] < rule.y1 - 1.0 < line["bbox"][3] - 1.0 for line, _ in _text_lines(above)):
        return blocks, None
    note_lines = _text_lines(below)
    if not note_lines:
        return blocks, None
    body_lines = _text_lines(above)
    note_size = median(max(span["size"] for span in spans) for _, spans in note_lines)
    body_size = median(max(span["size"] for span in spans) for _, spans in body_lines) if body_lines else None
    if body_size is not None and note_size > body_size + 0.5:
        return blocks, None
    notes: list[Note] = []
    continued: list[list[dict]] = []
    consumed: set[int] = set()
    previous_bottom: float | None = None
    for members, line, spans in _rows(note_lines):
        # The spans a note keeps are every span of its lines: PyMuPDF prints a word space as a
        # span of its own, and the inked spans alone run the words together.
        full = _full_spans(members)
        label = _label_of(spans, note_size)
        height = line["bbox"][3] - line["bbox"][1]
        apart = previous_bottom is not None and line["bbox"][1] - previous_bottom > _CONTINUATION_GAP * height
        if label is not None:
            rest = [dict(span) for span in full[full.index(spans[0]) + 1 :]]
            while rest and not rest[0]["text"].strip():
                rest.pop(0)
            if rest:
                rest[0]["text"] = rest[0]["text"].lstrip()
            notes.append(Note(label=label, lines=[rest]))
        elif apart or line["bbox"][0] > rule.x0 + _CONTINUATION_INDENT:
            # Set apart from the note above it, or set away from the margin (a centered page
            # number): the page's footer, not a note.
            break
        elif notes:
            notes[-1].lines.append(full)
        else:
            # Text under the rule before any label: a note continued from the page before.
            continued.append(full)
        consumed.update(id(member) for member in members)
        previous_bottom = line["bbox"][3]
    if not notes and not continued:
        return blocks, None
    if continued:
        # Unlabelled text under the rule finishes a note only when the page before ended with
        # one, and only when it is set smaller than the body: otherwise it is body text under
        # some other short rule (a signature line), and the page is left alone.
        smaller = body_size is None or note_size < body_size - 0.5
        if not note_open or not smaller:
            return blocks, None
    area_blocks: list[dict] = []
    rest_blocks: list[dict] = []
    for block in below:
        inked = [line for line, _ in _text_lines([block])]
        taken = [line for line in inked if id(line) in consumed]
        if taken and len(taken) < len(inked):
            # One block holds both note and footer lines: too tangled to split safely.
            return blocks, None
        (area_blocks if taken else rest_blocks).append(block)
    body = [block for block in blocks if block not in area_blocks]
    return body, FootnoteArea(top=rule.y0, notes=notes, continued=continued)


def is_reference_span(span: dict, line_spans: list[dict], body_size: float = 0.0) -> bool:
    """Tell whether a span is set as a footnote reference: raised, or small beside its text.

    The text to compare with is the rest of its line, or, for a number PyMuPDF set on a line of
    its own, ``body_size``: the page's body text size.
    """
    if span.get("flags", 0) & 1:
        return True
    sizes = [other.get("size", 0.0) for other in line_spans if other is not span and other.get("text", "").strip()]
    reference = max(sizes) if sizes else body_size
    return reference > 0 and span.get("size", 0.0) <= _LABEL_MAX_SIZE_SHARE * reference


def body_text_size(blocks: list[dict]) -> float:
    """Return the median size of a page's text lines (each line by its largest span), or 0."""
    lines = _text_lines(blocks)
    return median(max(span["size"] for span in spans) for _, spans in lines) if lines else 0.0
