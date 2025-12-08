#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/options/webarchive.py
"""Configuration options for Safari WebArchive parsing.

This module defines options for parsing Safari WebArchive (.webarchive) files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.html import HtmlOptions


@dataclass(frozen=True)
class WebArchiveOptions(HtmlOptions):
    """Configuration options for WebArchive-to-Markdown conversion.

    This dataclass contains settings specific to Safari WebArchive file processing,
    including options for handling embedded resources and nested frames.

    Parameters
    ----------
    extract_subresources : bool, default False
        Whether to extract embedded resources (images, CSS, JS) from WebSubresources.
        When True, resources are saved to attachment_output_dir if configured.
    handle_subframes : bool, default True
        Whether to process nested iframe content from WebSubframeArchives.
        When True, content from nested frames is included in the output.

    Examples
    --------
    Basic conversion:
        >>> options = WebArchiveOptions()

    Extract all embedded resources:
        >>> options = WebArchiveOptions(
        ...     extract_subresources=True,
        ...     attachment_output_dir="./extracted"
        ... )

    Ignore nested frames:
        >>> options = WebArchiveOptions(handle_subframes=False)

    Notes
    -----
    Inherits all options from HtmlOptions, including:
    - extract_title
    - strip_dangerous_elements
    - attachment_mode
    - network security settings
    - local file access settings

    """

    extract_subresources: bool = field(
        default=False,
        metadata={
            "help": "Extract embedded resources (images, CSS, JS) from WebSubresources",
            "importance": "core",
        },
    )
    handle_subframes: bool = field(
        default=True,
        metadata={
            "help": "Process nested iframe content from WebSubframeArchives",
            "cli_name": "no-handle-subframes",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
