#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for DOCX parsing and rendering.

This module defines options for Microsoft Word document conversion,
supporting both AST parsing and rendering operations.
"""

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_DOCX_CODE_FONT,
    DEFAULT_DOCX_CODE_FONT_SIZE,
    DEFAULT_DOCX_COMMENT_MODE,
    DEFAULT_DOCX_COMMENTS_POSITION,
    DEFAULT_DOCX_FONT,
    DEFAULT_DOCX_FONT_SIZE,
    DEFAULT_DOCX_INCLUDE_COMMENTS,
    DEFAULT_DOCX_INCLUDE_ENDNOTES,
    DEFAULT_DOCX_INCLUDE_FOOTNOTES,
    DEFAULT_DOCX_INCLUDE_IMAGE_CAPTIONS,
    DEFAULT_DOCX_TABLE_STYLE,
    DocxCommentMode,
    DocxCommentsPosition,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin, NetworkFetchOptions


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
    comment_mode : {"native", "visible", "ignore"}, default "native"
        How to render Comment and CommentInline AST nodes:
        - "native": Use python-docx native comment API (preserves Word comments when possible)
        - "visible": Render as regular text paragraphs with attribution
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from DOCX source files and other formats.

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
    comment_mode: DocxCommentMode = field(
        default=DEFAULT_DOCX_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "native (Word comments API), visible (text paragraphs with attribution), "
            "ignore (skip comment nodes entirely). Controls presentation of comments "
            "from DOCX source files and other format annotations.",
            "choices": ["native", "visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for DOCX renderer options.

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
        default=DEFAULT_DOCX_INCLUDE_FOOTNOTES,
        metadata={"help": "Include footnotes in output", "cli_name": "no-include-footnotes", "importance": "core"},
    )
    include_endnotes: bool = field(
        default=DEFAULT_DOCX_INCLUDE_ENDNOTES,
        metadata={"help": "Include endnotes in output", "cli_name": "no-include-endnotes", "importance": "core"},
    )
    include_comments: bool = field(
        default=DEFAULT_DOCX_INCLUDE_COMMENTS,
        metadata={"help": "Include document comments in output", "importance": "core"},
    )

    comments_position: DocxCommentsPosition = field(
        default=DEFAULT_DOCX_COMMENTS_POSITION,
        metadata={
            "help": (
                "Where to place Comment nodes in the AST: inline (CommentInline nodes at reference points) "
                "or footnotes (Comment block nodes appended at end)"
            ),
            "choices": ["inline", "footnotes"],
            "importance": "advanced",
        },
    )
    include_image_captions: bool = field(
        default=DEFAULT_DOCX_INCLUDE_IMAGE_CAPTIONS,
        metadata={
            "help": "Include image captions/descriptions in output",
            "cli_name": "no-include-image-captions",
            "importance": "advanced",
        },
    )
    code_style_names: list[str] = field(
        default_factory=lambda: ["Code", "HTML Code", "Source Code", "Macro Text"],
        metadata={
            "help": "List of paragraph style names to treat as code blocks (supports partial matching)",
            "importance": "advanced",
        },
    )
