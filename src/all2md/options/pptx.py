#  Copyright (c) 2025 Tom Villani, Ph.D.
"""PPTX parser and renderer options."""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_PPTX_CHARTS_MODE,
    DEFAULT_PPTX_COMMENT_MODE,
    DEFAULT_PPTX_DEFAULT_FONT,
    DEFAULT_PPTX_DEFAULT_FONT_SIZE,
    DEFAULT_PPTX_DEFAULT_LAYOUT,
    DEFAULT_PPTX_FORCE_TEXTBOX_BULLETS,
    DEFAULT_PPTX_IMAGE_LEFT,
    DEFAULT_PPTX_IMAGE_TOP,
    DEFAULT_PPTX_IMAGE_WIDTH,
    DEFAULT_PPTX_INCLUDE_NOTES,
    DEFAULT_PPTX_INCLUDE_TITLES_AS_H2,
    DEFAULT_PPTX_LIST_INDENT_PER_LEVEL,
    DEFAULT_PPTX_LIST_NUMBER_SPACING,
    DEFAULT_PPTX_PARSER_COMMENT_MODE,
    DEFAULT_PPTX_SLIDE_SPLIT_HEADING_LEVEL,
    DEFAULT_PPTX_SLIDE_SPLIT_MODE,
    DEFAULT_PPTX_STRICT_LIST_DETECTION,
    DEFAULT_PPTX_TABLE_HEIGHT_PER_ROW,
    DEFAULT_PPTX_TABLE_LEFT,
    DEFAULT_PPTX_TABLE_TOP,
    DEFAULT_PPTX_TABLE_WIDTH,
    DEFAULT_PPTX_TITLE_FONT_SIZE,
    DEFAULT_PPTX_TITLE_SLIDE_LAYOUT,
    DEFAULT_PPTX_USE_HEADING_AS_SLIDE_TITLE,
    DEFAULT_SLIDE_NUMBERS,
    ChartsMode,
    PptxCommentMode,
    PptxParserCommentMode,
    SlideSplitMode,
)
from all2md.options.base import BaseRendererOptions
from all2md.options.common import NetworkFetchOptions, PaginatedParserOptions


@dataclass(frozen=True)
class PptxRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to PPTX format.

    This dataclass contains settings specific to PowerPoint presentation
    generation from AST, including slide splitting strategies and layout.

    Parameters
    ----------
    slide_split_mode : {"separator", "heading", "auto"}, default "auto"
        How to split the AST into slides:
        - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
        - "heading": Split on specific heading level
        - "auto": Try separator first, fallback to heading-based splitting
    slide_split_heading_level : int, default 2
        Heading level to use for slide splits when using heading mode.
        Level 2 (H2) is typical (H1 might be document title).
    default_layout : str, default "Title and Content"
        Default slide layout name from template.
    title_slide_layout : str, default "Title Slide"
        Layout name for the first slide.
    use_heading_as_slide_title : bool, default True
        Use first heading in slide content as slide title.
    template_path : str or None, default None
        Path to .pptx template file. If None, uses default blank template.
    default_font : str, default "Calibri"
        Default font for slide content.
    default_font_size : int, default 18
        Default font size in points for body text.
    title_font_size : int, default 44
        Font size for slide titles.
    list_number_spacing : int, default 1
        Number of spaces after the number prefix in ordered lists (e.g., "1. " has 1 space).
        Affects visual consistency of manually numbered lists.
    list_indent_per_level : float, default 0.5
        Indentation per nesting level for lists, in inches.
        Controls horizontal spacing for nested lists. Note that actual indentation
        behavior may vary across PowerPoint templates.
    table_left : float, default 0.5
        Left position for tables in inches.
    table_top : float, default 2.0
        Top position for tables in inches.
    table_width : float, default 9.0
        Width for tables in inches.
    table_height_per_row : float, default 0.5
        Height per row for tables in inches.
    image_left : float, default 1.0
        Left position for images in inches.
    image_top : float, default 2.5
        Top position for images in inches.
    image_width : float, default 4.0
        Width for images in inches (aspect ratio maintained).
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security options for fetching remote images in slides.
    include_notes : bool, default True
        Whether to detect and render speaker notes from "Speaker Notes" sections.
        When True, H3 headings with "Speaker Notes" text are detected, and content
        after them is rendered to slide speaker notes. When False, speaker notes
        sections are ignored and rendered as regular slide content.
    comment_mode : {"speaker_notes", "visible", "ignore"}, default "speaker_notes"
        How to render Comment and CommentInline AST nodes:
        - "speaker_notes": Render in slide speaker notes (default)
        - "visible": Render as visible italic text in slide content
        - "ignore": Skip comments entirely
    force_textbox_bullets : bool, default True
        Enable bullets via OOXML manipulation for unordered lists in text boxes.
        When True (default), bullets are explicitly enabled via OOXML for all text boxes.
        When False, bullets are only applied to content placeholders (native PowerPoint behavior).
        Set to False if using strict templates that conflict with OOXML manipulation.

    Notes
    -----
    **List Rendering Limitations:**

    python-pptx has limited support for automatic list numbering. This renderer
    uses manual numbering for ordered lists by adding number prefixes (e.g., "1. ")
    as text runs. The following options provide some control over list formatting:

    - ``list_number_spacing``: Controls spacing after numbers
    - ``list_indent_per_level``: Controls nesting indentation

    However, deeper nesting and exact spacing behavior can be inconsistent across
    different PowerPoint templates. These limitations are inherent to python-pptx's
    API and the complexity of PowerPoint's list formatting system.

    **Unordered Lists in Text Boxes:**

    For unordered lists, bullets are explicitly enabled via OOXML manipulation
    to ensure they appear in both text boxes and content placeholders. Text boxes
    do not enable bullets by default, unlike content placeholders.

    """

    slide_split_mode: SlideSplitMode = field(
        default=DEFAULT_PPTX_SLIDE_SPLIT_MODE,
        metadata={
            "help": "Slide splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"],
            "importance": "core",
        },
    )
    slide_split_heading_level: int = field(
        default=DEFAULT_PPTX_SLIDE_SPLIT_HEADING_LEVEL,
        metadata={"help": "Heading level for slide splits (H2 = level 2)", "type": int, "importance": "advanced"},
    )
    default_layout: str = field(
        default=DEFAULT_PPTX_DEFAULT_LAYOUT,
        metadata={"help": "Default slide layout name", "importance": "advanced"},
    )
    title_slide_layout: str = field(
        default=DEFAULT_PPTX_TITLE_SLIDE_LAYOUT,
        metadata={"help": "Layout for first slide", "importance": "advanced"},
    )
    use_heading_as_slide_title: bool = field(
        default=DEFAULT_PPTX_USE_HEADING_AS_SLIDE_TITLE,
        metadata={
            "help": "Use first heading as slide title",
            "cli_name": "no-use-heading-as-slide-title",
            "importance": "core",
        },
    )
    template_path: str | None = field(
        default=None, metadata={"help": "Path to .pptx template file (None = default)", "importance": "core"}
    )
    default_font: str = field(
        default=DEFAULT_PPTX_DEFAULT_FONT,
        metadata={"help": "Default font for slide content", "importance": "core"},
    )
    default_font_size: int = field(
        default=DEFAULT_PPTX_DEFAULT_FONT_SIZE,
        metadata={"help": "Default font size for body text", "type": int, "importance": "core"},
    )
    title_font_size: int = field(
        default=DEFAULT_PPTX_TITLE_FONT_SIZE,
        metadata={"help": "Font size for slide titles", "type": int, "importance": "advanced"},
    )
    list_number_spacing: int = field(
        default=DEFAULT_PPTX_LIST_NUMBER_SPACING,
        metadata={
            "help": "Number of spaces after number prefix in ordered lists",
            "type": int,
            "importance": "advanced",
        },
    )
    list_indent_per_level: float = field(
        default=DEFAULT_PPTX_LIST_INDENT_PER_LEVEL,
        metadata={
            "help": "Indentation per nesting level for lists (in inches)",
            "type": float,
            "importance": "advanced",
        },
    )
    table_left: float = field(
        default=DEFAULT_PPTX_TABLE_LEFT,
        metadata={"help": "Left position for tables in inches", "type": float, "importance": "advanced"},
    )
    table_top: float = field(
        default=DEFAULT_PPTX_TABLE_TOP,
        metadata={"help": "Top position for tables in inches", "type": float, "importance": "advanced"},
    )
    table_width: float = field(
        default=DEFAULT_PPTX_TABLE_WIDTH,
        metadata={"help": "Width for tables in inches", "type": float, "importance": "advanced"},
    )
    table_height_per_row: float = field(
        default=DEFAULT_PPTX_TABLE_HEIGHT_PER_ROW,
        metadata={"help": "Height per row for tables in inches", "type": float, "importance": "advanced"},
    )
    image_left: float = field(
        default=DEFAULT_PPTX_IMAGE_LEFT,
        metadata={"help": "Left position for images in inches", "type": float, "importance": "advanced"},
    )
    image_top: float = field(
        default=DEFAULT_PPTX_IMAGE_TOP,
        metadata={"help": "Top position for images in inches", "type": float, "importance": "advanced"},
    )
    image_width: float = field(
        default=DEFAULT_PPTX_IMAGE_WIDTH,
        metadata={"help": "Width for images in inches", "type": float, "importance": "advanced"},
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions, metadata={"help": "Network security options for fetching remote images"}
    )
    include_notes: bool = field(
        default=DEFAULT_PPTX_INCLUDE_NOTES,
        metadata={
            "help": "Include speaker notes in rendered slides",
            "cli_name": "no-include-notes",
            "importance": "core",
        },
    )
    comment_mode: PptxCommentMode = field(
        default=DEFAULT_PPTX_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: speaker_notes, visible, or ignore",
            "choices": ["speaker_notes", "visible", "ignore"],
            "importance": "core",
        },
    )
    force_textbox_bullets: bool = field(
        default=DEFAULT_PPTX_FORCE_TEXTBOX_BULLETS,
        metadata={
            "help": "Enable bullets via OOXML for text boxes (disable for strict templates)",
            "cli_name": "no-force-textbox-bullets",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for PPTX renderer options.

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

        # Validate non-negative spacing
        if self.list_number_spacing < 0:
            raise ValueError(f"list_number_spacing must be non-negative, got {self.list_number_spacing}")

        if self.list_indent_per_level < 0:
            raise ValueError(f"list_indent_per_level must be non-negative, got {self.list_indent_per_level}")

        # Validate non-negative table dimensions
        if self.table_left < 0:
            raise ValueError(f"table_left must be non-negative, got {self.table_left}")

        if self.table_top < 0:
            raise ValueError(f"table_top must be non-negative, got {self.table_top}")

        if self.table_width < 0:
            raise ValueError(f"table_width must be non-negative, got {self.table_width}")

        if self.table_height_per_row < 0:
            raise ValueError(f"table_height_per_row must be non-negative, got {self.table_height_per_row}")

        # Validate non-negative image dimensions
        if self.image_left < 0:
            raise ValueError(f"image_left must be non-negative, got {self.image_left}")

        if self.image_top < 0:
            raise ValueError(f"image_top must be non-negative, got {self.image_top}")

        if self.image_width < 0:
            raise ValueError(f"image_width must be non-negative, got {self.image_width}")


@dataclass(frozen=True)
class PptxOptions(PaginatedParserOptions):
    """Configuration options for PPTX-to-Markdown conversion.

    This dataclass contains settings specific to PowerPoint presentation
    processing, including slide numbering and image handling.

    Parameters
    ----------
    include_slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    comment_mode : {"content", "comment", "ignore"}, default "content"
        How to parse speaker notes in the AST:
        - "content": Parse as regular content nodes with H3 heading (default, current behavior)
        - "comment": Parse as Comment AST nodes with metadata
        - "ignore": Skip speaker notes entirely
        Note: This controls parsing of speaker notes. For rendering, see PptxRendererOptions.comment_mode.

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(include_slide_numbers=True, attachment_mode="base64")

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)

    Parse speaker notes as Comment nodes:
        >>> options = PptxOptions(comment_mode="comment")

    """

    include_slide_numbers: bool = field(
        default=DEFAULT_SLIDE_NUMBERS, metadata={"help": "Include slide numbers in output", "importance": "core"}
    )
    include_notes: bool = field(
        default=True,
        metadata={"help": "Include speaker notes from slides", "cli_name": "no-include-notes", "importance": "core"},
    )
    comment_mode: PptxParserCommentMode = field(
        default=DEFAULT_PPTX_PARSER_COMMENT_MODE,
        metadata={
            "help": "How to parse speaker notes: content (regular nodes with H3 heading), "
            "comment (Comment AST nodes with metadata), or ignore (skip entirely)",
            "choices": ["content", "comment", "ignore"],
            "importance": "core",
        },
    )

    # Advanced PPTX options
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)", "importance": "core"},
    )
    charts_mode: ChartsMode = field(
        default=DEFAULT_PPTX_CHARTS_MODE,
        metadata={
            "help": "Chart conversion mode: 'data' (default, tables only), "
            "'mermaid' (diagrams only), or 'both' (tables + diagrams)",
            "choices": ["data", "mermaid", "both"],
            "importance": "advanced",
        },
    )
    include_titles_as_h2: bool = field(
        default=DEFAULT_PPTX_INCLUDE_TITLES_AS_H2,
        metadata={
            "help": "Include slide titles as H2 headings",
            "cli_name": "no-include-titles-as-h2",
            "importance": "core",
        },
    )
    strict_list_detection: bool = field(
        default=DEFAULT_PPTX_STRICT_LIST_DETECTION,
        metadata={
            "help": "Use strict list detection (XML-only, no heuristics). "
            "When True, only paragraphs with explicit list formatting in XML are treated as lists. "
            "When False (default), uses XML detection with heuristic fallbacks for unformatted lists.",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
