#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/csv.py
"""Configuration options for CSV parsing.

This module defines options for parsing CSV files with customizable dialects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from all2md.constants import HeaderCaseOption
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class CsvOptions(BaseParserOptions):
    r"""Configuration options for CSV/TSV conversion.

    This dataclass contains settings specific to delimiter-separated value
    file processing, including dialect detection and data limits.

    Parameters
    ----------
    detect_csv_dialect : bool, default True
        Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set).
    csv_delimiter : str | None, default None
        Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|').
        When set, disables dialect detection.
    csv_quotechar : str | None, default None
        Override quote character (e.g., '"', "'").
        When set, uses this for quoting.
    csv_escapechar : str | None, default None
        Override escape character (e.g., '\\\\').
        When set, uses this for escaping.
    csv_doublequote : bool | None, default None
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
            "help": "Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set)",
            "cli_name": "no-detect-csv-dialect",
            "importance": "advanced"
        }
    )
    dialect_sample_size: int = field(
        default=4096,
        metadata={
            "help": "Number of bytes to sample for dialect detection",
            "type": int,
            "importance": "advanced"
        }
    )
    csv_delimiter: Optional[str] = field(
        default=None,
        metadata={
            "help": "Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|')",
            "importance": "core"
        }
    )
    csv_quotechar: Optional[str] = field(
        default=None,
        metadata={
            "help": "Override quote character (e.g., '\"', \"'\")",
            "importance": "advanced"
        }
    )
    csv_escapechar: Optional[str] = field(
        default=None,
        metadata={
            "help": "Override escape character (e.g., '\\\\')",
            "importance": "advanced"
        }
    )
    csv_doublequote: Optional[bool] = field(
        default=None,
        metadata={
            "help": "Enable/disable double quoting (two quote chars = one literal quote)",
            "importance": "advanced"
        }
    )
    has_header: bool = field(
        default=True,
        metadata={
            "help": "Whether first row contains column headers",
            "cli_name": "no-has-header",
            "importance": "core"
        }
    )
    max_rows: Optional[int] = field(
        default=None,
        metadata={
            "help": "Maximum rows per table (None = unlimited)",
            "type": int,
            "importance": "advanced"
        }
    )
    max_cols: Optional[int] = field(
        default=None,
        metadata={
            "help": "Maximum columns per table (None = unlimited)",
            "type": int,
            "importance": "advanced"
        }
    )
    truncation_indicator: str = field(
        default="...",
        metadata={
            "help": "Note appended when rows/columns are truncated",
            "importance": "advanced"
        }
    )

    header_case: HeaderCaseOption = field(
        default="preserve",
        metadata={
            "help": "Transform header case: preserve, title, upper, or lower",
            "choices": ["preserve", "title", "upper", "lower"],
            "importance": "core"
        }
    )
    skip_empty_rows: bool = field(
        default=True,
        metadata={
            "help": "Skip completely empty rows",
            "cli_name": "no-skip-empty-rows",
            "importance": "core"
        }
    )
    strip_whitespace: bool = field(
        default=False,
        metadata={
            "help": "Strip leading/trailing whitespace from all cells",
            "importance": "core"
        }
    )
