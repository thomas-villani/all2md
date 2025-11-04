#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/json.py
"""JSON rendering from AST.

This module provides the JsonRenderer class which extracts structured data
from AST documents and converts it to JSON format. The primary use case is
extracting tables from markdown documentation as JSON arrays.

Examples
--------
Extract tables from markdown:

Input markdown:

.. code-block:: markdown

    # Users
    | name | age | active |
    |------|-----|--------|
    | Alice | 30 | true |
    | Bob | 25 | false |

Output JSON:

.. code-block:: json

    {
      "Users": [
        {"name": "Alice", "age": 30, "active": true},
        {"name": "Bob", "age": 25, "active": false}
      ]
    }

"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import IO, Any, Union

from all2md.ast.nodes import Document, Heading, Node, Table, TableCell, Text
from all2md.ast.nodes import List as AstList
from all2md.exceptions import RenderingError
from all2md.options.json import JsonRendererOptions
from all2md.renderers.base import BaseRenderer

logger = logging.getLogger(__name__)


class JsonRenderer(BaseRenderer):
    """Render AST to JSON format by extracting structured data.

    This renderer extracts tables and lists from AST documents and converts
    them to JSON structures. Tables become arrays of objects, with column
    headers as keys. Preceding headings are used as structure keys.

    Parameters
    ----------
    options : JsonRendererOptions or None, default = None
        JSON rendering options

    Examples
    --------
    Basic usage (extract tables):

        >>> from all2md.ast import Document, Table, TableRow, TableCell, Text, Heading
        >>> from all2md.renderers.json import JsonRenderer
        >>> table = Table(
        ...     header=TableRow(cells=[
        ...         TableCell(content=[Text(content="name")]),
        ...         TableCell(content=[Text(content="value")])
        ...     ]),
        ...     rows=[
        ...         TableRow(cells=[
        ...             TableCell(content=[Text(content="timeout")]),
        ...             TableCell(content=[Text(content="30")])
        ...         ])
        ...     ]
        ... )
        >>> heading = Heading(level=1, content=[Text(content="Configuration")])
        >>> doc = Document(children=[heading, table])
        >>> renderer = JsonRenderer()
        >>> json_text = renderer.render_to_string(doc)

    Extract lists as arrays:

        >>> from all2md.options.json import JsonRendererOptions
        >>> options = JsonRendererOptions(extract_mode="both")
        >>> renderer = JsonRenderer(options)

    """

    def __init__(self, options: JsonRendererOptions | None = None):
        """Initialize the JSON renderer with options."""
        BaseRenderer._validate_options_type(options, JsonRendererOptions, "json")
        options = options or JsonRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: JsonRendererOptions = options

    def render(self, doc: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render AST document to JSON file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, IO[bytes], or IO[str]
            Output destination

        """
        json_str = self.render_to_string(doc)

        # Write to output
        if isinstance(output, (str, Path)):
            with open(output, "w", encoding="utf-8") as f:
                f.write(json_str)
        elif hasattr(output, "write"):
            if hasattr(output, "mode") and "b" in getattr(output, "mode", ""):
                # Binary mode - encode to bytes
                output.write(json_str.encode("utf-8"))  # type: ignore[arg-type]
            else:
                # Text mode
                output.write(json_str)  # type: ignore[call-overload]
        else:
            raise RenderingError(f"Unsupported output type: {type(output)}")

    def render_to_string(self, doc: Document) -> str:
        """Render AST document to JSON string.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        str
            JSON string

        """
        try:
            # Extract structured data
            data = self._extract_data(doc)

            # Convert to JSON
            json_str = json.dumps(
                data,
                indent=self.options.indent,
                ensure_ascii=self.options.ensure_ascii,
                sort_keys=self.options.sort_keys,
            )

            return json_str

        except Exception as e:
            raise RenderingError(f"Failed to render JSON: {e}") from e

    def _extract_data(self, doc: Document) -> dict[str, Any] | list[Any]:
        """Extract structured data from document.

        Parameters
        ----------
        doc : Document
            Document to extract from

        Returns
        -------
        dict or list
            Extracted data structure

        """
        extractor = DataExtractor(self.options)
        result = extractor.extract(doc)

        # Handle flatten_single_table option
        if self.options.flatten_single_table and isinstance(result, dict) and len(result) == 1:
            # Return the single value directly
            return list(result.values())[0]

        return result


class DataExtractor:
    """Extractor that walks AST and extracts structured data.

    This class walks the AST and extracts tables and lists into
    structured data according to the renderer options.

    Parameters
    ----------
    options : JsonRendererOptions
        Rendering options

    """

    def __init__(self, options: JsonRendererOptions):
        """Initialize the data extractor."""
        self.options = options
        self.data: dict[str, Any] = {}
        self.current_heading: str | None = None
        self.section_counter: dict[str, int] = {}

    def extract(self, doc: Document) -> dict[str, Any]:
        """Extract data from document.

        Parameters
        ----------
        doc : Document
            Document to extract from

        Returns
        -------
        dict
            Extracted data

        """
        # Walk through document children
        for child in doc.children:
            self._process_node(child)
        return self.data

    def _process_node(self, node: Node) -> None:
        """Process a single node.

        Parameters
        ----------
        node : Node
            Node to process

        """
        if isinstance(node, Heading):
            self._process_heading(node)
        elif isinstance(node, Table):
            self._process_table(node)
        elif isinstance(node, AstList):
            self._process_list(node)
        # For other nodes, recursively process children
        elif hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                self._process_node(child)

    def _process_heading(self, node: Heading) -> None:
        """Process heading node and update current section.

        Parameters
        ----------
        node : Heading
            Heading node to process

        """
        # Extract text from heading
        text_parts: list[str] = []
        for child in node.content:
            if isinstance(child, Text):
                text_parts.append(child.content)
        self.current_heading = "".join(text_parts).strip()

    def _process_table(self, node: Table) -> None:
        """Process table node and extract data.

        Parameters
        ----------
        node : Table
            Table node to process

        """
        if self.options.extract_mode not in ("tables", "both"):
            return

        # Extract table data
        table_data = self._extract_table(node)

        if table_data:
            # Use heading as key if enabled
            if self.options.table_heading_keys and self.current_heading:
                key = self.current_heading

                # Handle duplicate keys
                if key in self.data:
                    # Add counter suffix
                    self.section_counter[key] = self.section_counter.get(key, 1) + 1
                    key = f"{key}_{self.section_counter[key]}"

                self.data[key] = table_data
            else:
                # No heading - use generic key with counter
                counter = len([k for k in self.data.keys() if k.startswith("table_")])
                self.data[f"table_{counter + 1}"] = table_data

    def _process_list(self, node: AstList) -> None:
        """Process list node and extract data.

        Parameters
        ----------
        node : AstList
            List node to process

        """
        if self.options.extract_mode not in ("lists", "both"):
            return

        # Extract list data
        list_data = self._extract_list(node)

        if list_data:
            # Use heading as key if enabled
            if self.options.table_heading_keys and self.current_heading:
                key = self.current_heading

                # Handle duplicate keys
                if key in self.data:
                    # Add counter suffix
                    self.section_counter[key] = self.section_counter.get(key, 1) + 1
                    key = f"{key}_{self.section_counter[key]}"

                self.data[key] = list_data
            else:
                # No heading - use generic key with counter
                counter = len([k for k in self.data.keys() if k.startswith("list_")])
                self.data[f"list_{counter + 1}"] = list_data

    def _extract_table(self, table: Table) -> list[dict[str, Any]]:
        """Extract data from table node.

        Parameters
        ----------
        table : Table
            Table to extract from

        Returns
        -------
        list[dict]
            Array of objects representing table rows

        """
        # Get column names from header
        columns: list[str] = []
        if table.header:
            for cell in table.header.cells:
                col_name = self._extract_cell_text(cell)
                columns.append(col_name)

        if not columns:
            return []

        # Extract rows
        rows: list[dict[str, Any]] = []
        for row in table.rows:
            row_data: dict[str, Any] = {}
            for i, cell in enumerate(row.cells):
                if i < len(columns):
                    col_name = columns[i]
                    cell_value = self._extract_cell_text(cell)

                    # Type inference
                    if self.options.type_inference:
                        cell_value = self._infer_type(cell_value)

                    row_data[col_name] = cell_value

            if row_data:
                rows.append(row_data)

        return rows

    def _extract_list(self, list_node: AstList) -> list[Any]:
        """Extract data from list node.

        Parameters
        ----------
        list_node : AstList
            List to extract from

        Returns
        -------
        list
            Array of values from list items

        """
        items: list[Any] = []

        for item in list_node.items:
            # Extract text from list item
            item_text = self._extract_node_text(item)

            # Type inference
            if self.options.type_inference:
                item_text = self._infer_type(item_text)

            items.append(item_text)

        return items

    def _extract_cell_text(self, cell: TableCell) -> str:
        """Extract text from table cell.

        Parameters
        ----------
        cell : TableCell
            Cell to extract from

        Returns
        -------
        str
            Cell text content

        """
        text_parts: list[str] = []
        for node in cell.content:
            text_parts.append(self._extract_node_text(node))
        return "".join(text_parts).strip()

    def _extract_node_text(self, node: Node) -> str:
        """Extract text from any node recursively.

        Parameters
        ----------
        node : Node
            Node to extract from

        Returns
        -------
        str
            Text content

        """
        if isinstance(node, Text):
            return node.content

        # Recursively extract from children
        text_parts: list[str] = []
        if hasattr(node, "content") and isinstance(node.content, list):
            for child in node.content:
                text_parts.append(self._extract_node_text(child))

        return "".join(text_parts)

    def _infer_type(self, value: str) -> Any:
        """Infer and convert type from string.

        Parameters
        ----------
        value : str
            String value to convert

        Returns
        -------
        Any
            Converted value with inferred type

        """
        # Empty string
        if not value or value.strip() == "":
            return ""

        stripped = value.strip().lower()

        # Boolean
        if stripped in ("true", "yes", "on", "1"):
            return True
        if stripped in ("false", "no", "off", "0"):
            return False

        # None/null
        if stripped in ("null", "none", "nil", "~"):
            return None

        # Number
        try:
            # Try integer first
            if "." not in value:
                return int(value.replace(",", ""))
            # Try float
            return float(value.replace(",", ""))
        except ValueError:
            pass

        # Return as string
        return value
