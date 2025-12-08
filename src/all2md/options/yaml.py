#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/yaml.py
"""Options for YAML parsing and rendering.

This module defines configuration options for converting between YAML and AST.
The parser converts YAML structures to readable document format, while the
renderer extracts tables and structured data from documents back to YAML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class YamlParserOptions(BaseParserOptions):
    """Configuration options for YAML to AST parsing.

    The parser converts YAML structures into human-readable document format:
    - Objects/dicts become heading hierarchies
    - Arrays of objects become tables
    - Arrays of primitives become lists
    - Nested structures become subsections

    Parameters
    ----------
    max_heading_depth : int, default = 6
        Maximum nesting depth for headings. Deeper structures will be rendered
        as definition lists or nested paragraphs instead of headings.
    array_as_table_threshold : int, default = 1
        Minimum number of items in an array to render it as a table (for arrays
        of objects with consistent keys). Set to 2 or higher to render single-item
        arrays as definition lists instead of tables.
    flatten_single_keys : bool, default = True
        If True, flatten objects that contain only a single key. For example,
        {"wrapper": {"actual_data": "value"}} becomes "# actual_data" instead of
        "# wrapper" > "## actual_data".
    include_type_hints : bool, default = False
        If True, add metadata hints about the original YAML types (useful for
        round-trip conversion or debugging).
    pretty_format_numbers : bool, default = True
        If True, format large numbers with thousand separators for readability.
    sort_keys : bool, default = False
        If True, sort object keys alphabetically when rendering.
    literal_block : bool, default = False
        If True, render YAML as a literal code block instead of converting to
        structured document format. Useful when you want to preserve the original
        YAML formatting or show it as example code.

    """

    literal_block: bool = field(
        default=False,
        metadata={"help": "Render as code block instead of structured document", "importance": "core"},
    )
    max_heading_depth: int = field(
        default=6,
        metadata={"help": "Maximum nesting depth for headings", "type": int, "importance": "advanced"},
    )
    array_as_table_threshold: int = field(
        default=1,
        metadata={"help": "Minimum items in array to render as table", "type": int, "importance": "advanced"},
    )
    flatten_single_keys: bool = field(
        default=True,
        metadata={"help": "Flatten objects with single keys", "importance": "advanced"},
    )
    include_type_hints: bool = field(
        default=False,
        metadata={"help": "Add metadata hints about original YAML types", "importance": "advanced"},
    )
    pretty_format_numbers: bool = field(
        default=True,
        metadata={"help": "Format large numbers with thousand separators", "importance": "core"},
    )
    sort_keys: bool = field(
        default=False,
        metadata={"help": "Sort object keys alphabetically", "importance": "core"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class YamlRendererOptions(BaseRendererOptions):
    """Configuration options for AST to YAML rendering.

    The renderer extracts structured data from markdown documents, primarily
    focusing on tables but optionally including lists and other elements.

    Parameters
    ----------
    extract_mode : Literal["tables", "lists", "both"], default = "tables"
        What to extract from the document:
        - "tables": Extract only tables as arrays of objects
        - "lists": Extract only lists as arrays
        - "both": Extract both tables and lists
    type_inference : bool, default = True
        If True, automatically detect and convert types (numbers, booleans, null).
        If False, all values remain as strings.
    table_heading_keys : bool, default = True
        If True, use the preceding heading text as the key name for each table.
        If False, tables are stored in a flat array.
    flatten_single_table : bool, default = False
        If True and only one table is found, return the array directly instead
        of wrapping it in an object with a key.
    include_table_metadata : bool, default = False
        If True, include metadata about table position, source heading, etc.
    indent : int | None, default = 2
        Number of spaces for YAML indentation. None for default YAML formatting.
    default_flow_style : bool | None, default = False
        YAML flow style (inline braces/brackets). False for block style (default),
        True for flow style, None for automatic selection.
    sort_keys : bool, default = False
        If True, sort keys in output YAML.

    """

    extract_mode: Literal["tables", "lists", "both"] = field(
        default="tables",
        metadata={"help": "What to extract: tables, lists, or both", "importance": "core"},
    )
    type_inference: bool = field(
        default=True,
        metadata={"help": "Auto-detect types (numbers, booleans, null)", "importance": "core"},
    )
    table_heading_keys: bool = field(
        default=True,
        metadata={"help": "Use preceding heading as key for each table", "importance": "core"},
    )
    flatten_single_table: bool = field(
        default=False,
        metadata={"help": "Return array directly if only one table found", "importance": "advanced"},
    )
    include_table_metadata: bool = field(
        default=False,
        metadata={"help": "Include metadata about table position and source", "importance": "advanced"},
    )
    indent: int | None = field(
        default=2,
        metadata={
            "help": "Number of spaces for YAML indentation (None for default)",
            "type": int,
            "importance": "core",
        },
    )
    default_flow_style: bool | None = field(
        default=False,
        metadata={"help": "YAML flow style (False=block, True=flow, None=auto)", "importance": "advanced"},
    )
    sort_keys: bool = field(
        default=False,
        metadata={"help": "Sort keys in output YAML", "importance": "core"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
