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
import textwrap
from pathlib import Path
from typing import IO, Union

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
        BaseRenderer._validate_options_type(options, RstRendererOptions, "rst")
        options = options or RstRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: RstRendererOptions = options
        self._output: list[str] = []
        self._in_list: bool = False
        self._list_depth: int = 0
        self._in_blockquote: int = 0
        self._in_footnote: int = 0

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
        self._in_blockquote = 0
        self._in_footnote = 0

        document.accept(self)

        result = "".join(self._output)
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
        text = re.sub(r"\n{4,}", "\n\n\n", text)
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
        char = chars[char_index] if char_index >= 0 else "="

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
                self._output.append("\n\n")

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

        if metadata.get("title"):
            docinfo_fields.append(f":Title: {metadata['title']}")
        if metadata.get("author"):
            docinfo_fields.append(f":Author: {metadata['author']}")
        if metadata.get("source"):
            docinfo_fields.append(f":Source: {metadata['source']}")
        if metadata.get("creation_date"):
            docinfo_fields.append(f":Date: {metadata['creation_date']}")
        if metadata.get("modification_date"):
            docinfo_fields.append(f":Updated: {metadata['modification_date']}")
        if metadata.get("accessed_date"):
            docinfo_fields.append(f":Accessed: {metadata['accessed_date']}")
        if metadata.get("description"):
            docinfo_fields.append(f":Summary: {metadata['description']}")
        if metadata.get("keywords"):
            keywords = metadata["keywords"]
            if isinstance(keywords, list):
                keywords_str = ", ".join(str(k) for k in keywords)
            else:
                keywords_str = str(keywords)
            docinfo_fields.append(f":Keywords: {keywords_str}")
        if metadata.get("language"):
            docinfo_fields.append(f":Language: {metadata['language']}")
        if metadata.get("category"):
            docinfo_fields.append(f":Category: {metadata['category']}")

        if "custom" in metadata and isinstance(metadata["custom"], dict):
            for key, value in metadata["custom"].items():
                docinfo_fields.append(f":{key.title()}: {value}")

        if docinfo_fields:
            for field in docinfo_fields:
                self._output.append(field + "\n")
            self._output.append("\n")

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
            lines = node.content.split("\n")
            for line in lines:
                self._output.append(f"   {line}\n")
        else:
            # Use :: literal block
            self._output.append("::\n\n")
            lines = node.content.split("\n")
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

        # Track blockquote depth
        self._in_blockquote += 1

        for child in node.children:
            child.accept(self)

        self._in_blockquote -= 1

        quoted = "".join(self._output)
        lines = quoted.split("\n")

        # Indent all lines
        quoted_lines = ["   " + line for line in lines]

        self._output = saved_output
        self._output.append("\n".join(quoted_lines))

    def visit_figure(self, node: Figure) -> None:
        """Render a Figure node.

        A figure that is exactly one paragraph holding one image maps onto the
        ``.. figure::`` directive -- the same spelling ``visit_image`` uses for
        a captioned image -- with the figure caption as the directive body. Any
        other shape renders its children normally with the caption following as
        an emphasised paragraph, emitted even with no children, since for a
        vector-drawn PDF figure the caption is the only record the figure
        existed.

        Parameters
        ----------
        node : Figure
            Figure to render

        """
        if node.caption and len(node.children) == 1:
            child = node.children[0]
            if isinstance(child, Paragraph) and len(child.content) == 1 and isinstance(child.content[0], Image):
                image = child.content[0]
                self._output.append(f".. figure:: {image.url}\n")
                if image.alt_text:
                    self._output.append(f"   :alt: {image.alt_text}\n")
                self._output.append(f"\n   {node.caption}\n")
                # The image's own caption, if distinct, survives as the legend.
                if image.caption and image.caption != node.caption:
                    self._output.append(f"\n   {image.caption}\n")
                return

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

        if node.caption:
            if node.children:
                self._output.append("\n\n")
            self._output.append(f"*{escape_rst(node.caption)}*")

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
            indent = "   " * (self._list_depth - 1)
            self._output.append(f"{indent}{marker}")

            # Render item content
            saved_output = self._output
            self._output = []
            item.accept(self)
            item_content = "".join(self._output)
            self._output = saved_output

            # Add item content (first line inline with marker, rest indented)
            lines = item_content.split("\n")
            if lines:
                self._output.append(lines[0])
                for line in lines[1:]:
                    if line.strip():
                        self._output.append(f"\n{indent}   {line}")

            if i < len(node.items) - 1:
                self._output.append("\n")

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
                self._output.append("\n")

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # A caption needs the `.. table::` directive, which takes the caption as its
        # argument and the table as its indented body. Without it the caption was
        # simply not written -- the renderer emitted a bare grid and the text was gone.
        if node.caption:
            self._output.append(f".. table:: {node.caption}\n\n")
            start = len(self._output)
            if self.options.table_style == "grid":
                self._render_grid_table(node)
            else:
                self._render_simple_table(node)
            body = "".join(self._output[start:])
            del self._output[start:]
            self._output.append(textwrap.indent(body, "   "))
            return

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

        # Resolve the grid once, centrally: a declared span that collides with
        # ground an earlier rowspan claimed would otherwise push the rest of the
        # row past the last column, silently dropping those cells.
        grid = self._layout_table_grid(rows_to_render)
        num_rows, num_cols = grid.num_rows, grid.num_cols

        # Build expanded grid. Positions a span covers stay empty; this renderer
        # writes each cell's content at its anchor only.
        rendered_grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]

        for placement in grid.placements:
            rendered_grid[placement.row][placement.col] = self._render_inline_content(placement.cell.content)

        # Calculate column widths from expanded grid
        col_widths = [0] * num_cols
        for row_cells in rendered_grid:
            for i, cell_content in enumerate(row_cells):
                col_widths[i] = max(col_widths[i], len(cell_content))

        # Build separator line
        separator = "+" + "+".join(["-" * (width + 2) for width in col_widths]) + "+"

        # Render table using expanded grid
        self._output.append(separator + "\n")

        for i, row_cells in enumerate(rendered_grid):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                padded = cell_content.ljust(col_widths[j])
                row_parts.append(f" {padded} ")
            self._output.append("|" + "|".join(row_parts) + "|\n")

            # Add separator after header or after last row
            if i == 0 and node.header:
                # Double separator after header
                header_sep = "+" + "+".join(["=" * (width + 2) for width in col_widths]) + "+"
                self._output.append(header_sep + "\n")
            elif i == len(rendered_grid) - 1:
                # Separator at end
                self._output.append(separator)
            else:
                # Separator between rows
                self._output.append(separator + "\n")

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
        separator = "  ".join(["=" * width for width in col_widths])

        # Render table
        self._output.append(separator + "\n")

        for i, row_cells in enumerate(rendered_rows):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    row_parts.append(padded)
            self._output.append("  ".join(row_parts) + "\n")

            # Add separator after header
            if i == 0 and node.header:
                self._output.append(separator + "\n")

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
        self._output.append("----")

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
            # Escape URL to prevent breaking RST syntax
            # Only escape characters that would break the <url> context:
            # - backticks (`) could break out of the outer backticks
            # - angle brackets (>) would close the URL prematurely
            escaped_url = node.url.replace("`", r"\`").replace(">", r"\>")
            self._output.append(f"`{content} <{escaped_url}>`_")
        else:
            self._output.append(content)

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        # RST image directive -- or `figure`, which is the same thing plus a caption.
        # The caption is the directive's body, so it needs the blank line and the
        # indent that separates a body from the option block above it (#338).
        directive = "figure" if node.caption else "image"
        self._output.append(f".. {directive}:: {node.url}\n")
        if node.alt_text:
            self._output.append(f"   :alt: {node.alt_text}\n")
        if node.caption:
            self._output.append(f"\n   {node.caption}\n")

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

        **line_block mode (default)**: Uses line block syntax with pipe prefix,
        which is the idiomatic RST approach for preserving explicit line breaks.
        May change semantic structure in complex containers like lists.

        **raw mode**: Uses plain newlines. Less faithful to RST but simpler in
        complex containers. May not preserve visual breaks in all RST processors.

        **Automatic fallback**: When ``hard_line_break_fallback_in_containers`` is True
        and we're inside a list or blockquote, automatically uses raw mode to prevent
        semantic changes from line block syntax.

        """
        if node.soft:
            # Soft breaks render as space in RST
            self._output.append(" ")
        else:
            # Hard line break rendering depends on configured mode and context
            # Check if we should fallback to raw mode in containers
            in_container = self._in_list or self._in_blockquote > 0 or self._in_footnote > 0
            use_raw_mode = self.options.hard_line_break_mode == "raw" or (
                self.options.hard_line_break_fallback_in_containers and in_container
            )

            if use_raw_mode:
                # Plain newline (simpler but less faithful)
                self._output.append("\n")
            else:
                # Standard RST line block syntax
                self._output.append("\n| ")

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
            self._output.append(term_content + "\n")

            # Every block of every description, rendered separately so blocks can be
            # joined with a blank line at the same indent -- the reST spelling of "the
            # definition continues". They used to be concatenated with nothing at all,
            # which fused the last word of one paragraph to the first word of the next
            # ('alpha' + 'beta' -> 'alphabeta'): destroyed word boundaries, not lost
            # formatting (#352). Several descriptions flatten into the one definition
            # reST gives each term (its syntax has no second one); their paragraphs
            # stay separate, so the merge loses the description count and nothing else.
            block_texts = []
            for desc in descriptions:
                for child in desc.content:
                    saved_output = self._output
                    self._output = []
                    child.accept(self)
                    block_texts.append("".join(self._output))
                    self._output = saved_output

            for j, block_text in enumerate(block_texts):
                if j > 0:
                    self._output.append("\n")
                for line in block_text.split("\n"):
                    if line.strip():
                        self._output.append(f"   {line}\n")

            if i < len(node.items) - 1:
                self._output.append("\n")

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

    @staticmethod
    def _footnote_label(identifier: str) -> str:
        """Spell a footnote identifier the way reST footnote syntax can carry it.

        A bare alphanumeric label (``[a1]_``) is reST *citation* syntax, so an
        identifier rendered that way stops being a footnote. Non-numeric
        identifiers need the named auto-numbered form (``[#a1]_``); purely
        numeric ones are already valid as manually numbered footnotes.
        """
        return identifier if identifier.isdigit() else f"#{identifier}"

    def _needs_inline_markup_boundary(self) -> bool:
        r"""Whether output ends where reST inline markup cannot start.

        Docutils only recognizes an inline markup start after whitespace or an
        opening/quoting character, so ``0[0]_`` is plain text. The reST idiom
        for a marker glued to a word is escaped whitespace: ``0\ [0]_``.
        """
        for fragment in reversed(self._output):
            if fragment:
                last = fragment[-1]
                return not (last.isspace() or last in "-:/'\"<([{")
        return False

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render footnote reference."""
        if self._needs_inline_markup_boundary():
            self._output.append("\\ ")
        self._output.append(f"[{self._footnote_label(node.identifier)}]_")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render footnote definition."""
        self._output.append(f".. [{self._footnote_label(node.identifier)}] ")
        # A footnote body is a container like a list item: line-block syntax
        # (`| line`) on the marker line becomes a line_block node instead of
        # the definition's paragraph, so hard breaks fall back to raw newlines
        # here, the same trade visit_line_break already makes inside lists.
        self._in_footnote += 1
        block_texts = []
        try:
            for child in node.content:
                saved_output = self._output
                self._output = []
                child.accept(self)
                block_texts.append("".join(self._output))
                self._output = saved_output
        finally:
            self._in_footnote -= 1

        # The first block rides the marker line; every further line -- a later
        # block, or a continuation line within one -- indents to the marker's
        # body column, with blank lines between blocks so they stay separate
        # paragraphs. Joining with a bare newline made every block a
        # continuation line of the first paragraph, collapsing a
        # multi-paragraph definition to one paragraph on re-parse (#347).
        for i, block_text in enumerate(block_texts):
            lines = [line for line in block_text.split("\n") if line.strip()]
            if i > 0:
                self._output.append("\n")
            for j, line in enumerate(lines):
                if i == 0 and j == 0:
                    self._output.append(line)
                else:
                    self._output.append(f"\n   {line}")

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
        lines = content.split("\n")
        for line in lines:
            self._output.append(f"   {line}\n")

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            Comment block to render

        Notes
        -----
        Renders as RST comment using the .. syntax with indented content.
        Each line of the comment content is indented with 3 spaces.

        """
        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        # Build attribution prefix
        prefix_parts = []
        if comment_type:
            prefix_parts.append(comment_type.upper())
        if label:
            prefix_parts.append(f"#{label}")
        prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

        if comment_mode == "note":
            # Render as .. note:: directive
            self._output.append(".. note::\n")
            self._output.append("\n")

            # Add attribution if present
            if author:
                if date:
                    self._output.append(f"   **{prefix} by {author} ({date}):**\n")
                else:
                    self._output.append(f"   **{prefix} by {author}:**\n")
                self._output.append("\n")

            # Add content (indented)
            lines = node.content.split("\n")
            for line in lines:
                self._output.append(f"   {line}\n")
            self._output.append("\n")
            return

        # Mode is "comment" - render as RST comments
        # RST comments use .. followed by indented content
        self._output.append("..\n")

        # Build comment text with metadata if available
        comment_text = node.content
        if author:
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        # Indent each line of content
        lines = comment_text.split("\n")
        for line in lines:
            self._output.append(f"   {line}\n")

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        RST does not have native inline comments. This method falls back
        to HTML comment syntax for inline comments, which is supported by
        RST processors.

        """
        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        # Build attribution prefix
        prefix_parts = []
        if comment_type:
            prefix_parts.append(comment_type.upper())
        if label:
            prefix_parts.append(f"#{label}")
        prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

        if comment_mode == "note":
            # Render as inline visible text in emphasis
            # Build full text
            if author:
                if date:
                    full_text = f"*[{prefix} by {author} ({date}): {node.content}]*"
                else:
                    full_text = f"*[{prefix} by {author}: {node.content}]*"
            else:
                full_text = f"*[{node.content}]*"

            self._output.append(full_text)
            return

        # Mode is "comment" - render as HTML comment (RST supports passthrough HTML)
        # Build comment text with metadata if available
        comment_text = node.content
        if author:
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        self._output.append(f"<!-- {comment_text} -->")

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
