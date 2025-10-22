#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/csv.py
"""Configuration options for CSV parsing.

This module defines options for parsing CSV files with customizable dialects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import HeaderCaseOption
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class CsvOptions(BaseParserOptions):
    r"""Configuration options for CSV/TSV conversion.

    This dataclass contains settings specific to delimiter-separated value
    file processing, including dialect detection and data limits.

    Parameters
    ----------
    detect_csv_dialect : bool, default True
        Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set).
    delimiter : str | None, default None
        Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|').
        When set, disables dialect detection.
    quote_char : str | None, default None
        Override quote character (e.g., '"', "'").
        When set, uses this for quoting.
    escape_char : str | None, default None
        Override escape character (e.g., '\\\\').
        When set, uses this for escaping.
    double_quote : bool | None, default None
        Enable/disable double quoting (two quote chars = one literal quote).
        When set, overrides dialect's doublequote setting.
    has_header : bool, default True
        Whether the first row contains column headers.
        When False, generates generic headers (Column 1, Column 2, etc.).
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    header_case : str, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    skip_empty_rows : bool, default True
        Whether to skip completely empty rows.
    strip_whitespace : bool, default False
        Whether to strip leading/trailing whitespace from all cells.
    dialect_sample_size : int, default 4096
        Number of bytes to sample for csv.Sniffer dialect detection.
        Larger values may improve detection for heavily columnated files
        but increase memory usage during detection.

    """

    detect_csv_dialect: bool = field(
        default=True,
        metadata={
            "help": "Enable csv.Sniffer-based dialect detection (ignored if delimiter is set)",
            "cli_name": "no-detect-csv-dialect",
            "importance": "advanced",
        },
    )
    dialect_sample_size: int = field(
        default=4096,
        metadata={"help": "Number of bytes to sample for dialect detection", "type": int, "importance": "advanced"},
    )
    delimiter: str | None = field(
        default=None, metadata={"help": "Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|')", "importance": "core"}
    )
    quote_char: str | None = field(
        default=None, metadata={"help": "Override quote character (e.g., '\"', \"'\")", "importance": "advanced"}
    )
    escape_char: str | None = field(
        default=None, metadata={"help": "Override escape character (e.g., '\\\\')", "importance": "advanced"}
    )
    double_quote: bool | None = field(
        default=None,
        metadata={
            "help": "Enable/disable double quoting (two quote chars = one literal quote)",
            "importance": "advanced",
        },
    )
    has_header: bool = field(
        default=True,
        metadata={
            "help": "Whether first row contains column headers",
            "cli_name": "no-has-header",
            "importance": "core",
        },
    )
    max_rows: int | None = field(
        default=None,
        metadata={"help": "Maximum rows per table (None = unlimited)", "type": int, "importance": "advanced"},
    )
    max_cols: int | None = field(
        default=None,
        metadata={"help": "Maximum columns per table (None = unlimited)", "type": int, "importance": "advanced"},
    )
    truncation_indicator: str = field(
        default="...", metadata={"help": "Note appended when rows/columns are truncated", "importance": "advanced"}
    )

    header_case: HeaderCaseOption = field(
        default="preserve",
        metadata={
            "help": "Transform header case: preserve, title, upper, or lower",
            "choices": ["preserve", "title", "upper", "lower"],
            "importance": "core",
        },
    )
    skip_empty_rows: bool = field(
        default=True,
        metadata={"help": "Skip completely empty rows", "cli_name": "no-skip-empty-rows", "importance": "core"},
    )
    strip_whitespace: bool = field(
        default=False, metadata={"help": "Strip leading/trailing whitespace from all cells", "importance": "core"}
    )


@dataclass(frozen=True)
class CsvRendererOptions(BaseRendererOptions):
    r"""Configuration options for CSV rendering from AST.

    This dataclass contains settings for rendering AST table nodes to CSV format,
    including table selection, multi-table handling, and CSV dialect options.

    Parameters
    ----------
    table_index : int or None, default=0
        Which table to export (0-indexed). Use 0 for first table, 1 for second, etc.
        Set to None to export all tables.
    table_heading : str or None, default=None
        Select table that appears after a heading matching this text (case-insensitive substring).
        Takes precedence over table_index if both are specified.
        Example: "Results" will find first table after any heading containing "results".
    multi_table_mode : Literal["first", "all", "error"], default="first"
        How to handle documents with multiple tables:
        - "first": Export only the first table (default, safest)
        - "all": Concatenate all tables with separator
        - "error": Raise RenderingError if multiple tables found
    table_separator : str, default="\\n\\n"
        Separator text between tables when multi_table_mode="all".
        Only used when multiple tables are exported to a single file.
    delimiter : str, default=","
        CSV field delimiter character. Common values: "," (comma), "\\t" (tab), ";" (semicolon).
    quoting : Literal["minimal", "all", "nonnumeric", "none"], default="minimal"
        CSV quoting style (maps to csv.QUOTE_* constants):
        - "minimal": Quote fields only when needed (special chars present)
        - "all": Quote all fields
        - "nonnumeric": Quote all non-numeric fields
        - "none": Never quote (escape special chars instead)
    include_table_headings : bool, default=False
        When multi_table_mode="all", include the document heading before each table
        as a comment line (prefixed with #). Useful for identifying tables in combined output.
    line_terminator : str, default="\\n"
        Line ending style. Use "\\n" for Unix/Mac, "\\r\\n" for Windows.
    handle_merged_cells : Literal["repeat", "blank", "placeholder"], default="repeat"
        How to handle merged cells (cells with colspan > 1 or rowspan > 1):
        - "repeat": Repeat the cell value across all merged positions
        - "blank": Only the first cell has value, rest are empty
        - "placeholder": Use "[merged]" marker in non-first cells
    quote_char : str, default='"'
        Character used for quoting fields when needed.
    escape_char : str or None, default=None
        Character used for escaping when quoting="none". If None, doubling is used.
    include_bom : bool, default=False
        Include UTF-8 BOM (byte order mark) at start of file.
        Useful for Excel compatibility with UTF-8 files.

    Examples
    --------
    Extract first table to CSV:
        >>> from all2md.renderers.csv import CsvRenderer
        >>> from all2md.options.csv import CsvRendererOptions
        >>> options = CsvRendererOptions()
        >>> renderer = CsvRenderer(options)

    Extract table by heading:
        >>> options = CsvRendererOptions(table_heading="Results")
        >>> renderer = CsvRenderer(options)

    Export all tables:
        >>> options = CsvRendererOptions(
        ...     multi_table_mode="all",
        ...     include_table_headings=True
        ... )

    """

    table_index: int | None = field(
        default=0,
        metadata={
            "help": "Which table to export (0-indexed, None = all tables)",
            "type": int,
            "importance": "core",
        },
    )
    table_heading: str | None = field(
        default=None,
        metadata={
            "help": "Select table after heading matching this text (case-insensitive)",
            "importance": "core",
        },
    )
    multi_table_mode: Literal["first", "all", "error"] = field(
        default="first",
        metadata={
            "help": "How to handle multiple tables: first, all, or error",
            "choices": ["first", "all", "error"],
            "importance": "core",
        },
    )
    table_separator: str = field(
        default="\n\n",
        metadata={"help": "Separator between tables when multi_table_mode='all'", "importance": "advanced"},
    )
    delimiter: str = field(
        default=",",
        metadata={"help": "CSV field delimiter (e.g., ',', '\\t', ';')", "importance": "core"},
    )
    quoting: Literal["minimal", "all", "nonnumeric", "none"] = field(
        default="minimal",
        metadata={
            "help": "CSV quoting style",
            "choices": ["minimal", "all", "nonnumeric", "none"],
            "importance": "core",
        },
    )
    include_table_headings: bool = field(
        default=False,
        metadata={
            "help": "Include heading comments before tables in multi-table mode",
            "importance": "advanced",
        },
    )
    line_terminator: str = field(
        default="\n",
        metadata={"help": "Line ending style ('\\n' or '\\r\\n')", "importance": "advanced"},
    )
    handle_merged_cells: Literal["repeat", "blank", "placeholder"] = field(
        default="repeat",
        metadata={
            "help": "How to handle merged cells",
            "choices": ["repeat", "blank", "placeholder"],
            "importance": "advanced",
        },
    )
    quote_char: str = field(
        default='"',
        metadata={"help": "Character used for quoting fields", "importance": "advanced"},
    )
    escape_char: str | None = field(
        default=None,
        metadata={"help": "Character used for escaping (None uses doubling)", "importance": "advanced"},
    )
    include_bom: bool = field(
        default=False,
        metadata={"help": "Include UTF-8 BOM for Excel compatibility", "importance": "advanced"},
    )
