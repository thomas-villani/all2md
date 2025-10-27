"""Unit tests for network security utilities and SSRF protection.

This test module validates the security measures implemented to prevent
Server-Side Request Forgery (SSRF) attacks in the all2md library.

Test Coverage:
- IP address validation (IPv4 and IPv6)
- Hostname resolution and validation
- URL security validation
- Environment variable controls
- Error handling and security exceptions
"""

import ipaddress
import os
import socket
from unittest.mock import MagicMock, Mock, patch

import pytest

from all2md.exceptions import NetworkSecurityError
from all2md.utils.network_security import (
    RateLimiter,
    _is_private_or_reserved_ip,
    _normalize_hostname,
    _parse_content_type,
    _resolve_hostname_to_ips,
    _validate_hostname_allowlist,
    fetch_image_securely,
    is_network_disabled,
    validate_url_security,
)


class TestPrivateIPValidation:
    """Test private and reserved IP address detection."""

    def test_ipv4_private_ranges(self):
        """Test IPv4 private IP range detection."""
        # Private ranges
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("10.0.0.1"))
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("172.16.1.1"))
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("192.168.1.1"))

        # Public IPs should be allowed
        assert not _is_private_or_reserved_ip(ipaddress.IPv4Address("8.8.8.8"))
        assert not _is_private_or_reserved_ip(ipaddress.IPv4Address("1.1.1.1"))

    def test_ipv4_loopback_and_local(self):
        """Test IPv4 loopback and link-local detection."""
        # Loopback
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("127.0.0.1"))
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("127.255.255.254"))

        # Link-local
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("169.254.1.1"))

    def test_ipv4_special_ranges(self):
        """Test IPv4 special-use and reserved ranges."""
        # RFC6598 Carrier NAT
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("100.64.0.1"))

        # Test networks
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("192.0.2.1"))  # Test-Net-1
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("198.51.100.1"))  # Test-Net-2
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("203.0.113.1"))  # Test-Net-3

        # Benchmarking
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("198.18.0.1"))

        # "This" network
        assert _is_private_or_reserved_ip(ipaddress.IPv4Address("0.0.0.1"))

    def test_ipv6_private_ranges(self):
        """Test IPv6 private and reserved ranges."""
        # Loopback
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("::1"))

        # Link-local
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("fe80::1"))

        # ULA (Unique Local Address)
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("fc00::1"))
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("fd00::1"))

        # Public IPv6 should be allowed
        assert not _is_private_or_reserved_ip(ipaddress.IPv6Address("2001:4860:4860::8888"))

    def test_ipv6_special_ranges(self):
        """Test IPv6 special-use ranges."""
        # IPv4-mapped IPv6
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("::ffff:127.0.0.1"))

        # Documentation
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("2001:db8::1"))

        # Teredo
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("2001::1"))

        # 6to4
        assert _is_private_or_reserved_ip(ipaddress.IPv6Address("2002::1"))


class TestHostnameResolution:
    """Test hostname resolution and validation."""

    @patch("socket.getaddrinfo")
    def test_resolve_hostname_success(self, mock_getaddrinfo):
        """Test successful hostname resolution."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:4860:4860::8888", 80, 0, 0)),
        ]

        ips = _resolve_hostname_to_ips("example.com")
        assert len(ips) == 2
        assert ipaddress.IPv4Address("8.8.8.8") in ips
        assert ipaddress.IPv6Address("2001:4860:4860::8888") in ips

    @patch("socket.getaddrinfo")
    def test_resolve_hostname_failure(self, mock_getaddrinfo):
        """Test hostname resolution failure."""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")

        with pytest.raises(NetworkSecurityError, match="Failed to resolve hostname"):
            _resolve_hostname_to_ips("nonexistent.example")

    @patch("socket.getaddrinfo")
    def test_resolve_hostname_no_valid_ips(self, mock_getaddrinfo):
        """Test hostname with no valid IP addresses."""
        mock_getaddrinfo.return_value = []

        with pytest.raises(NetworkSecurityError, match="No valid IP addresses resolved"):
            _resolve_hostname_to_ips("empty.example")


class TestHostnameNormalization:
    """Test hostname normalization for case-insensitive matching."""

    def test_normalize_lowercase(self):
        """Test normalization of lowercase hostnames."""
        assert _normalize_hostname("example.com") == "example.com"
        assert _normalize_hostname("trusted.org") == "trusted.org"

    def test_normalize_uppercase(self):
        """Test normalization of uppercase hostnames."""
        assert _normalize_hostname("EXAMPLE.COM") == "example.com"
        assert _normalize_hostname("TRUSTED.ORG") == "trusted.org"

    def test_normalize_mixed_case(self):
        """Test normalization of mixed-case hostnames."""
        assert _normalize_hostname("Example.com") == "example.com"
        assert _normalize_hostname("ExAmPlE.CoM") == "example.com"
        assert _normalize_hostname("TrUsTeD.oRg") == "trusted.org"

    def test_normalize_idna_ascii(self):
        """Test IDNA normalization of ASCII hostnames."""
        # ASCII hostnames should remain unchanged (except lowercasing)
        assert _normalize_hostname("example.com") == "example.com"
        assert _normalize_hostname("sub.example.com") == "sub.example.com"

    def test_normalize_with_subdomain(self):
        """Test normalization of hostnames with subdomains."""
        assert _normalize_hostname("api.Example.com") == "api.example.com"
        assert _normalize_hostname("WWW.EXAMPLE.COM") == "www.example.com"

    def test_normalize_preserves_dots(self):
        """Test that normalization preserves dot structure."""
        assert _normalize_hostname("a.b.c.example.com") == "a.b.c.example.com"
        assert _normalize_hostname("A.B.C.EXAMPLE.COM") == "a.b.c.example.com"


class TestHostnameAllowlist:
    """Test hostname allowlist validation."""

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_allowlist_none_allows_all(self, mock_resolve):
        """Test that None allowlist allows all hostnames."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
        assert _validate_hostname_allowlist("example.com", None)

    def test_allowlist_exact_hostname_match(self):
        """Test exact hostname matching in allowlist."""
        allowed_hosts = ["example.com", "trusted.org"]
        assert _validate_hostname_allowlist("example.com", allowed_hosts)
        assert not _validate_hostname_allowlist("evil.com", allowed_hosts)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_allowlist_cidr_match(self, mock_resolve):
        """Test CIDR block matching in allowlist."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
        allowed_hosts = ["8.8.8.0/24", "example.com"]

        assert _validate_hostname_allowlist("google-dns.example", allowed_hosts)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_allowlist_resolution_failure(self, mock_resolve):
        """Test allowlist behavior when hostname resolution fails."""
        mock_resolve.side_effect = NetworkSecurityError("Resolution failed")
        allowed_hosts = ["example.com"]

        assert not _validate_hostname_allowlist("badhost.example", allowed_hosts)

    def test_allowlist_case_insensitive_match(self):
        """Test that hostname matching is case-insensitive."""
        # Allowlist with mixed case
        allowed_hosts = ["Example.com", "TRUSTED.ORG"]

        # Lowercase incoming hostnames should match
        assert _validate_hostname_allowlist("example.com", allowed_hosts)
        assert _validate_hostname_allowlist("trusted.org", allowed_hosts)

        # Uppercase incoming hostnames should match
        assert _validate_hostname_allowlist("EXAMPLE.COM", allowed_hosts)
        assert _validate_hostname_allowlist("TRUSTED.ORG", allowed_hosts)

        # Mixed case incoming hostnames should match
        assert _validate_hostname_allowlist("ExAmPlE.cOm", allowed_hosts)
        assert _validate_hostname_allowlist("TrUsTeD.oRg", allowed_hosts)

    def test_allowlist_case_insensitive_with_lowercase_allowlist(self):
        """Test case-insensitive matching with lowercase allowlist."""
        # Allowlist with all lowercase (common case)
        allowed_hosts = ["example.com", "trusted.org"]

        # Various case variations should all match
        assert _validate_hostname_allowlist("Example.com", allowed_hosts)
        assert _validate_hostname_allowlist("EXAMPLE.COM", allowed_hosts)
        assert _validate_hostname_allowlist("example.com", allowed_hosts)

        # Non-matching hostname should still fail
        assert not _validate_hostname_allowlist("evil.com", allowed_hosts)
        assert not _validate_hostname_allowlist("EVIL.COM", allowed_hosts)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_allowlist_mixed_hostnames_and_cidr(self, mock_resolve):
        """Test allowlist with both case-varied hostnames and CIDR blocks."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
        allowed_hosts = ["Example.com", "8.8.8.0/24", "TRUSTED.ORG"]

        # Hostname matches should be case-insensitive
        assert _validate_hostname_allowlist("example.com", allowed_hosts)
        assert _validate_hostname_allowlist("EXAMPLE.COM", allowed_hosts)
        assert _validate_hostname_allowlist("trusted.org", allowed_hosts)

        # CIDR block match should still work
        assert _validate_hostname_allowlist("google-dns.example", allowed_hosts)

    def test_allowlist_idna_normalization(self):
        """Test that IDNA/punycode domains are properly normalized."""
        # Test with ASCII domain in allowlist
        allowed_hosts = ["example.com"]

        # Same domain but explicitly IDNA-encoded should match
        # (though encode("idna").decode("ascii") for ASCII is identity)
        assert _validate_hostname_allowlist("example.com", allowed_hosts)

        # Test case-insensitive IDNA
        allowed_hosts_mixed = ["Example.COM"]
        assert _validate_hostname_allowlist("example.com", allowed_hosts_mixed)


class TestURLSecurityValidation:
    """Test comprehensive URL security validation."""

    def test_invalid_url_format(self):
        """Test validation of malformed URLs."""
        with pytest.raises(NetworkSecurityError, match="Invalid URL format"):
            validate_url_security("not-a-url")

    def test_unsupported_scheme(self):
        """Test blocking of unsupported URL schemes."""
        with pytest.raises(NetworkSecurityError, match="Unsupported URL scheme"):
            validate_url_security("ftp://example.com/file.txt")

        with pytest.raises(NetworkSecurityError, match="Unsupported URL scheme"):
            validate_url_security("javascript:alert('xss')")

    def test_https_requirement(self):
        """Test HTTPS requirement enforcement."""
        with pytest.raises(NetworkSecurityError, match="HTTPS required"):
            validate_url_security("http://example.com", require_https=True)

        # Should not raise for HTTPS
        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
            validate_url_security("https://example.com", require_https=True)

    def test_missing_hostname(self):
        """Test validation of URLs without hostnames."""
        with pytest.raises(NetworkSecurityError, match="URL missing hostname"):
            validate_url_security("http:///path", require_https=False)

    @patch("all2md.utils.network_security._validate_hostname_allowlist")
    def test_hostname_allowlist_enforcement(self, mock_allowlist):
        """Test hostname allowlist enforcement."""
        mock_allowlist.return_value = False

        with pytest.raises(NetworkSecurityError, match="Hostname not in allowlist"):
            validate_url_security("http://evil.com", allowed_hosts=["trusted.com"], require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_private_ip_blocking(self, mock_resolve):
        """Test blocking of private IP addresses."""
        mock_resolve.return_value = [ipaddress.IPv4Address("192.168.1.1")]

        with pytest.raises(NetworkSecurityError, match="Access to private/reserved IP"):
            validate_url_security("http://internal.company.com", require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_valid_url_passes(self, mock_resolve):
        """Test that valid URLs pass validation."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        # Should not raise
        validate_url_security("https://example.com/image.png")


class TestEnvironmentControls:
    """Test environment variable controls."""

    def test_network_disabled_false_by_default(self):
        """Test that network is enabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            assert not is_network_disabled()

    def test_network_disabled_true_values(self):
        """Test various ways to disable network access."""
        true_values = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]

        for value in true_values:
            with patch.dict(os.environ, {"ALL2MD_DISABLE_NETWORK": value}):
                assert is_network_disabled()

    def test_network_disabled_false_values(self):
        """Test values that don't disable network access."""
        false_values = ["false", "False", "0", "no", "off", "random"]

        for value in false_values:
            with patch.dict(os.environ, {"ALL2MD_DISABLE_NETWORK": value}):
                assert not is_network_disabled()


class TestSecureImageFetching:
    """Test secure image fetching functionality."""

    @patch("all2md.utils.network_security.is_network_disabled")
    def test_fetch_blocked_by_global_disable(self, mock_disabled):
        """Test that global network disable blocks fetching."""
        mock_disabled.return_value = True

        with pytest.raises(NetworkSecurityError, match="Network access is globally disabled"):
            fetch_image_securely("https://example.com/image.png")

    @patch("all2md.utils.network_security.validate_url_security")
    @patch("all2md.utils.network_security.create_secure_http_client")
    @patch("all2md.utils.network_security.is_network_disabled")
    def test_fetch_successful(self, mock_disabled, mock_client, mock_validate):
        """Test successful image fetching."""
        mock_disabled.return_value = False
        mock_validate.return_value = None  # No exception

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {"content-type": "image/png", "content-length": "15"}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response
        mock_stream_response = Mock()
        mock_stream_response.headers = {"content-type": "image/png"}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = [b"fake_image_data"]
        mock_stream_response.__enter__ = Mock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = Mock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.head.return_value = mock_head_response
        mock_http_client.stream.return_value = mock_stream_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None

        mock_client.return_value = mock_http_client

        result = fetch_image_securely("https://example.com/image.png")
        assert result == b"fake_image_data"

    @patch("all2md.utils.network_security.validate_url_security")
    @patch("all2md.utils.network_security.create_secure_http_client")
    @patch("all2md.utils.network_security.is_network_disabled")
    def test_fetch_invalid_content_type(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of non-image content types."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {"content-type": "text/html", "content-length": "26"}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response - not reached due to HEAD content-type check
        mock_stream_response = Mock()
        mock_stream_response.headers = {"content-type": "text/html"}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = [b"<html>not an image</html>"]
        mock_stream_response.__enter__ = Mock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = Mock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.head.return_value = mock_head_response
        mock_http_client.stream.return_value = mock_stream_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None

        mock_client.return_value = mock_http_client

        with pytest.raises(NetworkSecurityError, match="Invalid content type"):
            fetch_image_securely("https://example.com/notimage.html")

    @patch("all2md.utils.network_security.validate_url_security")
    @patch("all2md.utils.network_security.create_secure_http_client")
    @patch("all2md.utils.network_security.is_network_disabled")
    def test_fetch_too_large(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of oversized content."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {"content-type": "image/png"}  # No content-length
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response with large chunks
        large_chunk = b"x" * (10 * 1024 * 1024)  # 10MB chunks
        mock_stream_response = Mock()
        mock_stream_response.headers = {"content-type": "image/png"}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = [large_chunk, large_chunk, large_chunk]  # 30MB total
        mock_stream_response.__enter__ = Mock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = Mock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.head.return_value = mock_head_response
        mock_http_client.stream.return_value = mock_stream_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None

        mock_client.return_value = mock_http_client

        with pytest.raises(NetworkSecurityError, match="Response too large"):
            fetch_image_securely("https://example.com/huge.png", max_size_bytes=20 * 1024 * 1024)

    @patch("all2md.utils.network_security.validate_url_security")
    @patch("all2md.utils.network_security.create_secure_http_client")
    @patch("all2md.utils.network_security.is_network_disabled")
    def test_fetch_empty_response(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of empty responses."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {"content-type": "image/png", "content-length": "0"}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response with empty content
        mock_stream_response = Mock()
        mock_stream_response.headers = {"content-type": "image/png"}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = []  # Empty content
        mock_stream_response.__enter__ = Mock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = Mock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.head.return_value = mock_head_response
        mock_http_client.stream.return_value = mock_stream_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None

        mock_client.return_value = mock_http_client

        with pytest.raises(NetworkSecurityError, match="Empty response received"):
            fetch_image_securely("https://example.com/empty.png")


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_localhost_attacks_blocked(self):
        """Test that localhost-based SSRF attacks are blocked."""
        localhost_urls = [
            "http://localhost/admin",
            "http://127.0.0.1:8080/internal",
            "http://[::1]/secret",
        ]

        for url in localhost_urls:
            with pytest.raises(NetworkSecurityError):
                validate_url_security(url)

    def test_private_network_attacks_blocked(self):
        """Test that private network SSRF attacks are blocked."""
        private_urls = [
            "http://192.168.1.1/router",
            "http://10.0.0.1/internal",
            "http://172.16.1.1/admin",
        ]

        for url in private_urls:
            with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
                # Extract IP from URL for mocking
                ip_str = url.split("//")[1].split("/")[0].split(":")[0]
                mock_resolve.return_value = [ipaddress.ip_address(ip_str)]

                with pytest.raises(NetworkSecurityError):
                    validate_url_security(url)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_cloud_metadata_attacks_blocked(self, mock_resolve):
        """Test that cloud metadata service attacks are blocked."""
        # AWS metadata service
        mock_resolve.return_value = [ipaddress.IPv4Address("169.254.169.254")]

        with pytest.raises(NetworkSecurityError):
            validate_url_security("http://169.254.169.254/latest/meta-data/")

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_legitimate_cdns_allowed(self, mock_resolve):
        """Test that legitimate CDNs are allowed."""
        mock_resolve.return_value = [ipaddress.IPv4Address("151.101.193.140")]  # Reddit CDN

        # Should not raise
        validate_url_security("https://i.redd.it/image.png")


class TestEventHooksImplementation:
    """Test the new event hooks-based HTTP client implementation."""

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_event_hooks_validate_initial_request(self, mock_resolve):
        """Test that request event hooks validate the initial URL."""
        from all2md.utils.network_security import create_secure_http_client

        # Mock private IP resolution to trigger security error
        mock_resolve.return_value = [ipaddress.IPv4Address("192.168.1.1")]

        client = create_secure_http_client()

        # Attempting to make a request should trigger validation in the request hook
        with pytest.raises(Exception):  # NetworkSecurityError will be wrapped by httpx
            with client:
                client.get("http://internal.company.com")

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_event_hooks_validate_redirect_chain(self, mock_resolve):
        """Test that response event hooks validate redirect chains."""
        from all2md.utils.network_security import create_secure_http_client

        # Create a mock response with redirect history containing a private IP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.history = [
            Mock(url="http://safe.example.com"),  # Initial URL (safe)
            Mock(url="http://192.168.1.1/evil"),  # Redirect to private IP (unsafe)
        ]

        mock_response.request.extensions = {"redirect_count": 2}

        # Mock resolution: safe.example.com -> public IP, but the redirect history contains private IP
        def mock_resolver(hostname):
            if hostname == "safe.example.com":
                return [ipaddress.IPv4Address("8.8.8.8")]  # Public IP
            elif hostname == "192.168.1.1":
                return [ipaddress.IPv4Address("192.168.1.1")]  # Private IP
            return [ipaddress.IPv4Address("8.8.8.8")]

        mock_resolve.side_effect = mock_resolver

        client = create_secure_http_client()

        # Test the response hook directly
        validate_response_redirects = None
        if hasattr(client, "event_hooks") and "response" in client.event_hooks:
            validate_response_redirects = client.event_hooks["response"][0]

        # Should raise NetworkSecurityError when validating redirect chain
        if validate_response_redirects:
            with pytest.raises(NetworkSecurityError):
                validate_response_redirects(mock_response)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_event_hooks_client_creation_success(self, mock_resolve):
        """Test that event hooks client is created successfully with valid configuration."""
        from all2md.utils.network_security import create_secure_http_client

        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        client = create_secure_http_client(
            timeout=15.0, max_redirects=3, allowed_hosts=["example.com"], require_https=True
        )

        # Verify client configuration - focus on event hooks
        assert client.follow_redirects is True
        assert hasattr(client, "event_hooks")
        assert "request" in client.event_hooks
        assert "response" in client.event_hooks
        assert len(client.event_hooks["request"]) == 1
        assert len(client.event_hooks["response"]) == 1

        # Verify timeout is set (as an httpx.Timeout object)
        assert client.timeout is not None


@pytest.mark.unit
@pytest.mark.security
class TestRedirectLimitEdgeCases:
    """Test redirect limit enforcement edge cases."""

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_exactly_at_redirect_limit(self, mock_resolve):
        """Test that exactly max_redirects redirects are allowed."""
        from all2md.utils.network_security import create_secure_http_client

        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        # Create client with max_redirects=3, allow HTTP for this test
        client = create_secure_http_client(max_redirects=3, require_https=False)

        # Create mock response with exactly 3 redirects in history
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.history = [
            Mock(url="http://example.com/1"),
            Mock(url="http://example.com/2"),
            Mock(url="http://example.com/3"),
        ]
        mock_response.request = Mock()
        mock_response.request.extensions = {"redirect_count": 3}

        # Get the response validation hook
        validate_response = client.event_hooks["response"][0]

        # Should not raise - exactly at limit
        validate_response(mock_response)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_one_over_redirect_limit(self, mock_resolve):
        """Test that max_redirects + 1 redirects are blocked."""
        from all2md.utils.network_security import create_secure_http_client

        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        client = create_secure_http_client(max_redirects=3)

        # Create mock response with 4 redirects (one over limit)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.history = [
            Mock(url="http://example.com/1"),
            Mock(url="http://example.com/2"),
            Mock(url="http://example.com/3"),
            Mock(url="http://example.com/4"),
        ]
        mock_response.request = Mock()
        mock_response.request.extensions = {"redirect_count": 4}

        validate_response = client.event_hooks["response"][0]

        # Should raise - over limit
        with pytest.raises(NetworkSecurityError, match="Too many redirects"):
            validate_response(mock_response)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_redirect_loop_detection(self, mock_resolve):
        """Test that redirect loops eventually get blocked by limit."""
        from all2md.utils.network_security import create_secure_http_client

        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        client = create_secure_http_client(max_redirects=5)

        # Simulate redirect loop
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.history = [
            Mock(url="http://example.com/a"),
            Mock(url="http://example.com/b"),
            Mock(url="http://example.com/a"),
            Mock(url="http://example.com/b"),
            Mock(url="http://example.com/a"),
            Mock(url="http://example.com/b"),
        ]
        mock_response.request = Mock()
        mock_response.request.extensions = {"redirect_count": 6}

        validate_response = client.event_hooks["response"][0]

        # Should raise - exceeds limit
        with pytest.raises(NetworkSecurityError, match="Too many redirects"):
            validate_response(mock_response)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_redirect_from_https_to_http_blocked_with_require_https(self, mock_resolve):
        """Test that HTTPS->HTTP redirects are blocked when require_https=True."""
        from all2md.utils.network_security import create_secure_http_client

        def mock_resolver(hostname):
            return [ipaddress.IPv4Address("8.8.8.8")]

        mock_resolve.side_effect = mock_resolver

        client = create_secure_http_client(max_redirects=5, require_https=True)

        # Simulate redirect from HTTPS to HTTP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.history = [
            Mock(url="https://example.com/secure"),
            Mock(url="http://example.com/insecure"),  # Downgrade to HTTP
        ]
        mock_response.request = Mock()
        mock_response.request.extensions = {"redirect_count": 2}

        validate_response = client.event_hooks["response"][0]

        # Should raise due to HTTP in redirect chain
        with pytest.raises(NetworkSecurityError, match="HTTPS required"):
            validate_response(mock_response)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_redirect_to_private_ip_blocked(self, mock_resolve):
        """Test that redirects to private IPs are blocked."""
        from all2md.utils.network_security import create_secure_http_client

        def mock_resolver(hostname):
            if hostname == "public.com":
                return [ipaddress.IPv4Address("8.8.8.8")]
            elif hostname == "192.168.1.1":
                return [ipaddress.IPv4Address("192.168.1.1")]
            return [ipaddress.IPv4Address("8.8.8.8")]

        mock_resolve.side_effect = mock_resolver

        client = create_secure_http_client(max_redirects=5)

        # Simulate redirect to private IP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.history = [
            Mock(url="http://public.com/start"),
            Mock(url="http://192.168.1.1/admin"),  # Private IP
        ]
        mock_response.request = Mock()
        mock_response.request.extensions = {"redirect_count": 2}

        validate_response = client.event_hooks["response"][0]

        # Should raise due to private IP in redirect
        with pytest.raises(NetworkSecurityError):
            validate_response(mock_response)


@pytest.mark.unit
@pytest.mark.security
class TestSSRFEdgeCases:
    """Test SSRF prevention edge cases and advanced attack vectors."""

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_dns_rebinding_simulation(self, mock_resolve):
        """Test that DNS rebinding attacks are prevented by checking all resolved IPs."""
        # Simulate DNS rebinding: first resolves to public IP, then to private
        call_count = [0]

        def dns_rebinding_resolver(hostname):
            call_count[0] += 1
            if call_count[0] == 1:
                # First resolution: public IP (attacker's server)
                return [ipaddress.IPv4Address("8.8.8.8")]
            else:
                # Subsequent resolutions: private IP (internal server)
                return [ipaddress.IPv4Address("192.168.1.1")]

        mock_resolve.side_effect = dns_rebinding_resolver

        # First call should pass (public IP)
        validate_url_security("http://rebinding.evil.com", require_https=False)

        # Second call with same hostname should fail (private IP)
        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://rebinding.evil.com", require_https=False)

    def test_ipv6_localhost_blocked(self):
        """Test that IPv6 localhost addresses are blocked."""
        ipv6_loopback_urls = [
            "http://[::1]/admin",
            "http://[0:0:0:0:0:0:0:1]/secret",
        ]

        for url in ipv6_loopback_urls:
            with pytest.raises(NetworkSecurityError):
                validate_url_security(url)

    def test_ipv6_link_local_blocked(self):
        """Test that IPv6 link-local addresses are blocked."""
        with pytest.raises(NetworkSecurityError):
            validate_url_security("http://[fe80::1]/internal")

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_ipv4_mapped_ipv6_blocked(self, mock_resolve):
        """Test that IPv4-mapped IPv6 addresses are blocked if they're private."""
        # IPv4-mapped IPv6 for 127.0.0.1
        mock_resolve.return_value = [ipaddress.IPv6Address("::ffff:127.0.0.1")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://ipv4mapped.example.com", require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_multiple_ips_with_one_private(self, mock_resolve):
        """Test that if any resolved IP is private, the URL is blocked."""
        # Hostname resolves to both public and private IPs
        mock_resolve.return_value = [
            ipaddress.IPv4Address("8.8.8.8"),  # Public
            ipaddress.IPv4Address("192.168.1.1"),  # Private
            ipaddress.IPv4Address("1.1.1.1"),  # Public
        ]

        # Should be blocked because one IP is private
        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://mixed-ips.example.com", require_https=False)

    def test_url_encoding_normalization(self):
        """Test that URL encoding doesn't bypass IP checks."""
        # URL-encoded localhost variations
        encoded_urls = [
            "http://127.0.0.1/admin",
            "http://0x7f.0x0.0x0.0x1/admin",  # Hex notation
        ]

        for url in encoded_urls:
            with pytest.raises(NetworkSecurityError):
                validate_url_security(url)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_aws_metadata_service_blocked(self, mock_resolve):
        """Test that AWS metadata service IP is blocked."""
        mock_resolve.return_value = [ipaddress.IPv4Address("169.254.169.254")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://instance-metadata.amazonaws.com", require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_gcp_metadata_service_blocked(self, mock_resolve):
        """Test that GCP metadata service IP is blocked."""
        # GCP uses 169.254.169.254 via metadata.google.internal
        mock_resolve.return_value = [ipaddress.IPv4Address("169.254.169.254")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://metadata.google.internal", require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_azure_metadata_service_blocked(self, mock_resolve):
        """Test that Azure metadata service IP is blocked."""
        # Azure uses 169.254.169.254
        mock_resolve.return_value = [ipaddress.IPv4Address("169.254.169.254")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://169.254.169.254/metadata/instance", require_https=False)

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_docker_internal_network_blocked(self, mock_resolve):
        """Test that Docker internal network IPs are blocked."""
        # Common Docker bridge network
        mock_resolve.return_value = [ipaddress.IPv4Address("172.17.0.1")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://docker.internal", require_https=False)

    def test_broadcast_address_blocked(self):
        """Test that broadcast addresses are blocked."""
        # 255.255.255.255 is reserved
        with pytest.raises(NetworkSecurityError):
            validate_url_security("http://255.255.255.255/admin")

    @patch("all2md.utils.network_security._resolve_hostname_to_ips")
    def test_multicast_address_blocked(self, mock_resolve):
        """Test that multicast addresses are blocked."""
        # 224.0.0.0/4 is multicast
        mock_resolve.return_value = [ipaddress.IPv4Address("224.0.0.1")]

        with pytest.raises(NetworkSecurityError, match="private/reserved IP"):
            validate_url_security("http://multicast.example.com", require_https=False)


class TestContentTypeParsing:
    """Test content-type header parsing."""

    def test_simple_content_type(self):
        """Test parsing simple content-type without parameters."""
        assert _parse_content_type("image/png") == "image/png"
        assert _parse_content_type("text/html") == "text/html"
        assert _parse_content_type("application/json") == "application/json"

    def test_content_type_with_charset(self):
        """Test parsing content-type with charset parameter."""
        assert _parse_content_type("text/html; charset=utf-8") == "text/html"
        assert _parse_content_type("text/html; charset=UTF-8") == "text/html"
        assert _parse_content_type("application/json; charset=utf-8") == "application/json"

    def test_content_type_with_boundary(self):
        """Test parsing content-type with boundary parameter."""
        assert _parse_content_type("multipart/form-data; boundary=----WebKitFormBoundary") == "multipart/form-data"

    def test_content_type_with_multiple_parameters(self):
        """Test parsing content-type with multiple parameters."""
        assert _parse_content_type("text/html; charset=utf-8; boundary=foo") == "text/html"
        assert _parse_content_type("image/png; name=file.png; size=1234") == "image/png"

    def test_content_type_case_insensitive(self):
        """Test that content-type parsing is case-insensitive."""
        assert _parse_content_type("IMAGE/PNG") == "image/png"
        assert _parse_content_type("Text/HTML; Charset=UTF-8") == "text/html"

    def test_content_type_with_malicious_parameters(self):
        """Test parsing content-type with potentially malicious parameters."""
        # Should extract only the main type, ignoring suspicious parameters
        assert _parse_content_type("image/png; <script>alert('xss')</script>") == "image/png"
        assert _parse_content_type("text/html; attack=payload") == "text/html"

    def test_empty_content_type(self):
        """Test parsing empty content-type."""
        assert _parse_content_type("") == ""
        assert _parse_content_type(None) == ""

    def test_invalid_content_type(self):
        """Test parsing invalid content-type."""
        # email.message.Message defaults to text/plain for invalid types
        assert _parse_content_type("invalid") == "text/plain"
        assert _parse_content_type("not-a-mime-type") == "text/plain"


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests_per_second=10.0, max_concurrent=5)
        assert limiter.max_requests_per_second == 10.0
        assert limiter.max_concurrent == 5

    def test_single_request_allowed(self):
        """Test that a single request is allowed immediately."""
        limiter = RateLimiter(max_requests_per_second=10.0, max_concurrent=5)
        assert limiter.acquire(timeout=1.0) is True
        limiter.release()

    def test_concurrent_limit(self):
        """Test that concurrent request limit is enforced."""
        import threading
        import time

        limiter = RateLimiter(max_requests_per_second=100.0, max_concurrent=2)
        acquired = []

        def worker(worker_id):
            if limiter.acquire(timeout=0.1):
                acquired.append(worker_id)
                time.sleep(0.5)  # Hold the slot
                limiter.release()

        # Start 3 threads trying to acquire 2 slots
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only 2 should have succeeded within the timeout
        assert len(acquired) == 2

    def test_rate_limiting_per_second(self):
        """Test that rate limiting enforces requests per second."""
        import time

        limiter = RateLimiter(max_requests_per_second=5.0, max_concurrent=10)

        # Make 5 rapid requests (should all succeed)
        for _ in range(5):
            assert limiter.acquire(timeout=2.0) is True
            limiter.release()

        # The 6th request should be delayed
        sixth_start = time.time()
        assert limiter.acquire(timeout=2.0) is True
        limiter.release()
        sixth_elapsed = time.time() - sixth_start

        # Should have waited at least a bit (bucket refill)
        # Allow for some timing variance
        assert sixth_elapsed > 0.05, "Rate limiter should have delayed the 6th request"

    def test_context_manager(self):
        """Test rate limiter as context manager."""
        limiter = RateLimiter(max_requests_per_second=10.0, max_concurrent=5)

        with limiter:
            # Should acquire successfully
            pass

        # Should have released automatically

    def test_timeout_behavior(self):
        """Test timeout behavior when rate limit is exceeded."""
        limiter = RateLimiter(max_requests_per_second=1.0, max_concurrent=1)

        # Acquire first slot
        assert limiter.acquire(timeout=1.0) is True

        # Try to acquire second slot immediately (should timeout)
        assert limiter.acquire(timeout=0.01) is False

        # Release first slot
        limiter.release()

    def test_semaphore_timeout_refunds_token(self):
        """Test that tokens are refunded when semaphore acquisition times out."""
        # Create limiter with high rate limit but low concurrent limit
        limiter = RateLimiter(max_requests_per_second=100.0, max_concurrent=1)

        # Record initial token count
        with limiter.lock:
            initial_tokens = limiter.tokens

        # Acquire the only concurrent slot
        assert limiter.acquire(timeout=1.0) is True

        # Try to acquire second slot - should timeout on semaphore
        # This should decrement a token, fail on semaphore, then refund the token
        assert limiter.acquire(timeout=0.05) is False

        # Check that token was refunded
        with limiter.lock:
            # Token should be back (minus the one used by first acquire)
            # Initial was 100, first acquire took 1 (99 remaining)
            # Second acquire should have taken 1, then refunded it (back to 99)
            # Allow small variance due to token refill during execution
            expected_tokens = initial_tokens - 1.0
            assert (
                abs(limiter.tokens - expected_tokens) < 0.5
            ), f"Expected ~{expected_tokens} tokens, got {limiter.tokens}"

        # Release first slot
        limiter.release()

    def test_token_bucket_integrity_after_semaphore_timeout(self):
        """Test token bucket integrity with multiple threads timing out on semaphore."""
        import threading
        import time

        limiter = RateLimiter(max_requests_per_second=50.0, max_concurrent=2)

        # Record initial token count
        with limiter.lock:
            initial_tokens = limiter.tokens

        successful_acquires = []
        failed_acquires = []

        def worker(worker_id):
            if limiter.acquire(timeout=0.1):
                successful_acquires.append(worker_id)
                time.sleep(0.3)  # Hold the slot
                limiter.release()
            else:
                failed_acquires.append(worker_id)

        # Start 10 threads competing for 2 slots
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Some should succeed, others should fail
        assert len(successful_acquires) > 0
        assert len(failed_acquires) > 0

        # Wait for token refill
        time.sleep(0.5)

        # Check token bucket integrity - tokens should be close to max
        # (allowing for small timing variations)
        with limiter.lock:
            # After waiting, tokens should have refilled significantly
            # At minimum, should have more than initial minus successful acquires
            assert limiter.tokens >= initial_tokens - len(successful_acquires)
            # Should not exceed maximum
            assert limiter.tokens <= limiter.max_requests_per_second

    def test_semaphore_timeout_allows_future_requests(self):
        """Test that refunded tokens from semaphore timeout can be used by future requests."""
        import time

        limiter = RateLimiter(max_requests_per_second=10.0, max_concurrent=1)

        # Acquire the concurrent slot
        assert limiter.acquire(timeout=1.0) is True

        # Attempt to acquire - should fail on semaphore and refund token
        assert limiter.acquire(timeout=0.05) is False

        # Release the concurrent slot
        limiter.release()

        # Now a new request should be able to use the refunded token immediately
        # without waiting for token bucket refill
        start_time = time.time()
        assert limiter.acquire(timeout=1.0) is True
        elapsed = time.time() - start_time

        # Should succeed quickly (not delayed by rate limiting)
        # since the token was refunded
        assert elapsed < 0.2, f"Request should succeed immediately with refunded token, took {elapsed}s"

        limiter.release()
