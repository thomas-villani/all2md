#  Copyright (c) 2025 Tom Villani, Ph.D.
"""PPTX parser and renderer options."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import DEFAULT_SLIDE_NUMBERS
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

    # TODO: move magic numbers/strings to constants.py

    slide_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Slide splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"],
            "importance": "core",
        },
    )
    slide_split_heading_level: int = field(
        default=2,
        metadata={"help": "Heading level for slide splits (H2 = level 2)", "type": int, "importance": "advanced"},
    )
    default_layout: str = field(
        default="Title and Content", metadata={"help": "Default slide layout name", "importance": "advanced"}
    )
    title_slide_layout: str = field(
        default="Title Slide", metadata={"help": "Layout for first slide", "importance": "advanced"}
    )
    use_heading_as_slide_title: bool = field(
        default=True,
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
        default="Calibri", metadata={"help": "Default font for slide content", "importance": "core"}
    )
    default_font_size: int = field(
        default=18, metadata={"help": "Default font size for body text", "type": int, "importance": "core"}
    )
    title_font_size: int = field(
        default=44, metadata={"help": "Font size for slide titles", "type": int, "importance": "advanced"}
    )
    list_number_spacing: int = field(
        default=1,
        metadata={
            "help": "Number of spaces after number prefix in ordered lists",
            "type": int,
            "importance": "advanced",
        },
    )
    list_indent_per_level: float = field(
        default=0.5,
        metadata={
            "help": "Indentation per nesting level for lists (in inches)",
            "type": float,
            "importance": "advanced",
        },
    )
    table_left: float = field(
        default=0.5, metadata={"help": "Left position for tables in inches", "type": float, "importance": "advanced"}
    )
    table_top: float = field(
        default=2.0, metadata={"help": "Top position for tables in inches", "type": float, "importance": "advanced"}
    )
    table_width: float = field(
        default=9.0, metadata={"help": "Width for tables in inches", "type": float, "importance": "advanced"}
    )
    table_height_per_row: float = field(
        default=0.5, metadata={"help": "Height per row for tables in inches", "type": float, "importance": "advanced"}
    )
    image_left: float = field(
        default=1.0, metadata={"help": "Left position for images in inches", "type": float, "importance": "advanced"}
    )
    image_top: float = field(
        default=2.5, metadata={"help": "Top position for images in inches", "type": float, "importance": "advanced"}
    )
    image_width: float = field(
        default=4.0, metadata={"help": "Width for images in inches", "type": float, "importance": "advanced"}
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions, metadata={"help": "Network security options for fetching remote images"}
    )


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

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(include_slide_numbers=True, attachment_mode="base64")

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)

    """

    include_slide_numbers: bool = field(
        default=DEFAULT_SLIDE_NUMBERS, metadata={"help": "Include slide numbers in output", "importance": "core"}
    )
    include_notes: bool = field(
        default=True,
        metadata={"help": "Include speaker notes from slides", "cli_name": "no-include-notes", "importance": "core"},
    )

    # Advanced PPTX options
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)", "importance": "core"},
    )
    charts_mode: Literal["data", "mermaid", "both"] = field(
        default="data",
        metadata={
            "help": "Chart conversion mode: 'data' (default, tables only), "
                    "'mermaid' (diagrams only), or 'both' (tables + diagrams)",
            "choices": ["data", "mermaid", "both"],
            "importance": "advanced",
        },
    )
    include_titles_as_h2: bool = field(
        default=True,
        metadata={
            "help": "Include slide titles as H2 headings",
            "cli_name": "no-include-titles-as-h2",
            "importance": "core",
        },
    )
    strict_list_detection: bool = field(
        default=False,
        metadata={
            "help": "Use strict list detection (XML-only, no heuristics). "
                    "When True, only paragraphs with explicit list formatting in XML are treated as lists. "
                    "When False (default), uses XML detection with heuristic fallbacks for unformatted lists.",
            "importance": "advanced",
        },
    )
