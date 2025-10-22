#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/odt.py
"""Configuration options for ODT (OpenDocument Text) parsing and rendering.

This module defines options for parsing and rendering ODT document files.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import AttachmentOptionsMixin, BaseParserOptions, BaseRendererOptions
from all2md.options.common import NetworkFetchOptions


@dataclass(frozen=True)
class OdtOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for ODT-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Text (ODT)
    processing, including table preservation, footnotes, and comments.
    Inherits attachment handling from AttachmentOptionsMixin for embedded images.

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
            "cli_name": "no-preserve-tables",
            "importance": "core",
        },
    )
    preserve_comments: bool = field(
        default=False, metadata={"help": "Include document comments in output", "importance": "advanced"}
    )
    include_footnotes: bool = field(
        default=True,
        metadata={"help": "Include footnotes in output", "cli_name": "no-include-footnotes", "importance": "core"},
    )
    include_endnotes: bool = field(
        default=True,
        metadata={"help": "Include endnotes in output", "cli_name": "no-include-endnotes", "importance": "core"},
    )


@dataclass(frozen=True)
class OdtRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to ODT format.

    This dataclass contains settings specific to OpenDocument Text generation,
    including fonts, styles, and formatting preferences.

    Parameters
    ----------
    default_font : str, default "Liberation Sans"
        Default font name for body text.
    default_font_size : int, default 11
        Default font size in points for body text.
    heading_font_sizes : dict[int, int] or None, default None
        Font sizes for heading levels 1-6. If None, uses built-in ODT heading styles.
    use_styles : bool, default True
        Whether to use built-in ODT styles vs direct formatting.
    code_font : str, default "Liberation Mono"
        Font name for code blocks and inline code.
    code_font_size : int, default 10
        Font size for code blocks and inline code.
    preserve_formatting : bool, default True
        Whether to preserve text formatting (bold, italic, etc.).
    template_path : str or None, default None
        Path to .odt template file. When specified, the renderer uses the template's
        styles instead of creating a blank document.
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security settings for fetching remote images.

    """

    default_font: str = field(
        default="Liberation Sans", metadata={"help": "Default font for body text", "importance": "core"}
    )
    default_font_size: int = field(
        default=11,
        metadata={"help": "Default font size in points", "type": int, "importance": "core"},
    )
    heading_font_sizes: dict[int, int] | None = field(
        default=None,
        metadata={
            "help": 'Font sizes for heading levels 1-6 as JSON object (e.g., \'{"1": 24, "2": 18}\')',
            "importance": "advanced",
        },
    )
    use_styles: bool = field(
        default=True,
        metadata={
            "help": "Use built-in ODT styles vs direct formatting",
            "cli_name": "no-use-styles",
            "importance": "advanced",
        },
    )
    code_font: str = field(
        default="Liberation Mono", metadata={"help": "Font for code blocks and inline code", "importance": "core"}
    )
    code_font_size: int = field(default=10, metadata={"help": "Font size for code", "type": int, "importance": "core"})
    preserve_formatting: bool = field(
        default=True,
        metadata={
            "help": "Preserve text formatting (bold, italic, etc.)",
            "cli_name": "no-preserve-formatting",
            "importance": "core",
        },
    )
    template_path: str | None = field(
        default=None,
        metadata={
            "help": "Path to .odt template file for styles (None = default blank document)",
            "importance": "core",
        },
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote image fetching",
            "cli_flatten": True,
        },
    )
