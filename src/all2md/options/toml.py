#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/toml.py
"""Options for TOML parsing and rendering.

This module defines configuration options for converting between TOML and AST.
The parser converts TOML structures to readable document format, while the
renderer extracts tables and structured data from documents back to TOML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class TomlParserOptions(BaseParserOptions):
    """Configuration options for TOML to AST parsing.

    The parser converts TOML structures into human-readable document format:
    - Sections/tables become heading hierarchies
    - Arrays of tables become markdown tables
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
        If True, add metadata hints about the original TOML types (useful for
        round-trip conversion or debugging).
    pretty_format_numbers : bool, default = True
        If True, format large numbers with thousand separators for readability.
    sort_keys : bool, default = False
        If True, sort object keys alphabetically when rendering.
    literal_block : bool, default = False
        If True, render TOML as a literal code block instead of converting to
        structured document format. Useful when you want to preserve the original
        TOML formatting or show it as example code.

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
        metadata={"help": "Add metadata hints about original TOML types", "importance": "advanced"},
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
class TomlRendererOptions(BaseRendererOptions):
    """Configuration options for AST to TOML rendering.

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
        If True, automatically detect and convert types (numbers, booleans).
        If False, all values remain as strings. Note: TOML does not support null.
    table_heading_keys : bool, default = True
        If True, use the preceding heading text as the key name for each table.
        If False, tables are stored in a flat array.
    flatten_single_table : bool, default = False
        If True and only one table is found, return the array directly instead
        of wrapping it in an object with a key.
    include_table_metadata : bool, default = False
        If True, include metadata about table position, source heading, etc.
    sort_keys : bool, default = False
        If True, sort keys in output TOML.

    """

    extract_mode: Literal["tables", "lists", "both"] = field(
        default="tables",
        metadata={"help": "What to extract: tables, lists, or both", "importance": "core"},
    )
    type_inference: bool = field(
        default=True,
        metadata={"help": "Auto-detect types (numbers, booleans)", "importance": "core"},
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
    sort_keys: bool = field(
        default=False,
        metadata={"help": "Sort keys in output TOML", "importance": "core"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
