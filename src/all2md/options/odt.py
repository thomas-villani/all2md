#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/odt.py
from __future__ import annotations

from dataclasses import dataclass, field

from all2md import BaseParserOptions


@dataclass(frozen=True)
class OdtOptions(BaseParserOptions):
    """Configuration options for ODT-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Text (ODT)
    processing, including table preservation, footnotes, and comments.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    preserve_comments : bool, default False
        Whether to include document comments in output.
    include_footnotes : bool, default True
        Whether to include footnotes in output.
    include_endnotes : bool, default True
        Whether to include endnotes in output.

    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )
    preserve_comments: bool = field(
        default=False,
        metadata={"help": "Include document comments in output"}
    )
    include_footnotes: bool = field(
        default=True,
        metadata={
            "help": "Include footnotes in output",
            "cli_name": "no-include-footnotes"
        }
    )
    include_endnotes: bool = field(
        default=True,
        metadata={
            "help": "Include endnotes in output",
            "cli_name": "no-include-endnotes"
        }
    )
