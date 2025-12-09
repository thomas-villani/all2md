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

import html
import re
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
from all2md.options.markdown import MarkdownRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.flavors import (
    CommonMarkFlavor,
    GFMFlavor,
    KramdownFlavor,
    MarkdownFlavor,
    MarkdownPlusFlavor,
    MultiMarkdownFlavor,
    PandocFlavor,
)
from all2md.utils.html_sanitizer import sanitize_html_content
from all2md.utils.html_utils import render_math_html
from all2md.utils.metadata import (
    format_json_frontmatter,
    format_toml_frontmatter,
    format_yaml_frontmatter,
)


class MarkdownRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
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
        >>> from all2md.options import MarkdownRendererOptions
        >>> from all2md.renderers.markdown import MarkdownRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = MarkdownRendererOptions(flavor="gfm")
        >>> renderer = MarkdownRenderer(options)
        >>> markdown = renderer.render_to_string(doc)
        >>> print(markdown)
        # Title

    """

    def __init__(self, options: MarkdownRendererOptions | None = None):
        """Initialize the Markdown renderer with options."""
        # Initialize BaseRenderer
        BaseRenderer._validate_options_type(options, MarkdownRendererOptions, "markdown")
        options = options or MarkdownRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: MarkdownRendererOptions = options
        self._flavor = self._get_flavor(self.options.flavor)
        self._output: list[str] = []
        self._indent_level: int = 0
        self._in_list: bool = False
        self._list_marker_stack: list[str] = []
        self._marker_width_stack: list[int] = []
        self._link_references: dict[str, int] = {}  # url -> ref_id for reference-style links
        self._next_ref_id: int = 1
        self._block_link_references: dict[str, int] = {}  # url -> ref_id for current block

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
        self._marker_width_stack = []
        self._link_references = {}
        self._next_ref_id = 1
        self._block_link_references = {}

        document.accept(self)

        # Append link references if using reference style with end_of_document placement
        if (
            self.options.link_style == "reference"
            and self.options.reference_link_placement == "end_of_document"
            and self._link_references
        ):
            self._output.append("\n\n")
            for url, ref_id in sorted(self._link_references.items(), key=lambda x: x[1]):
                self._output.append(f"[{ref_id}]: {url}\n")

        result = "".join(self._output)

        # Clear state to prevent memory leaks in long-running processes
        self._link_references.clear()
        self._block_link_references.clear()
        self._output.clear()
        self._list_marker_stack.clear()
        self._marker_width_stack.clear()

        return self._cleanup_output(result)

    def _get_plain_text_from_nodes(self, nodes: list) -> str:
        """Extract plain text from a list of inline nodes for length calculation.

        This method recursively extracts text content from inline nodes,
        stripping all formatting markup to get the actual visible text length.
        Used for setext heading underlines.

        Parameters
        ----------
        nodes : list
            List of inline AST nodes

        Returns
        -------
        str
            Plain text without markup

        """
        text_parts = []
        for node in nodes:
            if isinstance(node, Text):
                text_parts.append(node.content)
            elif hasattr(node, "content") and isinstance(node.content, list):
                # Recursively extract from nested nodes (Strong, Emphasis, etc.)
                text_parts.append(self._get_plain_text_from_nodes(node.content))
            elif isinstance(node, Code):
                # Code nodes have string content
                text_parts.append(node.content)
            elif isinstance(node, Link):
                # For links, use the link text, not the URL
                text_parts.append(self._get_plain_text_from_nodes(node.content))
            elif isinstance(node, Image):
                # For images, use alt text
                text_parts.append(node.alt_text)
            # Skip other node types (LineBreak, etc.)
        return "".join(text_parts)

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
        # Normalize line endings first (CRLF/CR -> LF)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if self.options.collapse_blank_lines:
            text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.rstrip()
        return text

    def _escape_markdown(self, text: str) -> str:
        """Escape special markdown characters with context awareness.

        This method provides intelligent escaping that considers context:
        - Does not escape # in inline text (only dangerous at line start)
        - Does not escape _ in the middle of words (e.g., snake_case)
        - Always escapes backslash, backticks, asterisks, braces, brackets

        Parameters
        ----------
        text : str
            Text to escape

        Returns
        -------
        str
            Escaped text

        Notes
        -----
        Context-aware escaping prevents over-escaping while maintaining safety:

        - **Hash symbols (#)**: Only need escaping at the start of a line to prevent
          accidental heading syntax. In inline text, # is safe and doesn't need escaping.

        - **Underscores (_)**: Only need escaping at word boundaries where they could
          trigger emphasis. Underscores in the middle of words (e.g., "snake_case",
          "my_variable") are safe in most Markdown flavors and don't need escaping.

        - **Always escaped**: Backslash, backticks, asterisks, braces, brackets are
          always escaped as they have special meaning in all contexts.

        """
        if not self.options.escape_special:
            return text

        # Characters that always need escaping in inline content
        always_escape = r"\`*{}[]"

        escaped_chars = []
        for i, char in enumerate(text):
            if char in always_escape:
                # Always escape these special characters
                escaped_chars.append("\\")
                escaped_chars.append(char)
            elif char == "#":
                # Only escape # at the start of text (where it could start a heading)
                # In inline contexts, # is safe and doesn't need escaping
                if i == 0:
                    escaped_chars.append("\\")
                    escaped_chars.append(char)
                else:
                    escaped_chars.append(char)
            elif char == "_":
                # Smart underscore escaping: don't escape if in middle of word
                # Check if surrounded by alphanumeric characters (word context)
                prev_alnum = i > 0 and text[i - 1].isalnum()
                next_alnum = i < len(text) - 1 and text[i + 1].isalnum()

                if prev_alnum and next_alnum:
                    # In middle of word (e.g., snake_case) - safe, no escaping needed
                    escaped_chars.append(char)
                else:
                    # At word boundary - could trigger emphasis, needs escaping
                    escaped_chars.append("\\")
                    escaped_chars.append(char)
            else:
                escaped_chars.append(char)

        return "".join(escaped_chars)

    def _autolink_bare_urls(self, text: str) -> str:
        """Convert bare URLs to Markdown autolinks.

        Parameters
        ----------
        text : str
            Text that may contain bare URLs

        Returns
        -------
        str
            Text with bare URLs converted to autolinks

        Notes
        -----
        This implementation uses a robust URL regex inspired by the GFM autolink spec.
        It handles:
        - Balanced parentheses (e.g., Wikipedia URLs)
        - Query strings with punctuation
        - URL fragments (#section)
        - Trailing punctuation that's not part of the URL
        - Nested parentheses in URLs

        **Edge Cases Handled:**
        - `https://en.wikipedia.org/wiki/Foo_(bar)` - keeps closing paren
        - `http://example.com?q=test` - handles query params
        - `(see http://example.com)` - strips closing paren
        - `http://example.com.` - strips trailing period
        - `http://example.com/path(foo(bar))` - handles nested parens

        """
        # Improved URL pattern based on GFM autolink extension
        # Pattern matches:
        # 1. Scheme: http://, https://, ftp://, ftps://
        # 2. Domain and path: any non-whitespace except angle brackets
        # The pattern is intentionally greedy; we clean up trailing chars later
        url_pattern = r"(https?://[^\s<>]+|ftps?://[^\s<>]+)"

        def replace_url(match: re.Match[str]) -> str:
            url = match.group(1)

            # GFM-style trailing punctuation removal
            # Ref: https://github.github.com/gfm/#extended-autolink-path-validation

            # Track original URL components for smart handling
            has_query = "?" in url

            # Step 1: Remove trailing punctuation that's unlikely to be part of URL
            # Be conservative: only remove if not in query string/fragment context
            trailing_chars = ".,;:!?"
            if not has_query:
                # No query string: safe to strip sentence-ending punctuation
                while url and url[-1] in trailing_chars:
                    url = url[:-1]
            else:
                # Has query string: only strip commas/semicolons (never in URLs)
                while url and url[-1] in ",;":
                    url = url[:-1]

            # Step 2: Handle parentheses balancing (GFM spec)
            # Count parentheses in the URL to handle nested parens correctly
            if url.endswith(")"):
                # Count how many parens are in the URL
                open_count = url.count("(")
                close_count = url.count(")")

                # Remove unbalanced closing parens from the end
                # This handles both "(see http://example.com)"
                # and "http://example.com/path(foo(bar))" correctly
                while close_count > open_count and url.endswith(")"):
                    url = url[:-1]
                    close_count -= 1

            # Step 3: Final cleanup - remove trailing punctuation after paren removal
            # (in case removing parens exposed more punctuation)
            if not has_query and url and url[-1] in ".,;:!?":
                while url and url[-1] in ".,;:!?":
                    url = url[:-1]

            return f"<{url}>"

        return re.sub(url_pattern, replace_url, text)

    def _process_html_content(self, content: str) -> str:
        """Process HTML content based on sanitization mode.

        Parameters
        ----------
        content : str
            Raw HTML content

        Returns
        -------
        str
            Processed HTML content based on html_passthrough_mode option

        """
        mode = self.options.html_passthrough_mode

        if mode == "pass-through":
            # Pass HTML through unchanged (use only with trusted content)
            return content
        elif mode == "escape":
            # HTML-escape the content to show as text (secure default)
            return html.escape(content)
        elif mode == "drop":
            # Remove HTML content entirely
            return ""
        else:  # mode == "sanitize"
            # Remove dangerous elements/attributes
            return sanitize_html_content(content, mode="sanitize")

    def _emit_block_references(self) -> None:
        """Emit accumulated link references after a block.

        This method outputs reference-style link definitions that were collected
        during rendering of the current block, when reference_link_placement is
        set to "after_block".

        """
        if not self._block_link_references:
            return

        self._output.append("\n\n")
        for url, ref_id in sorted(self._block_link_references.items(), key=lambda x: x[1]):
            self._output.append(f"[{ref_id}]: {url}\n")

        # Clear block references after emitting
        self._block_link_references.clear()

    def _current_indent(self) -> str:
        """Get the current indentation string.

        Returns
        -------
        str
            Indentation spaces

        """
        # For lists, use accumulated marker widths for indentation
        # This ensures proper alignment in nested lists
        if self._marker_width_stack:
            return " " * sum(self._marker_width_stack)
        return " " * (self._indent_level * self.options.list_indent_width)

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
        # Render metadata as frontmatter if present and enabled
        if self.options.metadata_frontmatter:
            self._render_frontmatter(node.metadata)
            # Frontmatter formatters already include trailing newlines

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

    def _render_frontmatter(self, metadata: dict | None) -> None:
        """Render metadata as frontmatter in the configured format.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary to render

        """
        filtered_metadata = self._prepare_metadata(metadata)
        if not filtered_metadata:
            return

        # Select formatter based on metadata_format option
        if self.options.metadata_format == "toml":
            frontmatter = format_toml_frontmatter(filtered_metadata, policy=self.metadata_policy)
        elif self.options.metadata_format == "json":
            frontmatter = format_json_frontmatter(filtered_metadata, policy=self.metadata_policy)
        else:  # default to yaml
            frontmatter = format_yaml_frontmatter(filtered_metadata, policy=self.metadata_policy)

        if frontmatter:
            self._output.append(frontmatter)

    def _yaml_escape(self, value: Any) -> str:
        """Escape a value for YAML output.

        Parameters
        ----------
        value : Any
            Value to escape

        Returns
        -------
        str
            YAML-safe string

        """
        value_str = str(value)

        # If the value contains special characters, quote it
        if any(char in value_str for char in [":", "#", "[", "]", "{", "}", ",", "&", "*", "!", "|", ">", "@", "`"]):
            # Escape any quotes in the value
            value_str = value_str.replace('"', '\\"')
            return f'"{value_str}"'

        # If it starts with a special character or looks like a number/boolean, quote it
        if value_str and (
            value_str[0] in ["-", "?", ":"] or value_str.lower() in ["true", "false", "yes", "no", "null"]
        ):
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
            underline_char = "=" if adjusted_level == 1 else "-"
            # Calculate underline width based on plain text length, not markup length
            plain_text = self._get_plain_text_from_nodes(node.content)
            underline = underline_char * len(plain_text)
            self._output.append(f"{content}\n{underline}")
        else:
            # Use hash style for h3-h6 or when use_hash_headings is True
            prefix = "#" * adjusted_level
            self._output.append(f"{prefix} {content}")

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

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

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

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
        lang = node.language or ""

        self._output.append(f"{fence}{lang}\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append(fence)

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        If the BlockQuote has admonition metadata (from RST parsing), prepends
        a styled label (e.g., "> **Note:** ") to the first line.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        saved_output = self._output
        self._output = []

        # Check if this is an admonition from RST
        admonition_type = node.metadata.get("admonition_type") if node.metadata else None
        admonition_title = node.metadata.get("admonition_title") if node.metadata else None

        # Render children
        for child in node.children:
            child.accept(self)

        quoted = "".join(self._output)
        lines = quoted.split("\n")

        # Prepend admonition label if this is an RST admonition
        if admonition_type and node.metadata.get("source_format") == "rst":
            # Use custom title if available, otherwise capitalize admonition type
            if admonition_title:
                label = admonition_title
            else:
                # Capitalize and format the admonition type
                label = admonition_type.capitalize()

            # Prepend label to first non-empty line
            for i, line in enumerate(lines):
                if line.strip():  # Find first non-empty line
                    lines[i] = f"**{label}:** {line}"
                    break

        # Quote all lines
        quoted_lines = ["> " + line for line in lines]

        self._output = saved_output
        self._output.append("\n".join(quoted_lines))

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        was_in_list = self._in_list

        # Increment indent level for nested lists
        if self._in_list:
            self._indent_level += 1

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
                    self._output.append("\n")
                else:
                    self._output.append("\n\n")

        self._in_list = was_in_list

        # Decrement indent level when exiting nested list
        if was_in_list:
            self._indent_level -= 1

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        indent = self._current_indent()
        marker = self._list_marker_stack[-1] if self._list_marker_stack else "* "

        if node.task_status and self._flavor.supports_task_lists():
            checkbox = "[x]" if node.task_status == "checked" else "[ ]"
            marker = f"{marker}{checkbox} "

        self._output.append(f"{indent}{marker}")

        marker_width = len(marker)

        # Render children - first child inline with marker, others indented
        for i, child in enumerate(node.children):
            if i == 0:
                # First child goes immediately after the marker (no indentation)
                # Temporarily clear state so first child renders without indent
                saved_output = self._output
                self._output = []

                # Save and clear both marker width stack and indent level
                # so first child doesn't add any indentation
                saved_stack = self._marker_width_stack.copy()
                saved_indent_level = self._indent_level
                self._marker_width_stack.clear()
                self._indent_level = 0

                child.accept(self)

                # Restore state
                self._marker_width_stack = saved_stack
                self._indent_level = saved_indent_level

                child_content = "".join(self._output)
                self._output = saved_output
                self._output.append(child_content)
            else:
                # For subsequent children, push marker width to stack first
                # This ensures nested content sees the correct indentation
                if i == 1:
                    self._marker_width_stack.append(marker_width)

                # Subsequent children are indented
                # Both nested lists and other blocks (paragraphs, code blocks, etc.)
                # will use _current_indent() which now includes the marker width
                self._output.append("\n")
                child.accept(self)

        # Pop marker width from stack if we pushed it
        if len(node.children) > 1:
            self._marker_width_stack.pop()

    def _render_cells_to_strings(self, rows: list) -> list[list[str]]:
        """Convert table cells to rendered strings.

        Parameters
        ----------
        rows : list
            List of table rows

        Returns
        -------
        list[list[str]]
            Rendered cell strings

        """
        rendered_rows: list[list[str]] = []
        for row in rows:
            cells: list[str] = []
            for cell in row.cells:
                content = self._render_inline_content(cell.content)
                if self.options.table_pipe_escape:
                    content = content.replace("|", "\\|")
                cells.append(content)
            rendered_rows.append(cells)
        return rendered_rows

    def _calculate_column_widths(self, rendered_rows: list[list[str]], num_cols: int) -> list[int]:
        """Calculate column widths for padded tables.

        Parameters
        ----------
        rendered_rows : list[list[str]]
            Rendered cell strings
        num_cols : int
            Number of columns

        Returns
        -------
        list[int]
            Column widths

        """
        col_widths: list[int] = [0] * num_cols
        for row_cells in rendered_rows:
            for i, cell_content in enumerate(row_cells):
                if i < num_cols:
                    col_widths[i] = max(col_widths[i], len(cell_content))
        return col_widths

    def _generate_alignment_row(self, node: Table, num_cols: int, col_widths: list[int] | None = None) -> str:
        """Generate alignment separator row.

        Parameters
        ----------
        node : Table
            Table node with alignment info
        num_cols : int
            Number of columns
        col_widths : list[int] or None
            Column widths (None for minimal mode)

        Returns
        -------
        str
            Alignment row string

        """
        alignments = []
        for j, alignment in enumerate(node.alignments if node.alignments else []):
            if j >= num_cols:
                break
            if col_widths:
                # Padded mode
                width = max(3, col_widths[j])
                if alignment == "center":
                    alignments.append(":" + "-" * width + ":")
                elif alignment == "right":
                    alignments.append("-" * width + ":")
                elif alignment == "left":
                    alignments.append(":" + "-" * width)
                else:
                    alignments.append("-" * width)
            else:
                # Minimal mode
                if alignment == "center":
                    alignments.append(":---:")
                elif alignment == "right":
                    alignments.append("---:")
                elif alignment == "left":
                    alignments.append(":---")
                else:
                    alignments.append("---")

        # Fill remaining columns
        while len(alignments) < num_cols:
            if col_widths:
                alignments.append("-" * max(3, col_widths[len(alignments)]))
            else:
                alignments.append("---")

        return "|" + "|".join(alignments) + "|"

    def _render_padded_table(self, node: Table, rendered_rows: list[list[str]], num_cols: int) -> None:
        """Render table with cell padding.

        Parameters
        ----------
        node : Table
            Table node
        rendered_rows : list[list[str]]
            Rendered cell strings
        num_cols : int
            Number of columns

        """
        col_widths = self._calculate_column_widths(rendered_rows, num_cols)

        for i, row_cells in enumerate(rendered_rows):
            if i > 0:
                self._output.append("\n")
            padded_cells: list[str] = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    padded_cells.append(padded)
            self._output.append("| " + " | ".join(padded_cells) + " |")

            if i == 0 and node.header:
                self._output.append("\n")
                self._output.append(self._generate_alignment_row(node, num_cols, col_widths))

    def _render_minimal_table(self, node: Table, rendered_rows: list[list[str]], num_cols: int) -> None:
        """Render table without padding.

        Parameters
        ----------
        node : Table
            Table node
        rendered_rows : list[list[str]]
            Rendered cell strings
        num_cols : int
            Number of columns

        """
        for i, row_cells in enumerate(rendered_rows):
            if i > 0:
                self._output.append("\n")
            self._output.append("| " + " | ".join(row_cells) + " |")

            if i == 0 and node.header:
                self._output.append("\n")
                self._output.append(self._generate_alignment_row(node, num_cols))

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
                return
            elif mode == "ascii":
                self._render_table_as_ascii(node)
                return
            elif mode == "html":
                self._render_table_as_html(node)
                return

        rows_to_render = [node.header] if node.header else []
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        num_cols = len(rows_to_render[0].cells) if rows_to_render else 0
        rendered_rows = self._render_cells_to_strings(rows_to_render)

        if self.options.pad_table_cells:
            self._render_padded_table(node, rendered_rows, num_cols)
        else:
            self._render_minimal_table(node, rendered_rows, num_cols)

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def _render_table_as_html(self, node: Table) -> None:
        """Render a table as HTML when markdown tables are not supported.

        Parameters
        ----------
        node : Table
            Table to render as HTML

        """
        self._output.append("<table>\n")
        if node.header:
            self._output.append("  <thead>\n    <tr>")
            for cell in node.header.cells:
                content = self._render_inline_content(cell.content)
                self._output.append(f"<th>{content}</th>")
            self._output.append("</tr>\n  </thead>\n")

        if node.rows:
            self._output.append("  <tbody>\n")
            for row in node.rows:
                self._output.append("    <tr>")
                for cell in row.cells:
                    content = self._render_inline_content(cell.content)
                    self._output.append(f"<td>{content}</td>")
                self._output.append("</tr>\n")
            self._output.append("  </tbody>\n")

        self._output.append("</table>")

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
        separator = "+" + "+".join(["-" * (width + 2) for width in col_widths]) + "+"

        # Render table
        self._output.append(separator + "\n")
        for i, row_cells in enumerate(rendered_rows):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                if j < num_cols:
                    padded = cell_content.ljust(col_widths[j])
                    row_parts.append(f" {padded} ")
            self._output.append("|" + "|".join(row_parts) + "|\n")

            # Add separator after header or after each row
            if i == 0 and node.header:
                # Double separator after header
                header_sep = "+" + "+".join(["=" * (width + 2) for width in col_widths]) + "+"
                self._output.append(header_sep + "\n")
            elif i < len(rendered_rows) - 1:
                # Single separator between rows
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
        self._output.append("---")

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        processed_html = self._process_html_content(node.content)
        if processed_html:  # Only append if not empty (e.g., after "drop" mode)
            self._output.append(processed_html)

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            Comment block to render

        """
        # Use renderer's comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        if comment_mode == "blockquote":
            # Render as blockquote for readability
            # Add author/date info if available
            if node.metadata.get("author") or node.metadata.get("date"):
                author = node.metadata.get("author", "Unknown")
                date = node.metadata.get("date", "")
                label = node.metadata.get("label", "")
                header = f"Comment {label} by {author}" if label else f"Comment by {author}"
                if date:
                    header += f" ({date})"
                self._output.append(f"> *{header}*\n> \n> {node.content}")
            else:
                self._output.append(f"> {node.content}")
        else:  # "html"
            # Render as HTML comment for maximum compatibility
            # Build comment text with metadata if available
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

            self._output.append(f"<!-- {comment_text} -->")

        # Emit block references if using after_block placement
        if self.options.link_style == "reference" and self.options.reference_link_placement == "after_block":
            self._emit_block_references()

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        text = self._escape_markdown(node.content)

        # Convert bare URLs to autolinks if enabled
        if self.options.autolink_bare_urls:
            text = self._autolink_bare_urls(text)

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
        backticks = "`"
        if "`" in node.content:
            backticks = "``"
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

            # Track in block references if using after_block placement
            if self.options.reference_link_placement == "after_block":
                self._block_link_references[node.url] = ref_id

            self._output.append(f"[{content}][{ref_id}]")
        else:
            # Inline-style links: [text](url)
            if node.title:
                self._output.append(f'[{content}]({node.url} "{node.title}")')
            else:
                self._output.append(f"[{content}]({node.url})")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        alt = node.alt_text.replace("[", "\\[").replace("]", "\\]")
        if not node.url:
            # Alt-text only (no URL)
            self._output.append(f"![{alt}]()")
        elif node.title:
            self._output.append(f'![{alt}]({node.url} "{node.title}")')
        else:
            self._output.append(f"![{alt}]({node.url})")

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            self._output.append("\n")
        else:
            self._output.append("  \n")

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
        processed_html = self._process_html_content(node.content)
        if processed_html:  # Only append if not empty (e.g., after "drop" mode)
            self._output.append(processed_html)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """
        # Use renderer's comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        if comment_mode == "blockquote":
            # For inline comments in blockquote mode, render as text with attribution
            comment_text = node.content
            if node.metadata.get("author"):
                author = node.metadata.get("author")
                label = node.metadata.get("label", "")
                prefix = f"[Comment {label}" if label else "[Comment"
                comment_text = f"{prefix} by {author}: {comment_text}]"
            else:
                comment_text = f"[{comment_text}]"
            self._output.append(comment_text)
        else:  # "html"
            # Render as HTML comment for inline comments
            # Build comment text with metadata if available
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

            self._output.append(f"<!-- {comment_text} -->")

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
                child_content = "".join(self._output)
                self._output = saved_output
                if i == 0:
                    self._output.append(child_content)
                else:
                    indent_lines = child_content.split("\n")
                    self._output.append("\n    " + "\n    ".join(indent_lines))
        else:
            mode = self.options.unsupported_inline_mode
            if mode == "drop":
                return
            elif mode == "html":
                self._output.append(f'<div id="fn-{node.identifier}">')
                for child in node.content:
                    child.accept(self)
                self._output.append("</div>")
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
            mode = self.options.unsupported_inline_mode

            # Smart fallback: Use Pandoc-style syntax for defaults, respect explicit choices
            # When user didn't explicitly set mode and we're using HTML (GFM default),
            # use "force" mode instead to generate readable Markdown
            if mode == "html" and not self.options._unsupported_inline_mode_was_explicit:
                mode = "force"

            if mode == "plain":
                # Render as plain text, dropping the definition list structure
                for term, descriptions in node.items:
                    term_content = self._render_inline_content(term.content)
                    self._output.append(term_content)
                    for desc in descriptions:
                        self._output.append("\n")
                        for child in desc.content:
                            child.accept(self)
                return
            elif mode == "html":
                self._output.append("<dl>\n")
                for term, descriptions in node.items:
                    self._output.append("  <dt>")
                    term_content = self._render_inline_content(term.content)
                    self._output.append(term_content)
                    self._output.append("</dt>\n")
                    for desc in descriptions:
                        self._output.append("  <dd>")
                        for child in desc.content:
                            child.accept(self)
                        self._output.append("</dd>\n")
                self._output.append("</dl>")
                return
            # else: mode == "force", continue with markdown rendering below
        for i, (term, descriptions) in enumerate(node.items):
            if i > 0:
                self._output.append("\n")
            term_content = self._render_inline_content(term.content)
            self._output.append(term_content)
            for desc in descriptions:
                self._output.append("\n: ")
                for j, child in enumerate(desc.content):
                    if j > 0:
                        self._output.append("\n    ")
                    saved_output = self._output
                    self._output = []
                    child.accept(self)
                    child_content = "".join(self._output)
                    self._output = saved_output
                    if j > 0:
                        indent_lines = child_content.split("\n")
                        self._output.append("\n    ".join(indent_lines))
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
            if not content.endswith("\n"):
                self._output.append("\n")
            self._output.append("$$")
            return

        if self._flavor.supports_math():
            self._output.append(render_math_html(content, notation, inline=False))
            return

        mode = self.options.unsupported_inline_mode
        if mode == "plain":
            # Render as plain text content
            self._output.append(content)
            return
        if mode == "html" or notation != "latex":
            self._output.append(render_math_html(content, notation, inline=False))
            return

        # Mode is force; fall back to latex block fencing
        self._output.append("$$\n")
        self._output.append(content)
        if not content.endswith("\n"):
            self._output.append("\n")
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
        self.write_text_output(markdown_text, output)
