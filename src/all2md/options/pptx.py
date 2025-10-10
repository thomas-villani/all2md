#  Copyright (c) 2025 Tom Villani, Ph.D.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import DEFAULT_PAGE_SEPARATOR, DEFAULT_SLIDE_NUMBERS
from all2md.options.base import BaseParserOptions, BaseRendererOptions

# all2md/options/pptx.py

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

    """

    # TODO: move magic numbers/strings to constants.py

    slide_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Slide splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"]
        }
    )
    slide_split_heading_level: int = field(
        default=2,
        metadata={
            "help": "Heading level for slide splits (H2 = level 2)",
            "type": int
        }
    )
    default_layout: str = field(
        default="Title and Content",
        metadata={"help": "Default slide layout name"}
    )
    title_slide_layout: str = field(
        default="Title Slide",
        metadata={"help": "Layout for first slide"}
    )
    use_heading_as_slide_title: bool = field(
        default=True,
        metadata={
            "help": "Use first heading as slide title",
            "cli_name": "no-use-heading-as-slide-title"
        }
    )
    template_path: str | None = field(
        default=None,
        metadata={"help": "Path to .pptx template file (None = default)"}
    )
    default_font: str = field(
        default="Calibri",
        metadata={"help": "Default font for slide content"}
    )
    default_font_size: int = field(
        default=18,
        metadata={"help": "Default font size for body text", "type": int}
    )
    title_font_size: int = field(
        default=44,
        metadata={"help": "Font size for slide titles", "type": int}
    )


@dataclass(frozen=True)
class PptxOptions(BaseParserOptions):
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
        default=DEFAULT_SLIDE_NUMBERS,
        metadata={"help": "Include slide numbers in output"}
    )
    include_notes: bool = field(
        default=True,
        metadata={
            "help": "Include speaker notes from slides",
            "cli_name": "no-include-notes"
        }
    )
    page_separator_template: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={
            "help": "Template for slide separators. Supports placeholders: {page_num}, {total_pages}."
        }
    )

    # Advanced PPTX options
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)"}
    )
    charts_mode: str = field(
        default="data",
        metadata={
            "help": "Chart conversion mode: 'data' (tables), 'image' (screenshots), 'mermaid', or 'both'"
        }
    )
    include_titles_as_h2: bool = field(
        default=True,
        metadata={
            "help": "Include slide titles as H2 headings",
            "cli_name": "no-include-titles-as-h2"
        }
    )
