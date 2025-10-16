#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/odp.py
"""Configuration options for ODP (OpenDocument Presentation) parsing.

This module defines options for parsing ODP presentation files.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.common import PaginatedParserOptions


@dataclass(frozen=True)
class OdpOptions(PaginatedParserOptions):
    """Configuration options for ODP-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Presentation (ODP)
    processing, including slide selection, numbering, and notes.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    include_slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    page_separator_template : str, default "---"
        Template for slide separators. Supports placeholders: {page_num}, {total_pages}.
    slides : str or None, default None
        Slide selection (e.g., "1,3-5,8" for slides 1, 3-5, and 8).

    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables",
            "importance": "core",
        },
    )
    include_slide_numbers: bool = field(
        default=False, metadata={"help": "Include slide numbers in output", "importance": "core"}
    )
    include_notes: bool = field(
        default=True,
        metadata={"help": "Include speaker notes from slides", "cli_name": "no-include-notes", "importance": "core"},
    )
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)", "importance": "core"},
    )
