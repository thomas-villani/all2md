#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/common.py
"""Common options shared across multiple parsers and renderers.

This module defines options for file access, network operations, and other
cross-cutting concerns used throughout the conversion pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from all2md.constants import (
    DEFAULT_ALLOW_CWD_FILES,
    DEFAULT_ALLOW_LOCAL_FILES,
    DEFAULT_ALLOW_REMOTE_FETCH,
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_REQUESTS_PER_SECOND,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_REQUIRE_HEAD_SUCCESS,
    DEFAULT_REQUIRE_HTTPS,
    HeaderCaseOption,
)
from all2md.options.base import BaseParserOptions, CloneFrozenMixin


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
        If None, all hosts are allowed (subject to other security constraints).
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
            "importance": "security"
        }
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching. "
                    "If None, all hosts are allowed (subject to other security constraints).",
            "importance": "security"
        }
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={
            "help": "Require HTTPS for all remote URL fetching",
            "importance": "security"
        }
    )
    require_head_success: bool = field(
        default=DEFAULT_REQUIRE_HEAD_SUCCESS,
        metadata={
            "help": "Require HEAD request success before remote URL fetching",
            "importance": "security"
        }
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={
            "help": "Timeout in seconds for remote URL fetching",
            "type": float,
            "importance": "security"
        }
    )
    max_redirects: int = field(
        default=5,
        metadata={
            "help": "Maximum number of HTTP redirects to follow",
            "type": int,
            "importance": "security"
        }
    )
    allowed_content_types: tuple[str, ...] | None = field(
        default=("image/",),
        metadata={
            "help": "Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')",
            "action": "append",
            "importance": "security"
        }
    )
    max_requests_per_second: float = field(
        default=DEFAULT_MAX_REQUESTS_PER_SECOND,
        metadata={
            "help": "Maximum number of network requests per second (rate limiting)",
            "type": float,
            "importance": "security"
        }
    )
    max_concurrent_requests: int = field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        metadata={
            "help": "Maximum number of concurrent network requests",
            "type": int,
            "importance": "security"
        }
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for network fetch options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate positive timeout
        if self.network_timeout <= 0:
            raise ValueError(
                f"network_timeout must be positive, got {self.network_timeout}"
            )

        # Validate positive rate limit
        if self.max_requests_per_second <= 0:
            raise ValueError(
                f"max_requests_per_second must be positive, got {self.max_requests_per_second}"
            )

        # Validate positive concurrent requests
        if self.max_concurrent_requests <= 0:
            raise ValueError(
                f"max_concurrent_requests must be positive, got {self.max_concurrent_requests}"
            )

        # Validate non-negative max redirects
        if self.max_redirects < 0:
            raise ValueError(
                f"max_redirects must be non-negative, got {self.max_redirects}"
            )


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
        metadata={
            "help": "Allow access to local files via file:// URLs (security setting)",
            "importance": "security"
        }
    )
    local_file_allowlist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories allowed for local file access (when allow_local_files=True)",
            "importance": "security"
        }
    )
    local_file_denylist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories denied for local file access",
            "importance": "security"
        }
    )
    allow_cwd_files: bool = field(
        default=DEFAULT_ALLOW_CWD_FILES,
        metadata={
            "help": "Allow local files from current working directory and subdirectories",
            "cli_name": "allow-cwd-files",  # default=False, use store_true
            "importance": "security"
        }
    )


@dataclass(frozen=True)
class PaginatedParserOptions(BaseParserOptions):
    """Base class for parsers that handle paginated documents (PDF, PPTX, ODP).

    This base class provides common options for documents with pages/slides,
    including page separator templates.

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
            "importance": "advanced"
        }
    )


@dataclass(frozen=True)
class SpreadsheetParserOptions(BaseParserOptions):
    """Base class for spreadsheet parsers (XLSX, ODS).

    This base class provides common options for spreadsheet documents,
    including sheet selection, data limits, and cell formatting.

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

    sheets: Union[list[str], str, None] = field(
        default=None,
        metadata={
            "help": "Sheet names to include (list or regex pattern). default = all sheets",
            "importance": "core"
        }
    )
    include_sheet_titles: bool = field(
        default=True,
        metadata={
            "help": "Prepend each sheet with '## {sheet_name}' heading",
            "cli_name": "no-include-sheet-titles",
            "importance": "core"
        }
    )
    render_formulas: bool = field(
        default=True,
        metadata={
            "help": "Use stored cell values (True) or show formulas (False)",
            "cli_name": "no-render-formulas",
            "importance": "core"
        }
    )
    max_rows: Optional[int] = field(
        default=None,
        metadata={
            "help": "Maximum rows per table (None = unlimited)",
            "type": int,
            "importance": "advanced"
        }
    )
    max_cols: Optional[int] = field(
        default=None,
        metadata={
            "help": "Maximum columns per table (None = unlimited)",
            "type": int,
            "importance": "advanced"
        }
    )
    truncation_indicator: str = field(
        default="...",
        metadata={
            "help": "Note appended when rows/columns are truncated",
            "importance": "advanced"
        }
    )
    preserve_newlines_in_cells: bool = field(
        default=False,
        metadata={"help": "Preserve line breaks within cells as <br> tags"}
    )
    trim_empty: Literal["none", "leading", "trailing", "both"] = field(
        default="trailing",
        metadata={
            "help": "Trim empty rows/columns: none, leading, trailing, or both",
            "choices": ["none", "leading", "trailing", "both"],
            "importance": "core"
        }
    )
    header_case: HeaderCaseOption = field(
        default="preserve",
        metadata={
            "help": "Transform header case: preserve, title, upper, or lower",
            "choices": ["preserve", "title", "upper", "lower"],
            "importance": "core"
        }
    )
    # TODO: move magic strings
    chart_mode: Literal["data", "skip"] = field(
        default="skip",
        metadata={
            "help": "Chart handling mode: 'data' (extract as tables) or 'skip' (ignore charts, default)",
            "choices": ["data", "skip"],
            "importance": "advanced"
        }
    )
    merged_cell_mode: Literal["spans", "flatten", "skip"] = field(
        default="flatten",
        metadata={
            "help": "Merged cell handling: 'spans' (use colspan/rowspan), 'flatten' (empty strings), or 'skip'",
            "choices": ["spans", "flatten", "skip"],
            "importance": "advanced"
        }
    )
