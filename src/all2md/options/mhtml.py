#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/options/mhtml.py
"""Configuration options for MHTML parsing.

This module defines options for parsing MHTML (MIME HTML) web archives.
"""

from __future__ import annotations

from dataclasses import dataclass

from all2md.options.html import HtmlOptions


@dataclass(frozen=True)
class MhtmlOptions(HtmlOptions):
    """Configuration options for MHTML-to-Markdown conversion.

    This dataclass contains settings specific to MHTML file processing,
    primarily for handling embedded assets like images and local file security.

    Parameters
    ----------
    Inherited from HtmlOptions

    """

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
