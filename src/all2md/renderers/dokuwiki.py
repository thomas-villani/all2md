#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/dokuwiki.py
"""DokuWiki rendering from AST.

This module provides the DokuWikiRenderer class which converts AST nodes
to DokuWiki markup text. The renderer supports configurable rendering options
for controlling output format suitable for DokuWiki-based wikis.

"""

from __future__ import annotations

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
from all2md.options.dokuwiki import DokuWikiOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.escape import escape_dokuwiki, escape_html_entities
from all2md.utils.html_sanitizer import sanitize_html_content


class DokuWikiRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to DokuWiki markup text.

    This class implements the visitor pattern to traverse an AST and
    generate DokuWiki output suitable for DokuWiki-based wikis.

    Parameters
    ----------
    options : DokuWikiOptions or None, default = None
        DokuWiki rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.dokuwiki import DokuWikiRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = DokuWikiRenderer()
        >>> wiki_text = renderer.render_to_string(doc)
        >>> print(wiki_text)
        ====== Title ======

    """

    def __init__(self, options: DokuWikiOptions | None = None):
        """Initialize the DokuWiki renderer with options."""
        BaseRenderer._validate_options_type(options, DokuWikiOptions, "dokuwiki")
        options = options or DokuWikiOptions()
        BaseRenderer.__init__(self, options)
        self.options: DokuWikiOptions = options
        self._output: list[str] = []
        self._list_level: int = 0
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to DokuWiki markup string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            DokuWiki markup text

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

        DokuWiki headings use equals signs: ====== Level 1 ======
        Level calculation: 6 equals for level 1, 5 for level 2, etc.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)
        # DokuWiki: level 1 = 6 equals, level 2 = 5 equals, etc.
        equals_count = 7 - node.level
        equals = "=" * equals_count
        self._output.append(f"{equals} {content} {equals}")

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

        DokuWiki code blocks use <code> or <code language>.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if node.language:
            self._output.append(f"<code {node.language}>\n")
        else:
            self._output.append("<code>\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append("</code>")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        DokuWiki blockquotes use > at the start of each line.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        # Render children and prefix each line with >
        for i, child in enumerate(node.children):
            child_output: list[str] = []
            old_output = self._output
            self._output = child_output
            child.accept(self)
            self._output = old_output

            # Get rendered child content
            child_text = "".join(child_output)
            # Prefix each line with >
            lines = child_text.split("\n")
            for line in lines:
                if line.strip():
                    self._output.append(f"> {line}\n")
                else:
                    self._output.append(">\n")

            # Add blank line between children in blockquote
            if i < len(node.children) - 1:
                self._output.append(">\n")

        # Remove trailing newline that will be added by block spacing
        if self._output and self._output[-1].endswith("\n"):
            self._output[-1] = self._output[-1].rstrip("\n")

    def visit_list(self, node: List) -> None:
        """Render a List node.

        DokuWiki lists use * for unordered and - for ordered.
        Nested lists are indented with 2 spaces per level.

        Parameters
        ----------
        node : List
            List to render

        """
        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)
        for item in node.items:
            item.accept(self)
        self._list_ordered_stack.pop()
        self._list_level -= 1

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Determine marker based on parent list type
        indent = "  " * (self._list_level - 1)
        # Get marker from list type stack
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False
        marker = "-" if is_ordered else "*"

        # Render first child (should be paragraph)
        if node.children:
            first_child = node.children[0]
            if isinstance(first_child, Paragraph):
                # Render paragraph inline
                content = self._render_inline_content(first_child.content)
                self._output.append(f"{indent}{marker} {content}\n")

                # Render remaining children (nested lists, etc.)
                for child in node.children[1:]:
                    child.accept(self)
            else:
                # No paragraph - render all children
                self._output.append(f"{indent}{marker} \n")
                for child in node.children:
                    child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        DokuWiki tables use ^ for headers and | for cells.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Render header if present
        if node.header:
            self._render_table_row(node.header, is_header=True)

        # Render body rows
        for row in node.rows:
            self._render_table_row(row, is_header=False)

    def _render_table_row(self, row: TableRow, is_header: bool = False) -> None:
        """Render a table row.

        Parameters
        ----------
        row : TableRow
            Table row to render
        is_header : bool, default = False
            Whether this is a header row

        """
        delimiter = "^" if is_header else "|"

        self._output.append(delimiter)
        for _, cell in enumerate(row.cells):
            # Render cell content
            content = self._render_inline_content(cell.content)
            # Escape content for table context
            content = escape_dokuwiki(content, context="table")
            self._output.append(f" {content} ")
            self._output.append(delimiter)
        self._output.append("\n")

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node.

        Note: Table rows are rendered by visit_table, not individually.

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        # This is called by visit_table via _render_table_row
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node.

        Note: Table cells are rendered by _render_table_row.

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        # Cells are rendered by _render_table_row
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        DokuWiki uses ---- for horizontal rules.

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
        # Escape special DokuWiki characters
        escaped = escape_dokuwiki(node.content, context="text")
        self._output.append(escaped)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis (italic) node.

        DokuWiki uses // for italic.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"//{content}//")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong (bold) node.

        DokuWiki uses ** for bold.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"**{content}**")

    def visit_code(self, node: Code) -> None:
        """Render an inline Code node.

        DokuWiki uses '' for monospace (two single quotes).
        Can optionally use <code> tags if monospace_fence is enabled.

        Parameters
        ----------
        node : Code
            Code to render

        """
        if self.options.monospace_fence:
            # Use <code> tags
            self._output.append(f"<code>{node.content}</code>")
        else:
            # Use '' (DokuWiki native)
            self._output.append(f"''{node.content}''")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        DokuWiki uses [[url]] or [[url|text]].

        Parameters
        ----------
        node : Link
            Link to render

        """
        # Get link text
        link_text = self._render_inline_content(node.content)

        # Check if text is same as URL (can omit text)
        if link_text == node.url:
            self._output.append(f"[[{node.url}]]")
        else:
            self._output.append(f"[[{node.url}|{link_text}]]")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        DokuWiki uses {{image.png}} or {{image.png|alt text}}.

        Parameters
        ----------
        node : Image
            Image to render

        """
        if node.alt_text:
            self._output.append(f"{{{{{node.url}|{node.alt_text}}}}}")
        else:
            self._output.append(f"{{{{{node.url}}}}}")

    def visit_line_break(self, node: LineBreak) -> None:
        r"""Render a LineBreak node.

        DokuWiki uses \\ for hard line breaks.
        Soft line breaks are rendered as newlines.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            self._output.append("\n")
        else:
            # Hard line break
            self._output.append("\\\\")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        DokuWiki uses <del>text</del> for strikethrough.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        if self.options.use_html_for_unsupported:
            self._output.append(f"<del>{content}</del>")
        else:
            # Just render as plain text
            self._output.append(content)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        DokuWiki uses __ for underline.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"__{content}__")

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        DokuWiki uses <sup>text</sup> for superscript.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        if self.options.use_html_for_unsupported:
            self._output.append(f"<sup>{content}</sup>")
        else:
            self._output.append(content)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        DokuWiki uses <sub>text</sub> for subscript.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        if self.options.use_html_for_unsupported:
            self._output.append(f"<sub>{content}</sub>")
        else:
            self._output.append(content)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        content = self._handle_html_content(node.content)
        self._output.append(content)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            HTML inline to render

        """
        content = self._handle_html_content(node.content)
        self._output.append(content)

    def _handle_html_content(self, content: str) -> str:
        """Handle HTML content according to html_passthrough_mode.

        Parameters
        ----------
        content : str
            HTML content to handle

        Returns
        -------
        str
            Processed HTML content

        """
        mode = self.options.html_passthrough_mode

        if mode == "pass-through":
            return content
        elif mode == "escape":
            return escape_html_entities(content)
        elif mode == "drop":
            return ""
        else:  # mode == "sanitize"
            return sanitize_html_content(content, mode="sanitize")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        DokuWiki uses ((footnote text)) for inline footnotes.
        Since we only have a reference ID, we render a placeholder.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # DokuWiki footnotes are inline, but we only have an ID
        # Render as a simple reference marker
        self._output.append(f"((footnote {node.identifier}))")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        DokuWiki doesn't have separate footnote definitions.
        Footnotes are inline using ((text)).

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # DokuWiki doesn't support separate footnote definitions
        # Skip or render as HTML comment if use_html_for_unsupported
        if self.options.use_html_for_unsupported:
            content = self._render_inline_content(node.content)
            self._output.append(f"<!-- Footnote {node.identifier}: {content} -->")

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        DokuWiki doesn't have native definition list syntax.
        Use HTML <dl>, <dt>, <dd> if use_html_for_unsupported is enabled.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        if not self.options.use_html_for_unsupported:
            # Render as plain paragraphs
            for term, descriptions in node.items:
                term.accept(self)
                self._output.append("\n")
                for desc in descriptions:
                    desc.accept(self)
                    self._output.append("\n")
            return

        # Render as HTML
        self._output.append("<dl>\n")
        for term, descriptions in node.items:
            self._output.append("<dt>")
            term_content = self._render_inline_content(term.content)
            self._output.append(term_content)
            self._output.append("</dt>\n")
            for desc in descriptions:
                self._output.append("<dd>")
                # Render description content
                old_output = self._output
                desc_output: list[str] = []
                self._output = desc_output
                for child in desc.content:
                    child.accept(self)
                self._output = old_output
                self._output.append("".join(desc_output))
                self._output.append("</dd>\n")
        self._output.append("</dl>")

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        for child in node.content:
            child.accept(self)

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        DokuWiki typically uses plugin syntax for math.
        Render as <math>content</math> if use_html_for_unsupported.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        if self.options.use_html_for_unsupported:
            content, _ = node.get_preferred_representation("latex")
            self._output.append(f"<math>{content}</math>")
        else:
            # Render as plain text with $ delimiters
            self._output.append(f"${node.content}$")

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        DokuWiki typically uses plugin syntax for math blocks.
        Render as <MATH>content</MATH> if use_html_for_unsupported.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        if self.options.use_html_for_unsupported:
            content, _ = node.get_preferred_representation("latex")
            self._output.append(f"<MATH>\n{content}\n</MATH>")
        else:
            # Render as code block
            self._output.append("<code>\n")
            self._output.append(node.content)
            if not node.content.endswith("\n"):
                self._output.append("\n")
            self._output.append("</code>")

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
        - "visible": Render as visible text
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
        elif comment_mode == "visible":
            self._output.append(comment_text)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node according to comment_mode option.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "html": Use C-style comment syntax (default)
        - "visible": Render as visible bracketed text
        - "ignore": Skip comment entirely

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
        elif comment_mode == "visible":
            comment_text = f"[{comment_text}]"

        if comment_mode == "html":
            self._output.append(f"/* {node.content} */")
        elif comment_mode == "visible":
            self._output.append(comment_text)

    def render(self, document: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render a document to an output destination.

        Parameters
        ----------
        document : Document
            Document to render
        output : str, Path, IO[bytes], or IO[str]
            Output destination (file path or file-like object)

        """
        content = self.render_to_string(document)
        self.write_text_output(content, output)


# =============================================================================
# Converter Metadata Registration
# =============================================================================

CONVERTER_METADATA = ConverterMetadata(
    format_name="dokuwiki",
    extensions=[".doku", ".dokuwiki"],
    mime_types=["text/plain"],
    magic_bytes=[],
    parser_class="all2md.parsers.dokuwiki.DokuWikiParser",
    renderer_class=DokuWikiRenderer,
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class="all2md.options.dokuwiki.DokuWikiParserOptions",
    renderer_options_class=DokuWikiOptions,
    description="Parse and render DokuWiki markup",
    priority=10,
)
