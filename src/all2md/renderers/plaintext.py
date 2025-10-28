#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/plaintext.py
"""Plain text rendering from AST.

This module provides the PlainTextRenderer class which converts AST nodes
to plain, unformatted text. The renderer strips all formatting (bold, italic,
headings, etc.) and outputs only the text content. This is useful for:
- Feeding document content into language models
- Text analysis and summarization
- Search indexing
- Data pipeline processing

The rendering process uses the visitor pattern to traverse the AST and
extract plain text while respecting document structure.

"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import IO, Literal, Union

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
from all2md.options.plaintext import PlainTextOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin


class PlainTextRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to plain, unformatted text.

    This class implements the visitor pattern to traverse an AST and
    generate plain text output. All formatting is stripped, leaving only
    the text content. Structural elements like tables and lists are
    rendered as plain text with simple separators.

    Parameters
    ----------
    options : PlainTextOptions or None, default = None
        Plain text rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text, Strong
        >>> from all2md.renderers.plaintext import PlainTextRenderer
        >>> from all2md.options import PlainTextOptions
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[
        ...         Text(content="Title with "),
        ...         Strong(content=[Text(content="bold")])
        ...     ])
        ... ])
        >>> renderer = PlainTextRenderer()
        >>> text = renderer.render_to_string(doc)
        >>> print(text)
        Title with bold

    """

    def __init__(self, options: PlainTextOptions | None = None):
        """Initialize the plain text renderer with options."""
        BaseRenderer._validate_options_type(options, PlainTextOptions, "plaintext")
        options = options or PlainTextOptions()
        BaseRenderer.__init__(self, options)
        self.options: PlainTextOptions = options
        self._output: list[str] = []

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to plain text string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            Plain text output

        """
        self._output = []
        document.accept(self)

        result = "".join(self._output)

        # Apply line wrapping if enabled
        if self.options.max_line_width is not None and self.options.max_line_width > 0:
            result = self._wrap_text(result)

        return result.rstrip()

    def _wrap_text(self, text: str) -> str:
        """Wrap text to specified line width.

        Parameters
        ----------
        text : str
            Text to wrap

        Returns
        -------
        str
            Wrapped text

        Notes
        -----
        Tab characters are protected during wrapping to prevent them from being
        expanded to spaces by textwrap.fill().

        When preserve_blank_lines is True (default), consecutive blank lines are
        preserved exactly as they appear. When False, consecutive blank lines are
        collapsed according to the paragraph_separator setting.

        """
        # Protect tab characters from being expanded by textwrap
        # Use a unique placeholder that won't appear in normal text
        TAB_PLACEHOLDER = "\x00TAB\x00"
        text = text.replace("\t", TAB_PLACEHOLDER)

        # Split into paragraphs (preserve existing paragraph breaks)
        paragraphs = text.split(self.options.paragraph_separator)
        wrapped_paragraphs = []

        for para in paragraphs:
            if para.strip():
                # Check if paragraph contains hard line breaks (single newlines within paragraph)
                # These should be preserved during wrapping
                lines = para.split("\n")
                wrapped_lines = []
                for line in lines:
                    if line.strip():
                        # Wrap each line separately
                        # max_line_width is guaranteed to be int here (checked above)
                        assert self.options.max_line_width is not None
                        wrapped = textwrap.fill(
                            line, width=self.options.max_line_width, break_long_words=False, break_on_hyphens=False
                        )
                        wrapped_lines.append(wrapped)
                    else:
                        wrapped_lines.append("")
                wrapped_paragraphs.append("\n".join(wrapped_lines))
            elif self.options.preserve_blank_lines:
                # Only preserve empty paragraphs if option is enabled
                # When disabled, consecutive blank lines are collapsed
                wrapped_paragraphs.append("")

        result = self.options.paragraph_separator.join(wrapped_paragraphs)

        # Restore tab characters
        result = result.replace(TAB_PLACEHOLDER, "\t")

        return result

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        for i, child in enumerate(node.children):
            # Save output position to detect if node added content
            output_before = len(self._output)
            child.accept(self)
            output_after = len(self._output)

            # Only add separator if node produced output and there are more children
            if output_after > output_before and i < len(node.children) - 1:
                self._output.append(self.options.paragraph_separator)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node (extract text only).

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

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
        if self.options.preserve_code_blocks:
            # Preserve the code block content with original formatting
            self._output.append(node.content.rstrip())
        else:
            # Treat code blocks like regular paragraphs
            self._output.append(node.content.strip())

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node (extract text only).

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append(self.options.paragraph_separator)

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        for i, item in enumerate(node.items):
            item.accept(self)
            # Add newline after each item except the last
            if i < len(node.items) - 1:
                self._output.append("\n")

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        self._output.append(self.options.list_item_prefix)

        # Render children
        for i, child in enumerate(node.children):
            if i == 0:
                # First child goes immediately after prefix
                saved_output = self._output
                self._output = []
                child.accept(self)
                child_content = "".join(self._output)
                self._output = saved_output
                self._output.append(child_content)
            else:
                # Subsequent children on new lines
                self._output.append("\n")
                child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node as plain text.

        Parameters
        ----------
        node : Table
            Table to render

        """
        rows_output = []

        # Render header if present and enabled
        if node.header and self.options.include_table_headers:
            rows_output.append(self._render_table_row_to_string(node.header))

        # Render rows
        for row in node.rows:
            rows_output.append(self._render_table_row_to_string(row))

        # Join all rows with newlines
        self._output.append("\n".join(rows_output))

    def _render_table_row_to_string(self, row: TableRow) -> str:
        """Render a table row as plain text with cell separators.

        Parameters
        ----------
        row : TableRow
            Table row to render

        Returns
        -------
        str
            Rendered row as string

        """
        cells_text = []
        for cell in row.cells:
            content = self._render_inline_content(cell.content)
            # Remove newlines from cell content
            content = content.replace("\n", " ")
            cells_text.append(content)

        return self.options.table_cell_separator.join(cells_text)

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node (handled by visit_table).

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node (handled by visit_table).

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node (skip in plain text).

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        # Skip thematic breaks in plain text
        pass

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node (skip HTML in plain text).

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # Skip HTML blocks in plain text
        pass

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        self._output.append(node.content)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_code(self, node: Code) -> None:
        """Render a Code node (extract text only).

        Parameters
        ----------
        node : Code
            Code to render

        """
        self._output.append(node.content)

    def visit_link(self, node: Link) -> None:
        """Render a Link node (extract text only, ignore URL).

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_image(self, node: Image) -> None:
        """Render an Image node (use alt text only).

        Parameters
        ----------
        node : Image
            Image to render

        """
        if node.alt_text:
            self._output.append(node.alt_text)

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            self._output.append(" ")
        else:
            self._output.append("\n")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node (extract text only, ignore formatting).

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node (skip HTML in plain text).

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        # Skip inline HTML in plain text
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node (skip in plain text).

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # Skip footnote references in plain text
        pass

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node (extract text representation).

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        # Use the primary representation (usually LaTeX)
        preferred: Literal["latex", "mathml", "html"] = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append(content)

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node (skip in plain text).

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # Skip footnote definitions in plain text
        pass

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for i, (term, descriptions) in enumerate(node.items):
            if i > 0:
                self._output.append("\n")

            # Render term
            term_content = self._render_inline_content(term.content)
            self._output.append(term_content)

            # Render descriptions
            for desc in descriptions:
                self._output.append("\n")
                for child in desc.content:
                    child.accept(self)

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node (extract text representation).

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        # Use the primary representation (usually LaTeX)
        preferred: Literal["latex", "mathml", "html"] = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append(content.rstrip())

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node according to comment_mode option.

        Parameters
        ----------
        node : Comment
            Comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "visible": Render as bracketed text
        - "ignore": Skip comment entirely (default)

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author"):
            author = node.metadata.get("author")
            date = node.metadata.get("date", "")
            label = node.metadata.get("label", "")
            prefix = f"Comment {label}" if label else "Comment"
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        if comment_mode == "visible":
            self._output.append(f"[{comment_text}]")
            self._output.append(self.options.paragraph_separator)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node according to comment_mode option.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "visible": Render as bracketed text
        - "ignore": Skip comment entirely (default)

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author") or node.metadata.get("label"):
            prefix_parts = []
            if node.metadata.get("label"):
                prefix_parts.append(f"Comment {node.metadata['label']}")
            else:
                prefix_parts.append("Comment")

            if node.metadata.get("author"):
                prefix_parts.append(f"by {node.metadata['author']}")

            if node.metadata.get("date"):
                prefix_parts.append(f"({node.metadata['date']})")

            prefix = " ".join(prefix_parts)
            comment_text = f"[{prefix}: {comment_text}]"
        else:
            comment_text = f"[{comment_text}]"

        if comment_mode == "visible":
            self._output.append(comment_text)

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to plain text and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        text = self.render_to_string(doc)
        self.write_text_output(text, output)
