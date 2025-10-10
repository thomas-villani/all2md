#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/common.py
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ALLOW_CWD_FILES,
    DEFAULT_ALLOW_LOCAL_FILES,
    DEFAULT_ALLOW_REMOTE_FETCH,
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_MAX_IMAGE_SIZE_BYTES,
    DEFAULT_MAX_REQUESTS_PER_SECOND,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_REQUIRE_HEAD_SUCCESS,
    DEFAULT_REQUIRE_HTTPS,
)
from all2md.options import CloneFrozenMixin


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
    max_remote_asset_bytes : int, default 20MB
        Maximum allowed size in bytes for downloaded remote assets.
    max_requests_per_second : float, default 10.0
        Maximum number of network requests per second (rate limiting).
    max_concurrent_requests : int, default 5
        Maximum number of concurrent network requests.

    """

    allow_remote_fetch: bool = field(
        default=DEFAULT_ALLOW_REMOTE_FETCH,
        metadata={
            "help": "Allow fetching remote URLs for images and other resources. "
                    "When False, prevents SSRF attacks by blocking all network requests."
        }
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching. "
                    "If None, all hosts are allowed (subject to other security constraints)."
        }
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={"help": "Require HTTPS for all remote URL fetching"}
    )
    require_head_success: bool = field(
        default=DEFAULT_REQUIRE_HEAD_SUCCESS,
        metadata={"help": "Require HEAD request success before remote URL fetching"}
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={
            "help": "Timeout in seconds for remote URL fetching",
            "type": float
        }
    )
    max_remote_asset_bytes: int = field(
        default=DEFAULT_MAX_IMAGE_SIZE_BYTES,  # Reuse existing default
        metadata={
            "help": "Maximum allowed size in bytes for downloaded remote assets",
            "type": int
        }
    )
    max_redirects: int = field(
        default=5,
        metadata={
            "help": "Maximum number of HTTP redirects to follow",
            "type": int
        }
    )
    allowed_content_types: tuple[str, ...] | None = field(
        default=("image/",),
        metadata={
            "help": "Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')",
            "action": "append"
        }
    )
    max_requests_per_second: float = field(
        default=DEFAULT_MAX_REQUESTS_PER_SECOND,
        metadata={
            "help": "Maximum number of network requests per second (rate limiting)",
            "type": float
        }
    )
    max_concurrent_requests: int = field(
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        metadata={
            "help": "Maximum number of concurrent network requests",
            "type": int
        }
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
            "cli_name": "allow-cwd-files"  # default=False, use store_true
        }
    )
