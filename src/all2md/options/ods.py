#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ods.py
"""Configuration options for ODS (OpenDocument Spreadsheet) parsing.

This module defines options for parsing ODS spreadsheet files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.common import SpreadsheetParserOptions


@dataclass(frozen=True)
class OdsSpreadsheetOptions(SpreadsheetParserOptions):
    """Configuration options for ODS spreadsheet conversion.

    This dataclass inherits all spreadsheet options from SpreadsheetParserOptions
    and adds ODS-specific options.

    Parameters
    ----------
    has_header : bool, default True
        Whether the first row contains column headers.

    See SpreadsheetParserOptions for complete documentation of inherited options.

    """

    has_header: bool = field(
        default=True,
        metadata={
            "help": "Whether the first row contains column headers",
            "cli_name": "no-has-header",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
