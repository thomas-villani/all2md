#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for DOCX parsing and rendering.

This module defines options for Microsoft Word document conversion,
supporting both AST parsing and rendering operations.
"""
from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import (
    DEFAULT_COMMENT_MODE,
    DEFAULT_DOCX_CODE_FONT,
    DEFAULT_DOCX_CODE_FONT_SIZE,
    DEFAULT_DOCX_FONT,
    DEFAULT_DOCX_FONT_SIZE,
    DEFAULT_DOCX_TABLE_STYLE,
    CommentMode,
)
from all2md.options.base import AttachmentOptionsMixin, BaseParserOptions, BaseRendererOptions
from all2md.options.common import NetworkFetchOptions


# src/all2md/options/docx.py
@dataclass(frozen=True)
class DocxRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to DOCX format.

    This dataclass contains settings specific to Word document generation,
    including fonts, styles, and formatting preferences.

    Parameters
    ----------
    default_font : str, default "Calibri"
        Default font name for body text.
    default_font_size : int, default 11
        Default font size in points for body text.
    heading_font_sizes : dict[int, int] or None, default None
        Font sizes for heading levels 1-6. If None, uses built-in Word heading styles.
    use_styles : bool, default True
        Whether to use built-in Word styles vs direct formatting.
    table_style : str or None, default "Light Grid Accent 1"
        Built-in table style name. If None, uses plain table formatting.
    code_font : str, default "Courier New"
        Font name for code blocks and inline code.
    code_font_size : int, default 10
        Font size for code blocks and inline code.
    preserve_formatting : bool, default True
        Whether to preserve text formatting (bold, italic, etc.).
    template_path : str or None, default None
        Path to .docx template file. When specified, the renderer uses the template's
        styles (headings, body text, etc.) instead of creating a blank document. This
        is powerful for corporate environments where documents must adopt specific style
        guidelines defined in a template.
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security settings for fetching remote images. By default,
        remote image fetching is disabled (allow_remote_fetch=False).
        Set network.allow_remote_fetch=True to enable secure remote image fetching
        with the same security guardrails as PPTX renderer.

    """

    default_font: str = field(
        default=DEFAULT_DOCX_FONT, metadata={"help": "Default font for body text", "importance": "core"}
    )
    default_font_size: int = field(
        default=DEFAULT_DOCX_FONT_SIZE,
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
            "help": "Use built-in Word styles vs direct formatting",
            "cli_name": "no-use-styles",
            "importance": "advanced",
        },
    )
    table_style: str | None = field(
        default=DEFAULT_DOCX_TABLE_STYLE,
        metadata={"help": "Built-in table style name (None = plain formatting)", "importance": "advanced"},
    )
    code_font: str = field(
        default=DEFAULT_DOCX_CODE_FONT, metadata={"help": "Font for code blocks and inline code", "importance": "core"}
    )
    code_font_size: int = field(
        default=DEFAULT_DOCX_CODE_FONT_SIZE, metadata={"help": "Font size for code", "type": int, "importance": "core"}
    )
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
            "help": "Path to .docx template file for styles (None = default blank document)",
            "importance": "core",
        },
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote image fetching",
            "cli_flatten": True,  # Nested, handled separately
        },
    )


@dataclass(frozen=True)
class DocxOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences. Inherits attachment
    handling from AttachmentOptionsMixin for embedded images and media.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.

    Examples
    --------
    Convert with base64 image embedding:
        >>> options = DocxOptions(attachment_mode="base64")

    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables",
            "importance": "core",
        },
    )

    # Advanced DOCX options
    include_footnotes: bool = field(
        default=True,
        metadata={"help": "Include footnotes in output", "cli_name": "no-include-footnotes", "importance": "core"},
    )
    include_endnotes: bool = field(
        default=True,
        metadata={"help": "Include endnotes in output", "cli_name": "no-include-endnotes", "importance": "core"},
    )
    include_comments: bool = field(
        default=False, metadata={"help": "Include document comments in output", "importance": "core"}
    )

    comments_position: Literal["inline", "footnotes"] = field(
        default="footnotes",
        metadata={
            "help": "Render comments inline or at document end",
            "choices": ["inline", "footnotes"],
            "importance": "advanced",
        },
    )
    comment_mode: CommentMode = field(
        default=DEFAULT_COMMENT_MODE,
        metadata={
            "help": "How to render comments: html (HTML comments), blockquote (quoted blocks), ignore (skip)",
            "choices": ["html", "blockquote", "ignore"],
            "importance": "advanced",
        },
    )
    include_image_captions: bool = field(
        default=True,
        metadata={
            "help": "Include image captions/descriptions in output",
            "cli_name": "no-include-image-captions",
            "importance": "advanced",
        },
    )
    list_numbering_style: Literal["detect", "decimal", "lowerroman", "upperroman", "loweralpha", "upperalpha"] = field(
        default="detect",
        metadata={
            "help": "List numbering style: detect, decimal, lowerroman, upperroman, loweralpha, upperalpha",
            "choices": ["detect", "decimal", "lowerroman", "upperroman", "loweralpha", "upperalpha"],
            "importance": "advanced",
        },
    )
