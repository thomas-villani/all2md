#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/common.py
"""Common options shared across multiple parsers and renderers.

This module defines options for file access, network operations, and other
cross-cutting concerns used throughout the conversion pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ALLOW_CWD_FILES,
    DEFAULT_ALLOW_LOCAL_FILES,
    DEFAULT_ALLOW_REMOTE_FETCH,
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALT_TEXT_MODE,
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_DEDUPLICATE_BY_HASH,
    DEFAULT_ATTACHMENT_FILENAME_TEMPLATE,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    DEFAULT_ATTACHMENT_OVERWRITE,
    DEFAULT_ATTACHMENTS_FOOTNOTES_SECTION,
    DEFAULT_MAX_ASSET_SIZE_BYTES,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_REQUESTS_PER_SECOND,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_OCR_AUTO_DETECT_LANGUAGE,
    DEFAULT_OCR_DPI,
    DEFAULT_OCR_ENABLED,
    DEFAULT_OCR_IMAGE_AREA_THRESHOLD,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_OCR_PRESERVE_EXISTING_TEXT,
    DEFAULT_OCR_TESSERACT_CONFIG,
    DEFAULT_OCR_TEXT_THRESHOLD,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_REQUIRE_HEAD_SUCCESS,
    DEFAULT_REQUIRE_HTTPS,
    DEFAULT_SPREADSHEET_CHART_MODE,
    DEFAULT_SPREADSHEET_INCLUDE_SHEET_TITLES,
    DEFAULT_SPREADSHEET_MERGED_CELL_MODE,
    DEFAULT_SPREADSHEET_PRESERVE_NEWLINES_IN_CELLS,
    DEFAULT_SPREADSHEET_RENDER_FORMULAS,
    DEFAULT_SPREADSHEET_TRIM_EMPTY,
    AltTextMode,
    AttachmentMode,
    AttachmentOverwriteMode,
    ChartMode,
    HeaderCaseOption,
    MergedCellMode,
    OCRMode,
    TrimEmptyMode,
)
from all2md.options.base import BaseParserOptions, CloneFrozenMixin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetworkFetchOptions(CloneFrozenMixin):
    """Network security options for remote resource fetching.

    This dataclass contains settings that control how remote resources
    (images, CSS, etc.) are fetched, including security constraints
    to prevent SSRF attacks.

    Parameters
    ----------
    allow_remote_fetch : bool, default False
        Whether to allow fetching remote URLs for images and other resources.
        When False, prevents SSRF attacks by blocking all network requests.
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks for remote fetching.
        If None and allow_remote_fetch=True, all hosts are allowed, which may pose
        an SSRF (Server-Side Request Forgery) risk. A security warning will be logged.
        In security-sensitive contexts, explicitly set this to an allowlist of trusted hosts.
    require_https : bool, default False
        Whether to require HTTPS for all remote URL fetching.
    network_timeout : float, default 10.0
        Timeout in seconds for remote URL fetching.
    max_requests_per_second : float, default 10.0
        Maximum number of network requests per second (rate limiting).
    max_concurrent_requests : int, default 5
        Maximum number of concurrent network requests.

    Notes
    -----
    Asset size limits are inherited from BaseParserOptions.max_asset_size_bytes.

    """

    allow_remote_fetch: bool = field(
        default=DEFAULT_ALLOW_REMOTE_FETCH,
        metadata={
            "help": "Allow fetching remote URLs for images and other resources. "
            "When False, prevents SSRF attacks by blocking all network requests.",
            "importance": "security",
        },
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching. "
            "If None, all hosts are allowed (subject to other security constraints).",
            "importance": "security",
        },
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={"help": "Require HTTPS for all remote URL fetching", "importance": "security"},
    )
    require_head_success: bool = field(
        default=DEFAULT_REQUIRE_HEAD_SUCCESS,
        metadata={"help": "Require HEAD request success before remote URL fetching", "importance": "security"},
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={"help": "Timeout in seconds for remote URL fetching", "type": float, "importance": "security"},
    )
    max_redirects: int = field(
        default=5,
        metadata={"help": "Maximum number of HTTP redirects to follow", "type": int, "importance": "security"},
    )
    allowed_content_types: tuple[str, ...] | None = field(
        default=("image/",),
        metadata={
            "help": "Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')",
            "action": "append",
            "importance": "security",
        },
    )
    max_requests_per_second: float = field(
        default=DEFAULT_MAX_REQUESTS_PER_SECOND,
        metadata={
            "help": "Maximum number of network requests per second (rate limiting)",
            "type": float,
            "importance": "security",
        },
    )
    max_concurrent_requests: int = field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        metadata={"help": "Maximum number of concurrent network requests", "type": int, "importance": "security"},
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges and ensure immutability for network fetch options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Defensive copy of mutable collections to ensure immutability
        if self.allowed_hosts is not None:
            object.__setattr__(self, "allowed_hosts", list(self.allowed_hosts))

        # Security validation: warn if remote fetch is enabled without host allowlist
        if self.allow_remote_fetch and self.allowed_hosts is None:
            logger.warning(
                "Security warning: allow_remote_fetch=True with allowed_hosts=None allows "
                "fetching from ANY remote host, which may pose an SSRF (Server-Side Request Forgery) risk. "
                "Consider setting allowed_hosts to an explicit allowlist in security-sensitive contexts."
            )

        # Validate positive timeout
        if self.network_timeout <= 0:
            raise ValueError(f"network_timeout must be positive, got {self.network_timeout}")

        # Validate positive rate limit
        if self.max_requests_per_second <= 0:
            raise ValueError(f"max_requests_per_second must be positive, got {self.max_requests_per_second}")

        # Validate positive concurrent requests
        if self.max_concurrent_requests <= 0:
            raise ValueError(f"max_concurrent_requests must be positive, got {self.max_concurrent_requests}")

        # Validate non-negative max redirects
        if self.max_redirects < 0:
            raise ValueError(f"max_redirects must be non-negative, got {self.max_redirects}")


@dataclass(frozen=True)
class LocalFileAccessOptions(CloneFrozenMixin):
    """Local file access security options.

    This dataclass contains settings that control access to local files
    via file:// URLs and similar mechanisms.

    Parameters
    ----------
    allow_local_files : bool, default False
        Whether to allow access to local files via file:// URLs.
    local_file_allowlist : list[str] | None, default None
        List of directories allowed for local file access.
        Only applies when allow_local_files=True.
    local_file_denylist : list[str] | None, default None
        List of directories denied for local file access.
    allow_cwd_files : bool, default False
        Whether to allow local files from current working directory and subdirectories.

    """

    allow_local_files: bool = field(
        default=DEFAULT_ALLOW_LOCAL_FILES,
        metadata={"help": "Allow access to local files via file:// URLs (security setting)", "importance": "security"},
    )
    local_file_allowlist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories allowed for local file access (when allow_local_files=True)",
            "importance": "security",
        },
    )
    local_file_denylist: list[str] | None = field(
        default=None, metadata={"help": "List of directories denied for local file access", "importance": "security"}
    )
    allow_cwd_files: bool = field(
        default=DEFAULT_ALLOW_CWD_FILES,
        metadata={
            "help": "Allow local files from current working directory and subdirectories",
            "cli_name": "allow-cwd-files",  # default=False, use store_true
            "importance": "security",
        },
    )

    def __post_init__(self) -> None:
        """Ensure immutability by defensively copying mutable collections."""
        # Defensive copy of mutable collections to ensure immutability
        if self.local_file_allowlist is not None:
            object.__setattr__(self, "local_file_allowlist", list(self.local_file_allowlist))
        if self.local_file_denylist is not None:
            object.__setattr__(self, "local_file_denylist", list(self.local_file_denylist))


@dataclass(frozen=True)
class AttachmentOptionsMixin(CloneFrozenMixin):
    """Mixin providing attachment handling options for parsers.

    This mixin adds attachment-related configuration options to parser classes
    that need to handle embedded images, downloads, and other binary assets.
    Only parsers that actually process attachments should inherit from this mixin.

    Parameters
    ----------
    attachment_mode : AttachmentMode
        How to handle attachments/images during parsing
    alt_text_mode : AltTextMode
        How to render alt-text content
    attachment_output_dir : str or None
        Directory to save attachments when using save mode
    attachment_base_url : str or None
        Base URL for resolving attachment references
    max_asset_size_bytes : int
        Maximum allowed size in bytes for any single asset
    attachment_filename_template : str
        Template for attachment filenames
    attachment_overwrite : Literal["unique", "overwrite", "skip"]
        File collision strategy
    attachment_deduplicate_by_hash : bool
        Avoid saving duplicate attachments by content hash
    attachments_footnotes_section : str or None
        Section title for footnote-style attachment references

    Notes
    -----
    This mixin should be used by parsers that handle formats with embedded
    images or binary assets (PDF, DOCX, HTML, EPUB, etc.). Pure text formats
    (CSV, plaintext, source code) should not use this mixin.

    Examples
    --------
    Parser with attachments::

        @dataclass(frozen=True)
        class PdfOptions(BaseParserOptions, AttachmentOptionsMixin):
            # PDF-specific options here
            pass

    Pure text parser without attachments::

        @dataclass(frozen=True)
        class CsvOptions(BaseParserOptions):
            # CSV-specific options here
            pass

    """

    attachment_mode: AttachmentMode = field(
        default=DEFAULT_ATTACHMENT_MODE,  # alt_text
        metadata={
            "help": "How to handle attachments/images",
            "choices": ["skip", "alt_text", "save", "base64"],
            "importance": "core",
        },
    )
    alt_text_mode: AltTextMode = field(
        default=DEFAULT_ALT_TEXT_MODE,
        metadata={
            "help": "How to render alt-text content when using alt_text attachment mode",
            "choices": ["default", "plain_filename", "strict_markdown", "footnote"],
            "importance": "advanced",
        },
    )
    attachment_output_dir: str | None = field(
        default=DEFAULT_ATTACHMENT_OUTPUT_DIR,
        metadata={"help": "Directory to save attachments when using `save` mode", "importance": "advanced"},
    )
    attachment_base_url: str | None = field(
        default=DEFAULT_ATTACHMENT_BASE_URL,
        metadata={"help": "Base URL for resolving attachment references", "importance": "advanced"},
    )
    max_asset_size_bytes: int = field(
        default=DEFAULT_MAX_ASSET_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset (images, downloads, attachments, etc.)",
            "type": int,
            "importance": "security",
        },
    )

    # Advanced attachment handling options
    attachment_filename_template: str = field(
        default=DEFAULT_ATTACHMENT_FILENAME_TEMPLATE,
        metadata={
            "help": "Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}",
            "importance": "advanced",
        },
    )
    attachment_overwrite: AttachmentOverwriteMode = field(
        default=DEFAULT_ATTACHMENT_OVERWRITE,
        metadata={
            "help": "File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'",
            "choices": ["unique", "overwrite", "skip"],
            "importance": "advanced",
        },
    )
    attachment_deduplicate_by_hash: bool = field(
        default=DEFAULT_ATTACHMENT_DEDUPLICATE_BY_HASH,
        metadata={"help": "Avoid saving duplicate attachments by content hash", "importance": "advanced"},
    )
    attachments_footnotes_section: str | None = field(
        default=DEFAULT_ATTACHMENTS_FOOTNOTES_SECTION,
        metadata={
            "help": "Section title for footnote-style attachment references (None to disable)",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for attachment options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate positive asset size limit
        if self.max_asset_size_bytes <= 0:
            raise ValueError(f"max_asset_size_bytes must be positive, got {self.max_asset_size_bytes}")


@dataclass(frozen=True)
class PaginatedParserOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Base class for parsers that handle paginated documents (PDF, PPTX, ODP).

    This base class provides common options for documents with pages/slides,
    including page separator templates. Inherits attachment handling from
    AttachmentOptionsMixin since paginated documents typically contain images.

    Parameters
    ----------
    page_separator_template : str, default "-----"
        Template for page/slide separators between pages.
        Supports placeholders: {page_num}, {total_pages}.

    """

    page_separator_template: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={
            "help": "Template for page/slide separators. Supports placeholders: {page_num}, {total_pages}. This "
            "string is inserted between pages/slides",
            "importance": "advanced",
        },
    )


@dataclass(frozen=True)
class SpreadsheetParserOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Base class for spreadsheet parsers (XLSX, ODS).

    This base class provides common options for spreadsheet documents,
    including sheet selection, data limits, and cell formatting. Inherits
    attachment handling from AttachmentOptionsMixin since spreadsheets can
    contain embedded charts and images.

    Parameters
    ----------
    sheets : list[str] | str | None, default None
        List of exact sheet names to include or a regex pattern.
        If None, includes all sheets.
    include_sheet_titles : bool, default True
        Prepend each sheet with a '## {sheet_name}' heading.
    render_formulas : bool, default True
        When True, uses stored cell values. When False, shows formulas.
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    preserve_newlines_in_cells : bool, default False
        Preserve line breaks within cells as <br> tags.
    trim_empty : {"none", "leading", "trailing", "both"}, default "trailing"
        Trim empty rows/columns: none, leading, trailing, or both.
    header_case : {"preserve", "title", "upper", "lower"}, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    chart_mode : {"data", "skip"}, default "skip"
        How to handle embedded charts:
        - "data": Extract chart data as markdown tables
        - "skip": Ignore charts entirely
    merged_cell_mode : {"spans", "flatten", "skip"}, default "flatten"
        How to handle merged cells:
        - "spans": Use colspan/rowspan in AST (future enhancement, currently behaves like "flatten")
        - "flatten": Replace merged followers with empty strings (current behavior)
        - "skip": Skip merged cell detection entirely

    """

    sheets: list[str] | str | None = field(
        default=None,
        metadata={"help": "Sheet names to include (list or regex pattern). default = all sheets", "importance": "core"},
    )
    include_sheet_titles: bool = field(
        default=DEFAULT_SPREADSHEET_INCLUDE_SHEET_TITLES,
        metadata={
            "help": "Prepend each sheet with '## {sheet_name}' heading",
            "cli_name": "no-include-sheet-titles",
            "importance": "core",
        },
    )
    render_formulas: bool = field(
        default=DEFAULT_SPREADSHEET_RENDER_FORMULAS,
        metadata={
            "help": "Use stored cell values (True) or show formulas (False)",
            "cli_name": "no-render-formulas",
            "importance": "core",
        },
    )
    max_rows: int | None = field(
        default=None,
        metadata={"help": "Maximum rows per table (None = unlimited)", "type": int, "importance": "advanced"},
    )
    max_cols: int | None = field(
        default=None,
        metadata={"help": "Maximum columns per table (None = unlimited)", "type": int, "importance": "advanced"},
    )
    truncation_indicator: str = field(
        default="...", metadata={"help": "Note appended when rows/columns are truncated", "importance": "advanced"}
    )
    preserve_newlines_in_cells: bool = field(
        default=DEFAULT_SPREADSHEET_PRESERVE_NEWLINES_IN_CELLS,
        metadata={"help": "Preserve line breaks within cells as <br> tags"},
    )
    trim_empty: TrimEmptyMode = field(
        default=DEFAULT_SPREADSHEET_TRIM_EMPTY,
        metadata={
            "help": "Trim empty rows/columns: none, leading, trailing, or both",
            "choices": ["none", "leading", "trailing", "both"],
            "importance": "core",
        },
    )
    header_case: HeaderCaseOption = field(
        default="preserve",
        metadata={
            "help": "Transform header case: preserve, title, upper, or lower",
            "choices": ["preserve", "title", "upper", "lower"],
            "importance": "core",
        },
    )
    chart_mode: ChartMode = field(
        default=DEFAULT_SPREADSHEET_CHART_MODE,
        metadata={
            "help": "Chart handling mode: 'data' (extract as tables) or 'skip' (ignore charts, default)",
            "choices": ["data", "skip"],
            "importance": "advanced",
        },
    )
    merged_cell_mode: MergedCellMode = field(
        default=DEFAULT_SPREADSHEET_MERGED_CELL_MODE,
        metadata={
            "help": "Merged cell handling: 'spans' (use colspan/rowspan), 'flatten' (empty strings), or 'skip'",
            "choices": ["spans", "flatten", "skip"],
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges and ensure immutability for spreadsheet options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation (AttachmentOptionsMixin has __post_init__)
        super().__post_init__()

        # Defensive copy of mutable collections to ensure immutability
        if isinstance(self.sheets, list):
            object.__setattr__(self, "sheets", list(self.sheets))

        # Validate max rows/cols (when not None)
        if self.max_rows is not None and self.max_rows <= 0:
            raise ValueError(f"max_rows must be positive when specified, got {self.max_rows}")

        if self.max_cols is not None and self.max_cols <= 0:
            raise ValueError(f"max_cols must be positive when specified, got {self.max_cols}")


@dataclass(frozen=True)
class OCROptions(CloneFrozenMixin):
    """Configuration options for OCR (Optical Character Recognition).

    This dataclass contains settings for detecting and extracting text from
    images using Tesseract OCR engine. Can be used by any parser that needs
    to extract text from images (PDF scanned pages, standalone images, etc.).

    Parameters
    ----------
    enabled : bool, default False
        Master switch to enable/disable OCR functionality. When False, all OCR
        processing is skipped regardless of other settings.
    mode : {"auto", "force", "off"}, default "auto"
        OCR triggering mode:
        - "auto": Automatically detect when OCR is needed (format-specific logic)
        - "force": Apply OCR unconditionally
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
        DPI (dots per inch) for rendering images for OCR.
        Higher values improve OCR accuracy but increase processing time.
        Recommended: 150 (fast), 300 (balanced), 600 (high quality).
    text_threshold : int, default 50
        Minimum number of characters to consider content as text-based.
        Used by parsers in "auto" mode to decide if OCR is needed.
    image_area_threshold : float, default 0.5
        Minimum ratio of image area to total area (0.0-1.0) to consider
        content as image-based. Used by parsers in "auto" mode.
    preserve_existing_text : bool, default False
        Whether to preserve existing text when OCR is applied:
        - False: Replace existing text entirely with OCR results
        - True: Combine existing text with OCR results
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
            "help": "Enable OCR for image-based content",
            "importance": "core",
        },
    )
    mode: OCRMode = field(
        default="auto",
        metadata={
            "help": "OCR mode: 'auto' (detect when needed), 'force' (always), 'off' (disable)",
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
            "help": "Attempt to auto-detect document language (requires `langdetect`)",
            "importance": "advanced",
        },
    )
    dpi: int = field(
        default=DEFAULT_OCR_DPI,
        metadata={
            "help": "DPI for rendering images for OCR (150-600 recommended)",
            "type": int,
            "importance": "advanced",
        },
    )
    text_threshold: int = field(
        default=DEFAULT_OCR_TEXT_THRESHOLD,
        metadata={
            "help": "Minimum characters to consider content text-based (for auto mode)",
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
            "help": "Preserve existing text when applying OCR (combine vs replace)",
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
