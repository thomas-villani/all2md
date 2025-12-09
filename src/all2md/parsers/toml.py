#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/toml.py
"""TOML to AST converter.

This module provides intelligent conversion from TOML structures to readable
document format. By default, it transforms the structure into a hierarchical
document with headings, tables, and lists. Alternatively, it can render TOML
as a literal code block (via the `literal_block` option).

Examples
--------
**Smart Conversion (default):**

Input TOML::

    [server]
    host = "localhost"
    port = 8080

    [[users]]
    name = "Alice"
    role = "admin"

    [[users]]
    name = "Bob"
    role = "user"

Output (as markdown):

.. code-block:: markdown

    # server
    * **host**: localhost
    * **port**: 8,080

    # users
    | name | role |
    |------|------|
    | Alice | admin |
    | Bob | user |

**Literal Block Mode:**

Input TOML (same as above)

Output (as markdown):

.. code-block:: toml

    [server]
    host = "localhost"
    port = 8080

    [[users]]
    name = "Alice"
    role = "admin"

    [[users]]
    name = "Bob"
    role = "user"

"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    LineBreak,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.constants import DEPS_TOML
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.toml import TomlParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class TomlParser(BaseParser):
    r"""Convert TOML structures to AST representation.

    This parser creates a readable document from TOML by converting:
    - Sections/tables → heading hierarchies
    - Arrays of tables → markdown tables
    - Arrays of primitives → lists
    - Nested structures → subsections

    Parameters
    ----------
    options : TomlParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = TomlParser()
        >>> doc = parser.parse('[server]\\nhost = "localhost"\\nport = 8080')

    With options:

        >>> options = TomlParserOptions(max_heading_depth=3, sort_keys=True)
        >>> parser = TomlParser(options)
        >>> doc = parser.parse(toml_file_path)

    """

    def __init__(self, options: TomlParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the TOML parser with options and progress callback."""
        BaseParser._validate_options_type(options, TomlParserOptions, "toml")
        options = options or TomlParserOptions()
        super().__init__(options, progress_callback)
        self.options: TomlParserOptions = options

    @requires_dependencies("toml", DEPS_TOML)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse TOML input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            TOML input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw TOML bytes
            - TOML string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        self._emit_progress("started", "Parsing TOML", current=0, total=100)

        try:
            # Load content using BaseParser helper
            content = self._load_text_content(input_data)

            # Import TOML library (prefer stdlib tomllib in Python 3.11+, fallback to tomli)
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib

            # Check if we should render as literal code block
            if self.options.literal_block:
                self._emit_progress("completed", "TOML wrapped as code block", current=100, total=100)

                # Optionally pretty-print the TOML
                try:
                    data = tomllib.loads(content)
                    # Re-serialize with formatting using tomli_w
                    import tomli_w

                    formatted_toml = tomli_w.dumps(data)
                except Exception:
                    # If invalid TOML or tomli_w not available, just use the raw content
                    formatted_toml = content

                # Create code block
                code_block = CodeBlock(content=formatted_toml, language="toml")
                metadata = DocumentMetadata()
                return Document(children=[code_block], metadata=metadata.to_dict())

            self._emit_progress("parsing", "Parsing TOML structure", current=30, total=100)

            # Parse TOML
            try:
                data = tomllib.loads(content)
            except Exception as e:
                raise ParsingError(f"Invalid TOML: {e}") from e

            self._emit_progress("converting", "Converting to document structure", current=60, total=100)

            # Convert to AST
            children = self._convert_value(data, depth=0)

            self._emit_progress("completed", "TOML parsing completed", current=100, total=100)

            # Create document
            metadata = self.extract_metadata(data)
            return Document(children=children, metadata=metadata.to_dict())

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Failed to parse TOML: {e}") from e

    def _convert_value(self, value: Any, depth: int, key: str | None = None) -> list[Node]:
        """Convert a TOML value to AST nodes.

        Parameters
        ----------
        value : Any
            TOML value to convert
        depth : int
            Current nesting depth
        key : str or None
            Key name for this value (if part of an object)

        Returns
        -------
        list[Node]
            List of AST nodes representing this value

        """
        # Note: TOML does not have null values
        if value is None:
            # This shouldn't happen in valid TOML, but handle it anyway
            return [Paragraph(content=[Text(content="")])]

        if isinstance(value, bool):
            return [Paragraph(content=[Text(content="true" if value else "false")])]

        if isinstance(value, (int, float)):
            if self.options.pretty_format_numbers and isinstance(value, int) and abs(value) >= 1000:
                text = f"{value:,}"
            else:
                text = str(value)
            return [Paragraph(content=[Text(content=text)])]

        if isinstance(value, str):
            # Handle multi-line strings
            if "\n" in value:
                lines = value.split("\n")
                content: list[Node] = []
                for i, line in enumerate(lines):
                    if i > 0:
                        content.append(LineBreak())
                    content.append(Text(content=line))
                return [Paragraph(content=content)]
            return [Paragraph(content=[Text(content=value)])]

        # TOML-specific types
        if isinstance(value, datetime.datetime):
            return [Paragraph(content=[Text(content=value.isoformat())])]
        if isinstance(value, datetime.date):
            return [Paragraph(content=[Text(content=value.isoformat())])]
        if isinstance(value, datetime.time):
            return [Paragraph(content=[Text(content=value.isoformat())])]

        if isinstance(value, list):
            return self._convert_array(value, depth, key)

        if isinstance(value, dict):
            return self._convert_object(value, depth)

        # Fallback for unknown types
        return [Paragraph(content=[Text(content=str(value))])]

    def _convert_object(self, obj: dict[str, Any], depth: int) -> list[Node]:
        """Convert a TOML object to AST nodes.

        Parameters
        ----------
        obj : dict
            TOML object to convert
        depth : int
            Current nesting depth

        Returns
        -------
        list[Node]
            List of AST nodes representing this object

        """
        nodes: list[Node] = []

        # Handle empty object
        if not obj:
            nodes.append(Paragraph(content=[Text(content="{}")]))
            return nodes

        # Get keys (optionally sorted)
        keys = sorted(obj.keys()) if self.options.sort_keys else list(obj.keys())

        # Check if we should flatten single-key objects
        if self.options.flatten_single_keys and len(keys) == 1:
            key = keys[0]
            value = obj[key]
            # Only flatten if the value is not a primitive
            if isinstance(value, (dict, list)):
                # Add heading for the single key and convert its value
                heading_level = min(depth + 1, self.options.max_heading_depth)
                nodes.append(Heading(level=heading_level, content=[Text(content=key)]))
                nodes.extend(self._convert_value(value, depth + 1, key))
                return nodes

        # Check if this object contains only primitive values
        # If so, render as a list with bold keys
        all_primitives = all(
            isinstance(obj[k], (str, int, float, bool, datetime.datetime, datetime.date, datetime.time)) for k in keys
        )

        if all_primitives:
            # Render as definition list (bullet list with bold keys)
            list_items: list[ListItem] = []
            for key in keys:
                value = obj[key]
                # Format: **key**: value
                value_nodes = self._convert_value(value, depth + 1, key)
                # Create list item with bold key
                paragraph = Paragraph(
                    content=[
                        Strong(content=[Text(content=key)]),
                        Text(content=": "),
                    ]
                )
                item_content: list[Node] = [paragraph]
                # Add value inline if it's a paragraph
                if value_nodes and isinstance(value_nodes[0], Paragraph):
                    paragraph.content.extend(value_nodes[0].content)
                else:
                    item_content.extend(value_nodes)

                list_items.append(ListItem(children=item_content))

            if list_items:
                nodes.append(List(items=list_items, ordered=False))
            return nodes

        # Complex object with nested structures - use headings
        for key in keys:
            value = obj[key]

            # Use heading if depth allows, otherwise use definition list style
            if depth < self.options.max_heading_depth:
                heading_level = min(depth + 1, 6)
                nodes.append(Heading(level=heading_level, content=[Text(content=key)]))
                nodes.extend(self._convert_value(value, depth + 1, key))
            else:
                # Too deep for headings - use bold key style in a list
                value_nodes = self._convert_value(value, depth + 1, key)
                paragraph = Paragraph(
                    content=[
                        Strong(content=[Text(content=key)]),
                        Text(content=": "),
                    ]
                )
                nested_item_content: list[Node] = [paragraph]
                if value_nodes and isinstance(value_nodes[0], Paragraph):
                    paragraph.content.extend(value_nodes[0].content)
                else:
                    nested_item_content.extend(value_nodes)

                nodes.append(ListItem(children=nested_item_content))

        return nodes

    def _convert_array(self, arr: list[Any], depth: int, key: str | None = None) -> list[Node]:
        """Convert a TOML array to AST nodes.

        Parameters
        ----------
        arr : list
            TOML array to convert
        depth : int
            Current nesting depth
        key : str or None
            Key name for this array (if known)

        Returns
        -------
        list[Node]
            List of AST nodes representing this array

        """
        nodes: list[Node] = []

        # Handle empty array
        if not arr:
            nodes.append(Paragraph(content=[Text(content="[]")]))
            return nodes

        # Check if this is an array of objects with consistent keys (table candidate)
        if len(arr) >= self.options.array_as_table_threshold and self._is_table_candidate(arr):
            table = self._array_to_table(arr)
            if table:
                nodes.append(table)
                return nodes

        # Convert as list
        list_items: list[ListItem] = []
        for item in arr:
            item_nodes = self._convert_value(item, depth + 1)
            # Wrap in list item
            list_items.append(ListItem(children=item_nodes))

        if list_items:
            nodes.append(List(items=list_items, ordered=False))

        return nodes

    def _is_table_candidate(self, arr: list[Any]) -> bool:
        """Check if array should be rendered as a table.

        Parameters
        ----------
        arr : list
            Array to check

        Returns
        -------
        bool
            True if array should be rendered as table

        """
        # Must be array of dicts
        if not all(isinstance(item, dict) for item in arr):
            return False

        # Must have at least one item
        if not arr:
            return False

        # Get all keys from first item
        first_keys = set(arr[0].keys())

        # Check if all items have same keys
        for item in arr[1:]:
            if set(item.keys()) != first_keys:
                return False

        # Must have at least one key
        return len(first_keys) > 0

    def _array_to_table(self, arr: list[dict[str, Any]]) -> Table | None:
        """Convert array of objects to a table.

        Parameters
        ----------
        arr : list[dict]
            Array of dictionaries to convert

        Returns
        -------
        Table or None
            Table node, or None if conversion fails

        """
        if not arr:
            return None

        # Get column names from first item
        columns = list(arr[0].keys())
        if self.options.sort_keys:
            columns = sorted(columns)

        # Create header row
        header_cells = [TableCell(content=[Text(content=str(col))]) for col in columns]
        header = TableRow(cells=header_cells)

        # Create data rows
        rows: list[TableRow] = []
        for item in arr:
            cells = []
            for col in columns:
                value = item.get(col)
                # Convert value to string
                # Note: TOML doesn't support null
                if value is None:
                    text = ""
                elif isinstance(value, bool):
                    text = "true" if value else "false"
                elif isinstance(value, (int, float)):
                    if self.options.pretty_format_numbers and isinstance(value, int) and abs(value) >= 1000:
                        text = f"{value:,}"
                    else:
                        text = str(value)
                elif isinstance(value, str):
                    text = value
                elif isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                    text = value.isoformat()
                else:
                    # Complex value - convert to TOML if possible
                    try:
                        import tomli_w

                        text = tomli_w.dumps({"_": value}).replace("_ = ", "").strip()
                    except Exception:
                        text = str(value)

                cells.append(TableCell(content=[Text(content=text)]))

            rows.append(TableRow(cells=cells))

        return Table(header=header, rows=rows)

    def extract_metadata(self, data: Any) -> DocumentMetadata:
        """Extract metadata from TOML structure.

        Parameters
        ----------
        data : Any
            TOML data structure

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Try to extract title from common keys
        if isinstance(data, dict):
            for key in ["title", "name", "label", "header"]:
                if key in data and isinstance(data[key], str):
                    metadata.title = data[key]
                    break

        return metadata


def _detect_toml_content(content: bytes) -> bool:
    """Detect if content is TOML.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be TOML

    """
    try:
        content_str = content.decode("utf-8", errors="ignore").strip()
        if not content_str:
            return False

        # Try to parse as TOML
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            try:
                import tomli as tomllib
            except ImportError:
                return False

        tomllib.loads(content_str)
        return True
    except Exception:
        return False


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="toml",
    extensions=[".toml"],
    mime_types=["application/toml", "text/toml"],
    magic_bytes=[],
    content_detector=_detect_toml_content,
    parser_class=TomlParser,
    renderer_class="all2md.renderers.toml.TomlRenderer",
    renders_as_string=True,
    parser_required_packages=[("tomli-w", "tomli_w", ">=1.0.0")],
    renderer_required_packages=[("tomli-w", "tomli_w", ">=1.0.0")],
    import_error_message="TOML conversion requires tomli and tomli-w (pip install tomli tomli-w)",
    parser_options_class=TomlParserOptions,
    renderer_options_class="all2md.options.toml.TomlRendererOptions",
    description="Convert TOML structures to/from readable documents with tables and lists",
    priority=10,
)
