#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/odp.py
"""Configuration options for ODP (OpenDocument Presentation) parsing and rendering.

This module defines options for parsing and rendering ODP presentation files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ODP_COMMENT_MODE,
    DEFAULT_ODP_DEFAULT_FONT,
    DEFAULT_ODP_DEFAULT_FONT_SIZE,
    DEFAULT_ODP_DEFAULT_LAYOUT,
    DEFAULT_ODP_INCLUDE_NOTES,
    DEFAULT_ODP_INCLUDE_SLIDE_NUMBERS,
    DEFAULT_ODP_PRESERVE_TABLES,
    DEFAULT_ODP_SLIDE_SPLIT_HEADING_LEVEL,
    DEFAULT_ODP_TITLE_FONT_SIZE,
    DEFAULT_ODP_TITLE_SLIDE_LAYOUT,
    DEFAULT_ODP_USE_HEADING_AS_SLIDE_TITLE,
    OdpCommentMode,
    SlideSplitMode,
)
from all2md.options.base import BaseRendererOptions
from all2md.options.common import NetworkFetchOptions, PaginatedParserOptions


@dataclass(frozen=True)
class OdpOptions(PaginatedParserOptions):
    """Configuration options for ODP-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Presentation (ODP)
    processing, including slide selection, numbering, and notes.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    include_slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    page_separator_template : str, default "---"
        Template for slide separators. Supports placeholders: {page_num}, {total_pages}.
    slides : str or None, default None
        Slide selection (e.g., "1,3-5,8" for slides 1, 3-5, and 8).

    """

    preserve_tables: bool = field(
        default=DEFAULT_ODP_PRESERVE_TABLES,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables",
            "importance": "core",
        },
    )
    include_slide_numbers: bool = field(
        default=DEFAULT_ODP_INCLUDE_SLIDE_NUMBERS,
        metadata={"help": "Include slide numbers in output", "importance": "core"},
    )
    include_notes: bool = field(
        default=DEFAULT_ODP_INCLUDE_NOTES,
        metadata={"help": "Include speaker notes from slides", "cli_name": "no-include-notes", "importance": "core"},
    )
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)", "importance": "core"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class OdpRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to ODP format.

    This dataclass contains settings specific to OpenDocument Presentation
    generation from AST, including slide splitting strategies and layout.

    Parameters
    ----------
    slide_split_mode : {"separator", "heading", "auto"}, default "auto"
        How to split the AST into slides:
        - "separator": Split on ThematicBreak nodes
        - "heading": Split on specific heading level
        - "auto": Try separator first, fallback to heading-based splitting
    slide_split_heading_level : int, default 2
        Heading level to use for slide splits when using heading mode.
    default_layout : str, default "Default"
        Default slide layout name.
    title_slide_layout : str, default "Title"
        Layout name for the first slide.
    use_heading_as_slide_title : bool, default True
        Use first heading in slide content as slide title.
    template_path : str or None, default None
        Path to .odp template file. If None, uses default blank template.
    default_font : str, default "Liberation Sans"
        Default font for slide content.
    default_font_size : int, default 18
        Default font size in points for body text.
    title_font_size : int, default 44
        Font size for slide titles.
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security options for fetching remote images in slides.
    include_notes : bool, default True
        Whether to detect and render speaker notes from "Speaker Notes" sections.
        When True, H3 headings with "Speaker Notes" text are detected, and content
        after them is rendered to slide speaker notes. When False, speaker notes
        sections are ignored and rendered as regular slide content.
    comment_mode : {"native", "visible", "ignore"}, default "native"
        How to render Comment and CommentInline AST nodes:
        - "native": Use ODF annotation elements (default)
        - "visible": Render as visible text in slide content
        - "ignore": Skip comments entirely

    """

    slide_split_mode: SlideSplitMode = field(
        default="auto",
        metadata={
            "help": "Slide splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"],
            "importance": "core",
        },
    )
    slide_split_heading_level: int = field(
        default=DEFAULT_ODP_SLIDE_SPLIT_HEADING_LEVEL,
        metadata={"help": "Heading level for slide splits (H2 = level 2)", "type": int, "importance": "advanced"},
    )
    default_layout: str = field(
        default=DEFAULT_ODP_DEFAULT_LAYOUT,
        metadata={"help": "Default slide layout name", "importance": "advanced"},
    )
    title_slide_layout: str = field(
        default=DEFAULT_ODP_TITLE_SLIDE_LAYOUT,
        metadata={"help": "Layout for first slide", "importance": "advanced"},
    )
    use_heading_as_slide_title: bool = field(
        default=DEFAULT_ODP_USE_HEADING_AS_SLIDE_TITLE,
        metadata={
            "help": "Use first heading as slide title",
            "cli_name": "no-use-heading-as-slide-title",
            "importance": "core",
        },
    )
    template_path: str | None = field(
        default=None, metadata={"help": "Path to .odp template file (None = default)", "importance": "core"}
    )
    default_font: str = field(
        default=DEFAULT_ODP_DEFAULT_FONT,
        metadata={"help": "Default font for slide content", "importance": "core"},
    )
    default_font_size: int = field(
        default=DEFAULT_ODP_DEFAULT_FONT_SIZE,
        metadata={"help": "Default font size for body text", "type": int, "importance": "core"},
    )
    title_font_size: int = field(
        default=DEFAULT_ODP_TITLE_FONT_SIZE,
        metadata={"help": "Font size for slide titles", "type": int, "importance": "advanced"},
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions, metadata={"help": "Network security options for fetching remote images"}
    )
    include_notes: bool = field(
        default=True,
        metadata={
            "help": "Include speaker notes in rendered slides",
            "cli_name": "no-include-notes",
            "importance": "core",
        },
    )
    comment_mode: OdpCommentMode = field(
        default=DEFAULT_ODP_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: native, visible, or ignore",
            "choices": ["native", "visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for ODP renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()

        # Validate heading level range
        if not 1 <= self.slide_split_heading_level <= 6:
            raise ValueError(f"slide_split_heading_level must be in range [1, 6], got {self.slide_split_heading_level}")

        # Validate positive font sizes
        if self.default_font_size <= 0:
            raise ValueError(f"default_font_size must be positive, got {self.default_font_size}")

        if self.title_font_size <= 0:
            raise ValueError(f"title_font_size must be positive, got {self.title_font_size}")
