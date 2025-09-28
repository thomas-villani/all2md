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

from dataclasses import dataclass, field, replace
from typing import Any, Optional, Self, Union

from .constants import (
    DEFAULT_ALLOW_CWD_FILES,
    DEFAULT_ALLOW_LOCAL_FILES,
    DEFAULT_ALLOW_REMOTE_FETCH,
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALT_TEXT_MODE,
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    # HTML-specific constants
    DEFAULT_BULLET_SYMBOLS,
    # Email-specific constants
    DEFAULT_CLEAN_QUOTES,
    DEFAULT_CLEAN_WRAPPED_URLS,
    DEFAULT_COLUMN_GAP_THRESHOLD,
    DEFAULT_CONVERT_HTML_TO_MARKDOWN,
    DEFAULT_CONVERT_NBSP,
    DEFAULT_DATE_FORMAT_MODE,
    DEFAULT_DATE_STRFTIME_PATTERN,
    DEFAULT_DETECT_COLUMNS,
    DEFAULT_DETECT_MERGED_CELLS,
    DEFAULT_DETECT_REPLY_SEPARATORS,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_EXTRACT_METADATA,
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
    DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
    DEFAULT_MAX_DOWNLOAD_BYTES,
    DEFAULT_MAX_IMAGE_SIZE_BYTES,
    DEFAULT_MERGE_HYPHENATED_WORDS,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_NORMALIZE_HEADERS,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_PAGE_SEPARATOR_FORMAT,
    DEFAULT_PRESERVE_NESTED_STRUCTURE,
    DEFAULT_PRESERVE_RAW_HEADERS,
    DEFAULT_REQUIRE_HTTPS,
    DEFAULT_SLIDE_NUMBERS,
    DEFAULT_STRIP_DANGEROUS_ELEMENTS,
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
    DEFAULT_TABLE_FALLBACK_DETECTION,
    DEFAULT_TABLE_RULING_LINE_THRESHOLD,
    DEFAULT_TRUNCATE_OUTPUT_LINES,
    DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
    DEFAULT_URL_WRAPPERS,
    DEFAULT_USE_HASH_HEADINGS,
    AltTextMode,
    AttachmentMode,
    DateFormatMode,
    EmphasisSymbol,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,
)


class _CloneMixin:
    def create_updated(self, **kwargs) -> Self:
        return replace(self, **kwargs)  # type: ignore


@dataclass(frozen=True)
class MarkdownOptions(_CloneMixin):
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

    escape_special: bool = field(
        default=DEFAULT_ESCAPE_SPECIAL,
        metadata={
            "help": "Escape special Markdown characters in text content",
            "cli_name": "no-escape-special"  # Since default=True, use --no-* flag
        }
    )
    emphasis_symbol: EmphasisSymbol = field(
        default=DEFAULT_EMPHASIS_SYMBOL,
        metadata={
            "help": "Symbol to use for emphasis/italic formatting",
            "choices": ["*", "_"]
        }
    )
    bullet_symbols: str = field(
        default=DEFAULT_BULLET_SYMBOLS,
        metadata={"help": "Characters to cycle through for nested bullet lists"}
    )
    page_separator: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={"help": "Text used to separate pages or sections in output"}
    )
    page_separator_format: str = field(
        default=DEFAULT_PAGE_SEPARATOR_FORMAT,
        metadata={"help": "Format string for page separators (can include {page_num})"}
    )
    include_page_numbers: bool = field(
        default=DEFAULT_INCLUDE_PAGE_NUMBERS,
        metadata={"help": "Include page numbers in page separators"}
    )
    list_indent_width: int = field(
        default=DEFAULT_LIST_INDENT_WIDTH,
        metadata={
            "help": "Number of spaces to use for each level of list indentation",
            "type": int
        }
    )
    underline_mode: UnderlineMode = field(
        default="html",
        metadata={
            "help": "How to handle underlined text",
            "choices": ["html", "markdown", "ignore"]
        }
    )
    superscript_mode: SuperscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle superscript text",
            "choices": ["html", "markdown", "ignore"]
        }
    )
    subscript_mode: SubscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle subscript text",
            "choices": ["html", "markdown", "ignore"]
        }
    )


@dataclass(frozen=True)
class BaseOptions(_CloneMixin):
    attachment_mode: AttachmentMode = field(
        default=DEFAULT_ATTACHMENT_MODE,
        metadata={
            "help": "How to handle attachments/images",
            "choices": ["skip", "alt_text", "download", "base64"]
        }
    )
    alt_text_mode: AltTextMode = field(
        default=DEFAULT_ALT_TEXT_MODE,
        metadata={
            "help": "How to render alt-text content when using alt_text attachment mode",
            "choices": ["default", "plain_filename", "strict_markdown", "footnote"]
        }
    )
    attachment_output_dir: str | None = field(
        default=DEFAULT_ATTACHMENT_OUTPUT_DIR,
        metadata={"help": "Directory to save attachments when using download mode"}
    )
    attachment_base_url: str | None = field(
        default=DEFAULT_ATTACHMENT_BASE_URL,
        metadata={"help": "Base URL for resolving attachment references"}
    )
    extract_metadata: bool = field(
        default=DEFAULT_EXTRACT_METADATA,
        metadata={"help": "Extract document metadata as YAML front matter"}
    )
    markdown_options: MarkdownOptions | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Special field, handled separately
    )
    max_download_bytes: int = field(
        default=DEFAULT_MAX_DOWNLOAD_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single download",
            "type": int
        }
    )


@dataclass(frozen=True)
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

    pages: list[int] | None = field(
        default=None,
        metadata={
            "help": "Specific pages to convert (comma-separated, 0-based indexing)",
            "type": "list_int"
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
    table_fallback_detection: bool = field(
        default=DEFAULT_TABLE_FALLBACK_DETECTION,
        metadata={
            "help": "Use heuristic fallback if PyMuPDF table detection fails",
            "cli_name": "no-table-fallback-detection"  # default=True, use --no-*
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


@dataclass(frozen=True)
class DocxOptions(BaseOptions):
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.

    Examples
    --------
    Convert with base64 image embedding:
        >>> options = DocxOptions(attachment_mode="base64")

    Convert with custom bullet symbols:
        >>> md_opts = MarkdownOptions(bullet_symbols="•→◦")
        >>> options = DocxOptions(markdown_options=md_opts)
    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )


@dataclass(frozen=True)
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
    convert_nbsp : bool, default False
        Whether to convert non-breaking spaces (&nbsp;) to regular spaces in the output.
    strip_dangerous_elements : bool, default False
        Whether to remove potentially dangerous HTML elements (script, style, etc.).
    table_alignment_auto_detect : bool, default True
        Whether to automatically detect table column alignment from CSS/attributes.
    preserve_nested_structure : bool, default True
        Whether to maintain proper nesting for blockquotes and other elements.

    Examples
    --------
    Convert with underline-style headings:
        >>> options = HtmlOptions(use_hash_headings=False)

    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True, remove_images=True)

    Convert with image download and base URL resolution:
        >>> options = HtmlOptions(base_url="https://example.com", download_images=True)

    Convert with content sanitization:
        >>> options = HtmlOptions(strip_dangerous_elements=True, convert_nbsp=True)
    """

    use_hash_headings: bool = field(
        default=DEFAULT_USE_HASH_HEADINGS,
        metadata={
            "help": "Use # syntax for headings instead of underline style",
            "cli_name": "no-use-hash-headings"  # default=True, use --no-*
        }
    )
    extract_title: bool = field(
        default=DEFAULT_EXTRACT_TITLE,
        metadata={"help": "Extract and use HTML <title> element as main heading"}
    )
    convert_nbsp: bool = field(
        default=DEFAULT_CONVERT_NBSP,
        metadata={"help": "Convert non-breaking spaces (&nbsp;) to regular spaces"}
    )
    strip_dangerous_elements: bool = field(
        default=DEFAULT_STRIP_DANGEROUS_ELEMENTS,
        metadata={"help": "Remove potentially dangerous HTML elements (script, style, etc.)"}
    )
    table_alignment_auto_detect: bool = field(
        default=DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
        metadata={
            "help": "Automatically detect table column alignment from CSS/attributes",
            "cli_name": "no-table-alignment-auto-detect"  # default=True, use --no-*
        }
    )

    # Network security options
    allow_remote_fetch: bool = field(
        default=DEFAULT_ALLOW_REMOTE_FETCH,
        metadata={
            "help": "Allow fetching remote URLs for images (base64/download modes). "
                    "When False, prevents SSRF attacks by blocking all network requests."
        }
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching. "
                    "If specified, only URLs from these hosts will be fetched."
        }
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={"help": "Require HTTPS for all remote URL fetching"}
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={
            "help": "Timeout in seconds for remote URL fetching",
            "type": float
        }
    )
    max_image_size_bytes: int = field(
        default=DEFAULT_MAX_IMAGE_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for downloaded images",
            "type": int
        }
    )
    preserve_nested_structure: bool = field(
        default=DEFAULT_PRESERVE_NESTED_STRUCTURE,
        metadata={
            "help": "Maintain proper nesting for blockquotes and other elements",
            "cli_name": "no-preserve-nested-structure"  # default=True, use --no-*
        }
    )
    allow_local_files: bool = field(
        default=DEFAULT_ALLOW_LOCAL_FILES,
        metadata={"help": "Allow access to local files via file:// URLs (security setting)"}
    )
    local_file_allowlist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories allowed for local file access (when allow_local_files=True)",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    local_file_denylist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories denied for local file access",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    allow_cwd_files: bool = field(
        default=DEFAULT_ALLOW_CWD_FILES,
        metadata={
            "help": "Allow local files from current working directory and subdirectories",
            "cli_name": "no-allow-cwd-files"  # default=True, use --no-*
        }
    )


@dataclass(frozen=True)
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

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(slide_numbers=True, attachment_mode="base64")

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)
    """

    slide_numbers: bool = field(
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


@dataclass(frozen=True)
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

    Examples
    --------
    Convert email with ISO 8601 date formatting:
        >>> options = EmlOptions(date_format_mode="iso8601")

    Convert with HTML-to-Markdown conversion enabled:
        >>> options = EmlOptions(convert_html_to_markdown=True)

    Disable quote cleaning and URL unwrapping:
        >>> options = EmlOptions(clean_quotes=False, clean_wrapped_urls=False)
    """

    include_headers: bool = field(
        default=True,
        metadata={
            "help": "Include email headers (From, To, Subject, Date) in output",
            "cli_name": "no-include-headers"
        }
    )
    preserve_thread_structure: bool = field(
        default=True,
        metadata={
            "help": "Maintain email thread/reply chain structure",
            "cli_name": "no-preserve-thread-structure"
        }
    )
    date_format_mode: DateFormatMode = field(
        default=DEFAULT_DATE_FORMAT_MODE,
        metadata={"help": "Date formatting mode: iso8601, locale, or strftime"}
    )
    date_strftime_pattern: str = field(
        default=DEFAULT_DATE_STRFTIME_PATTERN,
        metadata={"help": "Custom strftime pattern for date formatting"}
    )
    convert_html_to_markdown: bool = field(
        default=DEFAULT_CONVERT_HTML_TO_MARKDOWN,
        metadata={"help": "Convert HTML content to Markdown"}
    )
    clean_quotes: bool = field(
        default=DEFAULT_CLEAN_QUOTES,
        metadata={"help": "Clean and normalize quoted content"}
    )
    detect_reply_separators: bool = field(
        default=DEFAULT_DETECT_REPLY_SEPARATORS,
        metadata={"help": "Detect common reply separators"}
    )
    normalize_headers: bool = field(
        default=DEFAULT_NORMALIZE_HEADERS,
        metadata={"help": "Normalize header casing and whitespace"}
    )
    preserve_raw_headers: bool = field(
        default=DEFAULT_PRESERVE_RAW_HEADERS,
        metadata={"help": "Preserve both raw and decoded header values"}
    )
    clean_wrapped_urls: bool = field(
        default=DEFAULT_CLEAN_WRAPPED_URLS,
        metadata={"help": "Clean URL defense/safety wrappers from links"}
    )
    url_wrappers: list[str] | None = field(default_factory=lambda: DEFAULT_URL_WRAPPERS.copy())

    # Network security options (inherited by HTML conversion when enabled)
    allow_remote_fetch: bool = field(
        default=DEFAULT_ALLOW_REMOTE_FETCH,
        metadata={
            "help": "Allow fetching remote URLs when converting HTML parts to Markdown. "
                    "Only applies when convert_html_to_markdown=True."
        }
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching in HTML parts."
        }
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={"help": "Require HTTPS for remote URL fetching in HTML parts"}
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={
            "help": "Timeout in seconds for remote URL fetching in HTML parts",
            "type": float
        }
    )
    max_image_size_bytes: int = field(
        default=DEFAULT_MAX_IMAGE_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for downloaded images in HTML parts",
            "type": int
        }
    )
    max_attachment_size_bytes: int = field(
        default=DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for email attachments",
            "type": int
        }
    )


@dataclass(frozen=True)
class RtfOptions(BaseOptions):
    """Configuration options for RTF-to-Markdown conversion.

    This dataclass contains settings specific to Rich Text Format processing,
    primarily for handling embedded images and other attachments.

    Parameters
    ----------
    Inherited from `BaseOptions`
    """
    pass


@dataclass(frozen=True)
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
    """

    truncate_long_outputs: int | None = DEFAULT_TRUNCATE_OUTPUT_LINES
    truncate_output_message: str | None = DEFAULT_TRUNCATE_OUTPUT_MESSAGE


@dataclass(frozen=True)
class OdfOptions(BaseOptions):
    """Configuration options for ODF-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument (ODT, ODP)
    processing, including image handling and table preservation.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )


@dataclass(frozen=True)
class EpubOptions(BaseOptions):
    """Configuration options for EPUB-to-Markdown conversion.

    This dataclass contains settings specific to EPUB document processing,
    including chapter handling, table of contents generation, and image handling.

    Parameters
    ----------
    merge_chapters : bool, default True
        Whether to merge chapters into a single continuous document. If False,
        a separator is placed between chapters.
    include_toc : bool, default True
        Whether to generate and prepend a Markdown Table of Contents.
    """

    merge_chapters: bool = field(
        default=True,
        metadata={
            "help": "Merge chapters into a single continuous document",
            "cli_name": "no-merge-chapters"
        }
    )
    include_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate and prepend a Markdown Table of Contents",
            "cli_name": "no-include-toc"
        }
    )


@dataclass(frozen=True)
class MhtmlOptions(BaseOptions):
    """Configuration options for MHTML-to-Markdown conversion.

    This dataclass contains settings specific to MHTML file processing,
    primarily for handling embedded assets like images and local file security.

    Parameters
    ----------
    allow_local_files : bool, default False
        Allow access to local files via file:// URLs (security setting).
    local_file_allowlist : list[str] | None, default None
        List of directories allowed for local file access (when allow_local_files=True).
    local_file_denylist : list[str] | None, default None
        List of directories denied for local file access.
    allow_cwd_files : bool, default True
        Allow local files from current working directory and subdirectories.

    Other Parameters
    ----------------
    Inherited from BaseOptions
    """

    allow_local_files: bool = field(
        default=DEFAULT_ALLOW_LOCAL_FILES,
        metadata={"help": "Allow access to local files via file:// URLs (security setting)"}
    )
    local_file_allowlist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories allowed for local file access (when allow_local_files=True)",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    local_file_denylist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories denied for local file access",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    allow_cwd_files: bool = field(
        default=DEFAULT_ALLOW_CWD_FILES,
        metadata={
            "help": "Allow local files from current working directory and subdirectories",
            "cli_name": "no-allow-cwd-files"  # default=True, use --no-*
        }
    )


@dataclass(frozen=True)
class SpreadsheetOptions(BaseOptions):
    """Configuration options for Spreadsheet (XLSX/CSV/TSV) to Markdown conversion.

    Parameters
    ----------
    sheets : list[str] | str | None, default None
        For XLSX: list of exact sheet names to include or a regex pattern.
        If None, includes all sheets.
    include_sheet_titles : bool, default True
        Prepend each sheet with a '## {sheet_name}' heading.
    render_formulas : bool, default True
        For XLSX: when True, uses stored values (data_only=True). When False, shows formulas.
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    detect_csv_dialect : bool, default True
        For CSV/TSV: enable csv.Sniffer-based dialect detection (ignored if force delimiter).
    markdown_options : MarkdownOptions | None, default None
        Shared markdown formatting options.
    attachment_mode : AttachmentMode, default "alt_text"
        Reserved for future XLSX-embedded images (not currently extracted).
    attachment_output_dir : str | None, default None
        Directory for download mode (future use).
    attachment_base_url : str | None, default None
        Base URL for download mode (future use).
    """
    sheets: Union[list[str], str, None] = None
    include_sheet_titles: bool = True

    # XLSX-specific
    render_formulas: bool = True

    # Truncation
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."

    # CSV/TSV parsing
    detect_csv_dialect: bool = True


def create_updated_options(options: Any, **kwargs) -> Any:
    """Create a new options instance with updated values.

    This helper function supports the immutable pattern for frozen dataclasses.
    It creates a new instance of the options with the specified fields updated,
    rather than modifying the existing instance.

    Parameters
    ----------
    options : Any
        The original options instance (must be a dataclass)
    **kwargs
        Keyword arguments with the field names and new values to update

    Returns
    -------
    Any
        A new options instance with the updated values

    Examples
    --------
    >>> original = PdfOptions(pages=[1, 2, 3])
    >>> updated = create_updated_options(original, attachment_mode="base64", pages=[1])
    >>> # original remains unchanged, updated has new values
    """
    return replace(options, **kwargs)
