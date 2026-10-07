#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/terminal.py
"""Terminal rendering from AST.

This module provides the TerminalRenderer, which walks the AST and builds
`rich` renderables directly. The older terminal path rendered Markdown text and
handed it to ``rich.markdown.Markdown``, which parses it again with a smaller
dialect: footnotes, math, task lists, definition lists, admonitions and
underline came out as raw source, and Markdown escapes inside math were eaten.
Rendering from the AST keeps every node what it is.

Style names follow ``rich.markdown`` (``markdown.h1``, ``markdown.code``, ...),
so a ``[rich]`` theme written for the old path still applies; the nodes rich's
Markdown never had get names in the same family (``markdown.math``,
``markdown.admonition.warning``, ...).

"""

from __future__ import annotations

import io
import logging
import shutil
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Iterator, Mapping, Optional, Union, cast

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionList,
    Document,
    Emphasis,
    Figure,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    Mark,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.ast.transforms import remove_terminal_unsafe_characters
from all2md.ast.utils import extract_text
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.base import BaseRenderer

if TYPE_CHECKING:
    from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
    from rich.segment import Segment
    from rich.text import Text as RichText
    from rich.theme import Theme

logger = logging.getLogger(__name__)

_INLINE_TYPES: tuple[type[Node], ...] = (
    Text,
    Emphasis,
    Strong,
    Code,
    Link,
    Image,
    LineBreak,
    Strikethrough,
    Mark,
    Underline,
    Superscript,
    Subscript,
    HTMLInline,
    MathInline,
    FootnoteReference,
    CommentInline,
)

#: Styles for the nodes ``rich.markdown`` has no element for. Rich's own
#: ``markdown.*`` defaults cover the rest.
DEFAULT_STYLES: dict[str, str] = {
    "markdown.u": "underline",
    "markdown.mark": "black on yellow",
    "markdown.math": "italic cyan",
    "markdown.math.border": "dim",
    "markdown.footnote": "bold cyan",
    "markdown.dt": "bold",
    "markdown.html": "dim",
    "markdown.comment": "dim italic",
    "markdown.image": "magenta",
    "markdown.caption": "italic dim",
    "markdown.task.checked": "green",
    "markdown.task.unchecked": "dim",
    "markdown.admonition": "cyan",
    "markdown.admonition.note": "blue",
    "markdown.admonition.info": "blue",
    "markdown.admonition.abstract": "cyan",
    "markdown.admonition.tip": "green",
    "markdown.admonition.hint": "green",
    "markdown.admonition.success": "green",
    "markdown.admonition.important": "magenta",
    "markdown.admonition.example": "magenta",
    "markdown.admonition.question": "cyan",
    "markdown.admonition.warning": "yellow",
    "markdown.admonition.attention": "yellow",
    "markdown.admonition.caution": "red",
    "markdown.admonition.danger": "red",
    "markdown.admonition.error": "red",
    "markdown.admonition.failure": "red",
    "markdown.admonition.bug": "red",
    "markdown.admonition.quote": "dim",
}

_SUPERSCRIPT = str.maketrans("0123456789+-=()in", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁱⁿ")
_SUBSCRIPT = str.maketrans("0123456789+-=()aeox", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓ")
_SUPERSCRIPT_CHARS = frozenset("0123456789+-=()in")
_SUBSCRIPT_CHARS = frozenset("0123456789+-=()aeox")


@dataclass(frozen=True)
class HeadingPosition:
    """Where a heading lands in the rendered output.

    Parameters
    ----------
    level : int
        Heading level, 1-6.
    text : str
        The heading's plain text.
    line : int
        Zero-based line of the rendered output the heading starts on.
    anchor : str or None, default None
        The heading's explicit id from the source document (AsciiDoc ``[[id]]``,
        for example), when the parser kept one.

    """

    level: int
    text: str
    line: int
    anchor: Optional[str] = None


@dataclass(frozen=True)
class LinkPosition:
    """Where a link, or one line of it, lands in the rendered output.

    A link that wraps onto several lines has one position per line, all with
    the same ``index``.

    Parameters
    ----------
    line : int
        Zero-based line of the rendered output.
    start : int
        Terminal cell the link starts at on that line, zero-based.
    end : int
        Terminal cell just past the link's last cell on that line.
    target : str
        The link's URL as written in the document, or for a footnote reference
        the footnote's identifier.
    index : int
        The link's number in document order, counting from zero.
    footnote : bool, default False
        The link is a footnote reference; ``target`` names a key of
        ``TerminalLayout.footnotes``.

    """

    line: int
    start: int
    end: int
    target: str
    index: int
    footnote: bool = False


@dataclass(frozen=True)
class TerminalLayout:
    """A document laid out at one width: the text, and where things land in it.

    Parameters
    ----------
    text : str
        The rendered document, as ``TerminalRenderer.render_to_string`` returns it.
    width : int
        The width it was laid out at, in terminal cells.
    line_count : int
        Number of lines in ``text``.
    headings : tuple of HeadingPosition
        Every heading with text, nested ones included, in output order.
    links : tuple of LinkPosition
        Every link with a target and every footnote reference, in output order.
    footnotes : dict
        Line each footnote definition starts on, by identifier.

    """

    text: str
    width: int
    line_count: int
    headings: tuple[HeadingPosition, ...]
    links: tuple[LinkPosition, ...]
    footnotes: Mapping[str, int]


# Keys of the rich ``Style.meta`` the renderer tags headings, links and footnote
# definitions with, so one layout pass can say where each landed.
_HEADING_KEY = "all2md.heading"
_LINK_KEY = "all2md.link"
_FOOTNOTE_KEY = "all2md.footnote"


def _iter_nodes(node: Any) -> Iterator[Node]:
    """Yield every node under ``node`` (inclusive), in document order."""
    if isinstance(node, Node):
        yield node
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_nodes(item)
        return
    if not is_dataclass(node):
        return
    for f in fields(node):
        if f.name in ("metadata", "source_location"):
            continue
        value = getattr(node, f.name)
        if isinstance(value, (Node, list, tuple)):
            yield from _iter_nodes(value)


def build_theme(styles: Optional[Mapping[str, Any]] = None) -> "Theme":
    """Build the rich theme: our defaults, then the user's overrides.

    An element name such as ``h1``, ``math`` or ``item.bullet`` means
    ``markdown.h1`` (and so on); any other name is used as given. An invalid
    style is logged and skipped.

    Parameters
    ----------
    styles : dict or None
        User overrides, ``{name: style string}``.

    Returns
    -------
    rich.theme.Theme

    """
    from rich.default_styles import DEFAULT_STYLES as RICH_DEFAULTS
    from rich.errors import StyleSyntaxError
    from rich.style import Style
    from rich.theme import Theme

    known = {name for name in RICH_DEFAULTS if name.startswith("markdown.")} | set(DEFAULT_STYLES)
    resolved: dict[str, Union[str, Style]] = dict(DEFAULT_STYLES)
    for raw_key, raw_value in (styles or {}).items():
        key = str(raw_key).strip()
        # Any admonition kind can be styled, not only the ones with a default.
        if f"markdown.{key}" in known or key.startswith("admonition."):
            key = f"markdown.{key}"
        if not isinstance(raw_value, str):
            logger.warning("Ignoring style '%s': value must be a style string", raw_key)
            continue
        try:
            resolved[key] = Style.parse(raw_value)
        except StyleSyntaxError as exc:
            logger.warning("Ignoring invalid style '%s = %s': %s", raw_key, raw_value, exc)
    return Theme(resolved)


class _Prefixed:
    """Render content narrower and put a prefix before each line.

    ``first`` goes before the first line and ``rest`` before every other line;
    they should be the same width. List bullets and block-quote bars both use
    this, the way ``rich.markdown`` draws them.
    """

    def __init__(
        self,
        renderable: "RenderableType",
        first: str,
        rest: str,
        prefix_style: str = "none",
        style: str = "none",
        first_meta: Optional[dict[str, Any]] = None,
    ) -> None:
        self.renderable = renderable
        self.first = first
        self.rest = rest
        self.prefix_style = prefix_style
        self.style = style
        self.first_meta = first_meta

    def __rich_console__(self, console: "Console", options: "ConsoleOptions") -> "RenderResult":
        from rich.cells import cell_len
        from rich.segment import Segment
        from rich.style import Style

        width = max(1, options.max_width - cell_len(self.first))
        style = console.get_style(self.style, default="none")
        lines = console.render_lines(self.renderable, options.update(width=width), style=style, pad=False)
        if not lines:
            lines = [[]]
        prefix_style = console.get_style(self.prefix_style, default="none")
        first_style = prefix_style + Style(meta=self.first_meta) if self.first_meta else prefix_style
        first = Segment(self.first, first_style)
        rest = Segment(self.rest, prefix_style)
        new_line = Segment.line()
        for index, line in enumerate(lines):
            yield first if index == 0 else rest
            yield from line
            yield new_line


class _RenderedLines:
    """Lines already laid out, printed as they are.

    A meta tag splits a run of text into segments that differ only in their
    meta, which prints as the same styling closed and reopened. Those pieces
    are joined again, so tagging leaves the output byte for byte unchanged.
    """

    def __init__(self, lines: list[list["Segment"]]) -> None:
        self.lines = lines

    def __rich_console__(self, console: "Console", options: "ConsoleOptions") -> "RenderResult":
        from rich.segment import Segment
        from rich.style import Style

        untagged: dict[Style, tuple[Style, str]] = {}

        def printed(style: Style) -> tuple[Style, str]:
            """Return the style as the terminal sees it: no meta, but the link and its id kept."""
            if style not in untagged:
                # A meta-only style gets a link id too; it means nothing without a link.
                untagged[style] = (style.clear_meta_and_links(), style.link_id if style.link else "")
            return untagged[style]

        new_line = Segment.line()
        for line in self.lines:
            pending: Optional[Segment] = None
            # Whether ``pending`` holds a tagged piece; only those were split by a tag.
            pending_tagged = False
            for segment in line:
                tagged = segment.style is not None and bool(segment.style.meta)
                if (
                    pending is not None
                    and pending.style is not None
                    and segment.style is not None
                    and not pending.control
                    and not segment.control
                    and (pending_tagged or tagged)
                    and printed(pending.style) == printed(segment.style)
                ):
                    pending = Segment(pending.text + segment.text, pending.style)
                    pending_tagged = True
                    continue
                if pending is not None:
                    yield pending
                pending = segment
                pending_tagged = tagged
            if pending is not None:
                yield pending
            yield new_line


class TerminalRenderer(BaseRenderer):
    """Render an AST document for the terminal with `rich`.

    Parameters
    ----------
    options : TerminalRendererOptions or None, default None
        Terminal rendering options.

    Examples
    --------
    Plain text at a fixed width (no escape codes):

        >>> from all2md.ast import Document, Paragraph, Text
        >>> from all2md.options.terminal import TerminalRendererOptions
        >>> doc = Document(children=[Paragraph(content=[Text(content="Hello")])])
        >>> renderer = TerminalRenderer(TerminalRendererOptions(width=40, color_system="none"))
        >>> print(renderer.render_to_string(doc))
        Hello

    """

    def __init__(self, options: TerminalRendererOptions | None = None):
        """Initialize the renderer with options."""
        BaseRenderer._validate_options_type(options, TerminalRendererOptions, "terminal")
        options = options or TerminalRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: TerminalRendererOptions = options
        self._footnote_numbers: dict[str, int] = {}
        self._footnote_definitions: dict[str, FootnoteDefinition] = {}
        # What the meta tags in the last render_renderables() output point at.
        self._headings: list[Heading] = []
        self._links: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def make_console(self, file: Optional[IO[str]] = None) -> "Console":
        """Build the console this renderer lays documents out on.

        Parameters
        ----------
        file : file-like or None
            Where the console writes. ``None`` writes to an in-memory buffer.

        Returns
        -------
        rich.console.Console

        """
        from rich.console import Console

        width = self.options.width or shutil.get_terminal_size((80, 24)).columns
        color_system = None if self.options.color_system == "none" else self.options.color_system
        return Console(
            file=file if file is not None else io.StringIO(),
            force_terminal=True,
            color_system=color_system,
            width=width,
            theme=build_theme(self.options.styles),
            legacy_windows=False,
            highlight=False,
            emoji=False,
            markup=False,
        )

    def render_renderables(self, doc: Document) -> list["RenderableType"]:
        """Build the document's top-level rich renderables.

        Blank lines between blocks are included, and footnote definitions are
        collected and appended at the end under a rule, numbered in the order
        they are first referenced.

        A document is untrusted input, so every control character a terminal
        would act on (ESC, the C1 controls, carriage return...) is removed from
        its text, alt text and link targets first; tab and line feed stay.

        Parameters
        ----------
        doc : Document
            Document to render.

        Returns
        -------
        list of rich renderables

        """
        cleaned, _removed = remove_terminal_unsafe_characters(doc)
        doc = cast(Document, cleaned)
        self._number_footnotes(doc)
        self._headings = []
        self._links = []
        blocks = self._blocks(doc.children)
        notes = self._footnotes_section()
        if notes:
            blocks.extend(notes)
        return self._spaced(blocks)

    def render_to_string(self, doc: Document) -> str:
        """Render a document to a string of ANSI-styled text.

        Parameters
        ----------
        doc : Document
            Document to render.

        Returns
        -------
        str
            The rendered document; plain text when ``color_system`` is ``"none"``.

        """
        return self.layout(doc).text

    def layout(self, doc: Document) -> TerminalLayout:
        """Lay a document out once: its text, and where its headings and links land.

        Positions depend on the layout width, so this lays the document out at
        the renderer's width (the terminal's when ``width`` is unset).

        Parameters
        ----------
        doc : Document
            Document to render.

        Returns
        -------
        TerminalLayout

        """
        from rich.console import Group

        console = self.make_console()
        no_wrap = not self.options.word_wrap
        lines = console.render_lines(
            Group(*self.render_renderables(doc)), console.options.update(no_wrap=no_wrap), pad=False
        )
        with console.capture() as capture:
            console.print(_RenderedLines(lines), no_wrap=no_wrap, crop=True)
        text = capture.get().rstrip("\n")
        headings, links, footnotes = self._positions(lines)
        return TerminalLayout(
            text=text,
            width=console.width,
            line_count=text.count("\n") + 1 if text else 0,
            headings=headings,
            links=links,
            footnotes=footnotes,
        )

    def heading_positions(self, doc: Document) -> list[HeadingPosition]:
        """Find the output line each heading lands on, nested headings included.

        The line depends on the layout width, so this lays the document out at
        the renderer's width. A heading with no text has no position.

        Parameters
        ----------
        doc : Document
            Document to render.

        Returns
        -------
        list of HeadingPosition

        """
        return list(self.layout(doc).headings)

    def _positions(
        self, lines: list[list["Segment"]]
    ) -> tuple[tuple[HeadingPosition, ...], tuple[LinkPosition, ...], dict[str, int]]:
        """Read the meta tags back out of laid-out lines."""
        from rich.cells import cell_len

        headings: list[HeadingPosition] = []
        seen_headings: set[int] = set()
        links: list[LinkPosition] = []
        # The fragment of each link last seen, by link index, to join segments of one line.
        open_links: dict[int, int] = {}
        footnotes: dict[str, int] = {}
        for number, line in enumerate(lines):
            column = 0
            for segment in line:
                width = cell_len(segment.text)
                meta = segment.style.meta if segment.style is not None else None
                if meta:
                    heading_index = meta.get(_HEADING_KEY)
                    if heading_index is not None and heading_index not in seen_headings:
                        seen_headings.add(heading_index)
                        heading = self._headings[heading_index]
                        anchor = heading.metadata.get("id")
                        headings.append(
                            HeadingPosition(
                                heading.level,
                                extract_text(heading.content, joiner=""),
                                number,
                                anchor if isinstance(anchor, str) and anchor else None,
                            )
                        )
                    link_index = meta.get(_LINK_KEY)
                    if link_index is not None and width:
                        last = open_links.get(link_index)
                        if last is not None and links[last].line == number and links[last].end == column:
                            links[last] = replace(links[last], end=column + width)
                        else:
                            target, footnote = self._links[link_index]
                            open_links[link_index] = len(links)
                            links.append(LinkPosition(number, column, column + width, target, link_index, footnote))
                    footnote_id = meta.get(_FOOTNOTE_KEY)
                    if footnote_id is not None:
                        footnotes.setdefault(footnote_id, number)
                column += width
        return tuple(headings), tuple(links), footnotes

    def _tag(self, text: "RichText", start: int, key: str, value: Any) -> None:
        """Tag ``text[start:]`` so the layout pass can find where it lands."""
        from rich.style import Style

        if len(text) > start:
            text.stylize(Style(meta={key: value}), start, len(text))

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render a document to a file or file-like object.

        Parameters
        ----------
        doc : Document
            Document to render.
        output : str, Path, or IO[bytes]
            Output destination.

        """
        self.write_text_output(self.render_to_string(doc), output)

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    @staticmethod
    def _spaced(blocks: list["RenderableType"]) -> list["RenderableType"]:
        """Put a blank line between blocks."""
        from rich.text import Text as RichText

        spaced: list["RenderableType"] = []
        for index, block in enumerate(blocks):
            if index:
                spaced.append(RichText(""))
            spaced.append(block)
        return spaced

    def _stack(self, nodes: list[Node], spaced: bool = True) -> "RenderableType":
        """Render a container's children as one renderable."""
        from rich.console import Group

        blocks = self._blocks(nodes)
        return Group(*(self._spaced(blocks) if spaced else blocks))

    def _blocks(self, nodes: list[Node]) -> list["RenderableType"]:
        """Render nodes as blocks; runs of inline nodes become one paragraph."""
        blocks: list["RenderableType"] = []
        run: list[Node] = []
        for node in nodes:
            if isinstance(node, _INLINE_TYPES):
                run.append(node)
                continue
            if run:
                blocks.append(self._paragraph_text(run))
                run = []
            block = self._block(node)
            if block is not None:
                blocks.append(block)
        if run:
            blocks.append(self._paragraph_text(run))
        return blocks

    def _block(self, node: Node) -> Optional["RenderableType"]:  # noqa: C901
        """Render one block node, or None for a node that renders elsewhere or not at all."""
        from rich.rule import Rule
        from rich.text import Text as RichText

        if isinstance(node, Paragraph):
            return self._paragraph_text(node.content)
        if isinstance(node, Heading):
            return self._heading(node)
        if isinstance(node, CodeBlock):
            return self._code_block(node)
        if isinstance(node, BlockQuote):
            return self._block_quote(node)
        if isinstance(node, List):
            return self._list(node)
        if isinstance(node, Table):
            return self._table(node)
        if isinstance(node, DefinitionList):
            return self._definition_list(node)
        if isinstance(node, MathBlock):
            return self._math_block(node)
        if isinstance(node, Figure):
            return self._figure(node)
        if isinstance(node, ThematicBreak):
            return Rule(style="markdown.hr", characters="-")
        if isinstance(node, HTMLBlock):
            return RichText(node.content.rstrip("\n"), style="markdown.html")
        if isinstance(node, Comment):
            if self.options.comment_mode == "ignore":
                return None
            return RichText(self._comment_label(node) + node.content, style="markdown.comment")
        if isinstance(node, FootnoteDefinition):
            # Collected and printed together at the end.
            return None
        text = extract_text(node, joiner=" ")
        return RichText(text) if text else None

    def _paragraph_text(self, nodes: list[Node]) -> "RichText":
        from rich.text import Text as RichText

        text = RichText(style="markdown.paragraph", justify=self.options.justify or "default")
        self._inlines(nodes, text)
        return text

    def _heading(self, node: Heading) -> "RichText":
        from rich.text import Text as RichText

        level = min(max(node.level, 1), 6)
        text = RichText(style=f"markdown.h{level}", justify="center" if level == 1 else "left")
        self._inlines(node.content, text)
        self._tag(text, 0, _HEADING_KEY, len(self._headings))
        self._headings.append(node)
        return text

    def _code_block(self, node: CodeBlock) -> "RenderableType":
        from rich.syntax import Syntax

        return Syntax(
            node.content.rstrip("\n"),
            (node.language or "text").split()[0] if (node.language or "").strip() else "text",
            theme=self.options.code_theme,
            word_wrap=self.options.word_wrap,
            padding=1,
        )

    def _block_quote(self, node: BlockQuote) -> "RenderableType":
        from rich.panel import Panel
        from rich.text import Text as RichText

        admonition_type = node.metadata.get("admonition_type")
        if not admonition_type:
            return _Prefixed(self._stack(node.children), "▌ ", "▌ ", "markdown.block_quote", "markdown.block_quote")

        kind = str(admonition_type).lower()
        style = f"markdown.admonition.{kind}"
        if style not in DEFAULT_STYLES and not self._user_style(style):
            style = "markdown.admonition"
        title = RichText(str(node.metadata.get("admonition_title") or kind.capitalize()), style=style)
        title.stylize("bold")
        return Panel(
            self._stack(node.children),
            title=title,
            title_align="left",
            border_style=style,
            expand=True,
        )

    def _user_style(self, name: str) -> bool:
        styles = self.options.styles or {}
        return name in styles or name.removeprefix("markdown.") in styles

    def _list(self, node: List) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text as RichText

        rows: list["RenderableType"] = []
        last_number = node.start + len(node.items) - 1
        number_width = len(str(last_number)) + 2
        for index, item in enumerate(node.items):
            if node.ordered:
                first = f"{node.start + index}".rjust(number_width - 1) + " "
                prefix_style = "markdown.item.number"
            else:
                first = " • "
                prefix_style = "markdown.item.bullet"
            body = self._stack(item.children, spaced=not node.tight)
            if item.task_status:
                checked = item.task_status == "checked"
                box = RichText("☑ " if checked else "☐ ", style=f"markdown.task.{item.task_status}")
                if not node.ordered:
                    first = " " + box.plain
                    prefix_style = f"markdown.task.{item.task_status}"
                else:
                    body = _Prefixed(body, box.plain, "  ", prefix_style=f"markdown.task.{item.task_status}")
            if index and not node.tight:
                rows.append(RichText(""))
            rows.append(_Prefixed(body, first, " " * len(first), prefix_style=prefix_style, style="markdown.item"))
        return Group(*rows)

    def _table(self, node: Table) -> "RenderableType":
        """Render a table; a merged cell's content sits in its first cell and the rest are blank."""
        from rich import box
        from rich.table import Table as RichTable

        all_rows: list[TableRow] = ([node.header] if node.header else []) + list(node.rows)
        grid = self._layout_table_grid(all_rows)
        anchors = grid.anchors()
        table = RichTable(
            box=box.SIMPLE,
            pad_edge=False,
            style="markdown.table.border",
            show_edge=True,
            collapse_padding=True,
            show_header=node.header is not None,
            title=node.caption or None,
            title_style="markdown.caption",
        )

        def cell_renderable(row: int, col: int) -> "RenderableType":
            placement = anchors.get((row, col))
            if placement is None:
                return ""
            return self._cell(placement.cell, self._alignment(node, placement.cell, col))

        body_start = 0
        for col in range(grid.num_cols):
            justify = self._alignment(node, None, col) or "default"
            if node.header is not None:
                header = cell_renderable(0, col)
                if hasattr(header, "stylize"):
                    header.stylize("markdown.table.header")
                table.add_column(header, justify=justify)  # type: ignore[arg-type]
            else:
                table.add_column(justify=justify)  # type: ignore[arg-type]
        if node.header is not None:
            body_start = 1
        for row in range(body_start, grid.num_rows):
            table.add_row(*(cell_renderable(row, col) for col in range(grid.num_cols)))
        return table

    @staticmethod
    def _alignment(table: Table, cell: Optional[TableCell], col: int) -> Optional[str]:
        alignment = cell.alignment if cell is not None else None
        if alignment is None and col < len(table.alignments):
            alignment = table.alignments[col]
        return alignment if alignment in ("left", "center", "right") else None

    def _cell(self, cell: TableCell, alignment: Optional[str]) -> "RenderableType":
        if all(isinstance(child, _INLINE_TYPES) for child in cell.content):
            text = self._paragraph_text(cell.content)
            text.justify = alignment or "default"  # type: ignore[assignment]
            return text
        return self._stack(cell.content, spaced=False)

    def _definition_list(self, node: DefinitionList) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text as RichText

        rows: list["RenderableType"] = []
        for term, descriptions in node.items:
            term_text = RichText(style="markdown.dt")
            self._inlines(term.content, term_text)
            rows.append(term_text)
            for description in descriptions:
                rows.append(_Prefixed(self._stack(description.content, spaced=False), "    ", "    "))
        return Group(*rows)

    def _math_block(self, node: MathBlock) -> "RenderableType":
        from rich.panel import Panel
        from rich.text import Text as RichText

        content, _ = node.get_preferred_representation("latex")
        return Panel(
            RichText(content.strip("\n"), style="markdown.math"),
            border_style="markdown.math.border",
            expand=False,
        )

    def _figure(self, node: Figure) -> "RenderableType":
        from rich.console import Group
        from rich.text import Text as RichText

        parts = self._blocks(node.children)
        if node.caption:
            parts.append(RichText(node.caption, style="markdown.caption"))
        return Group(*parts)

    # ------------------------------------------------------------------
    # Footnotes
    # ------------------------------------------------------------------

    def _number_footnotes(self, doc: Document) -> None:
        """Assign footnote numbers in order of first reference; unreferenced ones come after."""
        self._footnote_numbers = {}
        self._footnote_definitions = {}
        for node in _iter_nodes(doc):
            if isinstance(node, FootnoteReference):
                self._footnote_numbers.setdefault(node.identifier, len(self._footnote_numbers) + 1)
            elif isinstance(node, FootnoteDefinition):
                self._footnote_definitions.setdefault(node.identifier, node)
        for identifier in self._footnote_definitions:
            self._footnote_numbers.setdefault(identifier, len(self._footnote_numbers) + 1)

    def _footnotes_section(self) -> list["RenderableType"]:
        from rich.console import Group
        from rich.rule import Rule

        if not self._footnote_definitions:
            return []
        ordered = sorted(self._footnote_definitions.items(), key=lambda pair: self._footnote_numbers[pair[0]])
        rows: list["RenderableType"] = []
        for identifier, definition in ordered:
            marker = f"[{self._footnote_numbers[identifier]}] "
            body = self._stack(definition.content, spaced=False)
            rows.append(
                _Prefixed(
                    body,
                    marker,
                    " " * len(marker),
                    prefix_style="markdown.footnote",
                    first_meta={_FOOTNOTE_KEY: identifier},
                )
            )
        return [Group(Rule(style="markdown.hr", characters="-"), *rows)]

    # ------------------------------------------------------------------
    # Inlines
    # ------------------------------------------------------------------

    def _inlines(self, nodes: list[Node], text: "RichText") -> None:
        for node in nodes:
            self._inline(node, text)

    def _styled(self, nodes: list[Node], text: "RichText", style: Any) -> None:
        start = len(text)
        self._inlines(nodes, text)
        text.stylize(style, start, len(text))

    def _inline(self, node: Node, text: "RichText") -> None:  # noqa: C901
        from rich.style import Style

        if isinstance(node, Text):
            text.append(node.content)
        elif isinstance(node, Strong):
            self._styled(node.content, text, "markdown.strong")
        elif isinstance(node, Emphasis):
            self._styled(node.content, text, "markdown.em")
        elif isinstance(node, Underline):
            self._styled(node.content, text, "markdown.u")
        elif isinstance(node, Strikethrough):
            self._styled(node.content, text, "markdown.s")
        elif isinstance(node, Mark):
            self._styled(node.content, text, "markdown.mark")
        elif isinstance(node, Code):
            self._inline_code(node.content, text)
        elif isinstance(node, Link):
            self._link(node, text)
        elif isinstance(node, Image):
            label = f"[image: {node.alt_text}]" if node.alt_text else "[image]"
            text.append(label, "markdown.image")
            if self.options.hyperlinks and node.url and not node.url.startswith("data:"):
                text.stylize(Style(link=node.url), len(text) - len(label), len(text))
        elif isinstance(node, LineBreak):
            text.append(" " if node.soft else "\n")
        elif isinstance(node, (Superscript, Subscript)):
            self._script(node, text)
        elif isinstance(node, MathInline):
            content, _ = node.get_preferred_representation("latex")
            text.append(content, "markdown.math")
        elif isinstance(node, FootnoteReference):
            number = self._footnote_numbers.get(node.identifier)
            start = len(text)
            text.append(f"[{number if number is not None else node.identifier}]", "markdown.footnote")
            if node.identifier in self._footnote_definitions:
                self._tag(text, start, _LINK_KEY, len(self._links))
                self._links.append((node.identifier, True))
        elif isinstance(node, HTMLInline):
            text.append(node.content, "markdown.html")
        elif isinstance(node, CommentInline):
            if self.options.comment_mode != "ignore":
                text.append(f"[{self._comment_label(node)}{node.content}]", "markdown.comment")
        else:
            text.append(extract_text(node, joiner=" "))

    def _inline_code(self, code: str, text: "RichText") -> None:
        if self.options.inline_code_theme:
            from rich.syntax import Syntax

            highlighted = Syntax(code, "text", theme=self.options.inline_code_theme).highlight(code)
            highlighted.rstrip()
            text.append_text(highlighted)
        else:
            text.append(code, "markdown.code")

    def _link(self, node: Link, text: "RichText") -> None:
        from rich.style import Style

        start = len(text)
        self._inlines(node.content, text)
        if node.url:
            self._tag(text, start, _LINK_KEY, len(self._links))
            self._links.append((node.url, False))
        if self.options.hyperlinks:
            text.stylize("markdown.link", start, len(text))
            text.stylize(Style(link=node.url), start, len(text))
            return
        text.stylize("markdown.link", start, len(text))
        if node.url and text.plain[start:] != node.url:
            text.append(" (")
            text.append(node.url, "markdown.link_url")
            text.append(")")

    def _script(self, node: Union[Superscript, Subscript], text: "RichText") -> None:
        from rich.text import Text as RichText

        inner = RichText()
        self._inlines(node.content, inner)
        plain = inner.plain
        is_super = isinstance(node, Superscript)
        allowed = _SUPERSCRIPT_CHARS if is_super else _SUBSCRIPT_CHARS
        if plain and set(plain) <= allowed:
            text.append(plain.translate(_SUPERSCRIPT if is_super else _SUBSCRIPT))
            return
        text.append("^" if is_super else "_")
        if len(plain) == 1:
            text.append_text(inner)
        else:
            text.append("(")
            text.append_text(inner)
            text.append(")")

    @staticmethod
    def _comment_label(node: Union[Comment, CommentInline]) -> str:
        author = node.metadata.get("author")
        return f"{author}: " if author else ""


# Converter Metadata Registration
# =============================================================================

from all2md.converter_metadata import ConverterMetadata  # noqa: E402

CONVERTER_METADATA = ConverterMetadata(
    format_name="terminal",
    extensions=[],
    mime_types=[],
    magic_bytes=[],
    parser_class=None,  # Render-only: there is nothing to parse.
    renderer_class=TerminalRenderer,
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[("rich", "rich", ">=14.2.0")],
    optional_packages=[],
    import_error_message="The terminal renderer requires rich. Install with: pip install 'all2md[cli_extras]'",
    parser_options_class=None,
    renderer_options_class=TerminalRendererOptions,
    description="Render documents for the terminal with rich (ANSI styling)",
    priority=10,
)
