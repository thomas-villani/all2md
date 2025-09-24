"""Configuration options and settings for all2md conversion modules.

This module provides dataclass-based configuration options for all conversion
modules in the all2md library. Using dataclasses provides type safety,
default values, and a clean API for configuring conversion behavior.

Each converter module has its own Options dataclass with module-specific
parameters, plus a shared MarkdownOptions class for common Markdown formatting
settings that apply across multiple converters.

Options Classes
---------------
- MarkdownOptions: Common Markdown formatting settings
- PdfOptions: PDF-specific conversion settings
- DocxOptions: Word document conversion settings
- HtmlOptions: HTML conversion settings
- PptxOptions: PowerPoint conversion settings
- EmlOptions: Email conversion settings
- Markdown2PdfOptions: Markdown-to-PDF conversion settings
- Markdown2DocxOptions: Markdown-to-Word conversion settings
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from dataclasses import dataclass

from .constants import (
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    # HTML-specific constants
    DEFAULT_BASE_URL,
    DEFAULT_BULLET_SYMBOLS,
    DEFAULT_COLUMN_GAP_THRESHOLD,
    DEFAULT_CONVERT_IMAGES_TO_BASE64,
    DEFAULT_DETECT_COLUMNS,
    DEFAULT_DETECT_MERGED_CELLS,
    DEFAULT_DOWNLOAD_IMAGES,
    DEFAULT_EMBED_IMAGES_AS_DATA_URI,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_EXTRACT_IMAGES,
    DEFAULT_EXTRACT_TITLE,
    DEFAULT_HANDLE_ROTATED_TEXT,
    # PDF-specific constants
    DEFAULT_HEADER_MIN_OCCURRENCES,
    DEFAULT_HEADER_PERCENTILE_THRESHOLD,
    DEFAULT_HEADER_USE_ALL_CAPS,
    DEFAULT_HEADER_USE_FONT_WEIGHT,
    DEFAULT_IMAGE_OUTPUT_DIR,
    DEFAULT_IMAGE_PLACEMENT_MARKERS,
    DEFAULT_INCLUDE_IMAGE_CAPTIONS,
    DEFAULT_INCLUDE_PAGE_NUMBERS,
    DEFAULT_LIST_INDENT_WIDTH,
    DEFAULT_MERGE_HYPHENATED_WORDS,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_PAGE_SEPARATOR_FORMAT,
    DEFAULT_PRESERVE_NBSP,
    DEFAULT_PRESERVE_NESTED_STRUCTURE,
    DEFAULT_REMOVE_IMAGES,
    DEFAULT_SLIDE_NUMBERS,
    DEFAULT_STRIP_DANGEROUS_ELEMENTS,
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
    DEFAULT_TABLE_FALLBACK_DETECTION,
    DEFAULT_TABLE_RULING_LINE_THRESHOLD,
    DEFAULT_USE_HASH_HEADINGS,
    AttachmentMode,
    EmphasisSymbol,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,
)


@dataclass
class MarkdownOptions:
    r"""Common Markdown formatting options used across conversion modules.

    This dataclass contains settings that control how Markdown output is
    formatted and structured. These options are used by multiple conversion
    modules to ensure consistent Markdown generation.

    Parameters
    ----------
    escape_special : bool, default True
        Whether to escape special Markdown characters in text content.
        When True, characters like *, _, #, [, ], (, ), \ are escaped
        to prevent unintended formatting.
    emphasis_symbol : {"*", "_"}, default "*"
        Symbol to use for emphasis/italic formatting in Markdown.
    bullet_symbols : str, default "*-+"
        Characters to cycle through for nested bullet lists.
    page_separator : str, default "-----"
        Text used to separate pages or sections in output.
    page_separator_format : str, default "-----"
        Format string for page separators. Can include {page_num} placeholder.
    include_page_numbers : bool, default False
        Whether to include page numbers in page separators.
    list_indent_width : int, default 4
        Number of spaces to use for each level of list indentation.
    underline_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle underlined text:
        - "html": Use <u>text</u> tags
        - "markdown": Use __text__ (non-standard)
        - "ignore": Strip underline formatting
    superscript_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle superscript text:
        - "html": Use <sup>text</sup> tags
        - "markdown": Use ^text^ (non-standard)
        - "ignore": Strip superscript formatting
    subscript_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle subscript text:
        - "html": Use <sub>text</sub> tags
        - "markdown": Use ~text~ (non-standard)
        - "ignore": Strip subscript formatting
    """

    escape_special: bool = DEFAULT_ESCAPE_SPECIAL
    emphasis_symbol: EmphasisSymbol = DEFAULT_EMPHASIS_SYMBOL
    bullet_symbols: str = DEFAULT_BULLET_SYMBOLS
    page_separator: str = DEFAULT_PAGE_SEPARATOR
    page_separator_format: str = DEFAULT_PAGE_SEPARATOR_FORMAT
    include_page_numbers: bool = DEFAULT_INCLUDE_PAGE_NUMBERS
    list_indent_width: int = DEFAULT_LIST_INDENT_WIDTH
    underline_mode: UnderlineMode = "html"
    superscript_mode: SuperscriptMode = "html"
    subscript_mode: SubscriptMode = "html"


@dataclass
class PdfOptions:
    """Configuration options for PDF-to-Markdown conversion.

    This dataclass contains settings specific to PDF document processing,
    including page selection, image handling, and formatting preferences.

    Parameters
    ----------
    pages : list[int] or None, default None
        Specific page numbers to convert (0-based indexing).
        If None, converts all pages.
    convert_images_to_base64 : bool, default False
        Whether to embed images as base64-encoded data URLs.
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
    table_fallback_detection : bool, default True
        Use heuristic fallback if PyMuPDF table detection fails.
    detect_merged_cells : bool, default True
        Attempt to identify merged cells in tables.
    table_ruling_line_threshold : float, default 0.5
        Threshold for detecting table ruling lines.

    # Image extraction parameters (deprecated - use attachment_mode)
    extract_images : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Extract images from PDF.
    image_output_dir : str | None, default None
        **Deprecated**: Use attachment_output_dir instead.
        Directory to save extracted images.
    image_placement_markers : bool, default True
        Add markers showing image positions.
    include_image_captions : bool, default True
        Try to extract image captions.

    # Unified attachment handling
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "alt_text"
        How to handle attachments (images):
        - "skip": Remove attachments completely
        - "alt_text": Use alt-text or filename references
        - "download": Save to folder and reference with links
        - "base64": Embed as base64 data URIs
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.

    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert only pages 1-3 with base64 images:
        >>> options = PdfOptions(pages=[0, 1, 2], convert_images_to_base64=True)

    Convert with custom Markdown formatting:
        >>> md_opts = MarkdownOptions(emphasis_symbol="_", page_separator="---")
        >>> options = PdfOptions(markdown_options=md_opts)

    Configure header detection:
        >>> options = PdfOptions(
        ...     header_sample_pages=[0, 1, 2],
        ...     header_percentile_threshold=80,
        ...     header_use_all_caps=True
        ... )
    """

    pages: list[int] | None = None
    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    password: str | None = None

    # Header detection parameters
    header_sample_pages: int | list[int] | None = None
    header_percentile_threshold: float = DEFAULT_HEADER_PERCENTILE_THRESHOLD
    header_min_occurrences: int = DEFAULT_HEADER_MIN_OCCURRENCES
    header_size_allowlist: list[float] | None = None
    header_size_denylist: list[float] | None = None
    header_use_font_weight: bool = DEFAULT_HEADER_USE_FONT_WEIGHT
    header_use_all_caps: bool = DEFAULT_HEADER_USE_ALL_CAPS

    # Reading order and layout parameters
    detect_columns: bool = DEFAULT_DETECT_COLUMNS
    merge_hyphenated_words: bool = DEFAULT_MERGE_HYPHENATED_WORDS
    handle_rotated_text: bool = DEFAULT_HANDLE_ROTATED_TEXT
    column_gap_threshold: float = DEFAULT_COLUMN_GAP_THRESHOLD

    # Table detection parameters
    table_fallback_detection: bool = DEFAULT_TABLE_FALLBACK_DETECTION
    detect_merged_cells: bool = DEFAULT_DETECT_MERGED_CELLS
    table_ruling_line_threshold: float = DEFAULT_TABLE_RULING_LINE_THRESHOLD

    # Image extraction parameters (deprecated - use attachment_mode)
    extract_images: bool = DEFAULT_EXTRACT_IMAGES
    image_output_dir: str | None = DEFAULT_IMAGE_OUTPUT_DIR
    image_placement_markers: bool = DEFAULT_IMAGE_PLACEMENT_MARKERS
    include_image_captions: bool = DEFAULT_INCLUDE_IMAGE_CAPTIONS

    # Unified attachment handling
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL

    markdown_options: MarkdownOptions | None = None


@dataclass
class DocxOptions:
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

    Parameters
    ----------
    convert_images_to_base64 : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Whether to embed images as base64-encoded data URLs.
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "alt_text"
        How to handle attachments (images):
        - "skip": Remove attachments completely
        - "alt_text": Use alt-text or filename references
        - "download": Save to folder and reference with links
        - "base64": Embed as base64 data URIs
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with base64 image embedding:
        >>> options = DocxOptions(convert_images_to_base64=True)

    Convert with custom bullet symbols:
        >>> md_opts = MarkdownOptions(bullet_symbols="•→◦")
        >>> options = DocxOptions(markdown_options=md_opts)
    """

    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    preserve_tables: bool = True
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL
    markdown_options: MarkdownOptions | None = None


@dataclass
class HtmlOptions:
    """Configuration options for HTML-to-Markdown conversion.

    This dataclass contains settings specific to HTML document processing,
    including heading styles, title extraction, image handling, content
    sanitization, and advanced formatting options.

    Parameters
    ----------
    use_hash_headings : bool, default True
        Whether to use # syntax for headings instead of underline style.
    extract_title : bool, default False
        Whether to extract and use the HTML <title> element.
    remove_images : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Whether to completely remove images from the output.
    base_url : str or None, default None
        **Deprecated**: Use attachment_base_url instead.
        Base URL for converting relative image/link URLs to absolute URLs.
    download_images : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Whether to download images and embed them as data URIs.
    embed_images_as_data_uri : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Whether to convert image sources to data URI format.
    preserve_nbsp : bool, default False
        Whether to preserve non-breaking spaces (&nbsp;) in the output.
    strip_dangerous_elements : bool, default False
        Whether to remove potentially dangerous HTML elements (script, style, etc.).
    table_alignment_auto_detect : bool, default True
        Whether to automatically detect table column alignment from CSS/attributes.
    preserve_nested_structure : bool, default True
        Whether to maintain proper nesting for blockquotes and other elements.
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "alt_text"
        How to handle attachments (images):
        - "skip": Remove attachments completely
        - "alt_text": Use alt-text or filename references
        - "download": Save to folder and reference with links
        - "base64": Embed as base64 data URIs
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with underline-style headings:
        >>> options = HtmlOptions(use_hash_headings=False)

    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True, remove_images=True)

    Convert with image download and base URL resolution:
        >>> options = HtmlOptions(base_url="https://example.com", download_images=True)

    Convert with content sanitization:
        >>> options = HtmlOptions(strip_dangerous_elements=True, preserve_nbsp=True)
    """

    use_hash_headings: bool = DEFAULT_USE_HASH_HEADINGS
    extract_title: bool = DEFAULT_EXTRACT_TITLE
    remove_images: bool = DEFAULT_REMOVE_IMAGES
    base_url: str | None = DEFAULT_BASE_URL
    download_images: bool = DEFAULT_DOWNLOAD_IMAGES
    embed_images_as_data_uri: bool = DEFAULT_EMBED_IMAGES_AS_DATA_URI
    preserve_nbsp: bool = DEFAULT_PRESERVE_NBSP
    strip_dangerous_elements: bool = DEFAULT_STRIP_DANGEROUS_ELEMENTS
    table_alignment_auto_detect: bool = DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT
    preserve_nested_structure: bool = DEFAULT_PRESERVE_NESTED_STRUCTURE
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL
    markdown_options: MarkdownOptions | None = None


@dataclass
class PptxOptions:
    """Configuration options for PPTX-to-Markdown conversion.

    This dataclass contains settings specific to PowerPoint presentation
    processing, including slide numbering and image handling.

    Parameters
    ----------
    convert_images_to_base64 : bool, default False
        **Deprecated**: Use attachment_mode instead.
        Whether to embed images as base64-encoded data URLs.
    slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "alt_text"
        How to handle attachments (images):
        - "skip": Remove attachments completely
        - "alt_text": Use alt-text or filename references
        - "download": Save to folder and reference with links
        - "base64": Embed as base64 data URIs
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(slide_numbers=True, convert_images_to_base64=True)

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)
    """

    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    slide_numbers: bool = DEFAULT_SLIDE_NUMBERS
    include_notes: bool = True
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL
    markdown_options: MarkdownOptions | None = None


@dataclass
class EmlOptions:
    """Configuration options for EML-to-Markdown conversion.

    This dataclass contains settings specific to email message processing,
    including thread handling and header extraction.

    Parameters
    ----------
    include_headers : bool, default True
        Whether to include email headers (From, To, Subject, Date) in output.
    include_attachments_info : bool, default True
        **Deprecated**: Use attachment_mode instead.
        Whether to include attachment information in the output.
    preserve_thread_structure : bool, default True
        Whether to maintain email thread/reply chain structure.
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "alt_text"
        How to handle attachments (images and files):
        - "skip": Remove attachments completely
        - "alt_text": Use alt-text for images, filename for files
        - "download": Save to folder and reference with links
        - "base64": Embed as base64 data URIs (images only)
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert email with minimal headers:
        >>> options = EmlOptions(include_headers=True, include_attachments_info=False)

    Convert as flat list (no thread structure):
        >>> options = EmlOptions(preserve_thread_structure=False)
    """

    include_headers: bool = True
    include_attachments_info: bool = True
    preserve_thread_structure: bool = True
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL
    markdown_options: MarkdownOptions | None = None

