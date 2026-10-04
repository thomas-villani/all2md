#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/man.py
"""man(7) page rendering from AST.

This module provides the ManRenderer class, which writes an AST as a Unix
manual page in the man(7) macro package, the input ``man``, ``groff -man`` and
``mandoc`` read.

Man pages have two heading levels (``.SH`` and ``.SS``), no footnotes, no
images and no strikethrough, so the mapping is lossy at the edges: deeper
headings become bold paragraphs, images their alt text, and footnotes tagged
paragraphs. Everything with a man(7) counterpart maps to it: lists to ``.IP``,
definition lists to ``.TP``, code to ``.EX``/``.EE``, links to ``.UR``/``.UE``
and tables to tbl(1).

"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
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
    ListItem,
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
from all2md.ast.visitors import NodeVisitor
from all2md.options.man import ManRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin

# Inline rendering marks a request that needs a line of its own (.br, .UR, .UE)
# by starting that line with this character; _text_lines() turns them back.
_CONTROL = "\x00"
# A title that carries its section: "LS(1)", "open(2)", "printf(3p)".
_TITLE_WITH_SECTION = re.compile(r"^\s*(.+?)\s*\(([0-9][A-Za-z0-9]*|[a-z])\)\s*$")
# A hyphen that starts a word (an option such as -l or --all, or the dash in
# "ls - list") is a minus sign; one inside a word ("x-ray") is a hyphen.
_WORD_START_HYPHENS = re.compile(r"(^|[\s(\[|=,/])(-+)")

_NON_ASCII = re.compile(r"[^\x00-\x7f]")

_Font = tuple[bool, bool, bool]  # bold, italic, constant width
_ROMAN: _Font = (False, False, False)


def _escape_non_ascii(text: str) -> str:
    return _NON_ASCII.sub(lambda m: f"\\[u{ord(m.group(0)):04X}]", text)


def _escape(text: str, code: bool = False) -> str:
    r"""Escape text for a roff input line.

    A backslash becomes ``\e``. In code every ``-`` becomes ``\-`` and quotes
    become ``\(aq``/``\(ga``, so the page can be copied from a terminal; in
    prose only a hyphen that starts a word does. Characters outside ASCII
    become ``\[uXXXX]``, which groff reads without preconv(1).
    """
    text = text.replace(_CONTROL, "").replace("\\", "\\e")
    if code:
        text = text.replace("-", "\\-").replace("'", "\\(aq").replace("`", "\\(ga")
    else:
        text = _WORD_START_HYPHENS.sub(lambda m: m.group(1) + "\\-" * len(m.group(2)), text)
    return _escape_non_ascii(text)


def _font_escape(font: _Font) -> str:
    bold, italic, mono = font
    name = ("C" if mono else "") + ("B" if bold else "") + ("I" if italic else "")
    if name in ("", "C"):
        name = "CR" if mono else "R"
    if len(name) == 1:
        return f"\\f{name}"
    if len(name) == 2:
        return f"\\f({name}"
    return f"\\f[{name}]"


def _protect_line_start(line: str) -> str:
    """Keep a text line that starts with a control character from being read as a request."""
    return "\\&" + line if line.startswith((".", "'")) else line


def _quote_argument(arg: str) -> str:
    """Quote a macro argument when it is empty or holds a space."""
    arg = arg.replace('"', "\\(dq")
    return f'"{arg}"' if not arg or any(ch.isspace() for ch in arg) else arg


def _plain_text(nodes: list[Node]) -> str:
    """Concatenate the text of inline nodes, without formatting."""
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, (Text, Code)):
            parts.append(node.content)
        elif isinstance(node, Image):
            parts.append(node.alt_text or "")
        elif isinstance(node, LineBreak):
            parts.append(" ")
        else:
            parts.append(_plain_text(getattr(node, "content", None) or []))
    return "".join(parts)


class ManRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    r"""Render AST nodes to a man(7) page.

    Parameters
    ----------
    options : ManRendererOptions or None, default = None
        Man page rendering options

    Examples
    --------
        >>> from all2md.ast import Document, Heading, Paragraph, Text
        >>> from all2md.renderers.man import ManRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="LS(1)")]),
        ...     Heading(level=2, content=[Text(content="Name")]),
        ...     Paragraph(content=[Text(content="ls - list directory contents")]),
        ... ])
        >>> print(ManRenderer().render_to_string(doc))
        .TH LS 1
        .SH NAME
        ls \- list directory contents
        <BLANKLINE>

    """

    def __init__(self, options: ManRendererOptions | None = None):
        """Initialize the man renderer with options."""
        BaseRenderer._validate_options_type(options, ManRendererOptions, "man")
        options = options or ManRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: ManRendererOptions = options
        self._lines: list[str] = []
        self._output: list[str] = []
        self._reset()

    def _reset(self) -> None:
        self._lines = []
        self._output = []
        self._font: _Font = _ROMAN
        # Set while rendering text that must stay on one line (a .TP tag, a
        # heading, a table cell), where .br and .UR cannot go.
        self._single_line = False
        self._uppercase = False
        # True right after a request that starts a paragraph itself (.SH, .IP,
        # ...), where a .PP would only be an empty paragraph.
        self._suppress_pp = True
        self._depth = 0
        self._heading_base = 1

    # ------------------------------------------------------------ document

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to man(7) source.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            The man page

        """
        self._reset()
        document.accept(self)
        return "\n".join(self._lines) + "\n"

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to a man page and write it to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        self.write_text_output(self.render_to_string(doc), output)

    def visit_document(self, node: Document) -> None:
        """Render a Document node: the ``.TH`` line, then the blocks.

        A leading level-1 heading is the page title and goes into ``.TH``. The
        shallowest remaining heading level becomes ``.SH`` and the next ``.SS``.

        Parameters
        ----------
        node : Document
            Document to render

        """
        children = list(node.children)
        title_node = children[0] if children and isinstance(children[0], Heading) and children[0].level == 1 else None
        if title_node is not None:
            children = children[1:]
        self._lines.append(self._title_line(node, title_node))
        levels = [child.level for child in children if isinstance(child, Heading)]
        self._heading_base = min(levels) if levels else 1
        self._suppress_pp = True
        for child in children:
            child.accept(self)

    def _title_line(self, document: Document, title_node: Optional[Heading]) -> str:
        """Build the ``.TH`` line from the title heading, the metadata and the options."""
        metadata = document.metadata
        meta: dict[str, Any] = metadata.to_dict() if hasattr(metadata, "to_dict") else dict(metadata or {})
        title = _plain_text(title_node.content) if title_node is not None else str(meta.get("title") or "")
        title = " ".join(title.split())
        title_section = ""
        match = _TITLE_WITH_SECTION.match(title)
        if match:
            title, title_section = match.group(1), match.group(2)
        name = title or "UNTITLED"
        section = self.options.section or title_section or str(meta.get("section") or "") or "1"
        raw_date = self.options.date or meta.get("modification_date") or meta.get("creation_date") or ""
        if isinstance(raw_date, (date, datetime)):
            raw_date = raw_date.strftime("%Y-%m-%d")
        source = self.options.source or str(meta.get("source") or "")
        manual = self.options.manual or str(meta.get("manual") or "")
        args = [name, section, str(raw_date), source, manual]
        while args and not args[-1]:
            args.pop()
        return ".TH " + " ".join(_quote_argument(_escape(arg)) for arg in args)

    # -------------------------------------------------------------- blocks

    def _start_block(self) -> None:
        """Begin a new paragraph, unless the request before already did."""
        if self._suppress_pp:
            self._suppress_pp = False
        else:
            self._lines.append(".PP")

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node as ``.SH``, ``.SS`` or, deeper, a bold paragraph.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        if self._depth == 0 and node.level <= self._heading_base + 1:
            is_section = node.level <= self._heading_base
            self._uppercase = is_section and self.options.uppercase_section_headings
            text = self._line_text(node.content)
            self._uppercase = False
            if not text:
                return
            self._lines.append(f"{'.SH' if is_section else '.SS'} {text.replace(chr(34), chr(92) + '(dq')}")
            self._suppress_pp = True
            return
        lines = self._text_lines(self._styled_text(node.content, bold=True))
        if lines:
            self._start_block()
            self._lines.extend(lines)

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node after ``.PP``.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        lines = self._text_lines(self._render_inline_content(node.content))
        if lines:
            self._start_block()
            self._lines.extend(lines)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node between ``.EX`` and ``.EE``.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        self._literal_block(node.content)

    def _literal_block(self, content: str) -> None:
        content = content.rstrip("\n")
        if not content.strip():
            return
        self._start_block()
        self._lines.append(".EX")
        self._lines.extend(_protect_line_start(_escape(line, code=True)) for line in content.split("\n"))
        self._lines.append(".EE")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node as an indented block (``.RS``/``.RE``).

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        self._indented(node.children)

    def _indented(self, children: list[Node]) -> None:
        self._lines.append(".RS")
        self._suppress_pp = False
        self._depth += 1
        for child in children:
            child.accept(self)
        self._depth -= 1
        self._lines.append(".RE")
        self._suppress_pp = False

    def _item_body(self, children: list[Node], prefix: str = "") -> None:
        """Render the blocks of a list item or definition after its tag line.

        The first paragraph follows the tag; later ones start with an untagged
        ``.IP`` so they keep the item's indent. Any other block is indented
        with ``.RS``/``.RE`` to line up with the item text.
        """
        first = True
        for child in children:
            if isinstance(child, Paragraph):
                lead = _escape(prefix) if first else ""
                lines = self._text_lines(lead + self._render_inline_content(child.content))
                if lines:
                    if not first:
                        self._lines.append(".IP")
                    self._lines.extend(lines)
                    first = False
                continue
            if first and prefix:
                self._lines.append(_protect_line_start(_escape(prefix.strip())))
            self._indented([child])
            first = False
        if first and prefix:
            self._lines.append(_protect_line_start(_escape(prefix.strip())))
        self._suppress_pp = False

    def visit_list(self, node: List) -> None:
        """Render a List node as tagged ``.IP`` paragraphs.

        Parameters
        ----------
        node : List
            List to render

        """
        width = len(f"{node.start + len(node.items) - 1}.") + 2
        for offset, item in enumerate(node.items):
            tag = f"{node.start + offset}. {max(width, 4)}" if node.ordered else "\\(bu 2"
            self._lines.append(f".IP {tag}")
            self._list_item_body(item)

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node outside a list as a bullet item.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        self._lines.append(".IP \\(bu 2")
        self._list_item_body(node)

    def _list_item_body(self, item: ListItem) -> None:
        prefix = {"checked": "[x] ", "unchecked": "[ ] "}.get(item.task_status or "", "")
        self._item_body(item.children, prefix)

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node as ``.TP`` items.

        A term with no description of its own shares the next one's, so it is
        joined to the next term with ``.TQ``.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        joined = False
        for term, descriptions in node.items:
            self._lines.append(".TQ" if joined else ".TP")
            self._lines.append(self._line_text(term.content) or "\\&")
            children = [child for description in descriptions for child in description.content]
            joined = not children
            if children:
                self._item_body(children)
        if joined:
            self._suppress_pp = False

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """

    def visit_table(self, node: Table) -> None:
        r"""Render a Table node as a tbl(1) table.

        The header row is set bold through the format line. Column spans become
        ``s`` entries in a per-row format, and row spans ``\^`` data entries.

        Parameters
        ----------
        node : Table
            Table to render

        """
        rows = ([node.header] if node.header else []) + list(node.rows)
        if not rows:
            return
        grid = self._layout_table_grid(rows)
        if grid.num_cols == 0:
            return
        if node.caption:
            self._start_block()
            self._lines.append(_protect_line_start(_escape(node.caption)))
        keys = [{"left": "l", "center": "c", "right": "r"}.get(a or "", "l") for a in node.alignments]
        keys += ["l"] * (grid.num_cols - len(keys))
        keys = keys[: grid.num_cols]

        # cells[row][col] holds the data entry, or None where a column span covers it.
        cells: list[list[Optional[str]]] = [[""] * grid.num_cols for _ in range(grid.num_rows)]
        formats = [list(keys) for _ in range(grid.num_rows)]
        for placement in grid.placements:
            cells[placement.row][placement.col] = self._cell_text(placement.cell)
            for c in range(placement.col + 1, placement.col + placement.colspan):
                formats[placement.row][c] = "s"
                cells[placement.row][c] = None
            for r in range(placement.row + 1, placement.row + placement.rowspan):
                cells[r][placement.col] = "\\^"
                for c in range(placement.col + 1, placement.col + placement.colspan):
                    formats[r][c] = "s"
                    cells[r][c] = None
        has_header = node.header is not None
        if has_header:
            formats[0] = [key if key == "s" else key + "B" for key in formats[0]]

        format_lines = [" ".join(row) for row in formats]
        if all(line == format_lines[-1] for line in format_lines[1:]):
            # No spans: one line for the header (if any) and one for the rest.
            format_lines = format_lines[:2] if has_header else format_lines[:1]
        self._start_block()
        self._lines.append(".TS")
        self._lines.append("allbox;")
        self._lines.extend(format_lines[:-1])
        self._lines.append(format_lines[-1] + ".")
        for row_cells in cells:
            line = "\t".join(cell for cell in row_cells if cell is not None)
            if line.strip() in ("_", "="):
                line = "\\&" + line
            self._lines.append(_protect_line_start(line))
        self._lines.append(".TE")

    def _cell_text(self, cell: TableCell) -> str:
        return self._line_text(cell.content).replace("\t", " ")

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node (handled by visit_table).

        Parameters
        ----------
        node : TableRow
            Table row to render

        """

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node (handled by visit_table).

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node as a row of asterisks; man(7) has no rule.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._start_block()
        self._lines.append("* * *")

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Skip an HTMLBlock node; a man page cannot hold HTML.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node as roff comment lines.

        Parameters
        ----------
        node : Comment
            Comment block to render

        """
        for line in node.content.split("\n"):
            self._lines.append(f'.\\" {_escape_non_ascii(line)}'.rstrip())

    def visit_figure(self, node: Figure) -> None:
        """Render a Figure node: its children, then the caption in italics.

        Parameters
        ----------
        node : Figure
            Figure to render

        """
        for child in node.children:
            child.accept(self)
        if node.caption:
            self._start_block()
            self._lines.append(f"\\fI{_escape(node.caption)}\\fR")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node as a ``.TP`` item tagged ``[id]``.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        self._lines.append(".TP")
        self._lines.append(_protect_line_start(f"[{_escape(node.identifier)}]"))
        self._item_body(node.content)

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node as a code block of its LaTeX source.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        content, _ = node.get_preferred_representation("latex")
        self._literal_block(content)

    # ------------------------------------------------------------- inlines

    def _line_text(self, content: list[Node]) -> str:
        """Render inline nodes for a line that must stay whole (tag, heading, cell)."""
        saved = self._single_line
        self._single_line = True
        try:
            text = self._render_inline_content(content)
        finally:
            self._single_line = saved
        return " ".join(text.split())

    def _styled_text(self, content: list[Node], bold: bool = False, italic: bool = False, mono: bool = False) -> str:
        """Render inline nodes in a font, switching back to the surrounding font after."""
        outer = self._font
        inner: _Font = (outer[0] or bold, outer[1] or italic, outer[2] or mono)
        if inner == outer:
            return self._render_inline_content(content)
        self._font = inner
        try:
            text = self._render_inline_content(content)
        finally:
            self._font = outer
        if not text.strip(" "):
            return text
        return _font_escape(inner) + text + _font_escape(outer)

    def _text_lines(self, text: str) -> list[str]:
        r"""Turn rendered inline text into roff input lines.

        Text lines lose their leading space (it would start a new line in the
        output) and blank ones are dropped (they would print a blank line).
        Requests marked by inline rendering stay on lines of their own. Text
        glued to a link keeps no gap: ``\c`` before ``.UR``, and punctuation
        after it moves into the ``.UE`` argument.
        """
        lines: list[str] = []
        last_raw: Optional[str] = None  # the raw text of lines[-1], when it is text
        for piece in text.split("\n"):
            if piece.startswith(_CONTROL):
                request = piece[len(_CONTROL) :]
                if request == ".br":
                    if lines and lines[-1] != ".br":
                        lines.append(request)
                    last_raw = None
                    continue
                if request.startswith((".UR", ".MT")) and last_raw and not last_raw[-1].isspace():
                    lines[-1] += "\\c"
                lines.append(request)
                last_raw = None
                continue
            if lines and lines[-1] in (".UE", ".ME") and piece[:1] and not piece[0].isspace():
                glued = re.match(r"\S+", piece)
                if glued:
                    lines[-1] += " " + glued.group(0).replace('"', "\\(dq")
                    piece = piece[glued.end() :]
            line = piece.strip()
            if not line:
                continue
            lines.append(_protect_line_start(line))
            last_raw = piece
        while lines and lines[-1] == ".br":
            lines.pop()
        return lines

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        content = node.content.upper() if self._uppercase else node.content
        self._output.append(_escape(content, code=self._font[2]))

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node in italics.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        self._output.append(self._styled_text(node.content, italic=True))

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node in bold.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        self._output.append(self._styled_text(node.content, bold=True))

    def visit_code(self, node: Code) -> None:
        """Render a Code node in the constant-width font.

        Parameters
        ----------
        node : Code
            Code to render

        """
        self._output.append(self._styled_text([Text(content=node.content.replace("\n", " "))], mono=True))

    def visit_link(self, node: Link) -> None:
        """Render a Link node with ``.UR``/``.UE``, or ``.MT``/``.ME`` for mail.

        Where a request cannot go (a tag, heading or table cell), the link
        text is followed by the URL in angle brackets.

        Parameters
        ----------
        node : Link
            Link to render

        """
        url = node.url
        is_mail = url.startswith("mailto:")
        target = url[len("mailto:") :] if is_mail else url
        shown = _plain_text(node.content).strip()
        text = self._render_inline_content(node.content)
        if self._single_line:
            if not shown or shown == target:
                self._output.append(_escape(target))
            else:
                self._output.append(f"{text} <{_escape(target)}>")
            return
        start, end = (".MT", ".ME") if is_mail else (".UR", ".UE")
        argument = _escape_non_ascii(target.replace("\\", "\\e").replace(" ", "%20").replace('"', "%22"))
        self._output.append(f"\n{_CONTROL}{start} {argument}\n")
        if shown and shown != target:
            self._output.append(text)
        self._output.append(f"\n{_CONTROL}{end}\n")

    def visit_image(self, node: Image) -> None:
        """Render an Image node as its alt text.

        Parameters
        ----------
        node : Image
            Image to render

        """
        if node.alt_text:
            self._output.append(_escape(node.alt_text))

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node: ``.br`` for a hard break, a space for a soft one.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft or self._single_line:
            self._output.append(" ")
        else:
            self._output.append(f"\n{_CONTROL}.br\n")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node as plain text; man(7) cannot strike out.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        self._output.append(self._render_inline_content(node.content))

    def visit_mark(self, node: Mark) -> None:
        """Render a Mark node as plain text.

        Parameters
        ----------
        node : Mark
            Highlighted text to render

        """
        self._output.append(self._render_inline_content(node.content))

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node in italics, which a terminal shows underlined.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        self._output.append(self._styled_text(node.content, italic=True))

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node as plain text.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        self._output.append(self._render_inline_content(node.content))

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node as plain text.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        self._output.append(self._render_inline_content(node.content))

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Skip an HTMLInline node; a man page cannot hold HTML.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Skip a CommentInline node; roff comments run to the end of the line.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node as ``[id]``.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        self._output.append(f"[{_escape(node.identifier)}]")

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node as its LaTeX source in the constant-width font.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        content, _ = node.get_preferred_representation("latex")
        self._output.append(self._styled_text([Text(content=content)], mono=True))
