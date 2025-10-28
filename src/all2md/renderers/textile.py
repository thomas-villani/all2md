#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/textile.py
"""Textile rendering from AST.

This module provides the TextileRenderer class which converts AST nodes
to Textile markup text. The renderer supports configurable rendering options
for controlling output format.

"""

from __future__ import annotations

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
from all2md.converter_metadata import ConverterMetadata
from all2md.options.textile import TextileRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.html_sanitizer import sanitize_html_content


class TextileRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to Textile markup text.

    This class implements the visitor pattern to traverse an AST and
    generate Textile output.

    Parameters
    ----------
    options : TextileRendererOptions or None, default = None
        Textile rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.textile import TextileRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = TextileRenderer()
        >>> textile_text = renderer.render_to_string(doc)
        >>> print(textile_text)
        h1. Title

    """

    def __init__(self, options: TextileRendererOptions | None = None):
        """Initialize the Textile renderer with options."""
        BaseRenderer._validate_options_type(options, TextileRendererOptions, "textile")
        options = options or TextileRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: TextileRendererOptions = options
        self._output: list[str] = []
        self._list_level: int = 0
        self._list_ordered_stack: list[bool] = []

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to Textile string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            Textile markup text

        """
        self._output = []
        self._list_level = 0
        self._list_ordered_stack = []

        document.accept(self)

        result = "".join(self._output)
        return result.rstrip() + "\n"

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
                self._output.append("\n\n")

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Textile uses h1., h2., etc. notation for headings.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"h{node.level}. {content}")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)

        # Apply line wrapping if configured
        if self.options.line_length > 0:
            content = self._wrap_text(content, self.options.line_length)

        self._output.append(content)

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text to specified line width.

        Parameters
        ----------
        text : str
            Text to wrap
        width : int
            Maximum line width (0 or negative means no wrapping)

        Returns
        -------
        str
            Wrapped text

        """
        if width <= 0:
            return text

        return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Textile uses bc. notation for code blocks.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if self.options.use_extended_blocks:
            self._output.append("bc. ")
            # Textile code blocks can be single-line or multi-line
            # For multi-line, each line needs to be prefixed
            lines = node.content.split("\n")
            for i, line in enumerate(lines):
                if i > 0:
                    self._output.append("\n")
                self._output.append(line)
        else:
            # Alternative: use @ for inline code spans on each line
            self._output.append("@")
            self._output.append(node.content.replace("\n", "@\n@"))
            self._output.append("@")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Textile uses bq. notation for block quotes.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        if self.options.use_extended_blocks:
            self._output.append("bq. ")

        for i, child in enumerate(node.children):
            if i > 0:
                self._output.append("\n\n")
            child.accept(self)

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Textile uses * for unordered lists and # for ordered lists.

        Parameters
        ----------
        node : List
            List to render

        """
        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)

        for i, item in enumerate(node.items):
            item.accept(self)
            if i < len(node.items) - 1:
                self._output.append("\n")

        self._list_level -= 1
        self._list_ordered_stack.pop()

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Determine list marker based on ordered/unordered
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False
        marker = "#" if is_ordered else "*"

        # Textile uses repeated markers for nesting
        prefix = marker * self._list_level

        self._output.append(f"{prefix} ")

        # Render children inline
        for i, child in enumerate(node.children):
            if isinstance(child, Paragraph):
                content = self._render_inline_content(child.content)
                self._output.append(content)
            else:
                child.accept(self)

            if i < len(node.children) - 1:
                self._output.append(" ")

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Textile uses pipe-cell-pipe notation for tables.
        Headers use pipe-underscore-dot-header-pipe notation.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Render header if present
        if node.header:
            self._output.append("|")
            for cell in node.header.cells:
                content = self._render_inline_content(cell.content)

                # Add span modifiers
                span_mods = ""
                if cell.colspan > 1:
                    span_mods += f"\\{cell.colspan}. "
                if cell.rowspan > 1:
                    span_mods += f"/{cell.rowspan}. "

                self._output.append(f"_{span_mods}.{content}|")
            self._output.append("\n")

        # Render rows
        for row in node.rows:
            self._output.append("|")
            for cell in row.cells:
                content = self._render_inline_content(cell.content)

                # Add span modifiers
                span_mods = ""
                if cell.colspan > 1:
                    span_mods += f"\\{cell.colspan}. "
                if cell.rowspan > 1:
                    span_mods += f"/{cell.rowspan}. "

                if span_mods:
                    self._output.append(f"{span_mods}{content}|")
                else:
                    self._output.append(f"{content}|")
            self._output.append("\n")

        # Remove trailing newline as it will be added by block spacing
        if self._output[-1] == "\n":
            self._output.pop()

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
        """Render a ThematicBreak node.

        Textile doesn't have a standard horizontal rule syntax,
        so we use HTML.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._output.append("<hr />")

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        sanitized = sanitize_html_content(node.content, mode=self.options.html_passthrough_mode)
        if sanitized:
            self._output.append(sanitized)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node according to comment_mode option.

        Parameters
        ----------
        node : Comment
            Comment block to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "blockquote": Render as Textile blockquote (bq.)
        - "ignore": Skip comment entirely

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

        if comment_mode == "html":
            self._output.append(f"<!-- {comment_text} -->")
        elif comment_mode == "blockquote":
            # Render as Textile blockquote
            self._output.append(f"bq. {comment_text}")

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # Textile doesn't require escaping in most contexts
        # Just output the text as-is
        self._output.append(node.content)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Textile uses _text_ for emphasis (italic).

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"_{content}_")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Textile uses *text* for strong (bold).

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"*{content}*")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Textile uses @code@ for inline code.

        Parameters
        ----------
        node : Code
            Code to render

        """
        self._output.append(f"@{node.content}@")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Textile uses "link text":url notation.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'"{content}":{node.url}')

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Textile uses !imageurl! notation for images.
        Alt text can be added with !imageurl(alt text)!

        Parameters
        ----------
        node : Image
            Image to render

        """
        if node.alt_text:
            self._output.append(f"!{node.url}({node.alt_text})!")
        else:
            self._output.append(f"!{node.url}!")

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

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Textile uses ^text^ for superscript.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"^{content}^")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Textile uses ~text~ for subscript.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"~{content}~")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Textile uses +text+ for underline (inserted text).

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"+{content}+")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Textile uses -text- for strikethrough (deleted text).

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"-{content}-")

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        sanitized = sanitize_html_content(node.content, mode=self.options.html_passthrough_mode)
        if sanitized:
            self._output.append(sanitized)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node according to comment_mode option.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "blockquote": Render as bracketed text (Textile has no inline blockquotes)
        - "ignore": Skip comment entirely

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
                comment_text = f"[{prefix} by {author} ({date}): {comment_text}]"
            else:
                comment_text = f"[{prefix} by {author}: {comment_text}]"
        elif node.metadata.get("label"):
            label = node.metadata.get("label")
            comment_text = f"[Comment {label}: {comment_text}]"
        else:
            # Add brackets for inline blockquote mode
            if comment_mode == "blockquote":
                comment_text = f"[{comment_text}]"

        if comment_mode == "html":
            self._output.append(f"<!-- {comment_text} -->")
        elif comment_mode == "blockquote":
            self._output.append(comment_text)

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Textile doesn't have native definition lists, so we render as
        bold term followed by indented description.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for i, (term, descriptions) in enumerate(node.items):
            if i > 0:
                self._output.append("\n")

            # Render term in bold
            term_content = self._render_inline_content(term.content)
            self._output.append(f"*{term_content}*\n")

            # Render descriptions
            for desc in descriptions:
                for child in desc.content:
                    child.accept(self)
                    self._output.append("\n")

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

    def visit_footnote_reference(self, node: "FootnoteReference") -> None:
        """Render a FootnoteReference node.

        Textile doesn't have native footnote syntax, so we render as superscript
        with the identifier.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        self._output.append(f"^[{node.identifier}]^")

    def visit_footnote_definition(self, node: "FootnoteDefinition") -> None:
        """Render a FootnoteDefinition node.

        Textile doesn't have native footnote syntax, so we render as a paragraph
        with a bold identifier followed by the content.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        self._output.append(f"*[{node.identifier}]* ")
        for child in node.content:
            child.accept(self)

    def visit_math_inline(self, node: "MathInline") -> None:
        """Render a MathInline node.

        Textile doesn't have native math support, so we render as inline code.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        content, _ = node.get_preferred_representation("latex")
        self._output.append(f"@{content}@")

    def visit_math_block(self, node: "MathBlock") -> None:
        """Render a MathBlock node.

        Textile doesn't have native math support, so we render as a code block.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        content, _ = node.get_preferred_representation("latex")
        self._output.append(f"bc. {content}")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to Textile and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        textile_text = self.render_to_string(doc)
        self.write_text_output(textile_text, output)


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="textile",
    extensions=[".textile"],
    mime_types=["text/x-textile"],
    magic_bytes=[],  # Plain text, no magic bytes
    parser_class="all2md.parsers.textile.TextileParser",
    renderer_class=TextileRenderer,
    renders_as_string=True,
    parser_required_packages=[("textile", "textile", "")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class="all2md.options.textile.TextileParserOptions",
    renderer_options_class=TextileRendererOptions,
    description="Parse and render Textile markup format",
    priority=10,
)
