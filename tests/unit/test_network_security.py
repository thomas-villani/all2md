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

from all2md.utils.network_security import (
    _is_private_or_reserved_ip,
    _resolve_hostname_to_ips,
    _validate_hostname_allowlist,
    fetch_image_securely,
    is_network_disabled,
    validate_url_security,
)
from all2md.exceptions import NetworkSecurityError


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

    @patch('socket.getaddrinfo')
    def test_resolve_hostname_success(self, mock_getaddrinfo):
        """Test successful hostname resolution."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 80)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:4860:4860::8888', 80, 0, 0)),
        ]

        ips = _resolve_hostname_to_ips("example.com")
        assert len(ips) == 2
        assert ipaddress.IPv4Address("8.8.8.8") in ips
        assert ipaddress.IPv6Address("2001:4860:4860::8888") in ips

    @patch('socket.getaddrinfo')
    def test_resolve_hostname_failure(self, mock_getaddrinfo):
        """Test hostname resolution failure."""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")

        with pytest.raises(NetworkSecurityError, match="Failed to resolve hostname"):
            _resolve_hostname_to_ips("nonexistent.example")

    @patch('socket.getaddrinfo')
    def test_resolve_hostname_no_valid_ips(self, mock_getaddrinfo):
        """Test hostname with no valid IP addresses."""
        mock_getaddrinfo.return_value = []

        with pytest.raises(NetworkSecurityError, match="No valid IP addresses resolved"):
            _resolve_hostname_to_ips("empty.example")


class TestHostnameAllowlist:
    """Test hostname allowlist validation."""

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_allowlist_none_allows_all(self, mock_resolve):
        """Test that None allowlist allows all hostnames."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
        assert _validate_hostname_allowlist("example.com", None)

    def test_allowlist_exact_hostname_match(self):
        """Test exact hostname matching in allowlist."""
        allowed_hosts = ["example.com", "trusted.org"]
        assert _validate_hostname_allowlist("example.com", allowed_hosts)
        assert not _validate_hostname_allowlist("evil.com", allowed_hosts)

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_allowlist_cidr_match(self, mock_resolve):
        """Test CIDR block matching in allowlist."""
        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
        allowed_hosts = ["8.8.8.0/24", "example.com"]

        assert _validate_hostname_allowlist("google-dns.example", allowed_hosts)

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_allowlist_resolution_failure(self, mock_resolve):
        """Test allowlist behavior when hostname resolution fails."""
        mock_resolve.side_effect = NetworkSecurityError("Resolution failed")
        allowed_hosts = ["example.com"]

        assert not _validate_hostname_allowlist("badhost.example", allowed_hosts)


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
        with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
            validate_url_security("https://example.com", require_https=True)

    def test_missing_hostname(self):
        """Test validation of URLs without hostnames."""
        with pytest.raises(NetworkSecurityError, match="URL missing hostname"):
            validate_url_security("http:///path")

    @patch('all2md.utils.network_security._validate_hostname_allowlist')
    def test_hostname_allowlist_enforcement(self, mock_allowlist):
        """Test hostname allowlist enforcement."""
        mock_allowlist.return_value = False

        with pytest.raises(NetworkSecurityError, match="Hostname not in allowlist"):
            validate_url_security("http://evil.com", allowed_hosts=["trusted.com"])

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_private_ip_blocking(self, mock_resolve):
        """Test blocking of private IP addresses."""
        mock_resolve.return_value = [ipaddress.IPv4Address("192.168.1.1")]

        with pytest.raises(NetworkSecurityError, match="Access to private/reserved IP"):
            validate_url_security("http://internal.company.com")

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
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
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']

        for value in true_values:
            with patch.dict(os.environ, {'ALL2MD_DISABLE_NETWORK': value}):
                assert is_network_disabled()

    def test_network_disabled_false_values(self):
        """Test values that don't disable network access."""
        false_values = ['false', 'False', '0', 'no', 'off', 'random']

        for value in false_values:
            with patch.dict(os.environ, {'ALL2MD_DISABLE_NETWORK': value}):
                assert not is_network_disabled()


class TestSecureImageFetching:
    """Test secure image fetching functionality."""

    @patch('all2md.utils.network_security.is_network_disabled')
    def test_fetch_blocked_by_global_disable(self, mock_disabled):
        """Test that global network disable blocks fetching."""
        mock_disabled.return_value = True

        with pytest.raises(NetworkSecurityError, match="Network access is globally disabled"):
            fetch_image_securely("https://example.com/image.png")

    @patch('all2md.utils.network_security.validate_url_security')
    @patch('all2md.utils.network_security.create_secure_http_client')
    @patch('all2md.utils.network_security.is_network_disabled')
    def test_fetch_successful(self, mock_disabled, mock_client, mock_validate):
        """Test successful image fetching."""
        mock_disabled.return_value = False
        mock_validate.return_value = None  # No exception

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'image/png', 'content-length': '15'}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response
        mock_stream_response = Mock()
        mock_stream_response.headers = {'content-type': 'image/png'}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = [b'fake_image_data']
        mock_stream_response.__enter__ = Mock(return_value=mock_stream_response)
        mock_stream_response.__exit__ = Mock(return_value=None)

        mock_http_client = MagicMock()
        mock_http_client.head.return_value = mock_head_response
        mock_http_client.stream.return_value = mock_stream_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None

        mock_client.return_value = mock_http_client

        result = fetch_image_securely("https://example.com/image.png")
        assert result == b'fake_image_data'

    @patch('all2md.utils.network_security.validate_url_security')
    @patch('all2md.utils.network_security.create_secure_http_client')
    @patch('all2md.utils.network_security.is_network_disabled')
    def test_fetch_invalid_content_type(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of non-image content types."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'text/html', 'content-length': '26'}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response - not reached due to HEAD content-type check
        mock_stream_response = Mock()
        mock_stream_response.headers = {'content-type': 'text/html'}
        mock_stream_response.raise_for_status.return_value = None
        mock_stream_response.iter_bytes.return_value = [b'<html>not an image</html>']
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

    @patch('all2md.utils.network_security.validate_url_security')
    @patch('all2md.utils.network_security.create_secure_http_client')
    @patch('all2md.utils.network_security.is_network_disabled')
    def test_fetch_too_large(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of oversized content."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'image/png'}  # No content-length
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response with large chunks
        large_chunk = b'x' * (10 * 1024 * 1024)  # 10MB chunks
        mock_stream_response = Mock()
        mock_stream_response.headers = {'content-type': 'image/png'}
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

    @patch('all2md.utils.network_security.validate_url_security')
    @patch('all2md.utils.network_security.create_secure_http_client')
    @patch('all2md.utils.network_security.is_network_disabled')
    def test_fetch_empty_response(self, mock_disabled, mock_client, mock_validate):
        """Test rejection of empty responses."""
        mock_disabled.return_value = False
        mock_validate.return_value = None

        # Mock HEAD response
        mock_head_response = Mock()
        mock_head_response.headers = {'content-type': 'image/png', 'content-length': '0'}
        mock_head_response.raise_for_status.return_value = None

        # Mock streaming response with empty content
        mock_stream_response = Mock()
        mock_stream_response.headers = {'content-type': 'image/png'}
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
            with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
                # Extract IP from URL for mocking
                ip_str = url.split('//')[1].split('/')[0].split(':')[0]
                mock_resolve.return_value = [ipaddress.ip_address(ip_str)]

                with pytest.raises(NetworkSecurityError):
                    validate_url_security(url)

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_cloud_metadata_attacks_blocked(self, mock_resolve):
        """Test that cloud metadata service attacks are blocked."""
        # AWS metadata service
        mock_resolve.return_value = [ipaddress.IPv4Address("169.254.169.254")]

        with pytest.raises(NetworkSecurityError):
            validate_url_security("http://169.254.169.254/latest/meta-data/")

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_legitimate_cdns_allowed(self, mock_resolve):
        """Test that legitimate CDNs are allowed."""
        mock_resolve.return_value = [ipaddress.IPv4Address("151.101.193.140")]  # Reddit CDN

        # Should not raise
        validate_url_security("https://i.redd.it/image.png")


class TestEventHooksImplementation:
    """Test the new event hooks-based HTTP client implementation."""

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
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

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_event_hooks_validate_redirect_chain(self, mock_resolve):
        """Test that response event hooks validate redirect chains."""

        from all2md.utils.network_security import create_secure_http_client

        # Create a mock response with redirect history containing a private IP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.history = [
            Mock(url="http://safe.example.com"),  # Initial URL (safe)
            Mock(url="http://192.168.1.1/evil")   # Redirect to private IP (unsafe)
        ]

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
        if hasattr(client, 'event_hooks') and 'response' in client.event_hooks:
            validate_response_redirects = client.event_hooks['response'][0]

        # Should raise NetworkSecurityError when validating redirect chain
        if validate_response_redirects:
            with pytest.raises(Exception):  # NetworkSecurityError will be raised
                validate_response_redirects(mock_response)

    @patch('all2md.utils.network_security._resolve_hostname_to_ips')
    def test_event_hooks_client_creation_success(self, mock_resolve):
        """Test that event hooks client is created successfully with valid configuration."""
        from all2md.utils.network_security import create_secure_http_client

        mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

        client = create_secure_http_client(
            timeout=15.0,
            max_redirects=3,
            allowed_hosts=["example.com"],
            require_https=True
        )

        # Verify client configuration - focus on event hooks
        assert client.follow_redirects is True
        assert hasattr(client, 'event_hooks')
        assert 'request' in client.event_hooks
        assert 'response' in client.event_hooks
        assert len(client.event_hooks['request']) == 1
        assert len(client.event_hooks['response']) == 1

        # Verify timeout is set (as an httpx.Timeout object)
        assert client.timeout is not None
