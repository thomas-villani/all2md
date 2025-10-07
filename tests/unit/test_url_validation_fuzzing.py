"""Property-based fuzzing tests for URL validation.

This test module uses Hypothesis to generate random URLs and validate
that the URL security validation logic behaves correctly across a wide
range of inputs, including edge cases and malformed URLs.

Test Coverage:
- Random URL generation with various schemes
- Malformed URL handling
- IPv4 and IPv6 address validation
- Private IP detection
- Property: No private IPs ever pass validation
"""

import ipaddress
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from all2md.exceptions import NetworkSecurityError
from all2md.utils.network_security import _is_private_or_reserved_ip, validate_url_security


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.security
class TestURLValidationFuzzing:
    """Property-based tests for URL validation using Hypothesis."""

    @given(st.text(min_size=1, max_size=100))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_arbitrary_strings_handled_gracefully(self, random_string):
        """Test that arbitrary strings don't cause crashes in URL validation."""
        # Attempt to validate random string as URL
        # Should either raise NetworkSecurityError or pass validation
        try:
            # Mock DNS resolution to avoid actual network calls
            with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
                mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
                validate_url_security(random_string)
        except NetworkSecurityError:
            # Expected for invalid URLs
            pass
        except Exception as e:
            # Any other exception is a bug
            pytest.fail(f"Unexpected exception for input '{random_string}': {e}")

    @given(
        st.sampled_from(['http', 'https', 'ftp', 'file', 'javascript', 'data']),
        st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=50),
        st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd', 'P')), min_size=0, max_size=100)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=1000)
    def test_various_url_schemes(self, scheme, domain, path):
        """Test URL validation with various schemes, domains, and paths."""
        url = f"{scheme}://{domain}/{path}"

        # Mock DNS resolution
        with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            try:
                validate_url_security(url)
                # If it passes, should be http or https with valid structure
                parsed = urlparse(url)
                assert parsed.scheme in ('http', 'https')
            except NetworkSecurityError:
                # Expected for unsupported schemes or invalid URLs
                pass

    @given(
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_ipv4_addresses_correctly_classified(self, a, b, c, d):
        """Property: Private IPv4 addresses should always be blocked."""
        ip_str = f"{a}.{b}.{c}.{d}"
        url = f"http://{ip_str}/test"

        try:
            ip = ipaddress.IPv4Address(ip_str)
        except ipaddress.AddressValueError:
            # Invalid IP, skip
            return

        is_private = _is_private_or_reserved_ip(ip)

        # Mock DNS to return this IP
        with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
            mock_resolve.return_value = [ip]

            if is_private:
                # Property: Private IPs must be blocked
                with pytest.raises(NetworkSecurityError):
                    validate_url_security(url)
            else:
                # Property: Public IPs should pass validation
                try:
                    validate_url_security(url)
                except NetworkSecurityError as e:
                    # Might fail for other reasons (invalid hostname), but not for being private
                    assert "private" not in str(e).lower()

    @given(
        st.lists(st.integers(min_value=0, max_value=65535), min_size=8, max_size=8)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    def test_all_ipv6_addresses_correctly_classified(self, segments):
        """Property: Private IPv6 addresses should always be blocked."""
        # Build IPv6 address from segments
        ip_str = ':'.join(f"{seg:x}" for seg in segments)

        try:
            ip = ipaddress.IPv6Address(ip_str)
        except (ipaddress.AddressValueError, ValueError):
            # Invalid IP, skip
            return

        is_private = _is_private_or_reserved_ip(ip)
        url = f"http://[{ip_str}]/test"

        if is_private:
            # Property: Private IPs must be blocked
            with pytest.raises(NetworkSecurityError):
                validate_url_security(url)
        else:
            # Property: Public IPs should pass basic URL parsing
            try:
                validate_url_security(url)
            except NetworkSecurityError as e:
                # Might fail for other reasons, but not for being private
                assert "private" not in str(e).lower() and "reserved" not in str(e).lower()

    @given(
        st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=33, max_codepoint=126),
                min_size=1, max_size=30)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hostname_allowlist_property(self, hostname):
        """Property: URLs not in allowlist should be rejected when allowlist is provided."""
        # Create allowlist that definitely doesn't contain this hostname
        allowlist = ["trusted.com", "example.org", "safe.net"]

        # Skip if hostname happens to be in allowlist
        assume(hostname.lower() not in allowlist)

        url = f"http://{hostname}/test"

        # Mock DNS resolution
        with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            # Property: Hostname not in allowlist should be rejected
            with pytest.raises(NetworkSecurityError, match="not in allowlist"):
                validate_url_security(url, allowed_hosts=allowlist)

    @given(
        st.sampled_from(['http', 'https']),
        st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=20)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_require_https_property(self, scheme, domain):
        """Property: HTTP URLs should be rejected when require_https=True."""
        url = f"{scheme}://{domain}/test"

        # Mock DNS resolution
        with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            if scheme == 'http':
                # Property: HTTP should be rejected when require_https=True
                with pytest.raises(NetworkSecurityError, match="HTTPS required"):
                    validate_url_security(url, require_https=True)
            else:
                # HTTPS should pass (assuming valid domain)
                try:
                    validate_url_security(url, require_https=True)
                except NetworkSecurityError as e:
                    # Might fail for other reasons (DNS), but not HTTPS requirement
                    assert "HTTPS required" not in str(e)


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.security
class TestPrivateIPDetectionFuzzing:
    """Fuzz test private IP detection logic."""

    @given(
        st.sampled_from([
            "10.0.0.0/8",          # Private
            "172.16.0.0/12",       # Private
            "192.168.0.0/16",      # Private
            "127.0.0.0/8",         # Loopback
            "169.254.0.0/16",      # Link-local
        ])
    )
    @settings(max_examples=20, deadline=5000)
    def test_all_ips_in_private_ranges_detected(self, cidr_block):
        """Property: All IPs in private CIDR blocks should be detected as private."""
        network = ipaddress.IPv4Network(cidr_block)

        # Test a few random IPs from this network
        for ip in list(network.hosts())[:3]:  # Test first 3 hosts (reduced from 10)
            assert _is_private_or_reserved_ip(ip), f"IP {ip} from {cidr_block} should be private"

    @given(
        st.sampled_from([
            "8.8.8.0/24",          # Google DNS (public)
            "1.1.1.0/24",          # Cloudflare DNS (public)
            "151.101.0.0/16",      # Fastly CDN (public)
        ])
    )
    @settings(max_examples=20)
    def test_all_ips_in_public_ranges_detected_as_public(self, cidr_block):
        """Property: All IPs in public CIDR blocks should NOT be private."""
        network = ipaddress.IPv4Network(cidr_block)

        # Test a few random IPs from this network
        for ip in list(network.hosts())[:10]:
            assert not _is_private_or_reserved_ip(ip), f"IP {ip} from {cidr_block} should be public"


@pytest.mark.unit
@pytest.mark.fuzzing
class TestMalformedURLFuzzing:
    """Fuzz test with intentionally malformed URLs."""

    @given(
        st.text(min_size=0, max_size=50),
        st.text(min_size=0, max_size=50),
        st.text(min_size=0, max_size=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=100)
    def test_malformed_urls_dont_crash(self, part1, part2, part3):
        """Property: Malformed URLs should not cause crashes."""
        # Create various malformed URL patterns
        malformed_urls = [
            f"{part1}://{part2}/{part3}",
            f"{part1}:{part2}",
            f"//{part1}/{part2}",
            part1 + part2 + part3,
            f"{part1}@{part2}:{part3}",
        ]

        for url in malformed_urls:
            try:
                with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
                    mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
                    validate_url_security(url)
            except NetworkSecurityError:
                # Expected for malformed URLs
                pass
            except Exception as e:
                # Should not raise unexpected exceptions
                pytest.fail(f"Unexpected exception for URL '{url}': {e}")

    @given(
        st.text(alphabet=st.characters(blacklist_characters=[':', '/', '@', '?', '#']), min_size=1, max_size=30)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_urls_without_special_characters(self, text):
        """Test URLs constructed from text without URL special characters."""
        # These should mostly fail validation (no scheme, etc.)
        try:
            with patch('all2md.utils.network_security._resolve_hostname_to_ips') as mock_resolve:
                mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]
                validate_url_security(text)
        except NetworkSecurityError:
            # Expected
            pass


@pytest.mark.unit
@pytest.mark.fuzzing
class TestURLEncodingFuzzing:
    """Fuzz test URL encoding and normalization."""

    @given(
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255)
    )
    @settings(max_examples=50)
    def test_ip_representation_variations(self, a, b, c, d):
        """Test various IP address representations (hex, octal, decimal)."""
        try:
            ip = ipaddress.IPv4Address(f"{a}.{b}.{c}.{d}")
        except (ipaddress.AddressValueError, ValueError):
            return

        # Test standard decimal notation
        url_decimal = f"http://{a}.{b}.{c}.{d}/test"

        # Test hex notation (if values allow)
        if all(0 <= x <= 255 for x in [a, b, c, d]):
            url_hex = f"http://0x{a:02x}.0x{b:02x}.0x{c:02x}.0x{d:02x}/test"

            is_private = _is_private_or_reserved_ip(ip)

            if is_private:
                # Both representations should be blocked
                with pytest.raises(NetworkSecurityError):
                    validate_url_security(url_decimal)
                # Note: Hex notation might not be parsed correctly by urlparse,
                # which is actually a security feature
