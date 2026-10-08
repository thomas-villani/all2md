"""A document laid out for the viewer, at whatever width the terminal has.

``DocumentLayout`` wraps one parsed document. It lays the document out once
per width with the terminal renderer and keeps the last few widths, so
scrolling never lays out again and a resize back to an earlier width is free.
Everything the viewer asks about the document goes through it: the text for
the body, the outline, the section a line belongs to, where a link points,
and where to scroll after a resize.

No Wijjit import here, so this module works, and is tested, on every Python
all2md supports.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote

from all2md.ast.nodes import Document
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.terminal import HeadingPosition, LinkPosition, TerminalLayout, TerminalRenderer
from all2md.utils.text import slugify

#: Widths kept laid out at once. A resize usually goes back and forth between a few.
DEFAULT_CACHE_SIZE = 4

_ESC = chr(27)
_BEL = chr(7)
# SGR and other CSI sequences, and OSC sequences (hyperlinks) ended by BEL or ESC backslash.
_ANSI = re.compile(
    re.escape(_ESC)
    + r"(?:\[[0-9;:?]*[ -/]*[@-~]|\][^"
    + _BEL
    + _ESC
    + r"]*(?:"
    + _BEL
    + "|"
    + re.escape(_ESC)
    + r"\\))"
)


@dataclass(frozen=True)
class OutlineEntry:
    """One heading in the outline, with the headings under it.

    Parameters
    ----------
    index : int
        The heading's number in document order, counting from zero; the key
        for ``DocumentLayout.heading_line``.
    level : int
        Heading level, 1-6.
    text : str
        The heading's plain text.
    children : tuple of OutlineEntry
        The headings of deeper levels that follow it, up to the next heading
        of the same or a shallower level.

    """

    index: int
    level: int
    text: str
    children: tuple["OutlineEntry", ...] = field(default_factory=tuple)


def github_slug(text: str) -> str:
    """Return the anchor GitHub gives a heading, before duplicates are numbered.

    Lowercase; letters, digits, marks, ``-`` and ``_`` kept; spaces become
    ``-``; everything else dropped. Non-ASCII letters are kept as they are.

    Parameters
    ----------
    text : str
        The heading's plain text.

    Returns
    -------
    str

    """
    kept = []
    for char in text.strip().lower():
        if char == " ":
            kept.append("-")
        elif char in "-_" or unicodedata.category(char)[0] in "LNM":
            kept.append(char)
    return "".join(kept)


class DocumentLayout:
    """One document, laid out at each width the viewer asks for.

    Parameters
    ----------
    doc : Document
        The parsed document.
    options : TerminalRendererOptions or None
        Renderer options; ``width`` is ignored, since every call names a width.
    cache_size : int, default DEFAULT_CACHE_SIZE
        How many widths to keep laid out.

    """

    def __init__(
        self,
        doc: Document,
        options: TerminalRendererOptions | None = None,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ) -> None:
        """Wrap a document; nothing is laid out until a width is asked for."""
        if cache_size < 1:
            raise ValueError("cache_size must be at least 1")
        self.doc = doc
        self.options = options or TerminalRendererOptions()
        self._cache_size = cache_size
        self._layouts: OrderedDict[int, TerminalLayout] = OrderedDict()
        # Per width: outline index -> output line, and the sorted lines for bisecting.
        self._heading_lines: dict[int, tuple[list[Optional[int]], list[tuple[int, int]]]] = {}
        self._headings: Optional[tuple[HeadingPosition, ...]] = None
        self._outline: Optional[tuple[OutlineEntry, ...]] = None
        self._anchors: Optional[dict[str, int]] = None
        self._loose_anchors: Optional[dict[str, int]] = None

    # ------------------------------------------------------------------
    # Laying out
    # ------------------------------------------------------------------

    def at(self, width: int) -> TerminalLayout:
        """Return the document laid out at ``width`` terminal cells.

        Parameters
        ----------
        width : int
            Width in terminal cells, at least 1.

        Returns
        -------
        TerminalLayout

        """
        if width < 1:
            raise ValueError(f"width must be at least 1, got {width}")
        layout = self._layouts.get(width)
        if layout is not None:
            self._layouts.move_to_end(width)
            return layout
        renderer = TerminalRenderer(self.options.create_updated(width=width))
        layout = renderer.layout(self.doc)
        self._layouts[width] = layout
        if self._headings is None or len(layout.headings) > len(self._headings):
            # A narrower width can crop a deeply indented heading away when word
            # wrap is off; keep the fullest list, so the outline only ever grows.
            self._headings = layout.headings
            self._outline = None
            self._anchors = self._loose_anchors = None
            self._heading_lines.clear()
        while len(self._layouts) > self._cache_size:
            evicted, _ = self._layouts.popitem(last=False)
            self._heading_lines.pop(evicted, None)
        return layout

    def text(self, width: int) -> str:
        """Return the rendered text at ``width``; what the body view shows.

        Parameters
        ----------
        width : int
            Width in terminal cells.

        Returns
        -------
        str

        """
        return self.at(width).text

    # ------------------------------------------------------------------
    # Headings and the outline
    # ------------------------------------------------------------------

    @property
    def headings(self) -> tuple[HeadingPosition, ...]:
        """The document's headings, in order, as first laid out.

        Their lines depend on the width, so ask ``heading_line`` for a line.
        Their number does not, except that with word wrap off a narrow width
        can crop a deeply indented heading away; the list is the fullest one
        laid out so far, and the outline is rebuilt if a later width adds to it.
        """
        if self._headings is None:
            self.at(self.options.width or 80)
        assert self._headings is not None
        return self._headings

    @property
    def outline(self) -> tuple[OutlineEntry, ...]:
        """The headings as a tree: each heading holds the deeper ones after it."""
        if self._outline is None:
            self._outline = _build_outline(self.headings)
        return self._outline

    def heading_line(self, index: int, width: int) -> Optional[int]:
        """Return the output line heading ``index`` starts on at ``width``.

        Parameters
        ----------
        index : int
            The heading's ``OutlineEntry.index``.
        width : int
            Width in terminal cells.

        Returns
        -------
        int or None
            ``None`` if the heading did not land anywhere at this width (only
            possible with word wrap off, when a deeply indented heading is
            cropped away).

        """
        lines, _ = self._lines_at(width)
        return lines[index] if 0 <= index < len(lines) else None

    def section_at(self, line: int, width: int) -> Optional[int]:
        """Return the heading whose section ``line`` is in, or ``None`` above the first.

        Parameters
        ----------
        line : int
            Zero-based output line.
        width : int
            Width in terminal cells.

        Returns
        -------
        int or None
            The heading's ``OutlineEntry.index``.

        """
        _, ordered = self._lines_at(width)
        position = bisect.bisect_right(ordered, (line, len(self.headings)))
        return ordered[position - 1][1] if position else None

    def next_heading(self, line: int, width: int) -> Optional[int]:
        """Return the line of the first heading below ``line``, if any."""
        _, ordered = self._lines_at(width)
        position = bisect.bisect_right(ordered, (line, len(self.headings)))
        return ordered[position][0] if position < len(ordered) else None

    def previous_heading(self, line: int, width: int) -> Optional[int]:
        """Return the line of the last heading above ``line``, if any."""
        _, ordered = self._lines_at(width)
        position = bisect.bisect_left(ordered, (line, -1))
        return ordered[position - 1][0] if position else None

    def relocate(self, line: int, from_width: int, to_width: int) -> int:
        """Return the line at ``to_width`` showing what ``line`` showed at ``from_width``.

        The viewer calls this on a resize so the top of the screen stays in
        the same place in the document. The line keeps its section and its
        proportional distance into that section; above the first heading it
        keeps its proportional distance into the document.

        Parameters
        ----------
        line : int
            Zero-based output line at ``from_width``.
        from_width, to_width : int
            The old and new widths.

        Returns
        -------
        int

        """
        old = self.at(from_width)
        new = self.at(to_width)
        if old.line_count == 0 or new.line_count == 0:
            return 0
        line = min(max(line, 0), old.line_count - 1)
        section = self.section_at(line, from_width)
        if section is None:
            old_start: Optional[int] = 0
            new_start: Optional[int] = 0
        else:
            old_start = self.heading_line(section, from_width)
            new_start = self.heading_line(section, to_width)
        if old_start is None or new_start is None:
            # The section's heading was cropped away at one of the widths.
            return min(round(line * new.line_count / old.line_count), new.line_count - 1)
        old_end = self.next_heading(line, from_width)
        new_end = self.next_heading(new_start, to_width)
        old_length = (old_end if old_end is not None else old.line_count) - old_start
        new_length = (new_end if new_end is not None else new.line_count) - new_start
        offset = round((line - old_start) * new_length / old_length) if old_length else 0
        return min(new_start + offset, new.line_count - 1)

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def link_label(self, position: LinkPosition, width: int) -> str:
        """Return the text a link shows, all of it when the link wraps over several lines.

        Parameters
        ----------
        position : LinkPosition
            Any position of the link.
        width : int
            Width in terminal cells.

        Returns
        -------
        str
            The link's visible text, its lines joined with a space.

        """
        layout = self.at(width)
        lines = layout.text.split(chr(10))
        parts = [
            _cells(_ANSI.sub("", lines[part.line]), part.start, part.end).strip()
            for part in layout.links
            if part.index == position.index and part.line < len(lines)
        ]
        return " ".join(part for part in parts if part)

    def links_between(self, top: int, bottom: int, width: int) -> list[LinkPosition]:
        """Return the links with any part on lines ``top`` to ``bottom - 1``.

        A link that wraps appears once, as its first position in the range.

        Parameters
        ----------
        top : int
            First output line, zero-based.
        bottom : int
            One past the last output line.
        width : int
            Width in terminal cells.

        Returns
        -------
        list of LinkPosition
            In document order.

        """
        seen: set[int] = set()
        found = []
        for position in self.at(width).links:
            if top <= position.line < bottom and position.index not in seen:
                seen.add(position.index)
                found.append(position)
        return found

    def resolve_fragment(self, fragment: str) -> Optional[int]:
        """Return the heading a ``#fragment`` names, or ``None``.

        An explicit heading id matches first, then the anchor GitHub would give
        the heading (``#my-heading``, duplicates numbered ``-1``, ``-2``...),
        then a looser comparison that ignores accents and punctuation.

        Parameters
        ----------
        fragment : str
            The part of a link after ``#``, with or without the ``#``;
            percent-escapes are decoded.

        Returns
        -------
        int or None
            The heading's ``OutlineEntry.index``.

        """
        if self._anchors is None:
            self._anchors, self._loose_anchors = _anchor_maps(self.headings)
        assert self._loose_anchors is not None
        fragment = unquote(fragment.removeprefix("#")).strip()
        if not fragment:
            return None
        for candidate in (fragment, fragment.lower()):
            if candidate in self._anchors:
                return self._anchors[candidate]
        loose = slugify(fragment)
        return self._loose_anchors.get(loose) if loose else None

    def jump_target(self, position: LinkPosition, width: int) -> Optional[int]:
        """Return the line a link moves the viewer to, or ``None`` if it leaves the document.

        Footnote references go to their definition and ``#fragment`` links to
        their heading. Anything else (a URL, a path) is ``None``: the viewer
        shows it and never opens it by itself.

        Parameters
        ----------
        position : LinkPosition
            A link from ``TerminalLayout.links``.
        width : int
            Width in terminal cells.

        Returns
        -------
        int or None

        """
        if position.footnote:
            return self.at(width).footnotes.get(position.target)
        if not position.target.startswith("#"):
            return None
        heading = self.resolve_fragment(position.target)
        return None if heading is None else self.heading_line(heading, width)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _lines_at(self, width: int) -> tuple[list[Optional[int]], list[tuple[int, int]]]:
        """Map each outline heading to its line at ``width``, and sort them by line."""
        cached = self._heading_lines.get(width)
        if cached is not None and width in self._layouts:
            return cached
        found = self.at(width).headings
        reference = self.headings
        lines: list[Optional[int]]
        if len(found) == len(reference):
            lines = [heading.line for heading in found]
        else:
            # Some headings were cropped away; match the rest up in order.
            lines = [None] * len(reference)
            cursor = 0
            for index, heading in enumerate(reference):
                for probe in range(cursor, len(found)):
                    if (found[probe].level, found[probe].text) == (heading.level, heading.text):
                        lines[index] = found[probe].line
                        cursor = probe + 1
                        break
        ordered = sorted((line, index) for index, line in enumerate(lines) if line is not None)
        self._heading_lines[width] = (lines, ordered)
        return lines, ordered


def _cells(line: str, start: int, end: int) -> str:
    """Return the characters of ``line`` occupying terminal cells ``start`` to ``end``."""
    from rich.cells import cell_len

    out = []
    column = 0
    for char in line:
        width = cell_len(char)
        if start <= column and column + width <= end:
            out.append(char)
        column += width
        if column >= end:
            break
    return "".join(out)


def _build_outline(headings: tuple[HeadingPosition, ...]) -> tuple[OutlineEntry, ...]:
    """Nest headings under the nearest shallower heading before them."""

    @dataclass
    class Open:
        index: int
        heading: HeadingPosition
        children: list[OutlineEntry] = field(default_factory=list)

    def close(entry: Open) -> OutlineEntry:
        return OutlineEntry(entry.index, entry.heading.level, entry.heading.text, tuple(entry.children))

    roots: list[OutlineEntry] = []
    stack: list[Open] = []
    for index, heading in enumerate(headings):
        while stack and stack[-1].heading.level >= heading.level:
            done = close(stack.pop())
            (stack[-1].children if stack else roots).append(done)
        stack.append(Open(index, heading))
    while stack:
        done = close(stack.pop())
        (stack[-1].children if stack else roots).append(done)
    return tuple(roots)


def _anchor_maps(headings: tuple[HeadingPosition, ...]) -> tuple[dict[str, int], dict[str, int]]:
    """Build the exact anchor map (ids, then GitHub slugs) and the loose one."""
    exact: dict[str, int] = {}
    for index, heading in enumerate(headings):
        if heading.anchor:
            exact.setdefault(heading.anchor, index)
    counts: dict[str, int] = {}
    taken: set[str] = set()
    loose: dict[str, int] = {}
    for index, heading in enumerate(headings):
        base = github_slug(heading.text)
        slug = base
        if base in counts:
            # GitHub numbers repeats from 1 and skips any number already in use.
            while slug in taken:
                counts[base] += 1
                slug = f"{base}-{counts[base]}"
        else:
            counts[base] = 0
        taken.add(slug)
        if slug:
            exact.setdefault(slug, index)
        loose.setdefault(slugify(heading.text), index)
    loose.pop("", None)
    return exact, loose
