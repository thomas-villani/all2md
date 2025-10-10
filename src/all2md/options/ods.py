#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ods.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class OdsSpreadsheetOptions(BaseParserOptions):
    """Configuration options for ODS spreadsheet conversion.

    This dataclass contains settings specific to OpenDocument Spreadsheet
    file processing, including sheet selection and data limits.

    Parameters
    ----------
    sheets : list[str] | str | None, default None
        List of exact sheet names to include or a regex pattern.
        If None, includes all sheets.
    include_sheet_titles : bool, default True
        Prepend each sheet with a '## {sheet_name}' heading.
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    preserve_newlines_in_cells : bool, default False
        Preserve line breaks within cells as <br> tags.
    trim_empty : str, default "trailing"
        Trim empty rows/columns: none, leading, trailing, or both.
    header_case : str, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    has_header : bool, default True
        Whether the first row contains column headers.
    chart_mode : {"data", "skip"}, default "skip"
        How to handle embedded charts:
        - "data": Extract chart data as markdown tables
        - "skip": Ignore charts entirely
    merged_cell_mode : {"spans", "flatten", "skip"}, default "flatten"
        How to handle merged cells:
        - "spans": Use colspan/rowspan in AST (future enhancement, currently behaves like "flatten")
        - "flatten": Replace merged followers with empty strings (current behavior)
        - "skip": Skip merged cell detection entirely

    """

    sheets: Union[list[str], str, None] = None
    include_sheet_titles: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."
    has_header: bool = True

    preserve_newlines_in_cells: bool = field(
        default=False,
        metadata={"help": "Preserve line breaks within cells as <br> tags"}
    )
    trim_empty: str = field(
        default="trailing",
        metadata={"help": "Trim empty rows/columns: none, leading, trailing, or both"}
    )
    header_case: str = field(
        default="preserve",
        metadata={"help": "Transform header case: preserve, title, upper, or lower"}
    )
    chart_mode: Literal["data", "skip"] = field(
        default="skip",
        metadata={
            "help": "Chart handling mode: 'data' (extract as tables) or 'skip' (ignore charts)",
            "choices": ["data", "skip"]
        }
    )
    merged_cell_mode: Literal["spans", "flatten", "skip"] = field(
        default="flatten",
        metadata={
            "help": "Merged cell handling: 'spans' (use colspan/rowspan), 'flatten' (empty strings), or 'skip'",
            "choices": ["spans", "flatten", "skip"]
        }
    )
