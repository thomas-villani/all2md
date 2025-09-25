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
from __future__ import annotations

import abc

from dataclasses import dataclass, field

from .constants import (
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    # HTML-specific constants
    DEFAULT_BULLET_SYMBOLS,
    DEFAULT_COLUMN_GAP_THRESHOLD,
    DEFAULT_DETECT_COLUMNS,
    DEFAULT_DETECT_MERGED_CELLS,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_EXTRACT_TITLE,
    DEFAULT_HANDLE_ROTATED_TEXT,
    # PDF-specific constants
    DEFAULT_HEADER_MIN_OCCURRENCES,
    DEFAULT_HEADER_PERCENTILE_THRESHOLD,
    DEFAULT_HEADER_USE_ALL_CAPS,
    DEFAULT_HEADER_USE_FONT_WEIGHT,
    DEFAULT_IMAGE_PLACEMENT_MARKERS,
    DEFAULT_INCLUDE_IMAGE_CAPTIONS,
    DEFAULT_INCLUDE_PAGE_NUMBERS,
    DEFAULT_LIST_INDENT_WIDTH,
    DEFAULT_MERGE_HYPHENATED_WORDS,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_PAGE_SEPARATOR_FORMAT,
    DEFAULT_PRESERVE_NBSP,
    DEFAULT_PRESERVE_NESTED_STRUCTURE,
    DEFAULT_SLIDE_NUMBERS,
    DEFAULT_STRIP_DANGEROUS_ELEMENTS,
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
    DEFAULT_TABLE_FALLBACK_DETECTION,
    DEFAULT_TABLE_RULING_LINE_THRESHOLD,
    DEFAULT_USE_HASH_HEADINGS,
    # Email-specific constants
    DEFAULT_CLEAN_QUOTES,
    DEFAULT_CLEAN_WRAPPED_URLS,
    DEFAULT_CONVERT_HTML_TO_MARKDOWN,
    DEFAULT_DATE_FORMAT_MODE,
    DEFAULT_DATE_STRFTIME_PATTERN,
    DEFAULT_DETECT_REPLY_SEPARATORS,
    DEFAULT_NORMALIZE_HEADERS,
    DEFAULT_PRESERVE_RAW_HEADERS,
    DEFAULT_URL_WRAPPERS,
    AttachmentMode,
    DateFormatMode,
    EmphasisSymbol,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,

    DEFAULT_TRUNCATE_OUTPUT_LINES,
    DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
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
class BaseOptions(abc.ABC):
    attachment_mode: AttachmentMode = DEFAULT_ATTACHMENT_MODE
    attachment_output_dir: str | None = DEFAULT_ATTACHMENT_OUTPUT_DIR
    attachment_base_url: str | None = DEFAULT_ATTACHMENT_BASE_URL
    markdown_options: MarkdownOptions | None = None

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


@dataclass
class PdfOptions(BaseOptions):
    """Configuration options for PDF-to-Markdown conversion.

    This dataclass contains settings specific to PDF document processing,
    including page selection, image handling, and formatting preferences.

    Parameters
    ----------
    pages : list[int] or None, default None
        Specific page numbers to convert (0-based indexing).
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
        >>> options = PdfOptions(pages=[0, 1, 2], attachment_mode="base64")

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

    image_placement_markers: bool = DEFAULT_IMAGE_PLACEMENT_MARKERS
    include_image_captions: bool = DEFAULT_INCLUDE_IMAGE_CAPTIONS


@dataclass
class DocxOptions(BaseOptions):
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

    Parameters
    ----------
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
        >>> options = DocxOptions(attachment_mode="base64")

    Convert with custom bullet symbols:
        >>> md_opts = MarkdownOptions(bullet_symbols="•→◦")
        >>> options = DocxOptions(markdown_options=md_opts)
    """

    preserve_tables: bool = True


@dataclass
class HtmlOptions(BaseOptions):
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
    preserve_nbsp: bool = DEFAULT_PRESERVE_NBSP
    strip_dangerous_elements: bool = DEFAULT_STRIP_DANGEROUS_ELEMENTS
    table_alignment_auto_detect: bool = DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT
    preserve_nested_structure: bool = DEFAULT_PRESERVE_NESTED_STRUCTURE


@dataclass
class PptxOptions(BaseOptions):
    """Configuration options for PPTX-to-Markdown conversion.

    This dataclass contains settings specific to PowerPoint presentation
    processing, including slide numbering and image handling.

    Parameters
    ----------
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
        >>> options = PptxOptions(slide_numbers=True, attachment_mode="base64")

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)
    """

    slide_numbers: bool = DEFAULT_SLIDE_NUMBERS
    include_notes: bool = True


@dataclass
class EmlOptions(BaseOptions):
    """Configuration options for EML-to-Markdown conversion.

    This dataclass contains settings specific to email message processing,
    including robust parsing, date handling, quote processing, and URL cleaning.

    Parameters
    ----------
    include_headers : bool, default True
        Whether to include email headers (From, To, Subject, Date) in output.
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
    date_format_mode : {"iso8601", "locale", "strftime"}, default "strftime"
        How to format dates in output:
        - "iso8601": Use ISO 8601 format (2023-01-01T10:00:00Z)
        - "locale": Use system locale-aware formatting
        - "strftime": Use custom strftime pattern
    date_strftime_pattern : str, default "%m/%d/%y %H:%M"
        Custom strftime pattern when date_format_mode is "strftime".
    convert_html_to_markdown : bool, default False
        Whether to convert HTML content to Markdown using html2markdown.
        When True, HTML parts are converted to Markdown; when False, HTML is preserved as-is.
    clean_quotes : bool, default True
        Whether to clean and normalize quoted content ("> " prefixes, etc.).
    detect_reply_separators : bool, default True
        Whether to detect common reply separators like "On <date>, <name> wrote:".
    normalize_headers : bool, default True
        Whether to normalize header casing and whitespace.
    preserve_raw_headers : bool, default False
        Whether to preserve both raw and decoded header values.
    clean_wrapped_urls : bool, default True
        Whether to clean URL defense/safety wrappers from links.
    url_wrappers : list[str], default from constants
        List of URL wrapper domains to clean (urldefense.com, safelinks, etc.).
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert email with ISO 8601 date formatting:
        >>> options = EmlOptions(date_format_mode="iso8601")

    Convert with HTML-to-Markdown conversion enabled:
        >>> options = EmlOptions(convert_html_to_markdown=True)

    Disable quote cleaning and URL unwrapping:
        >>> options = EmlOptions(clean_quotes=False, clean_wrapped_urls=False)
    """

    include_headers: bool = True
    preserve_thread_structure: bool = True
    date_format_mode: DateFormatMode = DEFAULT_DATE_FORMAT_MODE
    date_strftime_pattern: str = DEFAULT_DATE_STRFTIME_PATTERN
    convert_html_to_markdown: bool = DEFAULT_CONVERT_HTML_TO_MARKDOWN
    clean_quotes: bool = DEFAULT_CLEAN_QUOTES
    detect_reply_separators: bool = DEFAULT_DETECT_REPLY_SEPARATORS
    normalize_headers: bool = DEFAULT_NORMALIZE_HEADERS
    preserve_raw_headers: bool = DEFAULT_PRESERVE_RAW_HEADERS
    clean_wrapped_urls: bool = DEFAULT_CLEAN_WRAPPED_URLS
    url_wrappers: list[str] | None = field(default_factory=lambda: DEFAULT_URL_WRAPPERS.copy())


@dataclass
class RtfOptions(BaseOptions):
    """Configuration options for RTF-to-Markdown conversion.

    This dataclass contains settings specific to Rich Text Format processing,
    primarily for handling embedded images and other attachments.

    Parameters
    ----------
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
    """
    pass



@dataclass
class IpynbOptions(BaseOptions):
    """Configuration options for IPYNB-to-Markdown conversion.

    This dataclass contains settings specific to Jupyter Notebook processing,
    including output handling and image conversion preferences.

    Parameters
    ----------
    truncate_long_outputs : int or None, default DEFAULT_COLLAPSE_OUTPUT_LINES
        Maximum number of lines for text outputs before collapsing.
        If None, outputs are not collapsed.
    truncate_output_message : str or None, default = DEFAULT_COLLAPSE_OUTPUT_MESSAGE
        The message to place to indicate truncated message.
    attachment_mode : {"skip", "alt_text", "download", "base64"}, default "base64"
        How to handle image outputs:
        - "skip": Remove images completely.
        - "alt_text": Use alt-text placeholders (e.g., "![cell output]").
        - "download": Save to a folder and link to the files.
        - "base64": Embed images as base64 data URIs (default for notebooks).
    attachment_output_dir : str | None, default None
        Directory to save attachments when using "download" mode.
    attachment_base_url : str | None, default None
        Base URL for resolving relative attachment URLs.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.
    """

    truncate_long_outputs: int | None = DEFAULT_TRUNCATE_OUTPUT_LINES
    truncate_output_message: str | None = DEFAULT_TRUNCATE_OUTPUT_MESSAGE
