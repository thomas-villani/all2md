#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/org.py
"""Org-Mode rendering from AST.

This module provides the OrgRenderer class which converts AST nodes
to Org-Mode text. The renderer supports configurable handling of TODO states,
tags, and properties.

The rendering process uses the visitor pattern to traverse the AST and
generate Org-Mode output.

"""

from __future__ import annotations

import re
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
from all2md.options.org import OrgRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin


class OrgRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to Org-Mode.

    This class implements the visitor pattern to traverse an AST and
    generate Org-Mode output with configurable formatting options.

    Parameters
    ----------
    options : OrgRendererOptions or None, default = None
        Org-Mode formatting options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.org import OrgRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = OrgRenderer()
        >>> org = renderer.render_to_string(doc)
        >>> print(org)
        * Title

    Rendering enhanced Org features:

        >>> from all2md import to_markdown
        >>> from all2md.options.org import OrgParserOptions, OrgRendererOptions
        >>> # Parse with enhanced features
        >>> parser_opts = OrgParserOptions(
        ...     parse_logbook=True,
        ...     parse_clock=True,
        ...     parse_closed=True,
        ...     preserve_timestamp_metadata=True
        ... )
        >>> # Render with enhanced features
        >>> renderer_opts = OrgRendererOptions(
        ...     preserve_logbook=True,
        ...     preserve_clock=True,
        ...     preserve_closed=True
        ... )
        >>> # Round-trip conversion preserves these features
        >>> markdown = to_markdown(
        ...     "orgfile.org",
        ...     source_format="org",
        ...     parser_options=parser_opts
        ... )

    Notes
    -----
    **Enhanced Org-Mode Features:**

    The renderer can output enhanced Org-mode metadata including:

    - **CLOSED timestamps**: When tasks are completed (org_closed metadata)
    - **SCHEDULED/DEADLINE**: With repeaters and time ranges (org_scheduled,
      org_deadline metadata)
    - **LOGBOOK drawer**: State changes and notes (org_logbook metadata)
    - **CLOCK entries**: Time tracking entries (org_clock metadata)
    - **Tags**: Heading tags (tags metadata)
    - **TODO states**: Task states (todo_keyword metadata)

    **Metadata Format Compatibility:**

    The renderer handles both dictionary (new format) and string (legacy format)
    metadata for backward compatibility:

    - Dictionary format includes structured data (start date, repeater, etc.)
    - String format is rendered directly
    - This ensures existing AST structures continue to work

    **orgparse Parser Limitations:**

    When working with documents parsed by the OrgParser (which uses orgparse),
    be aware that some metadata may be incomplete:

    - LOGBOOK drawer content may be missing if SCHEDULED/DEADLINE are placed
      after PROPERTIES drawer (orgparse strips it)
    - CLOCK entries may be incomplete in nested sections
    - The renderer handles these gracefully by checking for None/empty values

    For best results when round-tripping Org-mode documents, use standard
    Org-mode formatting (SCHEDULED/DEADLINE before PROPERTIES drawer).

    """

    def __init__(self, options: OrgRendererOptions | None = None):
        """Initialize the Org renderer with options."""
        BaseRenderer._validate_options_type(options, OrgRendererOptions, "org")
        options = options or OrgRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: OrgRendererOptions = options
        self._output: list[str] = []
        self._in_list: bool = False
        self._list_depth: int = 0

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to Org-Mode string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            Org-Mode text

        """
        self._output = []
        self._in_list = False
        self._list_depth = 0

        document.accept(self)

        result = "".join(self._output)
        return self._cleanup_output(result)

    def _cleanup_output(self, text: str) -> str:
        """Clean up the final output.

        Parameters
        ----------
        text : str
            Raw Org text

        Returns
        -------
        str
            Cleaned Org text

        """
        # Remove excessive blank lines
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = text.rstrip()
        return text

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        # Render metadata as file-level properties if present
        metadata_block = self._prepare_metadata(node.metadata)
        if metadata_block:
            self._render_file_properties(metadata_block)

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

    def _render_file_properties(self, metadata: dict) -> None:
        """Render metadata as Org file-level properties.

        Parameters
        ----------
        metadata : dict
            Metadata dictionary

        """
        if not metadata:
            return

        # Org file-level properties
        if metadata.get("title"):
            self._output.append(f"#+TITLE: {metadata['title']}\n")
        if metadata.get("author"):
            self._output.append(f"#+AUTHOR: {metadata['author']}\n")
        if metadata.get("source"):
            self._output.append(f"#+SOURCE: {metadata['source']}\n")
        if metadata.get("creation_date"):
            self._output.append(f"#+DATE: {metadata['creation_date']}\n")
        if metadata.get("modification_date"):
            self._output.append(f"#+UPDATED: {metadata['modification_date']}\n")
        if metadata.get("accessed_date"):
            self._output.append(f"#+ACCESS_DATE: {metadata['accessed_date']}\n")
        if metadata.get("description"):
            self._output.append(f"#+DESCRIPTION: {metadata['description']}\n")
        if metadata.get("keywords"):
            if isinstance(metadata["keywords"], list):
                keywords = ", ".join(str(k) for k in metadata["keywords"])
            else:
                keywords = str(metadata["keywords"])
            self._output.append(f"#+KEYWORDS: {keywords}\n")
        if metadata.get("language"):
            self._output.append(f"#+LANGUAGE: {metadata['language']}\n")
        if metadata.get("category"):
            self._output.append(f"#+CATEGORY: {metadata['category']}\n")

        # Add other custom properties
        if "custom" in metadata and isinstance(metadata["custom"], dict):
            for key, value in metadata["custom"].items():
                self._output.append(f"#+{key.upper()}: {value}\n")

        if metadata:
            self._output.append("\n")

    def visit_heading(self, node: Heading) -> None:  # noqa: C901
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        # Generate stars based on level
        stars = "*" * node.level

        # Extract TODO state, priority, and tags from metadata
        todo_state = node.metadata.get("org_todo_state", "") if node.metadata else ""
        priority = node.metadata.get("org_priority", "") if node.metadata else ""
        tags = node.metadata.get("org_tags", []) if node.metadata else []

        # Render heading line
        parts = [stars]

        if todo_state and self.options.preserve_tags:
            parts.append(todo_state)

        if priority:
            parts.append(f"[#{priority}]")

        # Render heading content
        content = self._render_inline_content(node.content)
        parts.append(content)

        # Render tags
        if tags and self.options.preserve_tags:
            tags_str = ":" + ":".join(tags) + ":"
            parts.append(tags_str)

        self._output.append(" ".join(parts))

        # Render properties drawer if present and enabled
        if self.options.preserve_properties and node.metadata:
            properties = node.metadata.get("org_properties", {})
            if properties:
                self._output.append("\n:PROPERTIES:\n")
                for key, value in properties.items():
                    self._output.append(f":{key}: {value}\n")
                self._output.append(":END:")

        # Render CLOSED timestamp if present and enabled
        if self.options.preserve_closed and node.metadata:
            closed = node.metadata.get("org_closed")
            if closed:
                # Handle both dict (full metadata) and string (legacy) formats
                if isinstance(closed, dict):
                    closed_str = closed.get("string", str(closed))
                else:
                    closed_str = str(closed)
                self._output.append(f"\nCLOSED: {closed_str}")

        # Render SCHEDULED timestamp if present
        if node.metadata:
            scheduled = node.metadata.get("org_scheduled")
            if scheduled:
                # Handle both dict (full metadata) and string (legacy) formats
                if isinstance(scheduled, dict):
                    scheduled_str = scheduled.get("string", str(scheduled))
                else:
                    scheduled_str = str(scheduled)
                self._output.append(f"\nSCHEDULED: {scheduled_str}")

        # Render DEADLINE timestamp if present
        if node.metadata:
            deadline = node.metadata.get("org_deadline")
            if deadline:
                # Handle both dict (full metadata) and string (legacy) formats
                if isinstance(deadline, dict):
                    deadline_str = deadline.get("string", str(deadline))
                else:
                    deadline_str = str(deadline)
                self._output.append(f"\nDEADLINE: {deadline_str}")

        # Render LOGBOOK drawer if present and enabled
        if self.options.preserve_logbook and node.metadata:
            logbook = node.metadata.get("org_logbook")
            if logbook:
                # Only render if there are entries
                entries = logbook.get("entries", [])
                if entries:
                    self._output.append("\n:LOGBOOK:\n")

                    # Render entries
                    for entry in entries:
                        entry_type = entry.get("type")

                        if entry_type == "state_change":
                            self._output.append(
                                f"- State \"{entry['new_state']}\" "
                                f"from \"{entry['old_state']}\" "
                                f"[{entry['timestamp']}]\n"
                            )
                        elif entry_type == "clock":
                            if entry.get("end"):
                                clock_line = f"CLOCK: [{entry['start']}]--[{entry['end']}]"
                                if entry.get("duration"):
                                    clock_line += f" =>  {entry['duration']}"
                                self._output.append(clock_line + "\n")
                            else:
                                self._output.append(f"CLOCK: [{entry['start']}]\n")
                        elif entry_type == "note":
                            self._output.append(f"- {entry['content']} [{entry['timestamp']}]\n")

                    self._output.append(":END:")

        # Render CLOCK entries if present and enabled (outside LOGBOOK)
        # This handles clock entries that were extracted via node.clock
        if self.options.preserve_clock and node.metadata:
            clock_entries = node.metadata.get("org_clock")
            if clock_entries:
                # Only render if we haven't already rendered a LOGBOOK
                # (to avoid duplication if clock entries were in LOGBOOK)
                if not (self.options.preserve_logbook and node.metadata.get("org_logbook")):
                    self._output.append("\n:LOGBOOK:\n")
                    for clock in clock_entries:
                        if clock.get("end"):
                            clock_line = f"CLOCK: [{clock['start']}]--[{clock['end']}]"
                            if clock.get("duration"):
                                clock_line += f" =>  {clock['duration']}"
                            self._output.append(clock_line + "\n")
                        else:
                            self._output.append(f"CLOCK: [{clock['start']}]\n")
                    self._output.append(":END:")

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
        # Render as #+BEGIN_SRC / #+END_SRC block
        lang = node.language if node.language else ""
        self._output.append(f"#+BEGIN_SRC {lang}\n".rstrip() + "\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append("#+END_SRC")

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

        quoted = "".join(self._output)
        lines = quoted.split("\n")

        # Prefix each line with : for Org quote format
        quoted_lines = [": " + line for line in lines]

        self._output = saved_output
        self._output.append("\n".join(quoted_lines))

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
                marker = "- "

            # Add indentation for nested lists
            indent = "  " * (self._list_depth - 1)
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
                        self._output.append(f"\n{indent}  {line}")

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
        # Collect all rows
        rows_to_render = []
        if node.header:
            rows_to_render.append(node.header)
        rows_to_render.extend(node.rows)

        if not rows_to_render:
            return

        # Compute grid dimensions accounting for colspan/rowspan
        num_rows = len(rows_to_render)
        num_cols = self._compute_table_columns(rows_to_render)

        # Build expanded grid
        rendered_grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]
        occupied = [[False] * num_cols for _ in range(num_rows)]

        # Fill the grid
        for row_idx, ast_row in enumerate(rows_to_render):
            col_idx = 0
            for ast_cell in ast_row.cells:
                # Skip occupied cells
                while col_idx < num_cols and occupied[row_idx][col_idx]:
                    col_idx += 1

                if col_idx >= num_cols:
                    break

                # Render cell content
                content = self._render_inline_content(ast_cell.content)

                # Handle cell spanning
                colspan = ast_cell.colspan
                rowspan = ast_cell.rowspan

                # Fill the grid - center content in spanned area
                rendered_grid[row_idx][col_idx] = content

                # Fill remaining spanned cells with empty strings
                for r in range(row_idx, min(row_idx + rowspan, num_rows)):
                    for c in range(col_idx, min(col_idx + colspan, num_cols)):
                        occupied[r][c] = True
                        if r != row_idx or c != col_idx:
                            rendered_grid[r][c] = ""

                col_idx += colspan

        # Calculate column widths from expanded grid
        col_widths = [0] * num_cols
        for row_cells in rendered_grid:
            for i, cell_content in enumerate(row_cells):
                col_widths[i] = max(col_widths[i], len(cell_content))

        # Render table using expanded grid
        for i, row_cells in enumerate(rendered_grid):
            # Render row
            row_parts = []
            for j, cell_content in enumerate(row_cells):
                padded = cell_content.ljust(col_widths[j])
                row_parts.append(padded)
            self._output.append("| " + " | ".join(row_parts) + " |")

            if i < len(rendered_grid) - 1:
                self._output.append("\n")

            # Add separator after header
            if i == 0 and node.header:
                self._output.append("\n|")
                for width in col_widths:
                    self._output.append("-" * (width + 2) + "|")

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
        self._output.append("-----")

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # Escape Org special characters if they would cause issues
        text = node.content
        # Org generally doesn't need much escaping in plain text
        self._output.append(text)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"/{content}/")

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
        self._output.append(f"={node.content}=")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)

        # Org link syntax: [[url][description]]
        if node.url:
            if content and content != node.url:
                self._output.append(f"[[{node.url}][{content}]]")
            else:
                self._output.append(f"[[{node.url}]]")
        else:
            self._output.append(content)

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        # Org image syntax: [[file:path]]
        if node.url:
            # Add file: prefix if not present
            url = node.url if node.url.startswith("file:") else f"file:{node.url}"
            if node.alt_text and node.alt_text != node.url:
                self._output.append(f"[[{url}][{node.alt_text}]]")
            else:
                self._output.append(f"[[{url}]]")

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
            # Hard line break - use \\ in Org
            self._output.append(" \\\\\n")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"+{content}+")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"_{content}_")

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        # Org uses ^{} for superscript
        self._output.append(f"^{{{content}}}")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        # Org uses _{} for subscript
        self._output.append(f"_{{{content}}}")

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render inline HTML (preserve as-is)."""
        self._output.append(node.content)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render HTML block (wrap in export block)."""
        self._output.append("#+BEGIN_EXPORT html\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append("#+END_EXPORT")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render footnote reference."""
        self._output.append(f"[fn:{node.identifier}]")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render footnote definition."""
        self._output.append(f"[fn:{node.identifier}] ")
        for i, child in enumerate(node.content):
            if i > 0:
                self._output.append("\n")
            saved_output = self._output
            self._output = []
            child.accept(self)
            child_content = "".join(self._output)
            self._output = saved_output
            self._output.append(child_content)

    def visit_math_inline(self, node: MathInline) -> None:
        """Render inline math."""
        preferred: MathNotation = "latex"  # Org uses LaTeX for math
        content, notation = node.get_preferred_representation(preferred)
        # Org uses $...$ or \(...\) for inline math
        self._output.append(f"${content}$")

    def visit_math_block(self, node: MathBlock) -> None:
        """Render math block."""
        preferred: MathNotation = "latex"
        content, notation = node.get_preferred_representation(preferred)
        # Org uses $$...$$ or \[...\] for block math
        self._output.append("$$\n")
        self._output.append(content)
        if not content.endswith("\n"):
            self._output.append("\n")
        self._output.append("$$")

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
            self._output.append(f"- {term_content} :: ")

            # Render descriptions
            for j, desc in enumerate(descriptions):
                if j > 0:
                    self._output.append("\n  ")
                saved_output = self._output
                self._output = []

                for child in desc.content:
                    child.accept(self)

                desc_content = "".join(self._output)
                self._output = saved_output
                self._output.append(desc_content)

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

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

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

        if comment_mode == "drawer":
            # Render as :COMMENT: drawer block
            self._output.append(":COMMENT:\n")

            # Add attribution if present
            if author:
                if date:
                    self._output.append(f"{prefix} by {author} ({date}):\n")
                else:
                    self._output.append(f"{prefix} by {author}:\n")
                self._output.append("\n")

            # Add content
            self._output.append(node.content)
            self._output.append("\n:END:\n")
            return

        # Mode is "comment" - render as Org-mode comments
        # Org-mode uses # for comments
        # Each line should be prefixed with #
        lines = node.content.split("\n")

        # Add metadata header if available
        if author or date:
            header = f"{prefix} by {author}" if author else prefix
            if date:
                header += f" ({date})"
            self._output.append(f"# {header}\n")

        # Render each line as an Org comment
        for i, line in enumerate(lines):
            if i > 0:
                self._output.append("\n")
            self._output.append(f"# {line}")

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (inline).

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

        if comment_mode == "drawer":
            # Render as inline visible text (Org-mode doesn't support inline drawers)
            # Build full text
            if author:
                if date:
                    full_text = f"[{prefix} by {author} ({date}): {node.content}]"
                else:
                    full_text = f"[{prefix} by {author}: {node.content}]"
            else:
                full_text = f"[{node.content}]"

            self._output.append(full_text)
            return

        # Mode is "comment" - render as HTML comment (Org-mode doesn't have inline comments)
        # Build comment text with metadata if available
        comment_text = node.content
        if author:
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        # Use HTML comment as fallback since Org doesn't support inline comments
        self._output.append(f"<!-- {comment_text} -->")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to Org-Mode and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        org_text = self.render_to_string(doc)
        self.write_text_output(org_text, output)
