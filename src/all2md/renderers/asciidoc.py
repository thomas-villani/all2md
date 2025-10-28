#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/asciidoc.py
"""AsciiDoc rendering from AST.

This module provides the AsciiDocRenderer class which converts AST nodes
to AsciiDoc text. The renderer supports configurable rendering options
for controlling output format.

"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import IO, Any, Union

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
    Node,
    Paragraph,
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
from all2md.options.asciidoc import AsciiDocRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.escape import escape_asciidoc, escape_asciidoc_attribute
from all2md.utils.footnotes import FootnoteCollector
from all2md.utils.html_sanitizer import sanitize_html_content

logger = logging.getLogger(__name__)


class AsciiDocRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to AsciiDoc text.

    This class implements the visitor pattern to traverse an AST and
    generate AsciiDoc output. It supports configurable rendering options.

    Parameters
    ----------
    options : AsciiDocRendererOptions or None, default = None
        AsciiDoc rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.asciidoc import AsciiDocRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = AsciiDocRenderer()
        >>> asciidoc = renderer.render_to_string(doc)
        >>> print(asciidoc)
        = Title

    """

    def __init__(self, options: AsciiDocRendererOptions | None = None):
        """Initialize the AsciiDoc renderer with options."""
        BaseRenderer._validate_options_type(options, AsciiDocRendererOptions, "asciidoc")
        options = options or AsciiDocRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: AsciiDocRendererOptions = options
        self._output: list[str] = []
        self._list_level: int = 0
        self._in_list: bool = False
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level
        self._footnote_collector: FootnoteCollector = FootnoteCollector()
        self._footnotes_emitted: set[str] = set()  # Track which footnotes have been emitted inline

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to AsciiDoc string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            AsciiDoc text

        """
        self._output = []
        self._list_level = 0
        self._in_list = False
        self._list_ordered_stack = []
        self._footnote_collector = FootnoteCollector()
        self._footnotes_emitted = set()

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
        # Pre-collect all footnote definitions from the document
        # This ensures definitions are available when references are rendered
        self._collect_footnote_definitions(node)

        # Render metadata as attributes if enabled
        if self.options.use_attributes:
            metadata_block = self._prepare_metadata(node.metadata)
            if metadata_block:
                self._render_attributes(metadata_block)
                self._output.append("\n")

        for i, child in enumerate(node.children):
            child.accept(self)
            # Add blank line between blocks
            if i < len(node.children) - 1:
                self._output.append("\n\n")

    def _collect_footnote_definitions(self, node: Node) -> None:
        """Recursively collect all footnote definitions from the document.

        Parameters
        ----------
        node : Node
            Node to search for footnote definitions

        """
        if isinstance(node, FootnoteDefinition):
            self._footnote_collector.register_definition(node.identifier, node.content, note_type="footnote")

        # Recursively search children
        if hasattr(node, "children"):
            for child in node.children:
                self._collect_footnote_definitions(child)

        # Search content for inline nodes
        if hasattr(node, "content") and isinstance(node.content, list):
            for item in node.content:
                if isinstance(item, Node):
                    self._collect_footnote_definitions(item)

    def _render_attributes(self, metadata: dict) -> None:
        """Render metadata as AsciiDoc attributes.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary to render (from DocumentMetadata.to_dict())

        """
        # Define standard fields that shouldn't be rendered as AsciiDoc attributes
        # These are conversion metadata, not document attributes
        skip_fields = {
            "creation_date",
            "modification_date",
            "creator",
            "producer",
            "source_path",
            "page_count",
            "word_count",
            "sha256",
            "extraction_date",
            "category",
        }

        # Render in order: title, author, description, then others
        if "title" in metadata and metadata["title"]:
            escaped_title = escape_asciidoc_attribute(str(metadata["title"]))
            self._output.append(f":title: {escaped_title}\n")
        if "author" in metadata and metadata["author"]:
            escaped_author = escape_asciidoc_attribute(str(metadata["author"]))
            self._output.append(f":author: {escaped_author}\n")
        if "description" in metadata and metadata["description"]:
            escaped_desc = escape_asciidoc_attribute(str(metadata["description"]))
            self._output.append(f":description: {escaped_desc}\n")
        if "keywords" in metadata and metadata["keywords"]:
            # Render keywords as comma-separated string
            if isinstance(metadata["keywords"], list):
                keywords_str = ", ".join(str(k) for k in metadata["keywords"])
                escaped_keywords = escape_asciidoc_attribute(keywords_str)
                self._output.append(f":keywords: {escaped_keywords}\n")
            else:
                escaped_keywords = escape_asciidoc_attribute(str(metadata["keywords"]))
                self._output.append(f":keywords: {escaped_keywords}\n")
        if "language" in metadata and metadata["language"]:
            escaped_lang = escape_asciidoc_attribute(str(metadata["language"]))
            self._output.append(f":lang: {escaped_lang}\n")

        # Render all other fields (custom attributes)
        for key, value in metadata.items():
            if key not in ("title", "author", "description", "keywords", "language") and key not in skip_fields:
                if value:
                    escaped_value = escape_asciidoc_attribute(str(value))
                    self._output.append(f":{key}: {escaped_value}\n")

    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text to specified line width while preserving hard breaks.

        Preserves AsciiDoc hard breaks (lines ending with ' +').

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

        # Split on hard breaks first to preserve them
        hard_break_marker = " +"
        lines = text.split("\n")
        wrapped_lines = []

        for line in lines:
            # Check if this line has a hard break
            has_hard_break = line.rstrip().endswith(hard_break_marker)

            if has_hard_break:
                # Remove the hard break marker temporarily
                line_content = line.rstrip()[: -len(hard_break_marker)].rstrip()
            else:
                line_content = line

            # Wrap this line
            if line_content:
                wrapped = textwrap.fill(
                    line_content,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )

                # Re-add hard break marker if it was present
                if has_hard_break:
                    # Add marker to the last wrapped line
                    wrapped_parts = wrapped.split("\n")
                    wrapped_parts[-1] = wrapped_parts[-1] + hard_break_marker
                    wrapped = "\n".join(wrapped_parts)

                wrapped_lines.append(wrapped)
            else:
                wrapped_lines.append("")

        return "\n".join(wrapped_lines)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        AsciiDoc uses = prefix syntax for all headings. The number of = characters
        determines the heading level: = is document title (level 0), == is section
        level 1, === is section level 2, etc.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)

        # AsciiDoc levels: = is document title (level 0), == is section level 1, === is section level 2, etc.
        # Map AST heading levels to AsciiDoc: level 1 -> ==, level 2 -> ===, etc.
        prefix = "=" * (node.level + 1)
        self._output.append(f"{prefix} {content}")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node with optional line wrapping.

        Wraps text to options.line_length if set, while preserving hard breaks.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)

        # Apply line wrapping if line_length is configured
        if self.options.line_length > 0:
            content = self._wrap_text(content, self.options.line_length)

        self._output.append(content)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        # Use [source,language] attribute if language is specified
        if node.language:
            self._output.append(f"[source,{node.language}]\n")

        self._output.append("----\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append("----")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        self._output.append("____\n")

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

        if not self._output[-1].endswith("\n"):
            self._output.append("\n")
        self._output.append("____")

    def _is_block_element(self, node: Node) -> bool:
        """Check if a node is a block element requiring list continuation.

        In AsciiDoc, block elements inside list items need a list continuation
        line (+) to be properly associated with the list item.

        Parameters
        ----------
        node : Node
            Node to check

        Returns
        -------
        bool
            True if node is a block element

        """
        return isinstance(node, (CodeBlock, BlockQuote, List, Table))

    def _flatten_blocks_to_inline(self, nodes: list[Node]) -> str:
        """Flatten block-level nodes to inline text for use in inline contexts.

        AsciiDoc footnote macros (footnote:id[text]) only accept inline content.
        This method extracts text from block nodes and converts them to a plain
        text representation suitable for inline use.

        Parameters
        ----------
        nodes : list of Node
            Block or inline nodes to flatten

        Returns
        -------
        str
            Flattened inline text

        Notes
        -----
        Complex block structures (tables, nested lists, etc.) will lose formatting.
        This is an inherent limitation of AsciiDoc's footnote syntax.

        """
        result_parts = []

        for node in nodes:
            if isinstance(node, Paragraph):
                # Extract inline content from paragraph
                text = self._render_inline_content(node.content)
                result_parts.append(text)
            elif isinstance(node, CodeBlock):
                # Represent code block as inline code
                # Remove newlines and represent compactly
                code_text = node.content.replace("\n", " ").strip()
                result_parts.append(f"+{code_text}+")
            elif isinstance(node, Text):
                # Direct text node
                result_parts.append(escape_asciidoc(node.content))
            elif hasattr(node, "content") and isinstance(node.content, list):
                # Recursively flatten nodes with content lists
                text = self._flatten_blocks_to_inline(node.content)
                result_parts.append(text)
            # Skip other block types that can't be meaningfully represented inline

        return " ".join(result_parts).strip()

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        was_in_list = self._in_list
        self._in_list = True
        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)

        for i, item in enumerate(node.items):
            item.accept(self)
            if i < len(node.items) - 1:
                self._output.append("\n")

        self._list_level -= 1
        self._list_ordered_stack.pop()
        self._in_list = was_in_list

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        In AsciiDoc, block elements within list items require a list continuation
        line (+) to properly associate them with the list item. The continuation
        appears on its own line between the list item text and the block element.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Determine list marker based on nesting level and ordered/unordered
        # AsciiDoc uses * for unordered, . for ordered
        # Multiple chars for nesting: **, ***, etc. or .., ..., etc.
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False
        marker_char = "." if is_ordered else "*"
        marker = marker_char * self._list_level

        # Handle task lists
        if node.task_status:
            checkbox = "[x]" if node.task_status == "checked" else "[ ]"
            marker = f"{marker} {checkbox}"

        # Apply indentation for nested lists based on list_indent option
        indent = " " * ((self._list_level - 1) * self.options.list_indent)
        self._output.append(f"{indent}{marker} ")

        # Render children
        for i, child in enumerate(node.children):
            if i == 0:
                # First child inline with marker
                if isinstance(child, Paragraph):
                    content = self._render_inline_content(child.content)
                    self._output.append(content)
                else:
                    # First child is a block element - needs continuation
                    self._output.append(f"\n{indent}+\n")
                    child.accept(self)
            else:
                # Subsequent children need continuation marker if they're blocks
                if self._is_block_element(child):
                    self._output.append(f"\n{indent}+\n")
                    child.accept(self)
                else:
                    # Non-block subsequent children (e.g., additional Paragraphs)
                    self._output.append(f"\n{indent}+\n")
                    child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Render caption if present
        if node.caption:
            self._output.append(f".{node.caption}\n")

        # Render column alignment specification if alignments are provided
        if node.alignments:
            # Map alignment values to AsciiDoc column specs
            # 'left' -> '<', 'center' -> '^', 'right' -> '>', None -> no spec (defaults to left)
            alignment_map = {"left": "<", "center": "^", "right": ">", None: ""}
            col_specs = [alignment_map.get(align, "") for align in node.alignments]
            # Only add [cols=...] if we have at least one alignment specified
            if any(spec for spec in col_specs):
                cols_attr = ",".join(col_specs if col_specs else [""] * len(node.alignments))
                self._output.append(f'[cols="{cols_attr}"]\n')

        self._output.append("|===\n")

        # Render header
        if node.header:
            self._output.append("|")
            for cell in node.header.cells:
                content = self._render_inline_content(cell.content)
                self._output.append(f"{content} |")
            self._output.append("\n")

        # Render rows
        for row in node.rows:
            self._output.append("|")
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                self._output.append(f"{content} |")
            self._output.append("\n")

        self._output.append("|===")

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

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._output.append("'''")

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
        """Render a Comment node (block-level).

        AsciiDoc comments use // prefix for single-line comments.
        For multi-line comments, each line is prefixed with //.

        Parameters
        ----------
        node : Comment
            Comment block to render

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
            # Render as NOTE admonition block
            self._output.append("[NOTE]\n")
            self._output.append("====\n")

            # Add attribution if present
            if author:
                if date:
                    self._output.append(f"*{prefix} by {author} ({date}):*\n")
                else:
                    self._output.append(f"*{prefix} by {author}:*\n")

            # Add content
            self._output.append(node.content)
            # Ensure content ends with newline before closing delimiter
            if not node.content.endswith("\n"):
                self._output.append("\n")
            self._output.append("====\n")
            return

        # Mode is "comment" - render as AsciiDoc comments
        # Build comment text with metadata if available
        comment_text = node.content
        if author:
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        # Check if content is multiline
        lines = comment_text.split("\n")
        if len(lines) == 1:
            # Single-line comment
            self._output.append(f"// {comment_text}")
        else:
            # Multi-line comment - prefix each line with //
            for line in lines:
                self._output.append(f"// {line}\n")
            # Remove trailing newline from last line
            if self._output and self._output[-1].endswith("\n"):
                self._output[-1] = self._output[-1].rstrip("\n")

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # Escape special AsciiDoc characters
        text = escape_asciidoc(node.content)
        self._output.append(text)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"_{content}_")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"*{content}*")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        # AsciiDoc standard uses +text+ for monospaced inline (not backticks)
        # Backticks are only for Markdown compatibility mode
        content = node.content

        # If content contains +, escape it by doubling
        if "+" in content:
            # Double all + characters to escape them
            content = content.replace("+", "++")

        # Use + delimiter (AsciiDoc standard for monospaced inline)
        self._output.append(f"+{content}+")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)

        # Check if this is an auto-link (content equals URL)
        if len(node.content) == 1 and isinstance(node.content[0], Text):
            if node.content[0].content == node.url:
                # Auto-link - just output the URL
                self._output.append(node.url)
                return

        # Explicit link
        self._output.append(f"link:{node.url}[{content}]")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        # Block image by default
        self._output.append(f"image::{node.url}[{node.alt_text}]")

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            # Soft breaks render as space in AsciiDoc
            self._output.append(" ")
        else:
            # Hard break with explicit line break
            self._output.append(" +\n")

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"^{content}^")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"~{content}~")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        AsciiDoc doesn't have native underline, so render as HTML.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        # AsciiDoc supports passthrough inline HTML
        self._output.append(f"<u>{content}</u>")

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
        """Render a CommentInline node (inline).

        AsciiDoc doesn't have native inline comments, so we fall back to HTML
        comment syntax which is widely supported in AsciiDoc processors.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

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
            # Render as inline NOTE (visible text in italics)
            # Build full text
            if author:
                if date:
                    full_text = f"_[{prefix} by {author} ({date}): {node.content}]_"
                else:
                    full_text = f"_[{prefix} by {author}: {node.content}]_"
            else:
                full_text = f"_[{node.content}]_"

            self._output.append(full_text)
            return

        # Mode is "comment" - render as HTML comment (AsciiDoc supports passthrough HTML)
        # Build comment text with metadata if available
        comment_text = node.content
        if author:
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        # Use HTML comment for inline comments (AsciiDoc supports passthrough HTML)
        self._output.append(f"<!-- {comment_text} -->")

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
            self._output.append(f"{term_content}::")

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

    def visit_strikethrough(self, node: Any) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Any
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        # AsciiDoc uses [line-through] for strikethrough
        self._output.append(f"[line-through]#{content}#")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        AsciiDoc footnote macros only accept inline content. If the footnote
        definition contains block-level nodes, they will be flattened to plain text.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # Register the reference and get canonical identifier
        canonical_id = self._footnote_collector.register_reference(node.identifier, note_type="footnote")

        # Check if this is the first occurrence
        if canonical_id not in self._footnotes_emitted:
            # First occurrence: emit footnote:id[text]
            # Get the definition content if available
            definitions = list(self._footnote_collector.iter_definitions(note_type_priority=["footnote"]))
            footnote_text = ""
            for defn in definitions:
                if defn.identifier == canonical_id:
                    # Flatten the footnote content to inline text (handles block nodes)
                    footnote_text = self._flatten_blocks_to_inline(defn.content)
                    break

            if footnote_text:
                self._output.append(f"footnote:{canonical_id}[{footnote_text}]")
            else:
                # No definition found, just emit the reference
                logger.warning(f"Footnote reference '{canonical_id}' has no definition", stacklevel=2)
                self._output.append(f"footnote:{canonical_id}[]")

            self._footnotes_emitted.add(canonical_id)
        else:
            # Subsequent occurrence: emit footnote:id[]
            self._output.append(f"footnote:{canonical_id}[]")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # Footnote definitions are pre-collected in visit_document
        # and emitted inline at the first reference, so nothing to do here
        pass

    def visit_math_inline(self, node: Any) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : Any
            Inline math to render

        """
        # AsciiDoc supports LaTeX math with stem: macro
        preferred = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append(f"stem:[{content}]")

    def visit_math_block(self, node: Any) -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : Any
            Math block to render

        """
        # AsciiDoc supports LaTeX math blocks with [stem] attribute
        preferred = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append("[stem]\n")
        self._output.append("++++\n")
        self._output.append(content)
        if not content.endswith("\n"):
            self._output.append("\n")
        self._output.append("++++")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to AsciiDoc and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        asciidoc_text = self.render_to_string(doc)
        self.write_text_output(asciidoc_text, output)
