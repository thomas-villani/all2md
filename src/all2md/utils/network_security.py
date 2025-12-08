"""Network security utilities for preventing SSRF attacks.

This module provides comprehensive URL validation and secure HTTP client functionality
to prevent Server-Side Request Forgery (SSRF) attacks when fetching remote resources.

The security measures include:
- DNS resolution validation for all IP addresses
- Blocking private, loopback, and special-use IP ranges
- Redirect validation and hop limiting
- Content-type and size restrictions
- Timeout enforcement

Functions
---------
- validate_url_security: Comprehensive URL security validation
- create_secure_http_client: Create httpx client with security constraints
- fetch_image_securely: Secure image fetching with validation
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/network_security.py

import ipaddress
import logging
import os
import socket
import threading
import time
from email.message import Message
from typing import Any, Literal
from urllib.parse import urlparse

from all2md.constants import DEFAULT_USER_AGENT, DEPS_NETWORK
from all2md.exceptions import NetworkSecurityError
from all2md.utils.decorators import requires_dependencies

logger = logging.getLogger(__name__)


def _is_private_or_reserved_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is private, reserved, or otherwise restricted.

    Parameters
    ----------
    ip : ipaddress.IPv4Address | ipaddress.IPv6Address
        IP address to check

    Returns
    -------
    bool
        True if IP should be blocked, False if allowed

    """
    if isinstance(ip, ipaddress.IPv4Address):
        # IPv4 restricted ranges
        return (
            ip.is_private  # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
            or ip.is_loopback  # 127.0.0.0/8
            or ip.is_link_local  # 169.254.0.0/16
            or ip.is_reserved  # Various reserved ranges
            or ip.is_multicast  # 224.0.0.0/4
            or ip in ipaddress.IPv4Network("0.0.0.0/8")  # "This" network
            or ip in ipaddress.IPv4Network("100.64.0.0/10")  # RFC6598 Carrier NAT
            or ip in ipaddress.IPv4Network("192.0.0.0/24")  # RFC6890 Special use
            or ip in ipaddress.IPv4Network("192.0.2.0/24")  # RFC5737 Test-Net-1
            or ip in ipaddress.IPv4Network("198.18.0.0/15")  # RFC2544 Benchmarking
            or ip in ipaddress.IPv4Network("198.51.100.0/24")  # RFC5737 Test-Net-2
            or ip in ipaddress.IPv4Network("203.0.113.0/24")  # RFC5737 Test-Net-3
            or ip in ipaddress.IPv4Network("240.0.0.0/4")  # RFC1112 Reserved
        )
    else:  # IPv6
        # IPv6 restricted ranges
        return (
            ip.is_private  # fc00::/7 (ULA)
            or ip.is_loopback  # ::1/128
            or ip.is_link_local  # fe80::/10
            or ip.is_reserved  # Various reserved ranges
            or ip.is_multicast  # ff00::/8
            or ip in ipaddress.IPv6Network("::ffff:0:0/96")  # IPv4-mapped IPv6
            or ip in ipaddress.IPv6Network("2001:db8::/32")  # RFC3849 Documentation
            or ip in ipaddress.IPv6Network("2001::/32")  # RFC4380 Teredo
            or ip in ipaddress.IPv6Network("2002::/16")  # RFC3056 6to4
        )


def _resolve_hostname_to_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname to all associated IP addresses.

    Parameters
    ----------
    hostname : str
        Hostname to resolve

    Returns
    -------
    list[ipaddress.IPv4Address | ipaddress.IPv6Address]
        List of resolved IP addresses

    Raises
    ------
    NetworkSecurityError
        If hostname resolution fails or contains invalid addresses

    """
    try:
        # Get all address info for the hostname
        addr_infos = socket.getaddrinfo(hostname, None)
        ips = []

        for addr_info in addr_infos:
            ip_str = addr_info[4][0]  # Extract IP string from sockaddr
            try:
                ip = ipaddress.ip_address(ip_str)
                ips.append(ip)
            except ValueError:
                # Skip invalid IP addresses
                continue

        if not ips:
            raise NetworkSecurityError(f"No valid IP addresses resolved for hostname: {hostname}")

        return ips

    except socket.gaierror as e:
        raise NetworkSecurityError(f"Failed to resolve hostname {hostname}: {e}") from e


def _normalize_hostname(hostname: str) -> str:
    """Normalize a hostname for case-insensitive comparison.

    Applies IDNA encoding (for internationalized domain names) and lowercasing
    to ensure consistent hostname comparison regardless of input casing.

    Parameters
    ----------
    hostname : str
        Hostname to normalize

    Returns
    -------
    str
        Normalized hostname (IDNA-encoded and lowercased)

    Examples
    --------
    >>> _normalize_hostname("Example.com")
    'example.com'
    >>> _normalize_hostname("EXAMPLE.COM")
    'example.com'

    """
    try:
        # Apply IDNA encoding for internationalized domain names
        # Then lowercase for case-insensitive comparison
        return hostname.encode("idna").decode("ascii").lower()
    except Exception:
        # If IDNA encoding fails, fall back to simple lowercasing
        return hostname.lower()


def _validate_hostname_allowlist(hostname: str, allowed_hosts: list[str] | None) -> bool:
    """Check if hostname is in the allowlist.

    Normalizes both the incoming hostname and allowlist entries (IDNA encoding
    + lowercasing) to ensure case-insensitive matching. CIDR blocks in the
    allowlist are handled separately and don't require normalization.

    Parameters
    ----------
    hostname : str
        Hostname to check (will be normalized internally)
    allowed_hosts : list[str] | None
        List of allowed hostnames/CIDR blocks, or None to allow all

    Returns
    -------
    bool
        True if hostname is allowed, False otherwise

    """
    if allowed_hosts is None:
        return True

    # Normalize the incoming hostname for case-insensitive comparison
    normalized_hostname = _normalize_hostname(hostname)

    # Check exact hostname match with normalization
    for allowed_entry in allowed_hosts:
        # Try to parse as CIDR block first
        try:
            ipaddress.ip_network(allowed_entry, strict=False)
            # It's a valid CIDR block, skip normalization for this entry
            # We'll check it later with IP resolution
            continue
        except ValueError:
            # Not a CIDR block, treat as hostname and normalize for comparison
            normalized_allowed = _normalize_hostname(allowed_entry)
            if normalized_hostname == normalized_allowed:
                return True

    # Check if any of the resolved IPs are in allowed CIDR blocks
    try:
        resolved_ips = _resolve_hostname_to_ips(normalized_hostname)
        for allowed_entry in allowed_hosts:
            try:
                # Try to parse as CIDR block
                allowed_network = ipaddress.ip_network(allowed_entry, strict=False)
                for ip in resolved_ips:
                    if ip in allowed_network:
                        return True
            except ValueError:
                # Not a valid CIDR block, already checked as hostname above
                continue
    except NetworkSecurityError:
        # Hostname resolution failed, deny access
        return False

    return False


def _parse_content_type(content_type: str) -> str:
    """Parse content-type header to extract main MIME type.

    Uses email.message.Message to properly parse the content-type header,
    ignoring parameters like charset, boundary, etc.

    Parameters
    ----------
    content_type : str
        Raw content-type header value

    Returns
    -------
    str
        Main content type (e.g., "image/png"), lowercased, or empty string if parsing fails

    Examples
    --------
    >>> _parse_content_type("image/png")
    'image/png'
    >>> _parse_content_type("image/png; charset=utf-8")
    'image/png'
    >>> _parse_content_type("text/html; charset=UTF-8")
    'text/html'

    """
    if not content_type:
        return ""

    try:
        # Use email.message.Message to parse the content-type header
        msg = Message()
        msg["content-type"] = content_type
        # get_content_type() returns the main type, ignoring parameters
        return msg.get_content_type().lower()
    except Exception:
        # If parsing fails, return empty string
        return ""


class RateLimiter:
    """Rate limiter for network requests using token bucket algorithm.

    Implements both requests-per-second rate limiting and concurrent request limiting.
    Thread-safe implementation using locks and semaphores.

    Parameters
    ----------
    max_requests_per_second : float, default 10.0
        Maximum number of requests per second
    max_concurrent : int, default 5
        Maximum number of concurrent requests

    """

    def __init__(self, max_requests_per_second: float = 10.0, max_concurrent: int = 5):
        """Initialize rate limiter."""
        self.max_requests_per_second = max_requests_per_second
        self.max_concurrent = max_concurrent

        # Token bucket for rate limiting
        self.tokens = max_requests_per_second
        self.last_update = time.time()
        self.lock = threading.Lock()

        # Semaphore for concurrent limiting
        self.semaphore = threading.Semaphore(max_concurrent)

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire permission to make a request.

        Blocks until rate limit and concurrency constraints are satisfied.

        Parameters
        ----------
        timeout : float | None, default None
            Maximum time to wait in seconds. None means wait indefinitely.

        Returns
        -------
        bool
            True if acquired, False if timeout

        """
        start_time = time.time()

        # Wait for rate limit
        while True:
            with self.lock:
                now = time.time()
                # Refill tokens based on elapsed time
                elapsed = now - self.last_update
                self.tokens = min(self.max_requests_per_second, self.tokens + elapsed * self.max_requests_per_second)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    break

            # Check timeout
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False

            # Sleep briefly to avoid busy waiting
            time.sleep(0.01)

        # Acquire semaphore for concurrent limiting
        remaining_timeout = None if timeout is None else max(0, timeout - (time.time() - start_time))
        if not self.semaphore.acquire(timeout=remaining_timeout):
            # Refund the token since we won't be making the request
            with self.lock:
                self.tokens = min(self.max_requests_per_second, self.tokens + 1.0)
            return False

        return True

    def release(self) -> None:
        """Release a concurrent request slot."""
        self.semaphore.release()

    def __enter__(self) -> "RateLimiter":
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError("Rate limiter acquisition timeout")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Context manager exit."""
        self.release()
        return False


def validate_url_security(url: str, allowed_hosts: list[str] | None = None, require_https: bool = True) -> None:
    """Validate URL for security before making HTTP requests.

    Performs comprehensive security validation including DNS resolution,
    IP address validation, and hostname allowlist checking.

    Parameters
    ----------
    url : str
        URL to validate
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks. If None, all hosts allowed
        (subject to IP restrictions)
    require_https : bool, default True
        If True, only HTTPS URLs are allowed

    Raises
    ------
    NetworkSecurityError
        If URL fails security validation

    """
    try:
        parsed = urlparse(url)
        # Basic validation - ensure it looks like a URL
        if not parsed.scheme and not parsed.netloc:
            raise NetworkSecurityError(f"Invalid URL format: {url}")
    except Exception as e:
        raise NetworkSecurityError(f"Invalid URL format: {url}") from e

    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        raise NetworkSecurityError(f"Unsupported URL scheme: {parsed.scheme}")

    if require_https and parsed.scheme != "https":
        raise NetworkSecurityError(f"HTTPS required but got: {parsed.scheme}")

    # Validate hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise NetworkSecurityError("URL missing hostname")

    if not require_https and parsed.scheme == "http":
        logger.warning(
            f"Fetching URL over insecure HTTP (scheme: {parsed.scheme}, hostname: {hostname}). "
            f"Consider using HTTPS for {url}"
        )

    # Normalize hostname (handle IDN/punycode and case sensitivity)
    normalized_hostname = _normalize_hostname(hostname)

    # Check allowlist first (if specified)
    if not _validate_hostname_allowlist(normalized_hostname, allowed_hosts):
        raise NetworkSecurityError(f"Hostname not in allowlist: {normalized_hostname}")

    # Resolve hostname and validate all IP addresses
    resolved_ips = _resolve_hostname_to_ips(normalized_hostname)

    for ip in resolved_ips:
        if _is_private_or_reserved_ip(ip):
            raise NetworkSecurityError(
                f"Access to private/reserved IP address blocked: {ip} (hostname: {normalized_hostname})"
            )

    logger.debug(f"URL security validation passed for: {url}")


@requires_dependencies("network", DEPS_NETWORK)
def create_secure_http_client(
    timeout: float = 10.0,
    max_redirects: int = 5,
    allowed_hosts: list[str] | None = None,
    require_https: bool = True,
    user_agent: str | None = None,
) -> Any:
    """Create httpx client with security constraints.

    This implementation uses httpx event hooks for robust URL validation
    instead of fragile transport subclassing. Validates all requests including
    redirects using stable httpx APIs.

    The redirect limit is enforced by validating response.history length,
    which accurately tracks the complete redirect chain.

    Parameters
    ----------
    timeout : float, default 10.0
        Request timeout in seconds
    max_redirects : int, default 5
        Maximum number of redirects to follow
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default True
        If True, only HTTPS URLs are allowed
    user_agent : str | None, default None
        Custom User-Agent header for requests (currently unused)

    Returns
    -------
    httpx.Client
        Configured HTTP client with security constraints

    """
    import httpx

    def validate_request_url(request: Any) -> None:
        """Event hook to validate URLs before each request."""
        # Validate URL security
        try:
            validate_url_security(str(request.url), allowed_hosts=allowed_hosts, require_https=require_https)
        except NetworkSecurityError:
            # Re-raise to abort the request
            raise

    def validate_response_redirects(response: Any) -> None:
        """Event hook to validate redirect chains.

        Validates that the redirect chain length does not exceed max_redirects
        and that all URLs in the chain pass security validation.
        """
        # Validate response history length
        if len(response.history) > max_redirects:
            raise NetworkSecurityError(f"Too many redirects: {len(response.history)} > {max_redirects}")

        # Validate each URL in the redirect history
        for redirect_response in response.history:
            try:
                validate_url_security(
                    str(redirect_response.url), allowed_hosts=allowed_hosts, require_https=require_https
                )
            except NetworkSecurityError:
                # Re-raise to indicate security violation
                raise

    # Create client with event hooks for security validation
    effective_user_agent = user_agent or os.getenv("ALL2MD_USER_AGENT") or DEFAULT_USER_AGENT
    client = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        event_hooks={"request": [validate_request_url], "response": [validate_response_redirects]},
        headers={"User-Agent": effective_user_agent},
    )

    return client


def fetch_content_securely(
    url: str,
    allowed_hosts: list[str] | None = None,
    require_https: bool = True,
    max_size_bytes: int = 20 * 1024 * 1024,  # 20MB
    timeout: float = 10.0,
    expected_content_types: list[str] | None = None,
    require_head_success: bool = True,
    rate_limiter: RateLimiter | None = None,
    user_agent: str | None = None,
    bypass_robots_txt: bool = False,
) -> bytes:
    """Securely fetch content from URL with streaming and comprehensive validation.

    Parameters
    ----------
    url : str
        URL to fetch content from
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default True
        If True, only HTTPS URLs are allowed
    max_size_bytes : int, default 20MB
        Maximum allowed response size in bytes
    timeout : float, default 10.0
        Request timeout in seconds
    expected_content_types : list[str] | None, default None
        List of allowed content type prefixes (e.g., ["image/", "text/"])
    require_head_success : bool, default True
        Require a successful HEAD request prior to GET.
    rate_limiter : RateLimiter | None, default None
        Optional rate limiter to control request rate and concurrency
    user_agent : str | None, default None
        Custom User-Agent header for requests (currently unused)
    bypass_robots_txt : bool, default False
        If True, bypass robots.txt checking (used internally when fetching robots.txt itself)

    Returns
    -------
    bytes
        Content data

    Raises
    ------
    NetworkSecurityError
        If URL fails security validation or fetch constraints

    """
    from httpx import HTTPError

    # Check global network disable first
    if is_network_disabled():
        raise NetworkSecurityError(
            "Network access is globally disabled via ALL2MD_DISABLE_NETWORK environment variable"
        )

    # Initial URL validation
    validate_url_security(url, allowed_hosts=allowed_hosts, require_https=require_https)

    # Acquire rate limiter if provided
    if rate_limiter:
        if not rate_limiter.acquire(timeout=timeout):
            raise NetworkSecurityError(f"Rate limiter timeout for {url}")

    try:
        with create_secure_http_client(
            timeout=timeout, allowed_hosts=allowed_hosts, require_https=require_https, user_agent=user_agent
        ) as client:
            # Use HEAD request first to check content-length header
            try:
                head_response = client.head(url)
                head_response.raise_for_status()

                # Check content-length header if present
                content_length_header = head_response.headers.get("content-length")
                if content_length_header:
                    try:
                        declared_size = int(content_length_header)
                        if declared_size > max_size_bytes:
                            raise NetworkSecurityError(
                                f"Content-Length too large: {declared_size} bytes (max: {max_size_bytes})"
                            )
                    except ValueError:
                        pass  # Invalid content-length header, will check during streaming

                # Check content type from HEAD response
                content_type_raw = head_response.headers.get("content-type", "")
                content_type = _parse_content_type(content_type_raw)
                if expected_content_types and not any(content_type.startswith(ct) for ct in expected_content_types):
                    raise NetworkSecurityError(
                        f"Invalid content type: {content_type}. Expected one of: {expected_content_types}"
                    )
            except Exception as head_error:
                # HEAD request failed, continue with GET but be more cautious unless required head success
                if require_head_success:
                    raise NetworkSecurityError(
                        f"HEAD request required but failed: {head_error!r}", original_error=head_error
                    ) from head_error
                logger.debug(f"HEAD request failed for {url}: {head_error}")

            # Stream the actual content with size validation
            with client.stream("GET", url) as response:
                response.raise_for_status()

                # Final content type check from GET response
                content_type_raw = response.headers.get("content-type", "")
                content_type = _parse_content_type(content_type_raw)
                if expected_content_types and not any(content_type.startswith(ct) for ct in expected_content_types):
                    raise NetworkSecurityError(
                        f"Invalid content type: {content_type}. Expected one of: {expected_content_types}"
                    )

                # Stream content with size limit
                content_chunks = []
                total_size = 0

                for chunk in response.iter_bytes(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > max_size_bytes:
                        raise NetworkSecurityError(
                            f"Response too large: exceeded {max_size_bytes} bytes during streaming"
                        )
                    content_chunks.append(chunk)

                if total_size == 0:
                    raise NetworkSecurityError("Empty response received")

                content = b"".join(content_chunks)
                logger.debug(f"Successfully fetched {total_size} bytes from {url}")
                return content

    except NetworkSecurityError:
        raise
    except HTTPError as e:
        raise NetworkSecurityError(f"HTTP request failed for {url}: {e}", original_error=e) from e
    except Exception as e:
        raise NetworkSecurityError(f"Unexpected error fetching {url}: {e}") from e
    finally:
        # Release rate limiter if acquired
        if rate_limiter:
            rate_limiter.release()


def fetch_image_securely(
    url: str,
    allowed_hosts: list[str] | None = None,
    require_https: bool = True,
    max_size_bytes: int = 20 * 1024 * 1024,  # 20MB
    timeout: float = 30.0,
    require_head_success: bool = True,
    rate_limiter: RateLimiter | None = None,
    user_agent: str | None = None,
) -> bytes:
    """Securely fetch image data from URL with comprehensive validation.

    This is a convenience wrapper around fetch_content_securely for image downloads.

    Parameters
    ----------
    url : str
        URL to fetch image from
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default True
        If True, only HTTPS URLs are allowed
    max_size_bytes : int, default 20MB
        Maximum allowed response size in bytes
    timeout : float, default 10.0
        Request timeout in seconds
    require_head_success : bool, default True
        Require a successful HEAD request prior to GET
    rate_limiter : RateLimiter | None, default None
        Optional rate limiter to control request rate and concurrency
    user_agent : str | None, default None
        Optionally set the user agent for http requests.

    Returns
    -------
    bytes
        Image data

    Raises
    ------
    NetworkSecurityError
        If URL fails security validation or fetch constraints

    """
    return fetch_content_securely(
        url=url,
        allowed_hosts=allowed_hosts,
        require_https=require_https,
        max_size_bytes=max_size_bytes,
        timeout=timeout,
        require_head_success=require_head_success,
        expected_content_types=["image/"],
        rate_limiter=rate_limiter,
        user_agent=user_agent,
    )


def is_network_disabled() -> bool:
    """Check if network access is globally disabled via environment variable.

    Returns
    -------
    bool
        True if network access should be disabled, False otherwise

    """
    return os.getenv("ALL2MD_DISABLE_NETWORK", "").lower() in ("true", "1", "yes", "on")
