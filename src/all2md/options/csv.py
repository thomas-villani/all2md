#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/csv.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from all2md import BaseParserOptions


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

    """

    detect_csv_dialect: bool = True
    csv_delimiter: Optional[str] = None
    has_header: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."

    header_case: str = field(
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
