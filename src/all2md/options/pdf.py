#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for PDF parsing.

This module defines options for parsing PDF documents with advanced
table detection and layout analysis.
"""
from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import (
    DEFAULT_AUTO_TRIM_HEADERS_FOOTERS,
    DEFAULT_COLUMN_DETECTION_MODE,
    DEFAULT_COLUMN_GAP_THRESHOLD,
    DEFAULT_DETECT_COLUMNS,
    DEFAULT_DETECT_MERGED_CELLS,
    DEFAULT_FOOTER_HEIGHT,
    DEFAULT_HANDLE_ROTATED_TEXT,
    DEFAULT_HEADER_DEBUG_OUTPUT,
    DEFAULT_HEADER_FONT_SIZE_RATIO,
    DEFAULT_HEADER_HEIGHT,
    DEFAULT_HEADER_MAX_LINE_LENGTH,
    DEFAULT_HEADER_MIN_OCCURRENCES,
    DEFAULT_HEADER_PERCENTILE_THRESHOLD,
    DEFAULT_HEADER_USE_ALL_CAPS,
    DEFAULT_HEADER_USE_FONT_WEIGHT,
    DEFAULT_IMAGE_FORMAT,
    DEFAULT_IMAGE_PLACEMENT_MARKERS,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_INCLUDE_IMAGE_CAPTIONS,
    DEFAULT_INCLUDE_PAGE_NUMBERS,
    DEFAULT_LINK_OVERLAP_THRESHOLD,
    DEFAULT_MERGE_HYPHENATED_WORDS,
    DEFAULT_OCR_AUTO_DETECT_LANGUAGE,
    DEFAULT_OCR_DPI,
    DEFAULT_OCR_ENABLED,
    DEFAULT_OCR_IMAGE_AREA_THRESHOLD,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_OCR_MODE,
    DEFAULT_OCR_PRESERVE_EXISTING_TEXT,
    DEFAULT_OCR_TESSERACT_CONFIG,
    DEFAULT_OCR_TEXT_THRESHOLD,
    DEFAULT_PDF_CODE_FONT,
    DEFAULT_PDF_FONT_FAMILY,
    DEFAULT_PDF_FONT_SIZE,
    DEFAULT_PDF_LINE_SPACING,
    DEFAULT_PDF_MARGIN,
    DEFAULT_PDF_PAGE_SIZE,
    DEFAULT_TABLE_DETECTION_MODE,
    DEFAULT_TABLE_FALLBACK_DETECTION,
    DEFAULT_TABLE_FALLBACK_EXTRACTION_MODE,
    DEFAULT_TABLE_RULING_LINE_THRESHOLD,
    DEFAULT_TRIM_HEADERS_FOOTERS,
    DEFAULT_USE_COLUMN_CLUSTERING,
    ColumnDetectionMode,
    ImageFormat,
    OCRMode,
    PageSize,
    TableDetectionMode,
)
from all2md.options.base import BaseRendererOptions
from all2md.options.common import NetworkFetchOptions, PaginatedParserOptions


@dataclass(frozen=True)
class OCROptions:
    """Configuration options for OCR (Optical Character Recognition) in PDF parsing.

    This dataclass contains settings for detecting and extracting text from scanned
    or image-based PDF pages using Tesseract OCR engine.

    Parameters
    ----------
    enabled : bool, default False
        Master switch to enable/disable OCR functionality. When False, all OCR
        processing is skipped regardless of other settings.
    mode : {"auto", "force", "off"}, default "auto"
        OCR triggering mode:
        - "auto": Automatically detect scanned pages and apply OCR when needed
        - "force": Apply OCR to all pages regardless of text content
        - "off": Disable OCR (same as enabled=False)
    languages : str or list[str], default "eng"
        Tesseract language code(s) for OCR. Can be:
        - Single language: "eng", "fra", "deu", "spa", "chi_sim", etc.
        - Multiple languages: "eng+fra" or ["eng", "fra"]
        See Tesseract documentation for available language codes.
    auto_detect_language : bool, default False
        Attempt to automatically detect the document language before OCR.
        Requires Tesseract language detection support (experimental).
    dpi : int, default 300
        DPI (dots per inch) for rendering PDF pages to images for OCR.
        Higher values improve OCR accuracy but increase processing time.
        Recommended: 150 (fast), 300 (balanced), 600 (high quality).
    text_threshold : int, default 50
        Minimum number of characters extracted by PyMuPDF to consider a page
        as text-based. Pages with fewer characters may trigger OCR in "auto" mode.
    image_area_threshold : float, default 0.5
        Minimum ratio of image area to total page area (0.0-1.0) to consider
        a page as image-based. Pages exceeding this threshold may trigger OCR
        in "auto" mode even if some text is present.
    preserve_existing_text : bool, default False
        Whether to preserve text extracted by PyMuPDF when OCR is applied:
        - False: Replace PyMuPDF text entirely with OCR results
        - True: Combine PyMuPDF text with OCR results (supplements sparse text)
    tesseract_config : str, default ""
        Custom Tesseract configuration flags (advanced users).
        Example: "--psm 6 --oem 3" for custom page segmentation mode.

    Notes
    -----
    OCR requires the optional dependencies pytesseract and Pillow, plus the
    Tesseract OCR engine installed on your system. Install with::

        pip install all2md[ocr]

    Then install Tesseract system package (platform-specific).

    Examples
    --------
    Enable OCR with auto-detection::

        >>> ocr = OCROptions(enabled=True, mode="auto")

    Force OCR on all pages with French language::

        >>> ocr = OCROptions(enabled=True, mode="force", languages="fra")

    High-quality OCR with multiple languages::

        >>> ocr = OCROptions(
        ...     enabled=True,
        ...     mode="auto",
        ...     languages="eng+fra+deu",
        ...     dpi=600,
        ...     preserve_existing_text=True
        ... )

    """

    enabled: bool = field(
        default=DEFAULT_OCR_ENABLED,
        metadata={
            "help": "Enable OCR for scanned/image-based PDF pages",
            "importance": "core",
        },
    )
    mode: OCRMode = field(
        default=DEFAULT_OCR_MODE,
        metadata={
            "help": "OCR mode: 'auto' (detect scanned pages), 'force' (all pages), 'off' (disable)",
            "choices": ["auto", "force", "off"],
            "importance": "core",
        },
    )
    languages: str | list[str] = field(
        default=DEFAULT_OCR_LANGUAGES,
        metadata={
            "help": "Tesseract language code(s), e.g. 'eng', 'fra', 'eng+fra', or ['eng', 'fra']",
            "importance": "core",
        },
    )
    auto_detect_language: bool = field(
        default=DEFAULT_OCR_AUTO_DETECT_LANGUAGE,
        metadata={
            "help": "Attempt to auto-detect document language (experimental)",
            "importance": "advanced",
        },
    )
    dpi: int = field(
        default=DEFAULT_OCR_DPI,
        metadata={
            "help": "DPI for rendering pages to images for OCR (150-600 recommended)",
            "type": int,
            "importance": "advanced",
        },
    )
    text_threshold: int = field(
        default=DEFAULT_OCR_TEXT_THRESHOLD,
        metadata={
            "help": "Minimum characters to consider page text-based (for auto mode)",
            "type": int,
            "importance": "advanced",
        },
    )
    image_area_threshold: float = field(
        default=DEFAULT_OCR_IMAGE_AREA_THRESHOLD,
        metadata={
            "help": "Image area ratio (0.0-1.0) to trigger OCR (for auto mode)",
            "type": float,
            "importance": "advanced",
        },
    )
    preserve_existing_text: bool = field(
        default=DEFAULT_OCR_PRESERVE_EXISTING_TEXT,
        metadata={
            "help": "Preserve PyMuPDF text when applying OCR (combine vs replace)",
            "importance": "advanced",
        },
    )
    tesseract_config: str = field(
        default=DEFAULT_OCR_TESSERACT_CONFIG,
        metadata={
            "help": "Custom Tesseract configuration flags (advanced)",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate OCR option values.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate DPI range (reasonable values)
        if not 72 <= self.dpi <= 1200:
            raise ValueError(f"dpi must be in range [72, 1200], got {self.dpi}")

        # Validate threshold ranges
        if self.text_threshold < 0:
            raise ValueError(f"text_threshold must be non-negative, got {self.text_threshold}")

        if not 0.0 <= self.image_area_threshold <= 1.0:
            raise ValueError(f"image_area_threshold must be in range [0.0, 1.0], got {self.image_area_threshold}")

        # Validate languages format (basic check)
        if isinstance(self.languages, list):
            if not self.languages:
                raise ValueError("languages list cannot be empty")
            for lang in self.languages:
                if not isinstance(lang, str) or not lang.strip():
                    raise ValueError(f"Invalid language code in list: {lang}")


# src/all2md/options/pdf.py
@dataclass(frozen=True)
class PdfOptions(PaginatedParserOptions):
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
    header_debug_output : bool, default False
        Enable debug output for header detection analysis. When enabled,
        stores font size distribution and classification decisions for inspection.

    # Reading order and layout parameters
    detect_columns : bool, default True
        Enable multi-column layout detection.
    merge_hyphenated_words : bool, default True
        Merge words split by hyphens at line breaks.
    handle_rotated_text : bool, default True
        Process rotated text blocks.
    column_gap_threshold : float, default 20
        Minimum gap between columns in points.
    column_detection_mode : str, default "auto"
        Column detection strategy: "auto" (heuristic-based), "force_single" (disable detection),
        "force_multi" (force multi-column), or "disabled" (same as force_single).
    use_column_clustering : bool, default False
        Use k-means clustering on x-coordinates for more robust column detection.
        Alternative to gap heuristics, better for layouts with irregular column positions.

    # Table detection parameters
    enable_table_fallback_detection : bool, default True
        Use heuristic fallback if PyMuPDF table detection fails.
    detect_merged_cells : bool, default True
        Attempt to identify merged cells in tables.
    table_ruling_line_threshold : float, default 0.5
        Threshold for detecting table ruling lines (0.0-1.0, ratio of line length to page size).
    table_fallback_extraction_mode : str, default "grid"
        Table extraction mode for ruling line fallback: "none" (detect only, don't extract),
        "grid" (grid-based cell segmentation), or "text_clustering" (future: text position clustering).

    link_overlap_threshold : float, default 70.0
        Percentage overlap required for link detection (0-100). Lower values detect links
        with less overlap but may incorrectly link non-link text. Higher values reduce
        false positives but may miss valid links.

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
    auto_trim_headers_footers : bool, default False
        Automatically detect and remove repeating headers/footers. When enabled,
        analyzes content across pages to identify repeating header/footer patterns
        and automatically sets header_height/footer_height values. Takes precedence
        over manually specified header_height/footer_height.
    header_height : int, default 0
        Height in points to trim from top of page (requires trim_headers_footers).
    footer_height : int, default 0
        Height in points to trim from bottom of page (requires trim_headers_footers).
    skip_image_extraction : bool, default False
        Skip all image extraction for text-only conversion (improves performance for large PDFs).
    lazy_image_processing : bool, default False
        Placeholder for future lazy image loading support (currently no effect).
    ocr : OCROptions, default OCROptions()
        OCR settings for extracting text from scanned/image-based PDF pages.
        Requires optional dependencies: pip install all2md[ocr]
        See OCROptions documentation for detailed configuration options.

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

    Configure header detection with debug output:
        >>> options = PdfOptions(
        ...     header_sample_pages=[1, 2, 3],
        ...     header_percentile_threshold=80,
        ...     header_use_all_caps=True,
        ...     header_debug_output=True  # Enable debug analysis
        ... )

    Use k-means clustering for robust column detection:
        >>> options = PdfOptions(
        ...     use_column_clustering=True,
        ...     column_gap_threshold=25
        ... )

    Configure link detection sensitivity:
        >>> options = PdfOptions(
        ...     link_overlap_threshold=80.0  # Stricter link detection
        ... )

    Enable table ruling line extraction:
        >>> options = PdfOptions(
        ...     table_detection_mode="ruling",
        ...     table_fallback_extraction_mode="grid"
        ... )

    Enable OCR for scanned PDF documents:
        >>> from all2md.options.pdf import OCROptions
        >>> options = PdfOptions(
        ...     ocr=OCROptions(enabled=True, mode="auto", languages="eng")
        ... )

    """

    pages: list[int] | str | None = field(
        default=None,
        metadata={
            "help": "Pages to convert. Supports ranges: '1-3,5,10-' or list like [1,2,3]. Always 1-based.",
            "type": str,
            "importance": "core",
        },
    )
    password: str | None = field(
        default=None, metadata={"help": "Password for encrypted PDF documents", "importance": "security"}
    )

    # Header detection parameters
    header_sample_pages: int | list[int] | None = field(
        default=None,
        metadata={
            "help": "Pages to sample for header detection (single page or comma-separated list)",
            "importance": "advanced",
        },
    )
    header_percentile_threshold: float = field(
        default=DEFAULT_HEADER_PERCENTILE_THRESHOLD,
        metadata={"help": "Percentile threshold for header detection", "type": float, "importance": "advanced"},
    )
    header_min_occurrences: int = field(
        default=DEFAULT_HEADER_MIN_OCCURRENCES,
        metadata={
            "help": "Minimum occurrences of a font size to consider for headers",
            "type": int,
            "importance": "advanced",
        },
    )
    header_size_allowlist: list[float] | None = field(
        default=None,
        metadata={"help": "Specific font sizes (in points) to always treat as headers", "importance": "advanced"},
    )
    header_size_denylist: list[float] | None = field(
        default=None, metadata={"help": "Font sizes (in points) to never treat as headers", "importance": "advanced"}
    )
    header_use_font_weight: bool = field(
        default=DEFAULT_HEADER_USE_FONT_WEIGHT,
        metadata={
            "help": "Consider bold/font weight when detecting headers",
            "cli_name": "no-header-use-font-weight",  # default=True, use --no-*
            "importance": "advanced",
        },
    )
    header_use_all_caps: bool = field(
        default=DEFAULT_HEADER_USE_ALL_CAPS,
        metadata={
            "help": "Consider all-caps text as potential headers",
            "cli_name": "no-header-use-all-caps",  # default=True, use --no-*
            "importance": "advanced",
        },
    )
    header_font_size_ratio: float = field(
        default=DEFAULT_HEADER_FONT_SIZE_RATIO,
        metadata={
            "help": "Minimum ratio between header and body text font size",
            "type": float,
            "importance": "advanced",
        },
    )
    header_max_line_length: int = field(
        default=DEFAULT_HEADER_MAX_LINE_LENGTH,
        metadata={
            "help": "Maximum character length for text to be considered a header",
            "type": int,
            "importance": "advanced",
        },
    )
    header_debug_output: bool = field(
        default=DEFAULT_HEADER_DEBUG_OUTPUT,
        metadata={
            "help": "Enable debug output for header detection analysis (stores font size distribution)",
            "importance": "advanced",
        },
    )

    # Reading order and layout parameters
    detect_columns: bool = field(
        default=DEFAULT_DETECT_COLUMNS,
        metadata={
            "help": "Enable multi-column layout detection",
            "cli_name": "no-detect-columns",  # default=True, use --no-*
            "importance": "core",
        },
    )
    merge_hyphenated_words: bool = field(
        default=DEFAULT_MERGE_HYPHENATED_WORDS,
        metadata={
            "help": "Merge words split by hyphens at line breaks",
            "cli_name": "no-merge-hyphenated-words",  # default=True, use --no-*
            "importance": "core",
        },
    )
    handle_rotated_text: bool = field(
        default=DEFAULT_HANDLE_ROTATED_TEXT,
        metadata={
            "help": "Process rotated text blocks",
            "cli_name": "no-handle-rotated-text",  # default=True, use --no-*
            "importance": "advanced",
        },
    )
    column_gap_threshold: float = field(
        default=DEFAULT_COLUMN_GAP_THRESHOLD,
        metadata={"help": "Minimum gap between columns in points", "type": float, "importance": "advanced"},
    )
    column_detection_mode: ColumnDetectionMode = field(
        default=DEFAULT_COLUMN_DETECTION_MODE,
        metadata={
            "help": "Column detection strategy: 'auto', 'force_single', 'force_multi', 'disabled'",
            "choices": ["auto", "force_single", "force_multi", "disabled"],
            "importance": "advanced",
        },
    )
    use_column_clustering: bool = field(
        default=DEFAULT_USE_COLUMN_CLUSTERING,
        metadata={
            "help": "Use k-means clustering for more robust column detection (alternative to gap heuristics)",
            "importance": "advanced",
        },
    )

    # Table detection parameters
    enable_table_fallback_detection: bool = field(
        default=DEFAULT_TABLE_FALLBACK_DETECTION,
        metadata={
            "help": "Use heuristic fallback if PyMuPDF table detection fails",
            "cli_name": "no-enable-table-fallback-detection",  # default=True, use --no-*
            "importance": "advanced",
        },
    )
    detect_merged_cells: bool = field(
        default=DEFAULT_DETECT_MERGED_CELLS,
        metadata={
            "help": "Attempt to identify merged cells in tables",
            "cli_name": "no-detect-merged-cells",  # default=True, use --no-*
            "importance": "advanced",
        },
    )
    table_ruling_line_threshold: float = field(
        default=DEFAULT_TABLE_RULING_LINE_THRESHOLD,
        metadata={
            "help": "Threshold for detecting table ruling lines (0.0-1.0)",
            "type": float,
            "importance": "advanced",
        },
    )
    table_fallback_extraction_mode: Literal["none", "grid", "text_clustering"] = field(
        default=DEFAULT_TABLE_FALLBACK_EXTRACTION_MODE,
        metadata={
            "help": "Table extraction mode for ruling line fallback: 'none', 'grid', 'text_clustering'",
            "choices": ["none", "grid", "text_clustering"],
            "importance": "advanced",
        },
    )

    image_placement_markers: bool = field(
        default=DEFAULT_IMAGE_PLACEMENT_MARKERS,
        metadata={
            "help": "Add markers showing image positions",
            "cli_name": "no-image-placement-markers",  # default=True, use --no-*
            "importance": "core",
        },
    )
    include_image_captions: bool = field(
        default=DEFAULT_INCLUDE_IMAGE_CAPTIONS,
        metadata={
            "help": "Try to extract image captions",
            "cli_name": "no-include-image-captions",  # default=True, use --no-*
            "importance": "core",
        },
    )

    # Page number display
    include_page_numbers: bool = field(
        default=DEFAULT_INCLUDE_PAGE_NUMBERS,
        metadata={"help": "Include page numbers in output (e.g., 'Page 1/10')", "importance": "core"},
    )

    # Table detection mode
    table_detection_mode: TableDetectionMode = field(
        default=DEFAULT_TABLE_DETECTION_MODE,
        metadata={
            "help": "Table detection strategy: 'pymupdf', 'ruling', 'both', or 'none'",
            "choices": ["pymupdf", "ruling", "both", "none"],
            "importance": "core",
        },
    )

    # Image format options
    image_format: ImageFormat = field(
        default=DEFAULT_IMAGE_FORMAT,
        metadata={
            "help": "Output format for extracted images: 'png' or 'jpeg'",
            "choices": ["png", "jpeg"],
            "importance": "advanced",
        },
    )
    image_quality: int = field(
        default=DEFAULT_IMAGE_QUALITY,
        metadata={
            "help": "JPEG quality (1-100, only used when image_format='jpeg')",
            "type": int,
            "importance": "advanced",
        },
    )

    # Header/footer trimming
    trim_headers_footers: bool = field(
        default=DEFAULT_TRIM_HEADERS_FOOTERS,
        metadata={"help": "Remove repeated headers and footers from pages", "importance": "core"},
    )
    auto_trim_headers_footers: bool = field(
        default=DEFAULT_AUTO_TRIM_HEADERS_FOOTERS,
        metadata={
            "help": (
                "Automatically detect and remove repeating headers/footers "
                "(overrides manual header_height/footer_height)"
            ),
            "importance": "advanced",
        },
    )
    header_height: int = field(
        default=DEFAULT_HEADER_HEIGHT,
        metadata={
            "help": "Height in points to trim from top of page (requires trim_headers_footers)",
            "type": int,
            "importance": "advanced",
        },
    )
    footer_height: int = field(
        default=DEFAULT_FOOTER_HEIGHT,
        metadata={
            "help": "Height in points to trim from bottom of page (requires trim_headers_footers)",
            "type": int,
            "importance": "advanced",
        },
    )

    # Link resolution options
    link_overlap_threshold: float = field(
        default=DEFAULT_LINK_OVERLAP_THRESHOLD,
        metadata={
            "help": (
                "Percentage overlap required for link detection (0-100). "
                "Lower values detect links with less overlap."
            ),
            "type": float,
            "importance": "advanced",
        },
    )

    # Performance optimization options
    skip_image_extraction: bool = field(
        default=False,
        metadata={
            "help": "Completely skip image extraction for text-only conversion (improves performance for large PDFs)",
            "importance": "advanced",
        },
    )
    lazy_image_processing: bool = field(
        default=False,
        metadata={
            "help": "Placeholder for future lazy image loading support. Note: Full implementation would require "
                    "paginator interface for streaming large PDFs. Currently has no effect.",
            "importance": "advanced",
        },
    )

    # OCR options
    ocr: OCROptions = field(
        default_factory=OCROptions,
        metadata={
            "help": "OCR settings for extracting text from scanned/image-based PDF pages",
            "cli_flatten": True,
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges and dependent field constraints.

        Raises
        ------
        ValueError
            If any field value is outside its valid range or if dependent
            field constraints are violated.

        """
        # Validate percentage-based thresholds (0-100)
        if not 0 <= self.header_percentile_threshold <= 100:
            raise ValueError(
                f"header_percentile_threshold must be in range [0, 100], " f"got {self.header_percentile_threshold}"
            )
        if not 0 <= self.link_overlap_threshold <= 100:
            raise ValueError(f"link_overlap_threshold must be in range [0, 100], " f"got {self.link_overlap_threshold}")

        # Validate quality settings (1-100)
        if not 1 <= self.image_quality <= 100:
            raise ValueError(f"image_quality must be in range [1, 100], " f"got {self.image_quality}")

        # Validate ratio thresholds (0.0-1.0)
        if not 0.0 <= self.table_ruling_line_threshold <= 1.0:
            raise ValueError(
                f"table_ruling_line_threshold must be in range [0.0, 1.0], " f"got {self.table_ruling_line_threshold}"
            )

        # Validate positive values
        if self.header_font_size_ratio <= 0:
            raise ValueError(f"header_font_size_ratio must be positive, " f"got {self.header_font_size_ratio}")
        if self.column_gap_threshold <= 0:
            raise ValueError(f"column_gap_threshold must be positive, " f"got {self.column_gap_threshold}")

        # Validate dependent fields: auto_trim vs manual trim settings
        if self.auto_trim_headers_footers and (self.header_height > 0 or self.footer_height > 0):
            import warnings

            warnings.warn(
                "auto_trim_headers_footers=True will override manual header_height and footer_height settings. "
                "The auto-detection algorithm will determine optimal trim values.",
                UserWarning,
                stacklevel=2,
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
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security settings for fetching remote images. By default,
        remote image fetching is disabled (allow_remote_fetch=False).
        Set network.allow_remote_fetch=True to enable secure remote image fetching
        with the same security guardrails as PPTX renderer.

    """

    page_size: PageSize = field(
        default=DEFAULT_PDF_PAGE_SIZE,
        metadata={
            "help": "Page size: letter, a4, or legal",
            "choices": ["letter", "a4", "legal"],
            "importance": "core",
        },
    )
    margin_top: float = field(
        default=DEFAULT_PDF_MARGIN,
        metadata={"help": "Top margin in points (72pt = 1 inch)", "type": float, "importance": "advanced"},
    )
    margin_bottom: float = field(
        default=DEFAULT_PDF_MARGIN,
        metadata={"help": "Bottom margin in points", "type": float, "importance": "advanced"},
    )
    margin_left: float = field(
        default=DEFAULT_PDF_MARGIN, metadata={"help": "Left margin in points", "type": float, "importance": "advanced"}
    )
    margin_right: float = field(
        default=DEFAULT_PDF_MARGIN, metadata={"help": "Right margin in points", "type": float, "importance": "advanced"}
    )

    font_name: str = field(
        default=DEFAULT_PDF_FONT_FAMILY,
        metadata={"help": "Default font (Helvetica, Times-Roman, Courier)", "importance": "core"},
    )
    font_size: int = field(
        default=DEFAULT_PDF_FONT_SIZE,
        metadata={"help": "Default font size in points", "type": int, "importance": "core"},
    )
    heading_fonts: dict[int, tuple[str, int]] | None = field(
        default=None,
        metadata={
            "help": 'Heading font specs as JSON (e.g., \'{"1": ["Helvetica-Bold", 24]}\')',
            "importance": "advanced",
        },
    )
    code_font: str = field(
        default=DEFAULT_PDF_CODE_FONT, metadata={"help": "Monospace font for code", "importance": "core"}
    )
    line_spacing: float = field(
        default=DEFAULT_PDF_LINE_SPACING,
        metadata={"help": "Line spacing multiplier (1.0 = single)", "type": float, "importance": "advanced"},
    )
    include_page_numbers: bool = field(
        default=True,
        metadata={"help": "Add page numbers to footer", "cli_name": "no-page-numbers", "importance": "core"},
    )
    include_toc: bool = field(default=False, metadata={"help": "Generate table of contents", "importance": "core"})
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote image fetching",
            "cli_flatten": True,  # Handled via flattened fields
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for PDF renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate positive line spacing
        if self.line_spacing <= 0:
            raise ValueError(f"line_spacing must be positive, got {self.line_spacing}")

        # Validate non-negative margins
        if self.margin_top < 0:
            raise ValueError(f"margin_top must be non-negative, got {self.margin_top}")
        if self.margin_bottom < 0:
            raise ValueError(f"margin_bottom must be non-negative, got {self.margin_bottom}")
        if self.margin_left < 0:
            raise ValueError(f"margin_left must be non-negative, got {self.margin_left}")
        if self.margin_right < 0:
            raise ValueError(f"margin_right must be non-negative, got {self.margin_right}")

        # Validate positive font size
        if self.font_size <= 0:
            raise ValueError(f"font_size must be positive, got {self.font_size}")
