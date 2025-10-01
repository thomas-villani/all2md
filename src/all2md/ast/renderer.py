#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/renderer.py
"""Markdown rendering from AST.

This module provides the MarkdownRenderer class which converts AST nodes
to markdown text. The renderer supports multiple markdown flavors and
configurable rendering options.

The rendering process uses the visitor pattern to traverse the AST and
generate markdown output. The renderer maintains context (indentation,
list nesting) during traversal.

"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from all2md.ast.flavors import GFMFlavor, MarkdownFlavor
from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
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


@dataclass
class RenderOptions:
    """Configuration options for markdown rendering.

    This class contains all options that control how AST nodes are rendered
    to markdown text. It maps to the existing MarkdownOptions for backward
    compatibility.

    Parameters
    ----------
    flavor : MarkdownFlavor, default = GFMFlavor()
        Markdown dialect to use for rendering
    escape_special : bool, default = True
        Whether to escape special markdown characters
    emphasis_symbol : {'*', '_'}, default = '*'
        Symbol to use for emphasis (italic)
    bullet_symbols : str, default = '*-+'
        Characters to cycle through for nested bullet lists
    list_indent_width : int, default = 4
        Number of spaces per indentation level in lists
    underline_mode : {'html', 'markdown', 'ignore'}, default = 'html'
        How to render underlined text
    superscript_mode : {'html', 'markdown', 'ignore'}, default = 'html'
        How to render superscript text
    subscript_mode : {'html', 'markdown', 'ignore'}, default = 'html'
        How to render subscript text
    use_hash_headings : bool, default = True
        Use # style headings instead of underline style
    max_line_width : int or None, default = None
        Maximum line width (None for no limit)
    prefer_setext_headings : bool, default = False
        Prefer setext (underline) style for h1 and h2
    table_alignment_default : {'left', 'center', 'right'}, default = 'left'
        Default alignment for table columns

    """

    flavor: MarkdownFlavor = field(default_factory=GFMFlavor)
    escape_special: bool = True
    emphasis_symbol: Literal["*", "_"] = "*"
    bullet_symbols: str = "*-+"
    list_indent_width: int = 4
    underline_mode: Literal["html", "markdown", "ignore"] = "html"
    superscript_mode: Literal["html", "markdown", "ignore"] = "html"
    subscript_mode: Literal["html", "markdown", "ignore"] = "html"
    use_hash_headings: bool = True
    max_line_width: int | None = None
    prefer_setext_headings: bool = False
    table_alignment_default: Literal["left", "center", "right"] = "left"


class MarkdownRenderer(NodeVisitor):
    """Render AST nodes to markdown text.

    This class implements the visitor pattern to traverse an AST and
    generate markdown output. It supports multiple markdown flavors
    and configurable rendering options.

    Parameters
    ----------
    options : RenderOptions or None, default = None
        Rendering configuration options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text, MarkdownRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = MarkdownRenderer()
        >>> markdown = renderer.render(doc)
        >>> print(markdown)
        # Title

    """

    def __init__(self, options: RenderOptions | None = None):
        self.options = options or RenderOptions()
        self._output: list[str] = []
        self._indent_level: int = 0
        self._in_list: bool = False
        self._list_marker_stack: list[str] = []

    def render(self, document: Document) -> str:
        """Render a document AST to markdown.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            Markdown text

        """
        self._output = []
        self._indent_level = 0
        self._in_list = False
        self._list_marker_stack = []

        document.accept(self)
        result = ''.join(self._output)

        return self._cleanup_output(result)

    def _cleanup_output(self, text: str) -> str:
        """Clean up the final output.

        Parameters
        ----------
        text : str
            Raw markdown text

        Returns
        -------
        str
            Cleaned markdown text

        """
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.rstrip()
        return text

    def _escape_markdown(self, text: str) -> str:
        """Escape special markdown characters.

        Parameters
        ----------
        text : str
            Text to escape

        Returns
        -------
        str
            Escaped text

        """
        if not self.options.escape_special:
            return text

        # Escape characters that need it in inline content
        # Note: Some chars like +, -, ., ! only need escaping in specific contexts
        # but # can start a heading, so we escape it
        special_chars = r'\`*_{}[]#'
        escaped = ''
        for char in text:
            if char in special_chars:
                escaped += '\\' + char
            else:
                escaped += char
        return escaped

    def _render_inline_content(self, content: list[Node]) -> str:
        """Render a list of inline nodes to text.

        Parameters
        ----------
        content : list of Node
            Inline nodes to render

        Returns
        -------
        str
            Rendered inline text

        """
        saved_output = self._output
        self._output = []

        for node in content:
            node.accept(self)

        result = ''.join(self._output)
        self._output = saved_output
        return result

    def _current_indent(self) -> str:
        """Get the current indentation string.

        Returns
        -------
        str
            Indentation spaces

        """
        return ' ' * (self._indent_level * self.options.list_indent_width)

    def _get_bullet_symbol(self, depth: int) -> str:
        """Get the bullet symbol for a given nesting depth.

        Parameters
        ----------
        depth : int
            Nesting depth (0-based)

        Returns
        -------
        str
            Bullet character

        """
        symbols = self.options.bullet_symbols
        return symbols[depth % len(symbols)]

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append('\n\n')

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)

        # Use setext style if hash headings are disabled or prefer_setext is set for h1/h2
        if (not self.options.use_hash_headings or self.options.prefer_setext_headings) and node.level <= 2:
            underline_char = '=' if node.level == 1 else '-'
            underline = underline_char * len(content)
            self._output.append(f"{content}\n{underline}")
        else:
            # Use hash style for h3-h6 or when use_hash_headings is True
            prefix = '#' * node.level
            self._output.append(f"{prefix} {content}")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        indent = self._current_indent()
        self._output.append(f"{indent}{content}")

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        fence = node.fence_char * node.fence_length
        lang = node.language or ''

        self._output.append(f"{fence}{lang}\n")
        self._output.append(node.content)
        if not node.content.endswith('\n'):
            self._output.append('\n')
        self._output.append(fence)

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        saved_output = self._output
        self._output = []

        for child in node.children:
            child.accept(self)

        quoted = ''.join(self._output)
        lines = quoted.split('\n')
        quoted_lines = ['> ' + line for line in lines]

        self._output = saved_output
        self._output.append('\n'.join(quoted_lines))

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        was_in_list = self._in_list
        self._in_list = True

        for i, item in enumerate(node.items):
            if node.ordered:
                marker = f"{node.start + i}. "
            else:
                depth = len(self._list_marker_stack)
                bullet = self._get_bullet_symbol(depth)
                marker = f"{bullet} "

            self._list_marker_stack.append(marker)
            item.accept(self)
            self._list_marker_stack.pop()

            if i < len(node.items) - 1:
                if node.tight:
                    self._output.append('\n')
                else:
                    self._output.append('\n\n')

        self._in_list = was_in_list

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        indent = self._current_indent()
        marker = self._list_marker_stack[-1] if self._list_marker_stack else '* '

        if node.task_status and self.options.flavor.supports_task_lists():
            checkbox = '[x]' if node.task_status == 'checked' else '[ ]'
            marker = f"{marker}{checkbox} "

        self._output.append(f"{indent}{marker}")

        # Render children - first child inline with marker, others indented
        for i, child in enumerate(node.children):
            if i == 0:
                # First child goes immediately after the marker
                saved_output = self._output
                self._output = []
                child.accept(self)
                child_content = ''.join(self._output)
                self._output = saved_output
                self._output.append(child_content)
            else:
                # Subsequent children are indented
                self._indent_level += 1
                child_indent = self._current_indent()
                self._output.append(f"\n{child_indent}")
                child.accept(self)
                self._indent_level -= 1

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Render caption if present
        if node.caption:
            self._output.append(f"*{node.caption}*\n\n")

        if not self.options.flavor.supports_tables():
            self._render_table_as_html(node)
            return

        rows_to_render = [node.header] if node.header else []
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        num_cols = len(rows_to_render[0].cells) if rows_to_render else 0

        rendered_rows: list[list[str]] = []
        for row in rows_to_render:
            cells: list[str] = []
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                content = content.replace('|', '\\|')
                cells.append(content)
            rendered_rows.append(cells)

        col_widths: list[int] = [0] * num_cols
        for row_cells in rendered_rows:
            for i, cell_content in enumerate(row_cells):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell_content))

        for i, row_cells in enumerate(rendered_rows):
            padded_cells: list[str] = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    padded_cells.append(padded)
            self._output.append('| ' + ' | '.join(padded_cells) + ' |')

            if i == 0 and node.header:
                alignments = []
                for j, alignment in enumerate(node.alignments if node.alignments else []):
                    # Use exactly 3 dashes for alignment (markdown minimum)
                    if alignment == 'center':
                        alignments.append(':---:')
                    elif alignment == 'right':
                        alignments.append('---:')
                    elif alignment == 'left':
                        alignments.append(':---')
                    else:
                        # Default to left alignment
                        alignments.append('---')

                # Fill remaining columns with default alignment
                while len(alignments) < num_cols:
                    alignments.append('---')

                self._output.append('\n|' + '|'.join(alignments) + '|')

            if i < len(rendered_rows) - 1:
                self._output.append('\n')

    def _render_table_as_html(self, node: Table) -> None:
        """Render a table as HTML when markdown tables are not supported.

        Parameters
        ----------
        node : Table
            Table to render as HTML

        """
        self._output.append('<table>\n')
        if node.header:
            self._output.append('  <thead>\n    <tr>')
            for cell in node.header.cells:
                content = self._render_inline_content(cell.content)
                self._output.append(f'<th>{content}</th>')
            self._output.append('</tr>\n  </thead>\n')

        if node.rows:
            self._output.append('  <tbody>\n')
            for row in node.rows:
                self._output.append('    <tr>')
                for cell in row.cells:
                    content = self._render_inline_content(cell.content)
                    self._output.append(f'<td>{content}</td>')
                self._output.append('</tr>\n')
            self._output.append('  </tbody>\n')

        self._output.append('</table>')

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node.

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node.

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._output.append('---')

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        self._output.append(node.content)

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        text = self._escape_markdown(node.content)
        self._output.append(text)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        symbol = self.options.emphasis_symbol
        self._output.append(f"{symbol}{content}{symbol}")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"**{content}**")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        backticks = '`'
        if '`' in node.content:
            backticks = '``'
        self._output.append(f"{backticks}{node.content}{backticks}")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        if node.title:
            self._output.append(f'[{content}]({node.url} "{node.title}")')
        else:
            self._output.append(f'[{content}]({node.url})')

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        alt = node.alt_text.replace('[', '\\[').replace(']', '\\]')
        if node.title:
            self._output.append(f'![{alt}]({node.url} "{node.title}")')
        else:
            self._output.append(f'![{alt}]({node.url})')

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            self._output.append('\n')
        else:
            self._output.append('  \n')

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        if self.options.flavor.supports_strikethrough():
            self._output.append(f"~~{content}~~")
        else:
            self._output.append(f"<del>{content}</del>")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        mode = self.options.underline_mode

        if mode == "html":
            self._output.append(f"<u>{content}</u>")
        elif mode == "markdown":
            self._output.append(f"__{content}__")
        else:
            self._output.append(content)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        mode = self.options.superscript_mode

        if mode == "html":
            self._output.append(f"<sup>{content}</sup>")
        elif mode == "markdown":
            self._output.append(f"^{content}^")
        else:
            self._output.append(content)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        mode = self.options.subscript_mode

        if mode == "html":
            self._output.append(f"<sub>{content}</sub>")
        elif mode == "markdown":
            self._output.append(f"~{content}~")
        else:
            self._output.append(content)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        self._output.append(node.content)
