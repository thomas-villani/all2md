#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/csv.py
"""Configuration options for CSV parsing.

This module defines options for parsing CSV files with customizable dialects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal

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

    detect_csv_dialect: bool = True
    dialect_sample_size: int = 4096
    csv_delimiter: Optional[str] = None
    csv_quotechar: Optional[str] = None
    csv_escapechar: Optional[str] = None
    csv_doublequote: Optional[bool] = None
    has_header: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."

    header_case: HeaderCaseOption = field(
        default="preserve",
        metadata={"help": "Transform header case: preserve, title, upper, or lower"}
    )
    skip_empty_rows: bool = field(
        default=True,
        metadata={"help": "Skip completely empty rows"}
    )
    strip_whitespace: bool = field(
        default=False,
        metadata={"help": "Strip leading/trailing whitespace from all cells"}
    )
