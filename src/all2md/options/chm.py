#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/chm.py
from __future__ import annotations

from dataclasses import dataclass, field

from all2md import BaseParserOptions, HtmlOptions


@dataclass(frozen=True)
class ChmOptions(BaseParserOptions):
    """Configuration options for CHM-to-Markdown conversion.

    This dataclass contains settings specific to Microsoft Compiled HTML Help (CHM)
    document processing, including page handling, table of contents generation, and
    HTML parsing configuration.

    Parameters
    ----------
    include_toc : bool, default True
        Whether to generate and prepend a Markdown Table of Contents from the CHM's
        internal TOC structure at the start of the document.
    merge_pages : bool, default True
        Whether to merge all pages into a single continuous document. If False,
        pages are separated with thematic breaks.
    html_options : HtmlOptions or None, default None
        Options for parsing HTML content within the CHM file. If None, uses default
        HTML parsing options.

    """

    include_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate and prepend a Markdown Table of Contents from CHM TOC",
            "cli_name": "no-include-toc"
        }
    )
    merge_pages: bool = field(
        default=True,
        metadata={
            "help": "Merge all pages into a single continuous document",
            "cli_name": "no-merge-pages"
        }
    )

    html_options: HtmlOptions | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Special field, handled separately
    )
