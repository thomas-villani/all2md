# Copyright (c) 2025 All2md Contributors
"""SimpleDoc format renderer.

This module implements the AST to SimpleDoc converter, demonstrating how to
build a renderer plugin for the all2md library using the visitor pattern.
"""

from __future__ import annotations

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
from all2md.renderers.base import BaseRenderer, InlineContentMixin

from .options import SimpleDocRendererOptions


class SimpleDocRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to SimpleDoc format.

    This class implements the visitor pattern to traverse an AST and
    generate SimpleDoc output. It demonstrates proper renderer plugin
    implementation for the all2md library.

    SimpleDoc is a minimal format, so some AST node types don't have
    direct equivalents. This renderer handles them by:
    - Extracting text content from formatting nodes (strikethrough, underline, etc.)
    - Skipping unsupported elements (HTML, footnotes, math)
    - Providing simplified representations where appropriate

    Parameters
    ----------
    options : SimpleDocRendererOptions or None
        Rendering options

    """

    def __init__(self, options: SimpleDocRendererOptions | None = None):
        """Initialize the SimpleDoc renderer with options."""
        options = options or SimpleDocRendererOptions()
        # Multiple inheritance: Initialize all base classes
        # NodeVisitor provides visit_*() dispatching, InlineContentMixin provides helpers,
        # BaseRenderer provides common renderer infrastructure
        BaseRenderer.__init__(self, options)
        self.options: SimpleDocRendererOptions = options
        # Output accumulation: Build output incrementally as we traverse the AST
        # Using a list for efficient string concatenation (vs. repeated string +=)
        self._output: list[str] = []

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to SimpleDoc string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            SimpleDoc format output

        """
        # Reset output buffer for fresh rendering
        self._output = []
        # Visitor pattern: Call accept() on root node to start traversal
        # This triggers visit_document(), which recursively visits all children
        document.accept(self)
        # Finalize: Join accumulated strings and ensure single trailing newline
        result = "".join(self._output)
        return result.rstrip() + "\n"

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to SimpleDoc and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        text = self.render_to_string(doc)
        self.write_text_output(text, output)

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        # Frontmatter rendering: Optional based on settings
        if self.options.include_frontmatter and node.metadata:
            self._render_frontmatter(node.metadata)

        # Traverse children: Each child.accept(self) dispatches to the appropriate visit_*() method
        for i, child in enumerate(node.children):
            child.accept(self)  # Visitor pattern dispatch

            # Block spacing: Add configurable blank lines between elements
            # This keeps output readable and matches SimpleDoc conventions
            if i < len(node.children) - 1:
                self._output.append("\n" * (self.options.newlines_between_blocks + 1))

    def _render_frontmatter(self, metadata: dict) -> None:
        """Render frontmatter metadata block.

        Parameters
        ----------
        metadata : dict
            Document metadata

        """
        if not metadata:
            return

        self._output.append("---\n")

        # Render standard fields first
        if "title" in metadata:
            self._output.append(f"title: {metadata['title']}\n")
        if "author" in metadata:
            self._output.append(f"author: {metadata['author']}\n")
        if "date" in metadata:
            self._output.append(f"date: {metadata['date']}\n")
        if "keywords" in metadata and metadata["keywords"]:
            tags = ", ".join(metadata["keywords"])
            self._output.append(f"tags: {tags}\n")

        # Render custom fields
        standard_fields = {"title", "author", "date", "keywords", "custom"}
        for key, value in metadata.items():
            if key not in standard_fields and value:
                self._output.append(f"{key}: {value}\n")

        # Render nested custom metadata
        if "custom" in metadata and isinstance(metadata["custom"], dict):
            for key, value in metadata["custom"].items():
                self._output.append(f"{key}: {value}\n")

        self._output.append("---\n\n")

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        # InlineContentMixin: Use helper to extract text from inline nodes
        # This handles nested formatting (bold, italic, links) within headings
        content = self._render_inline_content(node.content)
        # SimpleDoc format: All headings use same marker (no levels)
        self._output.append(f"{self.options.heading_marker} {content}\n")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"{content}\n")

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        # Opening fence with language
        if node.language:
            self._output.append(f"```{node.language}\n")
        else:
            self._output.append("```\n")

        # Code content
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")

        # Closing fence
        self._output.append("```\n")

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        for item in node.items:
            item.accept(self)

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Nested rendering: Capture child output separately
        # This pattern is useful when you need to process child content before appending
        if node.children:
            # Save and reset output buffer to capture child content
            saved_output = self._output
            self._output = []

            # Render first child (typically a Paragraph)
            node.children[0].accept(self)

            # Get the captured content
            child_content = "".join(self._output).strip()

            # Restore main output buffer and append formatted list item
            self._output = saved_output
            self._output.append(f"{self.options.list_marker} {child_content}\n")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        SimpleDoc doesn't have native blockquote syntax, so we render
        children as-is.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        for child in node.children:
            child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        SimpleDoc doesn't have native table syntax, so we render a
        simplified text representation.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Direct child access pattern: We directly access cell.content instead of calling accept()
        # This gives us control over formatting while avoiding the need for TableCell visitor logic
        self._output.append("Table:\n")

        # Render header if present
        if node.header:
            self._output.append("Header: ")
            for i, cell in enumerate(node.header.cells):
                if i > 0:
                    self._output.append(" | ")
                # Extract inline content from cells directly
                content = self._render_inline_content(cell.content)
                self._output.append(content)
            self._output.append("\n")

        # Render data rows
        for row_idx, row in enumerate(node.rows):
            self._output.append(f"Row {row_idx + 1}: ")
            for i, cell in enumerate(row.cells):
                if i > 0:
                    self._output.append(" | ")
                content = self._render_inline_content(cell.content)
                self._output.append(content)
            self._output.append("\n")

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node (handled by visit_table).

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        pass

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        self._output.append(node.content)

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        SimpleDoc doesn't have bold formatting, so we just render content.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        # Pattern 1: Extract content from unsupported formatting
        # We preserve the text but lose the bold formatting
        # This is the standard approach for formatting nodes your format doesn't support
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        SimpleDoc doesn't have italic formatting, so we just render content.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        SimpleDoc doesn't have inline code formatting, so we render as-is.

        Parameters
        ----------
        node : Code
            Code to render

        """
        self._output.append(node.content)

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        SimpleDoc doesn't have link syntax, so we render the text content
        with the URL in parentheses.

        Parameters
        ----------
        node : Link
            Link to render

        """
        # Pattern 2: Provide simplified representation
        # Instead of just dropping the link, we include the URL in plain text
        # This preserves information even if not in ideal format
        content = self._render_inline_content(node.content)
        self._output.append(f"{content} ({node.url})")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        SimpleDoc doesn't have image syntax, so we render alt text.

        Parameters
        ----------
        node : Image
            Image to render

        """
        if node.alt_text:
            self._output.append(f"[Image: {node.alt_text}]")
        else:
            self._output.append(f"[Image: {node.url}]")

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
        """Render a Strikethrough node.

        SimpleDoc doesn't have strikethrough formatting, so we extract
        and render the text content without the formatting.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        SimpleDoc doesn't have underline formatting, so we extract
        and render the text content without the formatting.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        SimpleDoc doesn't have superscript formatting, so we extract
        and render the text content without the formatting.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        SimpleDoc doesn't have subscript formatting, so we extract
        and render the text content without the formatting.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node.

        This is handled by visit_table, so this method is a no-op.
        The table visitor directly accesses cell content.

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        # Structural node pattern: Parent handles rendering
        # Some nodes (cells, rows, etc.) are only rendered as part of their parent
        # We still need this method to satisfy NodeVisitor, but it does nothing
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        SimpleDoc doesn't have a thematic break element (horizontal rule),
        so we skip rendering this node.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        pass

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        SimpleDoc doesn't support HTML blocks, so we skip them.
        In a real implementation, you might want to extract text content
        or provide a placeholder.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # Pattern 3: Skip unsupported elements entirely
        # Use 'pass' for elements your format truly cannot represent
        # IMPORTANT: Always document WHY you're skipping, don't leave empty methods unexplained
        pass

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        SimpleDoc doesn't support inline HTML, so we skip it.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        SimpleDoc doesn't support footnotes, so we skip the reference.
        In a more sophisticated implementation, you might render
        the footnote content inline.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        pass

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        SimpleDoc doesn't support footnotes, so we skip the definition.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        pass

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        SimpleDoc doesn't support mathematical notation, so we skip it.
        Alternatively, you could render the LaTeX source as plain text.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        pass

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        SimpleDoc doesn't support mathematical notation, so we skip it.
        Alternatively, you could render the LaTeX source in a code block.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        pass

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        SimpleDoc doesn't have native definition list syntax,
        so we render it as a simplified text representation.

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
            self._output.append(f"Term: {term_content}\n")

            # Render descriptions
            for desc in descriptions:
                self._output.append("  Definition: ")
                for child in desc.content:
                    child.accept(self)
                self._output.append("\n")

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node.

        This is handled by visit_definition_list, so this method is a no-op.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node.

        This is handled by visit_definition_list, so this method is a no-op.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass
