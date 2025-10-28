#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/csv.py
"""CSV rendering from AST.

This module provides the CsvRenderer class which converts AST table nodes
to CSV (Comma-Separated Values) format. The renderer supports:
- Table selection by index or heading proximity
- Multi-table handling (first, all, or error)
- Merged cell handling
- Configurable CSV dialects
- Excel compatibility (BOM support)

The rendering process extracts table data from the AST and writes it to
CSV using Python's csv module with full control over formatting options.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import IO, Union

from all2md.ast.nodes import Comment, CommentInline, Document, Heading, Node, Table, TableRow, Text
from all2md.exceptions import RenderingError
from all2md.options.csv import CsvRendererOptions
from all2md.renderers.base import BaseRenderer

logger = logging.getLogger(__name__)


class CsvRenderer(BaseRenderer):
    """Render AST table nodes to CSV format.

    This class extracts table data from an AST document and renders it to
    CSV format with configurable options for table selection, merged cell
    handling, and CSV dialect settings.

    Parameters
    ----------
    options : CsvRendererOptions or None, default = None
        CSV rendering options

    Examples
    --------
    Basic usage (export first table):

        >>> from all2md.ast import Document, Table, TableRow, TableCell, Text
        >>> from all2md.renderers.csv import CsvRenderer
        >>> from all2md.options.csv import CsvRendererOptions
        >>> table = Table(
        ...     header=TableRow(cells=[
        ...         TableCell(content=[Text(content="Name")]),
        ...         TableCell(content=[Text(content="Age")])
        ...     ]),
        ...     rows=[
        ...         TableRow(cells=[
        ...             TableCell(content=[Text(content="Alice")]),
        ...             TableCell(content=[Text(content="30")])
        ...         ])
        ...     ]
        ... )
        >>> doc = Document(children=[table])
        >>> renderer = CsvRenderer()
        >>> csv_text = renderer.render_to_string(doc)
        >>> print(csv_text)
        Name,Age
        Alice,30

    Extract table by heading:

        >>> options = CsvRendererOptions(table_heading="Results")
        >>> renderer = CsvRenderer(options)

    Export all tables:

        >>> options = CsvRendererOptions(
        ...     multi_table_mode="all",
        ...     include_table_headings=True
        ... )
        >>> renderer = CsvRenderer(options)

    """

    def __init__(self, options: CsvRendererOptions | None = None):
        """Initialize the CSV renderer with options."""
        BaseRenderer._validate_options_type(options, CsvRendererOptions, "csv")
        options = options or CsvRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: CsvRendererOptions = options

    def render(self, doc: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render AST document to CSV file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, IO[bytes], or IO[str]
            Output destination

        Raises
        ------
        RenderingError
            If no tables found or rendering fails

        """
        csv_text = self.render_to_string(doc)
        self.write_text_output(csv_text, output)

    def render_to_string(self, doc: Document) -> str:
        """Render AST document to CSV string.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        str
            Rendered CSV content

        Raises
        ------
        RenderingError
            If no tables found or rendering fails

        """
        # Find all tables and their preceding headings
        tables_with_context = self._find_tables_with_headings(doc)

        if not tables_with_context:
            raise RenderingError("No tables found in document")

        # Select table(s) based on options
        selected_tables = self._select_tables(tables_with_context)

        if not selected_tables:
            if self.options.table_heading:
                raise RenderingError(f"No table found after heading matching '{self.options.table_heading}'")
            else:
                raise RenderingError("No table found at requested index")

        # Handle multi-table mode
        if len(selected_tables) > 1:
            if self.options.multi_table_mode == "error":
                raise RenderingError(f"Found {len(selected_tables)} tables, but multi_table_mode='error'")
            elif self.options.multi_table_mode == "first":
                selected_tables = [selected_tables[0]]

        # Render table(s)
        csv_parts = []
        for heading_text, table in selected_tables:
            if self.options.include_table_headings and heading_text and len(selected_tables) > 1:
                # Add heading as comment
                csv_parts.append(f"# {heading_text}")

            csv_parts.append(self._render_table(table))

        # Join with separator
        result = self.options.table_separator.join(csv_parts)

        # Add BOM if requested
        if self.options.include_bom:
            result = "\ufeff" + result

        return result

    def _find_tables_with_headings(self, doc: Document) -> list[tuple[str | None, Table]]:
        """Find all tables in document with their preceding heading text.

        Parameters
        ----------
        doc : Document
            Document to search

        Returns
        -------
        list[tuple[str | None, Table]]
            List of (heading_text, table) tuples

        """
        results: list[tuple[str | None, Table]] = []
        current_heading: str | None = None

        def visit_node(node: Node) -> None:
            nonlocal current_heading

            if isinstance(node, Heading):
                # Extract heading text
                current_heading = self._extract_text_content(node.content)
            elif isinstance(node, Table):
                results.append((current_heading, node))

            # Recurse into children
            if hasattr(node, "children"):
                for child in node.children:
                    visit_node(child)
            # Also check rows for tables
            if isinstance(node, Table):
                pass  # Already added, don't recurse

        for child in doc.children:
            visit_node(child)

        return results

    def _select_tables(self, tables_with_context: list[tuple[str | None, Table]]) -> list[tuple[str | None, Table]]:
        """Select table(s) based on options.

        Parameters
        ----------
        tables_with_context : list[tuple[str | None, Table]]
            All tables with their heading context

        Returns
        -------
        list[tuple[str | None, Table]]
            Selected tables

        """
        # If table_heading specified, search by heading
        if self.options.table_heading:
            search_text = self.options.table_heading.lower()
            for heading_text, table in tables_with_context:
                if heading_text and search_text in heading_text.lower():
                    return [(heading_text, table)]
            return []

        # If table_index is None, return all
        if self.options.table_index is None:
            return tables_with_context

        # Return specific index
        if 0 <= self.options.table_index < len(tables_with_context):
            return [tables_with_context[self.options.table_index]]

        return []

    def _render_table(self, table: Table) -> str:
        """Render a single table to CSV.

        Parameters
        ----------
        table : Table
            Table node to render

        Returns
        -------
        str
            CSV representation of table

        """
        output = io.StringIO()

        # Map quoting option to csv constant
        quoting_map = {
            "minimal": csv.QUOTE_MINIMAL,
            "all": csv.QUOTE_ALL,
            "nonnumeric": csv.QUOTE_NONNUMERIC,
            "none": csv.QUOTE_NONE,
        }
        quoting = quoting_map[self.options.quoting]

        # Create CSV writer
        writer_kwargs = {
            "delimiter": self.options.delimiter,
            "quotechar": self.options.quote_char,
            "quoting": quoting,
            "lineterminator": self.options.line_terminator,
        }
        if self.options.escape_char is not None:
            writer_kwargs["escapechar"] = self.options.escape_char

        writer = csv.writer(output, **writer_kwargs)  # type: ignore[arg-type]

        # Process header if present
        if table.header:
            header_row = self._process_row(table.header)
            writer.writerow(header_row)

        # Process body rows
        for row in table.rows:
            csv_row = self._process_row(row)
            writer.writerow(csv_row)

        return output.getvalue()

    def _process_row(self, row: TableRow) -> list[str]:
        """Process a table row, handling merged cells.

        Parameters
        ----------
        row : TableRow
            Table row to process

        Returns
        -------
        list[str]
            List of cell values (expanded for merged cells)

        """
        result: list[str] = []

        for cell in row.cells:
            # Extract cell text content
            cell_text = self._extract_text_content(cell.content)

            # Add cell value
            result.append(cell_text)

            # Handle colspan
            if cell.colspan > 1:
                for _ in range(cell.colspan - 1):
                    if self.options.handle_merged_cells == "repeat":
                        result.append(cell_text)
                    elif self.options.handle_merged_cells == "blank":
                        result.append("")
                    else:  # placeholder
                        result.append("[merged]")

        # Note: rowspan is more complex and would require tracking state across rows
        # For now, we handle it simply by treating each row independently
        # A full implementation would need to track which cells span down

        return result

    def _extract_text_content(self, nodes: list[Node]) -> str:
        """Extract plain text from inline content nodes.

        Parameters
        ----------
        nodes : list[Node]
            Inline content nodes

        Returns
        -------
        str
            Extracted text content

        """
        parts: list[str] = []

        for node in nodes:
            if isinstance(node, Text):
                parts.append(node.content)
            elif hasattr(node, "content"):
                # Recurse into inline containers (Strong, Emphasis, Link, etc.)
                parts.append(self._extract_text_content(node.content))

        return "".join(parts)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (strip in CSV).

        Parameters
        ----------
        node : Comment
            Comment to render

        """
        # Skip comments in CSV output (doesn't make sense in CSV)
        pass

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (strip in CSV).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """
        # Skip inline comments in CSV output (doesn't make sense in CSV)
        pass
