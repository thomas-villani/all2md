#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/rtf.py
"""Configuration options for RTF (Rich Text Format) parsing and rendering.

This module defines options for parsing RTF documents and rendering AST
back into RTF using the pyth3 library.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_RTF_BOLD_HEADINGS,
    DEFAULT_RTF_COMMENT_MODE,
    DEFAULT_RTF_FONT_FAMILY,
    RtfCommentMode,
    RtfFontFamily,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin


@dataclass(frozen=True)
class RtfRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST documents to RTF.

    Parameters
    ----------
    font_family : {"roman", "swiss"}, default "roman"
        Base font family to pass to ``pyth``'s ``Rtf15Writer``. The ``roman``
        family maps to Times New Roman, while ``swiss`` maps to Calibri.
    bold_headings : bool, default True
        When True, heading text is rendered with the RTF bold style to
        distinguish it from body paragraphs.
    comment_mode : {"bracketed", "ignore"}, default "bracketed"
        How to render Comment and CommentInline AST nodes:
        - "bracketed": Render as [bracketed text] (default)
        - "ignore": Skip comments entirely

    """

    font_family: RtfFontFamily = field(
        default=DEFAULT_RTF_FONT_FAMILY,
        metadata={
            "help": "Base font family for the entire RTF document",
            "choices": ["roman", "swiss"],
            "importance": "core",
        },
    )
    bold_headings: bool = field(
        default=DEFAULT_RTF_BOLD_HEADINGS,
        metadata={"help": "Render heading content in bold", "cli_name": "no-bold-headings", "importance": "core"},
    )
    comment_mode: RtfCommentMode = field(
        default=DEFAULT_RTF_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: bracketed or ignore",
            "choices": ["bracketed", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class RtfOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for RTF-to-Markdown conversion.

    This dataclass contains settings specific to Rich Text Format processing,
    including handling of embedded images and other attachments. Inherits
    attachment handling from AttachmentOptionsMixin.

    Parameters
    ----------
    Inherited from `BaseParserOptions` and `AttachmentOptionsMixin`

    """

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
