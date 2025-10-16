#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/rst.py
"""reStructuredText rendering from AST.

This module provides the RestructuredTextRenderer class which converts AST nodes
to reStructuredText. The renderer supports configurable heading underlines,
table styles, and code block formatting.

The rendering process uses the visitor pattern to traverse the AST and
generate RST output.

"""

from __future__ import annotations

import re
from pathlib import Path
from typing import IO, Union

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
    MathNotation,
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
from all2md.options.rst import RstRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.escape import escape_rst


class RestructuredTextRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to reStructuredText.

    This class implements the visitor pattern to traverse an AST and
    generate RST output with configurable formatting options.

    Parameters
    ----------
    options : RstRendererOptions or None, default = None
        RST formatting options

    Examples
    --------
    Basic usage:

        >>> from all2md.options.rst import RstRendererOptions
        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.rst import RestructuredTextRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = RestructuredTextRenderer()
        >>> rst = renderer.render_to_string(doc)
        >>> print(rst)
        Title
        =====

    """

    def __init__(self, options: RstRendererOptions | None = None):
        """Initialize the RST renderer with options."""
        BaseRenderer.__init__(self, options or RstRendererOptions())
        self.options: RstRendererOptions = self.options  # type narrowing
        self._output: list[str] = []
        self._in_list: bool = False
        self._list_depth: int = 0

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to RST string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            RST text

        """
        self._output = []
        self._in_list = False
        self._list_depth = 0

        document.accept(self)

        result = ''.join(self._output)
        return self._cleanup_output(result)

    def _cleanup_output(self, text: str) -> str:
        """Clean up the final output.

        Parameters
        ----------
        text : str
            Raw RST text

        Returns
        -------
        str
            Cleaned RST text

        """
        # Remove excessive blank lines
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        text = text.rstrip()
        return text

    def _get_heading_underline(self, level: int, text: str) -> str:
        """Get the underline character and string for a heading.

        Parameters
        ----------
        level : int
            Heading level (1-6)
        text : str
            Heading text (to determine underline length)

        Returns
        -------
        str
            Underline string

        """
        # Map level to character from options
        chars = self.options.heading_chars
        char_index = min(level - 1, len(chars) - 1)
        char = chars[char_index] if char_index >= 0 else '='

        # Underline should be at least as long as text
        return char * len(text)

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        # Render metadata as docinfo if present
        metadata_block = self._prepare_metadata(node.metadata)
        if metadata_block:
            self._render_docinfo(metadata_block)

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append('\n\n')

    def _render_docinfo(self, metadata: dict) -> None:
        """Render metadata as RST docinfo block.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary

        """
        if not metadata:
            return

        docinfo_fields = []

        if metadata.get('title'):
            docinfo_fields.append(f":Title: {metadata['title']}")
        if metadata.get('author'):
            docinfo_fields.append(f":Author: {metadata['author']}")
        if metadata.get('source'):
            docinfo_fields.append(f":Source: {metadata['source']}")
        if metadata.get('creation_date'):
            docinfo_fields.append(f":Date: {metadata['creation_date']}")
        if metadata.get('modification_date'):
            docinfo_fields.append(f":Updated: {metadata['modification_date']}")
        if metadata.get('accessed_date'):
            docinfo_fields.append(f":Accessed: {metadata['accessed_date']}")
        if metadata.get('description'):
            docinfo_fields.append(f":Summary: {metadata['description']}")
        if metadata.get('keywords'):
            keywords = metadata['keywords']
            if isinstance(keywords, list):
                keywords_str = ', '.join(str(k) for k in keywords)
            else:
                keywords_str = str(keywords)
            docinfo_fields.append(f":Keywords: {keywords_str}")
        if metadata.get('language'):
            docinfo_fields.append(f":Language: {metadata['language']}")
        if metadata.get('category'):
            docinfo_fields.append(f":Category: {metadata['category']}")

        if 'custom' in metadata and isinstance(metadata['custom'], dict):
            for key, value in metadata['custom'].items():
                docinfo_fields.append(f":{key.title()}: {value}")

        if docinfo_fields:
            for field in docinfo_fields:
                self._output.append(field + '\n')
            self._output.append('\n')

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)
        underline = self._get_heading_underline(node.level, content)

        self._output.append(f"{content}\n{underline}")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if self.options.code_directive_style == "directive":
            # Use .. code-block:: directive
            if node.language:
                self._output.append(f".. code-block:: {node.language}\n\n")
            else:
                self._output.append(".. code-block::\n\n")

            # Indent code content
            lines = node.content.split('\n')
            for line in lines:
                self._output.append(f"   {line}\n")
        else:
            # Use :: literal block
            self._output.append("::\n\n")
            lines = node.content.split('\n')
            for line in lines:
                self._output.append(f"   {line}\n")

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

        # Indent all lines
        quoted_lines = ['   ' + line for line in lines]

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
        self._list_depth += 1

        for i, item in enumerate(node.items):
            if node.ordered:
                # Use numbered list format
                number = node.start + i
                marker = f"{number}. "
            else:
                # Use bullet list format
                marker = "* "

            # Add indentation for nested lists
            indent = '   ' * (self._list_depth - 1)
            self._output.append(f"{indent}{marker}")

            # Render item content
            saved_output = self._output
            self._output = []
            item.accept(self)
            item_content = ''.join(self._output)
            self._output = saved_output

            # Add item content (first line inline with marker, rest indented)
            lines = item_content.split('\n')
            if lines:
                self._output.append(lines[0])
                for line in lines[1:]:
                    if line.strip():
                        self._output.append(f"\n{indent}   {line}")

            if i < len(node.items) - 1:
                self._output.append('\n')

        self._list_depth -= 1
        self._in_list = was_in_list

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append('\n')

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        if self.options.table_style == "grid":
            self._render_grid_table(node)
        else:
            self._render_simple_table(node)

    def _render_grid_table(self, node: Table) -> None:
        """Render a table as RST grid table.

        Parameters
        ----------
        node : Table
            Table to render

        Notes
        -----
        Multi-line cell content is not supported. Cell content is rendered
        inline, which may cause formatting issues for complex content like
        multiple paragraphs or nested lists.

        """
        # Collect all rows
        rows_to_render = []
        if node.header:
            rows_to_render.append(node.header)
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        # Render all cells to determine column widths
        rendered_rows = []
        num_cols = len(rows_to_render[0].cells) if rows_to_render else 0

        for row in rows_to_render:
            cells = []
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                cells.append(content)
            rendered_rows.append(cells)

        # Calculate column widths
        col_widths = [0] * num_cols
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

            # Add separator after header or after last row
            if i == 0 and node.header:
                # Double separator after header
                header_sep = '+' + '+'.join(['=' * (width + 2) for width in col_widths]) + '+'
                self._output.append(header_sep + '\n')
            elif i == len(rendered_rows) - 1:
                # Separator at end
                self._output.append(separator)
            else:
                # Separator between rows
                self._output.append(separator + '\n')

    def _render_simple_table(self, node: Table) -> None:
        """Render a table as RST simple table.

        Parameters
        ----------
        node : Table
            Table to render

        Notes
        -----
        Multi-line cell content is not supported. Cell content is rendered
        inline, which may cause formatting issues for complex content like
        multiple paragraphs or nested lists.

        """
        # Collect all rows
        rows_to_render = []
        if node.header:
            rows_to_render.append(node.header)
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        # Render all cells
        rendered_rows = []
        num_cols = len(rows_to_render[0].cells) if rows_to_render else 0

        for row in rows_to_render:
            cells = []
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                cells.append(content)
            rendered_rows.append(cells)

        # Calculate column widths
        col_widths = [0] * num_cols
        for row_cells in rendered_rows:
            for i, cell_content in enumerate(row_cells):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell_content))

        # Build separator line
        separator = '  '.join(['=' * width for width in col_widths])

        # Render table
        self._output.append(separator + '\n')

        for i, row_cells in enumerate(rendered_rows):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    row_parts.append(padded)
            self._output.append('  '.join(row_parts) + '\n')

            # Add separator after header
            if i == 0 and node.header:
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
        self._output.append('----')

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # Escape RST special characters
        text = escape_rst(node.content)
        self._output.append(text)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"*{content}*")

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
        self._output.append(f"``{node.content}``")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)

        # RST link syntax: `text <url>`_
        if node.url:
            self._output.append(f"`{content} <{node.url}>`_")
        else:
            self._output.append(content)

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        # RST image directive
        self._output.append(f".. image:: {node.url}\n")
        if node.alt_text:
            self._output.append(f"   :alt: {node.alt_text}\n")

    def visit_line_break(self, node: LineBreak) -> None:
        r"""Render a LineBreak node.

        Soft line breaks render as spaces to maintain paragraph flow.
        Hard line breaks rendering depends on the ``hard_line_break_mode`` option.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        Notes
        -----
        RST does not have a direct equivalent to hard line breaks within paragraphs.

        **line_block mode (default)**: Uses line block syntax (``\| ``) which is the
        idiomatic RST approach for preserving explicit line breaks. May change
        semantic structure in complex containers like lists.

        **raw mode**: Uses plain newlines. Less faithful to RST but simpler in
        complex containers. May not preserve visual breaks in all RST processors.

        """
        if node.soft:
            # Soft breaks render as space in RST
            self._output.append(' ')
        else:
            # Hard line break rendering depends on configured mode
            if self.options.hard_line_break_mode == "line_block":
                # Standard RST line block syntax
                self._output.append('\n| ')
            else:  # "raw"
                # Plain newline (simpler but less faithful)
                self._output.append('\n')

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for i, (term, descriptions) in enumerate(node.items):
            # Render term
            term_content = self._render_inline_content(term.content)
            self._output.append(term_content + '\n')

            # Render descriptions
            for desc in descriptions:
                saved_output = self._output
                self._output = []

                for child in desc.content:
                    child.accept(self)

                desc_content = ''.join(self._output)
                self._output = saved_output

                # Indent description
                lines = desc_content.split('\n')
                for line in lines:
                    if line.strip():
                        self._output.append(f"   {line}\n")

            if i < len(node.items) - 1:
                self._output.append('\n')

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node as plain text.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough node to render

        Notes
        -----
        reStructuredText has no native strikethrough syntax. Content is
        rendered as plain text without any special formatting. This is
        the standard fallback for unsupported inline formatting in RST.

        """
        content = self._render_inline_content(node.content)
        # RST doesn't have native strikethrough, render as plain text
        self._output.append(content)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node as plain text.

        Parameters
        ----------
        node : Underline
            Underline node to render

        Notes
        -----
        reStructuredText has no native underline syntax for inline text.
        Content is rendered as plain text without any special formatting.
        This is the standard fallback for unsupported inline formatting in RST.

        """
        content = self._render_inline_content(node.content)
        # RST doesn't have native underline, render as plain text
        self._output.append(content)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node using RST role syntax.

        Parameters
        ----------
        node : Superscript
            Superscript node to render

        Notes
        -----
        Uses RST's ``:sup:`` interpreted text role for superscript formatting.
        This requires Docutils or Sphinx for proper rendering.

        """
        content = self._render_inline_content(node.content)
        # RST uses :sup: role syntax for superscript
        self._output.append(f":sup:`{content}`")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node using RST role syntax.

        Parameters
        ----------
        node : Subscript
            Subscript node to render

        Notes
        -----
        Uses RST's ``:sub:`` interpreted text role for subscript formatting.
        This requires Docutils or Sphinx for proper rendering.

        """
        content = self._render_inline_content(node.content)
        # RST uses :sub: role syntax for subscript
        self._output.append(f":sub:`{content}`")

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render inline HTML (preserve as-is)."""
        self._output.append(node.content)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render HTML block (preserve as-is)."""
        self._output.append(node.content)

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render footnote reference."""
        self._output.append(f"[{node.identifier}]_")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render footnote definition."""
        self._output.append(f".. [{node.identifier}] ")
        for i, child in enumerate(node.content):
            if i > 0:
                self._output.append("\n   ")
            saved_output = self._output
            self._output = []
            child.accept(self)
            child_content = ''.join(self._output)
            self._output = saved_output
            self._output.append(child_content)

    def visit_math_inline(self, node: MathInline) -> None:
        """Render inline math."""
        preferred: MathNotation = "latex"  # RST prefers LaTeX for math
        content, notation = node.get_preferred_representation(preferred)
        # RST uses :math: role for inline math
        self._output.append(f":math:`{content}`")

    def visit_math_block(self, node: MathBlock) -> None:
        """Render math block."""
        preferred: MathNotation = "latex"
        content, notation = node.get_preferred_representation(preferred)
        # RST uses .. math:: directive for block math
        self._output.append(".. math::\n\n")
        lines = content.split('\n')
        for line in lines:
            self._output.append(f"   {line}\n")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to RST and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        rst_text = self.render_to_string(doc)
        self.write_text_output(rst_text, output)
