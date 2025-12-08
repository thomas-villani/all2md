#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/xlsx.py
"""Configuration options for XLSX (Excel) parsing.

This module defines options for parsing Excel spreadsheet files.
"""

from __future__ import annotations

from dataclasses import dataclass

from all2md.options.common import SpreadsheetParserOptions


@dataclass(frozen=True)
class XlsxOptions(SpreadsheetParserOptions):
    """Configuration options for XLSX spreadsheet conversion.

    This dataclass inherits all spreadsheet options from SpreadsheetParserOptions.
    Currently, XLSX has no format-specific options beyond the base spreadsheet options.

    See SpreadsheetParserOptions for complete documentation of available options.

    """

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
