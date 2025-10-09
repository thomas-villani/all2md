#  Copyright (c) 2025 Tom Villani, Ph.D.
from dataclasses import field, dataclass
from typing import Literal

from all2md.constants import DEFAULT_HEADER_PERCENTILE_THRESHOLD, DEFAULT_HEADER_MIN_OCCURRENCES, \
    DEFAULT_HEADER_USE_FONT_WEIGHT, DEFAULT_HEADER_USE_ALL_CAPS, DEFAULT_HEADER_FONT_SIZE_RATIO, \
    DEFAULT_HEADER_MAX_LINE_LENGTH, DEFAULT_DETECT_COLUMNS, DEFAULT_MERGE_HYPHENATED_WORDS, DEFAULT_HANDLE_ROTATED_TEXT, \
    DEFAULT_COLUMN_GAP_THRESHOLD, DEFAULT_TABLE_FALLBACK_DETECTION, DEFAULT_DETECT_MERGED_CELLS, \
    DEFAULT_TABLE_RULING_LINE_THRESHOLD, DEFAULT_INCLUDE_IMAGE_CAPTIONS, DEFAULT_INCLUDE_PAGE_NUMBERS, \
    DEFAULT_PAGE_SEPARATOR, DEFAULT_TABLE_DETECTION_MODE, DEFAULT_IMAGE_FORMAT, DEFAULT_IMAGE_QUALITY, \
    DEFAULT_TRIM_HEADERS_FOOTERS, DEFAULT_HEADER_HEIGHT, DEFAULT_FOOTER_HEIGHT, DEFAULT_IMAGE_PLACEMENT_MARKERS
from all2md.options.base import BaseRendererOptions, BaseParserOptions


# src/all2md/options/pdf.py
@dataclass(frozen=True)
class PdfOptions(BaseParserOptions):
    """Configuration options for PDF-to-Markdown conversion.

    This dataclass contains settings specific to PDF document processing,
    including page selection, image handling, and formatting preferences.

    Parameters
    ----------
    pages : list[int], str, or None, default None
        Pages to convert (1-based indexing, like "page 1, page 2").
        Can be a list [1, 2, 3] or string range "1-3,5,10-".
        If None, converts all pages.
    password : str or None, default None
        Password for encrypted PDF documents.

    # Header detection parameters
    header_sample_pages : int | list[int] | None, default None
        Pages to sample for header font size analysis. If None, samples all pages.
    header_percentile_threshold : float, default 75
        Percentile threshold for header detection (e.g., 75 = top 25% of font sizes).
    header_min_occurrences : int, default 3
        Minimum occurrences of a font size to consider it for headers.
    header_size_allowlist : list[float] | None, default None
        Specific font sizes to always treat as headers.
    header_size_denylist : list[float] | None, default None
        Font sizes to never treat as headers.
    header_use_font_weight : bool, default True
        Consider bold/font weight when detecting headers.
    header_use_all_caps : bool, default True
        Consider all-caps text as potential headers.
    header_font_size_ratio : float, default 1.2
        Minimum ratio between header and body text font size.
    header_max_line_length : int, default 100
        Maximum character length for text to be considered a header.

    # Reading order and layout parameters
    detect_columns : bool, default True
        Enable multi-column layout detection.
    merge_hyphenated_words : bool, default True
        Merge words split by hyphens at line breaks.
    handle_rotated_text : bool, default True
        Process rotated text blocks.
    column_gap_threshold : float, default 20
        Minimum gap between columns in points.

    # Table detection parameters
    enable_table_fallback_detection : bool, default True
        Use heuristic fallback if PyMuPDF table detection fails.
    detect_merged_cells : bool, default True
        Attempt to identify merged cells in tables.
    table_ruling_line_threshold : float, default 0.5
        Threshold for detecting table ruling lines.

    image_placement_markers : bool, default True
        Add markers showing image positions.
    include_image_captions : bool, default True
        Try to extract image captions.

    include_page_numbers : bool, default False
        Include page numbers in output (automatically added to separator).
    page_separator_template : str, default "-----"
        Template for page separators between pages.
        Supports placeholders: {page_num}, {total_pages}.

    table_detection_mode : str, default "both"
        Table detection strategy: "pymupdf", "ruling", "both", or "none".
    image_format : str, default "png"
        Output format for extracted images: "png" or "jpeg".
    image_quality : int, default 90
        JPEG quality (1-100, only used when image_format="jpeg").

    trim_headers_footers : bool, default False
        Remove repeated headers and footers from pages.
    header_height : int, default 0
        Height in points to trim from top of page (requires trim_headers_footers).
    footer_height : int, default 0
        Height in points to trim from bottom of page (requires trim_headers_footers).
    skip_image_extraction : bool, default False
        Skip all image extraction for text-only conversion (improves performance for large PDFs).
    lazy_image_processing : bool, default False
        Placeholder for future lazy image loading support (currently no effect).

    Notes
    -----
    For large PDFs (hundreds of pages), consider using skip_image_extraction=True if you only need
    text content. This significantly reduces memory pressure by avoiding image decoding.
    Parallel processing (CLI --parallel flag) can further improve throughput for multi-file batches,
    but note that each worker process imports dependencies anew, adding startup overhead.

    Examples
    --------
    Convert only pages 1-3 with base64 images:
        >>> options = PdfOptions(pages=[1, 2, 3], attachment_mode="base64")
        >>> # Or using string range:
        >>> options = PdfOptions(pages="1-3", attachment_mode="base64")

    Convert with custom page separators:
        >>> options = PdfOptions(
        ...     page_separator_template="--- Page {page_num} of {total_pages} ---",
        ...     include_page_numbers=True
        ... )

    Configure header detection:
        >>> options = PdfOptions(
        ...     header_sample_pages=[0, 1, 2],
        ...     header_percentile_threshold=80,
        ...     header_use_all_caps=True
        ... )

    """

    pages: list[int] | str | None = field(
        default=None,
        metadata={
            "help": "Pages to convert. Supports ranges: '1-3,5,10-' or list like [1,2,3]. Always 1-based.",
            "type": str
        }
    )
    password: str | None = field(
        default=None,
        metadata={"help": "Password for encrypted PDF documents"}
    )

    # Header detection parameters
    header_sample_pages: int | list[int] | None = field(
        default=None,
        metadata={
            "help": "Pages to sample for header detection",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    header_percentile_threshold: float = field(
        default=DEFAULT_HEADER_PERCENTILE_THRESHOLD,
        metadata={
            "help": "Percentile threshold for header detection",
            "type": float
        }
    )
    header_min_occurrences: int = field(
        default=DEFAULT_HEADER_MIN_OCCURRENCES,
        metadata={
            "help": "Minimum occurrences of a font size to consider for headers",
            "type": int
        }
    )
    header_size_allowlist: list[float] | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Complex type, exclude for now
    )
    header_size_denylist: list[float] | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Complex type, exclude for now
    )
    header_use_font_weight: bool = field(
        default=DEFAULT_HEADER_USE_FONT_WEIGHT,
        metadata={
            "help": "Consider bold/font weight when detecting headers",
            "cli_name": "no-header-use-font-weight"  # default=True, use --no-*
        }
    )
    header_use_all_caps: bool = field(
        default=DEFAULT_HEADER_USE_ALL_CAPS,
        metadata={
            "help": "Consider all-caps text as potential headers",
            "cli_name": "no-header-use-all-caps"  # default=True, use --no-*
        }
    )
    header_font_size_ratio: float = field(
        default=DEFAULT_HEADER_FONT_SIZE_RATIO,
        metadata={
            "help": "Minimum ratio between header and body text font size",
            "type": float
        }
    )
    header_max_line_length: int = field(
        default=DEFAULT_HEADER_MAX_LINE_LENGTH,
        metadata={
            "help": "Maximum character length for text to be considered a header",
            "type": int
        }
    )

    # Reading order and layout parameters
    detect_columns: bool = field(
        default=DEFAULT_DETECT_COLUMNS,
        metadata={
            "help": "Enable multi-column layout detection",
            "cli_name": "no-detect-columns"  # default=True, use --no-*
        }
    )
    merge_hyphenated_words: bool = field(
        default=DEFAULT_MERGE_HYPHENATED_WORDS,
        metadata={
            "help": "Merge words split by hyphens at line breaks",
            "cli_name": "no-merge-hyphenated-words"  # default=True, use --no-*
        }
    )
    handle_rotated_text: bool = field(
        default=DEFAULT_HANDLE_ROTATED_TEXT,
        metadata={
            "help": "Process rotated text blocks",
            "cli_name": "no-handle-rotated-text"  # default=True, use --no-*
        }
    )
    column_gap_threshold: float = field(
        default=DEFAULT_COLUMN_GAP_THRESHOLD,
        metadata={
            "help": "Minimum gap between columns in points",
            "type": float
        }
    )

    # Table detection parameters
    enable_table_fallback_detection: bool = field(
        default=DEFAULT_TABLE_FALLBACK_DETECTION,
        metadata={
            "help": "Use heuristic fallback if PyMuPDF table detection fails",
            "cli_name": "no-enable-table-fallback-detection"  # default=True, use --no-*
        }
    )
    detect_merged_cells: bool = field(
        default=DEFAULT_DETECT_MERGED_CELLS,
        metadata={
            "help": "Attempt to identify merged cells in tables",
            "cli_name": "no-detect-merged-cells"  # default=True, use --no-*
        }
    )
    table_ruling_line_threshold: float = field(
        default=DEFAULT_TABLE_RULING_LINE_THRESHOLD,
        metadata={
            "help": "Threshold for detecting table ruling lines",
            "type": float
        }
    )

    image_placement_markers: bool = field(
        default=DEFAULT_IMAGE_PLACEMENT_MARKERS,
        metadata={
            "help": "Add markers showing image positions",
            "cli_name": "no-image-placement-markers"  # default=True, use --no-*
        }
    )
    include_image_captions: bool = field(
        default=DEFAULT_INCLUDE_IMAGE_CAPTIONS,
        metadata={
            "help": "Try to extract image captions",
            "cli_name": "no-include-image-captions"  # default=True, use --no-*
        }
    )

    # Page number display and separators
    include_page_numbers: bool = field(
        default=DEFAULT_INCLUDE_PAGE_NUMBERS,
        metadata={
            "help": "Include page numbers in output (e.g., 'Page 1/10')"
        }
    )
    page_separator_template: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={
            "help": "Template for page separators. Supports placeholders: {page_num}, {total_pages}. "
                    "Use plain text without placeholders for simple separators."
        }
    )

    # Table detection mode
    table_detection_mode: str = field(
        default=DEFAULT_TABLE_DETECTION_MODE,
        metadata={
            "help": "Table detection strategy: 'pymupdf', 'ruling', 'both', or 'none'",
            "choices": ["pymupdf", "ruling", "both", "none"]
        }
    )

    # Image format options
    image_format: str = field(
        default=DEFAULT_IMAGE_FORMAT,
        metadata={
            "help": "Output format for extracted images: 'png' or 'jpeg'",
            "choices": ["png", "jpeg"]
        }
    )
    image_quality: int = field(
        default=DEFAULT_IMAGE_QUALITY,
        metadata={
            "help": "JPEG quality (1-100, only used when image_format='jpeg')",
            "type": int
        }
    )

    # Header/footer trimming
    trim_headers_footers: bool = field(
        default=DEFAULT_TRIM_HEADERS_FOOTERS,
        metadata={
            "help": "Remove repeated headers and footers from pages"
        }
    )
    header_height: int = field(
        default=DEFAULT_HEADER_HEIGHT,
        metadata={
            "help": "Height in points to trim from top of page (requires trim_headers_footers)",
            "type": int
        }
    )
    footer_height: int = field(
        default=DEFAULT_FOOTER_HEIGHT,
        metadata={
            "help": "Height in points to trim from bottom of page (requires trim_headers_footers)",
            "type": int
        }
    )

    # Performance optimization options
    skip_image_extraction: bool = field(
        default=False,
        metadata={
            "help": "Completely skip image extraction for text-only conversion (improves performance for large PDFs)"
        }
    )
    lazy_image_processing: bool = field(
        default=False,
        metadata={
            "help": "Placeholder for future lazy image loading support. Note: Full implementation would require "
                    "paginator interface for streaming large PDFs. Currently has no effect."
        }
    )


@dataclass(frozen=True)
class PdfRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to PDF format.

    This dataclass contains settings specific to PDF generation using ReportLab,
    including page layout, fonts, margins, and formatting preferences.

    Parameters
    ----------
    page_size : {"letter", "a4", "legal"}, default "letter"
        Page size for the PDF document.
    margin_top : float, default 72.0
        Top margin in points (72 points = 1 inch).
    margin_bottom : float, default 72.0
        Bottom margin in points.
    margin_left : float, default 72.0
        Left margin in points.
    margin_right : float, default 72.0
        Right margin in points.
    font_name : str, default "Helvetica"
        Default font for body text. Standard PDF fonts: Helvetica, Times-Roman, Courier.
    font_size : int, default 11
        Default font size in points for body text.
    heading_fonts : dict[int, tuple[str, int]] or None, default None
        Font specifications for headings as {level: (font_name, font_size)}.
        If None, uses scaled versions of default font.
    code_font : str, default "Courier"
        Monospace font for code blocks and inline code.
    line_spacing : float, default 1.2
        Line spacing multiplier (1.0 = single spacing).
    include_page_numbers : bool, default True
        Add page numbers to footer.
    include_toc : bool, default False
        Generate table of contents from headings.

    """

    page_size: Literal["letter", "a4", "legal"] = field(
        default="letter",
        metadata={
            "help": "Page size: letter, a4, or legal",
            "choices": ["letter", "a4", "legal"]
        }
    )
    margin_top: float = field(
        default=72.0,
        metadata={"help": "Top margin in points (72pt = 1 inch)", "type": float}
    )
    margin_bottom: float = field(
        default=72.0,
        metadata={"help": "Bottom margin in points", "type": float}
    )
    margin_left: float = field(
        default=72.0,
        metadata={"help": "Left margin in points", "type": float}
    )
    margin_right: float = field(
        default=72.0,
        metadata={"help": "Right margin in points", "type": float}
    )
    font_name: str = field(
        default="Helvetica",
        metadata={"help": "Default font (Helvetica, Times-Roman, Courier)"}
    )
    font_size: int = field(
        default=11,
        metadata={"help": "Default font size in points", "type": int}
    )
    heading_fonts: dict[int, tuple[str, int]] | None = field(
        default=None,
        metadata={
            "help": "Heading font specs as {level: (font, size)}",
            "exclude_from_cli": True
        }
    )
    code_font: str = field(
        default="Courier",
        metadata={"help": "Monospace font for code"}
    )
    line_spacing: float = field(
        default=1.2,
        metadata={"help": "Line spacing multiplier (1.0 = single)", "type": float}
    )
    include_page_numbers: bool = field(
        default=True,
        metadata={
            "help": "Add page numbers to footer",
            "cli_name": "no-page-numbers"
        }
    )
    include_toc: bool = field(
        default=False,
        metadata={"help": "Generate table of contents"}
    )