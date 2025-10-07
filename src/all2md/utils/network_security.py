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

import ipaddress
import logging
import os
import socket
from typing import Any
from urllib.parse import urlparse

from all2md.exceptions import NetworkSecurityError

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
                ip.is_private or  # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
                ip.is_loopback or  # 127.0.0.0/8
                ip.is_link_local or  # 169.254.0.0/16
                ip.is_reserved or  # Various reserved ranges
                ip.is_multicast or  # 224.0.0.0/4
                ip in ipaddress.IPv4Network('0.0.0.0/8') or  # "This" network
                ip in ipaddress.IPv4Network('100.64.0.0/10') or  # RFC6598 Carrier NAT
                ip in ipaddress.IPv4Network('192.0.0.0/24') or  # RFC6890 Special use
                ip in ipaddress.IPv4Network('192.0.2.0/24') or  # RFC5737 Test-Net-1
                ip in ipaddress.IPv4Network('198.18.0.0/15') or  # RFC2544 Benchmarking
                ip in ipaddress.IPv4Network('198.51.100.0/24') or  # RFC5737 Test-Net-2
                ip in ipaddress.IPv4Network('203.0.113.0/24') or  # RFC5737 Test-Net-3
                ip in ipaddress.IPv4Network('240.0.0.0/4')  # RFC1112 Reserved
        )
    else:  # IPv6
        # IPv6 restricted ranges
        return (
                ip.is_private or  # fc00::/7 (ULA)
                ip.is_loopback or  # ::1/128
                ip.is_link_local or  # fe80::/10
                ip.is_reserved or  # Various reserved ranges
                ip.is_multicast or  # ff00::/8
                ip in ipaddress.IPv6Network('::ffff:0:0/96') or  # IPv4-mapped IPv6
                ip in ipaddress.IPv6Network('2001:db8::/32') or  # RFC3849 Documentation
                ip in ipaddress.IPv6Network('2001::/32') or  # RFC4380 Teredo
                ip in ipaddress.IPv6Network('2002::/16')  # RFC3056 6to4
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


def _validate_hostname_allowlist(hostname: str, allowed_hosts: list[str] | None) -> bool:
    """Check if hostname is in the allowlist.

    Parameters
    ----------
    hostname : str
        Hostname to check
    allowed_hosts : list[str] | None
        List of allowed hostnames/CIDR blocks, or None to allow all

    Returns
    -------
    bool
        True if hostname is allowed, False otherwise

    """
    if allowed_hosts is None:
        return True

    # Check exact hostname match
    if hostname in allowed_hosts:
        return True

    # Check if any of the resolved IPs are in allowed CIDR blocks
    try:
        resolved_ips = _resolve_hostname_to_ips(hostname)
        for allowed_entry in allowed_hosts:
            try:
                # Try to parse as CIDR block
                allowed_network = ipaddress.ip_network(allowed_entry, strict=False)
                for ip in resolved_ips:
                    if ip in allowed_network:
                        return True
            except ValueError:
                # Not a valid CIDR block, skip
                continue
    except NetworkSecurityError:
        # Hostname resolution failed, deny access
        return False

    return False


def validate_url_security(
        url: str,
        allowed_hosts: list[str] | None = None,
        require_https: bool = True
) -> None:
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
    require_https : bool, default False
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
    if parsed.scheme not in ('http', 'https'):
        raise NetworkSecurityError(f"Unsupported URL scheme: {parsed.scheme}")

    if require_https and parsed.scheme != 'https':
        raise NetworkSecurityError(f"HTTPS required but got: {parsed.scheme}")

    if not require_https and parsed.scheme == "http":
        logger.warning(f"Fetching {url} over insecure HTTP. Consider using HTTPS.")

    # Validate hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise NetworkSecurityError("URL missing hostname")

    # Normalize hostname (handle IDN/punycode)
    try:
        normalized_hostname = hostname.encode('idna').decode('ascii').lower()
    except Exception:
        # If IDN encoding fails, use original hostname
        normalized_hostname = hostname.lower()

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


def create_secure_http_client(
        timeout: float = 10.0,
        max_redirects: int = 5,
        allowed_hosts: list[str] | None = None,
        require_https: bool = False
) -> Any:
    """Create httpx client with security constraints.

    This implementation uses httpx event hooks for robust URL validation
    instead of fragile transport subclassing. Validates all requests including
    redirects using stable httpx APIs.

    The redirect limit is enforced using two complementary mechanisms:
    1. Primary check: Validates response.history length (standard httpx API)
    2. Secondary check: Tracks hop count explicitly via request.extensions for defense-in-depth

    Parameters
    ----------
    timeout : float, default 10.0
        Request timeout in seconds
    max_redirects : int, default 5
        Maximum number of redirects to follow
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default False
        If True, only HTTPS URLs are allowed

    Returns
    -------
    httpx.Client
        Configured HTTP client with security constraints

    """
    import httpx

    def validate_request_url(request: Any) -> None:
        """Event hook to validate URLs before each request.

        Also tracks redirect hop count in request.extensions for
        additional enforcement beyond response.history validation.
        """
        # Validate URL security
        try:
            validate_url_security(
                str(request.url),
                allowed_hosts=allowed_hosts,
                require_https=require_https
            )
        except NetworkSecurityError:
            # Re-raise to abort the request
            raise

        # Track redirect count in extensions for defense-in-depth
        # Initialize or increment hop counter
        if 'redirect_count' not in request.extensions:
            request.extensions['redirect_count'] = 0
        else:
            request.extensions['redirect_count'] += 1

        # Secondary enforcement: Check hop counter
        redirect_count = request.extensions['redirect_count']
        if redirect_count > max_redirects:
            raise NetworkSecurityError(
                f"Too many redirects (hop count): {redirect_count} > {max_redirects}"
            )

    def validate_response_redirects(response: Any) -> None:
        """Event hook to validate redirect chains.

        Uses dual validation: both response.history (primary) and
        request.extensions hop count (secondary defense-in-depth).
        """
        # Primary check: Validate response history length
        if len(response.history) > max_redirects:
            raise NetworkSecurityError(
                f"Too many redirects (history): {len(response.history)} > {max_redirects}"
            )

        # Secondary check: Validate hop counter from request extensions
        if hasattr(response, 'request') and response.request:
            redirect_count = response.request.extensions.get('redirect_count', 0)
            if redirect_count > max_redirects:
                raise NetworkSecurityError(
                    f"Too many redirects (hop count): {redirect_count} > {max_redirects}"
                )

        # Validate each URL in the redirect history
        for redirect_response in response.history:
            try:
                validate_url_security(
                    str(redirect_response.url),
                    allowed_hosts=allowed_hosts,
                    require_https=require_https
                )
            except NetworkSecurityError:
                # Re-raise to indicate security violation
                raise

    # Create client with event hooks for security validation
    client = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        event_hooks={
            'request': [validate_request_url],
            'response': [validate_response_redirects]
        },
        headers={
            'User-Agent': 'all2md-image-fetcher/1.0'
        }
    )

    return client


def fetch_content_securely(
        url: str,
        allowed_hosts: list[str] | None = None,
        require_https: bool = False,
        max_size_bytes: int = 20 * 1024 * 1024,  # 20MB
        timeout: float = 10.0,
        expected_content_types: list[str] | None = None,
        require_head_success: bool = True
) -> bytes:
    """Securely fetch content from URL with streaming and comprehensive validation.

    Parameters
    ----------
    url : str
        URL to fetch content from
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default False
        If True, only HTTPS URLs are allowed
    max_size_bytes : int, default 20MB
        Maximum allowed response size in bytes
    timeout : float, default 10.0
        Request timeout in seconds
    expected_content_types : list[str] | None, default None
        List of allowed content type prefixes (e.g., ["image/", "text/"])
    require_head_success : bool, default True
        Require a successful HEAD request prior to GET.

    Returns
    -------
    bytes
        Content data

    Raises
    ------
    NetworkSecurityError
        If URL fails security validation or fetch constraints

    """
    # Check global network disable first
    if is_network_disabled():
        raise NetworkSecurityError(
            "Network access is globally disabled via ALL2MD_DISABLE_NETWORK environment variable")

    # Initial URL validation
    validate_url_security(url, allowed_hosts=allowed_hosts, require_https=require_https)

    try:
        with create_secure_http_client(
                timeout=timeout,
                allowed_hosts=allowed_hosts,
                require_https=require_https
        ) as client:
            # Use HEAD request first to check content-length header
            try:
                head_response = client.head(url)
                head_response.raise_for_status()

                # Check content-length header if present
                content_length_header = head_response.headers.get('content-length')
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
                content_type = head_response.headers.get('content-type', '').lower()
                if expected_content_types and not any(content_type.startswith(ct) for ct in expected_content_types):
                    raise NetworkSecurityError(
                        f"Invalid content type: {content_type}. Expected one of: {expected_content_types}"
                    )
            except Exception as head_error:
                # HEAD request failed, continue with GET but be more cautious
                if require_head_success:
                    raise NetworkSecurityError(f"HEAD request required but failed: {head_error!r}",
                                               original_error=head_error) from head_error
                logger.debug(f"HEAD request failed for {url}: {head_error}")


            # Stream the actual content with size validation
            with client.stream('GET', url) as response:
                response.raise_for_status()

                # Final content type check from GET response
                content_type = response.headers.get('content-type', '').lower()
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

                content = b''.join(content_chunks)
                logger.debug(f"Successfully fetched {total_size} bytes from {url}")
                return content

    except Exception as e:
        if isinstance(e, NetworkSecurityError):
            raise
        # Check if it's an httpx error
        if hasattr(e, '__module__') and e.__module__ and 'httpx' in e.__module__:
            raise NetworkSecurityError(f"HTTP request failed for {url}: {e}") from e
        raise NetworkSecurityError(f"Unexpected error fetching {url}: {e}") from e


def fetch_image_securely(
        url: str,
        allowed_hosts: list[str] | None = None,
        require_https: bool = False,
        max_size_bytes: int = 20 * 1024 * 1024,  # 20MB
        timeout: float = 30.0,
        require_head_success: bool = True,
) -> bytes:
    """Securely fetch image data from URL with comprehensive validation.

    This is a convenience wrapper around fetch_content_securely for image downloads.

    Parameters
    ----------
    url : str
        URL to fetch image from
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks
    require_https : bool, default False
        If True, only HTTPS URLs are allowed
    max_size_bytes : int, default 20MB
        Maximum allowed response size in bytes
    timeout : float, default 10.0
        Request timeout in seconds

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
        expected_content_types=["image/"]
    )


def is_network_disabled() -> bool:
    """Check if network access is globally disabled via environment variable.

    Returns
    -------
    bool
        True if network access should be disabled, False otherwise

    """
    return os.getenv('ALL2MD_DISABLE_NETWORK', '').lower() in ('true', '1', 'yes', 'on')
