#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/odt.py
"""Configuration options for ODT (OpenDocument Text) parsing and rendering.

This module defines options for parsing and rendering ODT document files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ODT_CODE_FONT,
    DEFAULT_ODT_CODE_FONT_SIZE,
    DEFAULT_ODT_COMMENT_MODE,
    DEFAULT_ODT_DEFAULT_FONT,
    DEFAULT_ODT_DEFAULT_FONT_SIZE,
    DEFAULT_ODT_PRESERVE_FORMATTING,
    DEFAULT_ODT_PRESERVE_TABLES,
    DEFAULT_ODT_USE_STYLES,
    OdtCommentMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin, NetworkFetchOptions


@dataclass(frozen=True)
class OdtOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for ODT-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Text (ODT)
    processing. Inherits attachment handling from AttachmentOptionsMixin
    for embedded images.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.

    """

    preserve_tables: bool = field(
        default=DEFAULT_ODT_PRESERVE_TABLES,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


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
    comment_mode : {"native", "visible", "ignore"}, default "native"
        How to render Comment and CommentInline AST nodes:
        - "native": Use odfpy native comment/annotation support (preserves ODT comments when possible)
        - "visible": Render as regular text paragraphs with attribution
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from ODT source files and other formats.

    """

    default_font: str = field(
        default=DEFAULT_ODT_DEFAULT_FONT, metadata={"help": "Default font for body text", "importance": "core"}
    )
    default_font_size: int = field(
        default=DEFAULT_ODT_DEFAULT_FONT_SIZE,
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
        default=DEFAULT_ODT_USE_STYLES,
        metadata={
            "help": "Use built-in ODT styles vs direct formatting",
            "cli_name": "no-use-styles",
            "importance": "advanced",
        },
    )
    code_font: str = field(
        default=DEFAULT_ODT_CODE_FONT,
        metadata={"help": "Font for code blocks and inline code", "importance": "core"},
    )
    code_font_size: int = field(
        default=DEFAULT_ODT_CODE_FONT_SIZE,
        metadata={"help": "Font size for code", "type": int, "importance": "core"},
    )
    preserve_formatting: bool = field(
        default=DEFAULT_ODT_PRESERVE_FORMATTING,
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
    comment_mode: OdtCommentMode = field(
        default=DEFAULT_ODT_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "native (ODT annotations), visible (text paragraphs with attribution), "
            "ignore (skip comment nodes entirely). Controls presentation of comments "
            "from ODT source files and other format annotations.",
            "choices": ["native", "visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for ODT renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()

        # Validate positive font sizes
        if self.default_font_size <= 0:
            raise ValueError(f"default_font_size must be positive, got {self.default_font_size}")

        if self.code_font_size <= 0:
            raise ValueError(f"code_font_size must be positive, got {self.code_font_size}")

        # Validate heading font sizes dictionary
        if self.heading_font_sizes is not None:
            for level, size in self.heading_font_sizes.items():
                if not 1 <= level <= 6:
                    raise ValueError(f"heading_font_sizes keys must be in range [1, 6], got {level}")
                if size <= 0:
                    raise ValueError(f"heading_font_sizes values must be positive, got {size} for level {level}")
