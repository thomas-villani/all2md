#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/yaml.py
"""YAML to AST converter.

This module provides intelligent conversion from YAML structures to readable
document format. By default, it transforms the structure into a hierarchical
document with headings, tables, and lists. Alternatively, it can render YAML
as a literal code block (via the `literal_block` option).

Examples
--------
**Smart Conversion (default):**

Input YAML::

    server:
      host: localhost
      port: 8080
    users:
      - name: Alice
        role: admin
      - name: Bob
        role: user

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

Input YAML (same as above)

Output (as markdown):

.. code-block:: yaml

    server:
      host: localhost
      port: 8080
    users:
      - name: Alice
        role: admin
      - name: Bob
        role: user

"""

from __future__ import annotations

import datetime
import logging
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
from all2md.constants import DEPS_YAML
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.yaml import YamlParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class YamlParser(BaseParser):
    r"""Convert YAML structures to AST representation.

    This parser creates a readable document from YAML by converting:
    - Objects/dicts → heading hierarchies
    - Arrays of objects → tables
    - Arrays of primitives → lists
    - Nested structures → subsections

    Parameters
    ----------
    options : YamlParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = YamlParser()
        >>> doc = parser.parse('name: John\\nage: 30')

    With options:

        >>> options = YamlParserOptions(max_heading_depth=3, sort_keys=True)
        >>> parser = YamlParser(options)
        >>> doc = parser.parse(yaml_file_path)

    """

    def __init__(self, options: YamlParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the YAML parser with options and progress callback."""
        BaseParser._validate_options_type(options, YamlParserOptions, "yaml")
        options = options or YamlParserOptions()
        super().__init__(options, progress_callback)
        self.options: YamlParserOptions = options

    @requires_dependencies("yaml", DEPS_YAML)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse YAML input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            YAML input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw YAML bytes
            - YAML string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        self._emit_progress("started", "Parsing YAML", current=0, total=100)

        try:
            # Load content using BaseParser helper
            content = self._load_text_content(input_data)

            # Import yaml (lazy loaded via decorator)
            import yaml

            # Check if we should render as literal code block
            if self.options.literal_block:
                self._emit_progress("completed", "YAML wrapped as code block", current=100, total=100)

                # Optionally pretty-print the YAML
                try:
                    data = yaml.safe_load(content)
                    # Re-serialize with formatting
                    formatted_yaml = yaml.dump(
                        data, default_flow_style=False, allow_unicode=True, sort_keys=self.options.sort_keys
                    )
                except yaml.YAMLError:
                    # If invalid YAML, just use the raw content
                    formatted_yaml = content

                # Create code block
                code_block = CodeBlock(content=formatted_yaml, language="yaml")
                metadata = DocumentMetadata()
                return Document(children=[code_block], metadata=metadata.to_dict())

            self._emit_progress("parsing", "Parsing YAML structure", current=30, total=100)

            # Parse YAML
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ParsingError(f"Invalid YAML: {e}") from e

            self._emit_progress("converting", "Converting to document structure", current=60, total=100)

            # Convert to AST
            children = self._convert_value(data, depth=0)

            self._emit_progress("completed", "YAML parsing completed", current=100, total=100)

            # Create document
            metadata = self.extract_metadata(data)
            return Document(children=children, metadata=metadata.to_dict())

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Failed to parse YAML: {e}") from e

    def _convert_value(self, value: Any, depth: int, key: str | None = None) -> list[Node]:
        """Convert a YAML value to AST nodes.

        Parameters
        ----------
        value : Any
            YAML value to convert
        depth : int
            Current nesting depth
        key : str or None
            Key name for this value (if part of an object)

        Returns
        -------
        list[Node]
            List of AST nodes representing this value

        """
        if value is None:
            return [Paragraph(content=[Text(content="null")])]

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

        # YAML-specific types
        if isinstance(value, datetime.datetime):
            return [Paragraph(content=[Text(content=value.isoformat())])]
        if isinstance(value, datetime.date):
            return [Paragraph(content=[Text(content=value.isoformat())])]

        if isinstance(value, list):
            return self._convert_array(value, depth, key)

        if isinstance(value, dict):
            return self._convert_object(value, depth)

        # Fallback for unknown types
        return [Paragraph(content=[Text(content=str(value))])]

    def _convert_object(self, obj: dict[str, Any], depth: int) -> list[Node]:
        """Convert a YAML object to AST nodes.

        Parameters
        ----------
        obj : dict
            YAML object to convert
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
            isinstance(obj[k], (str, int, float, bool, type(None), datetime.datetime, datetime.date)) for k in keys
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
        """Convert a YAML array to AST nodes.

        Parameters
        ----------
        arr : list
            YAML array to convert
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
                elif isinstance(value, (datetime.datetime, datetime.date)):
                    text = value.isoformat()
                else:
                    # Complex value - convert to YAML
                    import yaml

                    text = yaml.dump(value, default_flow_style=True, allow_unicode=True).strip()

                cells.append(TableCell(content=[Text(content=text)]))

            rows.append(TableRow(cells=cells))

        return Table(header=header, rows=rows)

    def extract_metadata(self, data: Any) -> DocumentMetadata:
        """Extract metadata from YAML structure.

        Parameters
        ----------
        data : Any
            YAML data structure

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


def _detect_yaml_content(content: bytes) -> bool:
    """Detect if content is YAML.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be YAML

    """
    try:
        content_str = content.decode("utf-8", errors="ignore").strip()
        if not content_str:
            return False

        # Check for YAML-specific patterns before attempting to parse
        # This prevents false positives for content that happens to be valid YAML
        # but isn't actually intended as YAML (e.g., CSV, plain text)
        lines = [line.rstrip() for line in content_str.split("\n") if line.strip()]

        if not lines:
            return False

        # Look for YAML-specific syntax patterns
        yaml_indicators = 0

        for line in lines:
            stripped = line.lstrip()
            # Key-value pairs with colon (e.g., "key: value")
            if ": " in line or line.endswith(":"):
                yaml_indicators += 1
            # List items (e.g., "- item")
            elif stripped.startswith("- "):
                yaml_indicators += 1
            # YAML document markers
            elif stripped in ("---", "..."):
                yaml_indicators += 2

        # Require at least 2 YAML indicators or 1 if it's a document marker
        if yaml_indicators < 2:
            return False

        # Now try to parse as YAML to validate structure
        import yaml

        result = yaml.safe_load(content_str)
        # Reject if result is just a plain string or number
        # (indicates content is not structured YAML)
        if isinstance(result, (str, int, float, bool)) or result is None:
            return False

        return True
    except (yaml.YAMLError, UnicodeDecodeError):
        return False
    except ImportError:
        # yaml not installed, can't detect
        return False


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="yaml",
    extensions=[".yaml", ".yml"],
    mime_types=["application/x-yaml", "text/yaml", "text/x-yaml"],
    magic_bytes=[],
    content_detector=_detect_yaml_content,
    parser_class=YamlParser,
    renderer_class="all2md.renderers.yaml.YamlRenderer",
    renders_as_string=True,
    parser_required_packages=[("pyyaml", "yaml", ">=6.0")],
    renderer_required_packages=[("pyyaml", "yaml", ">=6.0")],
    import_error_message="YAML conversion requires PyYAML (pip install pyyaml)",
    parser_options_class=YamlParserOptions,
    renderer_options_class="all2md.options.yaml.YamlRendererOptions",
    description="Convert YAML structures to/from readable documents with tables and lists",
    priority=5,
)
