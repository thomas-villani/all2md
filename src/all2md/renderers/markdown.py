#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/markdown.py
"""Markdown rendering from AST.

This module provides the MarkdownRenderer class which converts AST nodes
to markdown text. The renderer supports multiple markdown flavors and
configurable rendering options.

The rendering process uses the visitor pattern to traverse the AST and
generate markdown output. The renderer maintains context (indentation,
list nesting) during traversal.

"""

from __future__ import annotations

from pathlib import Path
import re
from typing import IO, Union

from all2md.utils.flavors import (
    CommonMarkFlavor,
    GFMFlavor,
    KramdownFlavor,
    MarkdownFlavor,
    MarkdownPlusFlavor,
    MultiMarkdownFlavor,
    PandocFlavor,
)
from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
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
from all2md.options import MarkdownOptions
from all2md.renderers.base import BaseRenderer
from all2md.ast.visitors import NodeVisitor
from all2md.utils.html_utils import render_math_html


class MarkdownRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to markdown text.

    This class implements the visitor pattern to traverse an AST and
    generate markdown output. It supports multiple markdown flavors
    and configurable rendering options.

    Parameters
    ----------
    options : MarkdownOptions or None, default = None
        Markdown formatting options (shared with parsers)

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.options import MarkdownOptions
        >>> from all2md.renderers.markdown import MarkdownRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = MarkdownOptions(flavor="gfm")
        >>> renderer = MarkdownRenderer(options)
        >>> markdown = renderer.render_to_string(doc)
        >>> print(markdown)
        # Title

    """

    def __init__(self, options: MarkdownOptions | None = None):
        # Initialize BaseRenderer
        options = options or MarkdownOptions()
        BaseRenderer.__init__(self, options)
        self.options: MarkdownOptions = options
        self._flavor = self._get_flavor(self.options.flavor)
        self._output: list[str] = []
        self._indent_level: int = 0
        self._in_list: bool = False
        self._list_marker_stack: list[str] = []
        self._link_references: dict[str, int] = {}  # url -> ref_id for reference-style links
        self._next_ref_id: int = 1

    @staticmethod
    def _get_flavor(flavor_name: str) -> MarkdownFlavor:
        """Get flavor instance from string name.

        Parameters
        ----------
        flavor_name : str
            Flavor name ("gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus")

        Returns
        -------
        MarkdownFlavor
            Flavor instance

        """
        flavors = {
            "gfm": GFMFlavor(),
            "commonmark": CommonMarkFlavor(),
            "multimarkdown": MultiMarkdownFlavor(),
            "pandoc": PandocFlavor(),
            "kramdown": KramdownFlavor(),
            "markdown_plus": MarkdownPlusFlavor(),
        }
        return flavors.get(flavor_name, GFMFlavor())

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to markdown string.

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
        self._link_references = {}
        self._next_ref_id = 1

        document.accept(self)

        # Append link references if using reference style
        if self.options.link_style == "reference" and self._link_references:
            self._output.append('\n\n')
            for url, ref_id in sorted(self._link_references.items(), key=lambda x: x[1]):
                self._output.append(f'[{ref_id}]: {url}\n')

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
        if self.options.collapse_blank_lines:
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
        # Render metadata as YAML frontmatter if present and enabled
        if self.options.metadata_frontmatter and node.metadata:
            self._render_yaml_frontmatter(node.metadata)
            self._output.append('\n\n')

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append('\n\n')

    def _render_yaml_frontmatter(self, metadata: dict) -> None:
        """Render metadata as YAML frontmatter.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary to render

        """
        if not metadata:
            return

        self._output.append('---\n')

        for key, value in metadata.items():
            if value is None:
                continue

            # Handle list values
            if isinstance(value, list):
                if value:  # Only render non-empty lists
                    self._output.append(f'{key}:\n')
                    for item in value:
                        self._output.append(f'  - {self._yaml_escape(item)}\n')
            # Handle dict values
            elif isinstance(value, dict):
                self._output.append(f'{key}:\n')
                for sub_key, sub_value in value.items():
                    if sub_value is not None:
                        self._output.append(f'  {sub_key}: {self._yaml_escape(sub_value)}\n')
            # Handle simple values
            else:
                self._output.append(f'{key}: {self._yaml_escape(value)}\n')

        self._output.append('---')

    def _yaml_escape(self, value: any) -> str:
        """Escape a value for YAML output.

        Parameters
        ----------
        value : any
            Value to escape

        Returns
        -------
        str
            YAML-safe string

        """
        value_str = str(value)

        # If the value contains special characters, quote it
        if any(char in value_str for char in [':', '#', '[', ']', '{', '}', ',', '&', '*', '!', '|', '>', '@', '`']):
            # Escape any quotes in the value
            value_str = value_str.replace('"', '\\"')
            return f'"{value_str}"'

        # If it starts with a special character or looks like a number/boolean, quote it
        if value_str and (value_str[0] in ['-', '?', ':'] or value_str.lower() in ['true', 'false', 'yes', 'no', 'null']):
            return f'"{value_str}"'

        return value_str

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)

        # Apply heading level offset (clamped to valid range 1-6)
        adjusted_level = max(1, min(6, node.level + self.options.heading_level_offset))

        # Use setext style if hash headings are disabled or prefer_setext is set for h1/h2
        if (not self.options.use_hash_headings or self.options.prefer_setext_headings) and adjusted_level <= 2:
            underline_char = '=' if adjusted_level == 1 else '-'
            underline = underline_char * len(content)
            self._output.append(f"{content}\n{underline}")
        else:
            # Use hash style for h3-h6 or when use_hash_headings is True
            prefix = '#' * adjusted_level
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
        # Use fence char from options
        fence_char = self.options.code_fence_char

        # Calculate required fence length (at least code_fence_min, longer if needed)
        fence_length = self.options.code_fence_min
        # Check if code content contains fence sequences that would break parsing
        if fence_char in node.content:
            # Find longest sequence of fence_char in content
            max_consecutive = 0
            current_consecutive = 0
            for char in node.content:
                if char == fence_char:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 0
            # Use fence length that's longer than any sequence in content
            fence_length = max(fence_length, max_consecutive + 1)

        fence = fence_char * fence_length
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

        if node.task_status and self._flavor.supports_task_lists():
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
                # Subsequent children (nested lists, paragraphs) are indented
                # Use marker width for proper alignment
                marker_width = len(marker)
                child_indent = indent + (' ' * marker_width)
                self._output.append(f"\n{child_indent}")

                # Save and restore indent level for nested lists
                saved_indent = self._indent_level
                self._indent_level = len(indent + (' ' * marker_width)) // self.options.list_indent_width
                child.accept(self)
                self._indent_level = saved_indent

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

        # Handle tables not supported by the flavor
        if not self._flavor.supports_tables():
            mode = self.options.unsupported_table_mode
            if mode == "drop":
                # Skip table entirely
                return
            elif mode == "ascii":
                # Render as ASCII art
                self._render_table_as_ascii(node)
                return
            elif mode == "html":
                # Render as HTML
                self._render_table_as_html(node)
                return
            # else: mode == "force", continue with pipe table rendering

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
                if self.options.table_pipe_escape:
                    content = content.replace('|', '\\|')
                cells.append(content)
            rendered_rows.append(cells)

        if self.options.pad_table_cells:
            # Calculate column widths and pad cells for alignment
            col_widths: list[int] = [0] * num_cols
            for row_cells in rendered_rows:
                for i, cell_content in enumerate(row_cells):
                    if i < num_cols:
                        col_widths[i] = max(col_widths[i], len(cell_content))

            for i, row_cells in enumerate(rendered_rows):
                if i > 0:
                    self._output.append('\n')
                padded_cells: list[str] = []
                for j, cell_content in enumerate(row_cells):
                    if j < num_cols:
                        padded = cell_content.ljust(col_widths[j])
                        padded_cells.append(padded)
                self._output.append('| ' + ' | '.join(padded_cells) + ' |')

                if i == 0 and node.header:
                    self._output.append('\n')
                    alignments = []
                    for j, alignment in enumerate(node.alignments if node.alignments else []):
                        if j >= num_cols:
                            break
                        if alignment == 'center':
                            alignments.append(':' + '-' * max(3, col_widths[j]) + ':')
                        elif alignment == 'right':
                            alignments.append('-' * max(3, col_widths[j]) + ':')
                        elif alignment == 'left':
                            alignments.append(':' + '-' * max(3, col_widths[j]))
                        else:
                            alignments.append('-' * max(3, col_widths[j]))
                    # Fill remaining columns with default alignment
                    while len(alignments) < num_cols:
                        alignments.append('-' * max(3, col_widths[len(alignments)]))
                    # Alignment row without spaces (for backward compatibility)
                    self._output.append('|' + '|'.join(alignments) + '|')
        else:
            # Minimal spacing - no padding
            for i, row_cells in enumerate(rendered_rows):
                if i > 0:
                    self._output.append('\n')
                self._output.append('| ' + ' | '.join(row_cells) + ' |')

                if i == 0 and node.header:
                    self._output.append('\n')
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

                    # Alignment row without spaces (for backward compatibility)
                    self._output.append('|' + '|'.join(alignments) + '|')

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

    def _render_table_as_ascii(self, node: Table) -> None:
        """Render a table as ASCII art when markdown tables are not supported.

        Parameters
        ----------
        node : Table
            Table to render as ASCII art

        """
        rows_to_render = [node.header] if node.header else []
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        num_cols = len(rows_to_render[0].cells) if rows_to_render else 0

        # Render all cells to determine column widths
        rendered_rows: list[list[str]] = []
        for row in rows_to_render:
            cells: list[str] = []
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                cells.append(content)
            rendered_rows.append(cells)

        # Calculate column widths
        col_widths: list[int] = [0] * num_cols
        for row_cells in rendered_rows:
            for i, cell_content in enumerate(row_cells):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell_content))

        # Build separator line
        separator = '+' + '+'.join(['-' * (width + 2) for width in col_widths]) + '+'

        # Render table
        self._output.append(separator + '\n')
        for i, row_cells in enumerate(rendered_rows):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    row_parts.append(f' {padded} ')
            self._output.append('|' + '|'.join(row_parts) + '|\n')

            # Add separator after header or after each row
            if i == 0 and node.header:
                # Double separator after header
                header_sep = '+' + '+'.join(['=' * (width + 2) for width in col_widths]) + '+'
                self._output.append(header_sep + '\n')
            elif i < len(rendered_rows) - 1:
                # Single separator between rows
                self._output.append(separator + '\n')

        # Final separator
        self._output.append(separator)

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

        if self.options.link_style == "reference":
            # Reference-style links: [text][ref]
            # Get or create reference ID for this URL
            if node.url not in self._link_references:
                self._link_references[node.url] = self._next_ref_id
                self._next_ref_id += 1
            ref_id = self._link_references[node.url]
            self._output.append(f'[{content}][{ref_id}]')
        else:
            # Inline-style links: [text](url)
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
        if not node.url:
            # Alt-text only (no URL)
            self._output.append(f'![{alt}]()')
        elif node.title:
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
        if self._flavor.supports_strikethrough():
            self._output.append(f"~~{content}~~")
        else:
            mode = self.options.unsupported_inline_mode
            if mode == "plain":
                # Strip formatting, render content only
                self._output.append(content)
            elif mode == "force":
                # Use markdown syntax anyway
                self._output.append(f"~~{content}~~")
            else:  # mode == "html"
                # Use HTML tags
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

    def visit_footnote_reference(self, node: "FootnoteReference") -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        if self._flavor.supports_footnotes():
            self._output.append(f"[^{node.identifier}]")
        else:
            mode = self.options.unsupported_inline_mode
            if mode == "plain":
                pass
            elif mode == "force":
                self._output.append(f"[^{node.identifier}]")
            else:
                self._output.append(f"<sup>{node.identifier}</sup>")

    def visit_math_inline(self, node: "MathInline") -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        preferred = self.options.math_mode
        content, notation = node.get_preferred_representation(preferred)

        if self._flavor.supports_math() and notation == "latex":
            self._output.append(f"${content}$")
            return

        if self._flavor.supports_math():
            self._output.append(render_math_html(content, notation, inline=True))
            return

        mode = self.options.unsupported_inline_mode
        if mode == "plain":
            self._output.append(content)
        elif mode == "force" and notation == "latex":
            self._output.append(f"${content}$")
        else:
            self._output.append(render_math_html(content, notation, inline=True))

    def visit_footnote_definition(self, node: "FootnoteDefinition") -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        if self._flavor.supports_footnotes():
            self._output.append(f"[^{node.identifier}]: ")
            for i, child in enumerate(node.content):
                saved_output = self._output
                self._output = []
                child.accept(self)
                child_content = ''.join(self._output)
                self._output = saved_output
                if i == 0:
                    self._output.append(child_content)
                else:
                    indent_lines = child_content.split('\n')
                    self._output.append('\n    ' + '\n    '.join(indent_lines))
        else:
            mode = self.options.unsupported_table_mode
            if mode == "drop":
                return
            elif mode == "html":
                self._output.append(f'<div id="fn-{node.identifier}">')
                for child in node.content:
                    child.accept(self)
                self._output.append('</div>')
            else:
                self._output.append(f"[^{node.identifier}]: ")
                for child in node.content:
                    child.accept(self)

    def visit_definition_list(self, node: "DefinitionList") -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        if not self._flavor.supports_definition_lists():
            mode = self.options.unsupported_table_mode
            if mode == "drop":
                return
            elif mode == "html":
                self._output.append('<dl>\n')
                for term, descriptions in node.items:
                    self._output.append('  <dt>')
                    term_content = self._render_inline_content(term.content)
                    self._output.append(term_content)
                    self._output.append('</dt>\n')
                    for desc in descriptions:
                        self._output.append('  <dd>')
                        for child in desc.content:
                            child.accept(self)
                        self._output.append('</dd>\n')
                self._output.append('</dl>')
                return
        for i, (term, descriptions) in enumerate(node.items):
            if i > 0:
                self._output.append('\n')
            term_content = self._render_inline_content(term.content)
            self._output.append(term_content)
            for desc in descriptions:
                self._output.append('\n: ')
                for j, child in enumerate(desc.content):
                    if j > 0:
                        self._output.append('\n    ')
                    saved_output = self._output
                    self._output = []
                    child.accept(self)
                    child_content = ''.join(self._output)
                    self._output = saved_output
                    if j > 0:
                        indent_lines = child_content.split('\n')
                        self._output.append('\n    '.join(indent_lines))
                    else:
                        self._output.append(child_content)

    def visit_definition_term(self, node: "DefinitionTerm") -> None:
        """Render a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass

    def visit_definition_description(self, node: "DefinitionDescription") -> None:
        """Render a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass

    def visit_math_block(self, node: "MathBlock") -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        preferred = self.options.math_mode
        content, notation = node.get_preferred_representation(preferred)

        if self._flavor.supports_math() and notation == "latex":
            self._output.append("$$\n")
            self._output.append(content)
            if not content.endswith('\n'):
                self._output.append('\n')
            self._output.append("$$")
            return

        if self._flavor.supports_math():
            self._output.append(render_math_html(content, notation, inline=False))
            return

        mode = self.options.unsupported_table_mode
        if mode == "drop":
            return
        if mode == "html" or notation != "latex":
            self._output.append(render_math_html(content, notation, inline=False))
            return

        # Mode is force or ascii; fall back to latex block fencing
        self._output.append("$$\n")
        self._output.append(content)
        if not content.endswith('\n'):
            self._output.append('\n')
        self._output.append("$$")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to markdown and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        markdown_text = self.render_to_string(doc)

        if isinstance(output, (str, Path)):
            # Write to file
            Path(output).write_text(markdown_text, encoding="utf-8")
        else:
            # Write to file-like object
            if hasattr(output, 'mode') and 'b' in output.mode:
                # Binary mode
                output.write(markdown_text.encode('utf-8'))
            else:
                # Text mode
                output.write(markdown_text)
