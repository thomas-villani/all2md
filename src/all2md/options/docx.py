#  Copyright (c) 2025 Tom Villani, Ph.D.
from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import CommentMode, DEFAULT_COMMENT_MODE
from all2md.options.base import BaseRendererOptions, BaseParserOptions


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

    """

    default_font: str = field(
        default="Calibri",
        metadata={"help": "Default font for body text"}
    )
    default_font_size: int = field(
        default=11,
        metadata={"help": "Default font size in points", "type": int}
    )
    heading_font_sizes: dict[int, int] | None = field(
        default=None,
        metadata={
            "help": "Font sizes for heading levels 1-6 (None = use built-in styles)",
            "exclude_from_cli": True
        }
    )
    use_styles: bool = field(
        default=True,
        metadata={
            "help": "Use built-in Word styles vs direct formatting",
            "cli_name": "no-use-styles"
        }
    )
    table_style: str | None = field(
        default="Light Grid Accent 1",
        metadata={"help": "Built-in table style name (None = plain formatting)"}
    )
    code_font: str = field(
        default="Courier New",
        metadata={"help": "Font for code blocks and inline code"}
    )
    code_font_size: int = field(
        default=10,
        metadata={"help": "Font size for code", "type": int}
    )
    preserve_formatting: bool = field(
        default=True,
        metadata={
            "help": "Preserve text formatting (bold, italic, etc.)",
            "cli_name": "no-preserve-formatting"
        }
    )


@dataclass(frozen=True)
class DocxOptions(BaseParserOptions):
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

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
            "cli_name": "no-preserve-tables"
        }
    )

    # Advanced DOCX options
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
    include_comments: bool = field(
        default=False,
        metadata={"help": "Include document comments in output"}
    )
    comments_position: Literal["inline", "footnotes"] = field(
        default="footnotes",
        metadata={
            "help": "Render comments inline or at document end",
            "choices": ["inline", "footnotes"],
        },
    )
    comment_mode: CommentMode = field(
        default=DEFAULT_COMMENT_MODE,
        metadata={
            "help": "How to render comments: html (HTML comments), blockquote (quoted blocks), ignore (skip)",
            "choices": ["html", "blockquote", "ignore"]
        }
    )
    include_image_captions: bool = field(
        default=True,
        metadata={
            "help": "Include image captions/descriptions in output",
            "cli_name": "no-include-image-captions"
        }
    )
    list_numbering_style: str = field(
        default="detect",
        metadata={
            "help": "List numbering style: detect, decimal, lowerroman, upperroman, loweralpha, upperalpha"
        }
    )