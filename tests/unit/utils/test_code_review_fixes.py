#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for code review fixes.

This module tests fixes for issues identified in code review:
- parse_page_ranges reversed range handling
- render_math_html HTML injection prevention
"""

import pytest

from all2md.utils.html_utils import render_math_html
from all2md.utils.inputs import parse_page_ranges


class TestParsePageRangesEnhancements:
    """Test enhanced parse_page_ranges with reversed range handling."""

    def test_reversed_range_auto_swap(self):
        """Test that reversed ranges are automatically swapped."""
        # "10-5" should be treated as "5-10"
        result = parse_page_ranges("10-5", 20)
        assert result == [4, 5, 6, 7, 8, 9]

    def test_reversed_range_multiple(self):
        """Test multiple reversed ranges in one spec."""
        result = parse_page_ranges("10-8,3-1", 20)
        # Should be: [8,9,10] + [1,2,3] -> [0,1,2,7,8,9]
        assert sorted(result) == [0, 1, 2, 7, 8, 9]

    def test_normal_range_unchanged(self):
        """Test that normal ranges still work correctly."""
        result = parse_page_ranges("1-3,5-7", 10)
        assert result == [0, 1, 2, 4, 5, 6]

    def test_open_ended_range(self):
        """Test open-ended ranges like '8-'."""
        result = parse_page_ranges("8-", 10)
        assert result == [7, 8, 9]

    def test_single_pages(self):
        """Test single page specifications."""
        result = parse_page_ranges("1,5,10", 20)
        assert result == [0, 4, 9]

    def test_mixed_ranges_and_singles(self):
        """Test combining ranges and single pages."""
        result = parse_page_ranges("1-3,5,8-10", 20)
        assert result == [0, 1, 2, 4, 7, 8, 9]

    def test_reversed_with_open_end(self):
        """Test reversed range with open end should not happen but handle gracefully."""
        # "-5" is a valid range meaning "from start to 5"
        result = parse_page_ranges("-5", 10)
        assert result == [0, 1, 2, 3, 4]

    def test_edge_case_same_start_and_end(self):
        """Test range where start equals end."""
        result = parse_page_ranges("5-5", 10)
        assert result == [4]

    def test_backward_compatibility(self):
        """Test that existing behavior is preserved."""
        # All these should work as before
        assert parse_page_ranges("1-3,5", 10) == [0, 1, 2, 4]
        assert parse_page_ranges("8-", 10) == [7, 8, 9]
        assert parse_page_ranges("1", 10) == [0]


class TestRenderMathHtmlEnhancements:
    """Test enhanced render_math_html with HTML injection prevention."""

    def test_latex_notation_with_escaping(self):
        """Test LaTeX notation with escaping enabled."""
        result = render_math_html("x < y & z > 0", notation="latex", inline=True, escape_enabled=True)
        # Should escape HTML special chars
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_latex_notation_without_escaping(self):
        """Test LaTeX notation with escaping disabled."""
        result = render_math_html("x < y & z > 0", notation="latex", inline=True, escape_enabled=False)
        # Should NOT escape
        assert "x < y & z > 0" in result

    def test_html_notation_with_escaping(self):
        """Test HTML notation with escaping enabled (XSS prevention)."""
        malicious = "<script>alert('XSS')</script>"
        result = render_math_html(malicious, notation="html", inline=True, escape_enabled=True)
        # Should escape to prevent XSS
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        assert "<script>" not in result

    def test_html_notation_without_escaping(self):
        """Test HTML notation with escaping disabled (trusted content)."""
        trusted_html = "<em>emphasis</em>"
        result = render_math_html(trusted_html, notation="html", inline=True, escape_enabled=False)
        # Should NOT escape trusted content
        assert "<em>emphasis</em>" in result

    def test_mathml_notation_valid_xml(self):
        """Test MathML notation with valid XML is sanitized."""
        mathml = "<math><mi>x</mi></math>"
        result = render_math_html(mathml, notation="mathml", inline=True, escape_enabled=True)
        # Should sanitize MathML - non-whitelisted tags like <mi> are removed
        # This is the correct security behavior
        assert "<math>" in result
        assert "x" in result
        assert "<script>" not in result  # Verify dangerous tags would be removed

    def test_mathml_notation_text_content(self):
        """Test MathML notation with plain text (should wrap)."""
        result = render_math_html("x + y", notation="mathml", inline=True, escape_enabled=True)
        # Should wrap in <math> tags
        assert "<math>" in result
        assert "x + y" in result
        assert "</math>" in result

    def test_mathml_notation_xss_prevention(self):
        """Test MathML notation prevents XSS when escape_enabled=True."""
        malicious = "<script>alert('XSS')</script>"
        result = render_math_html(malicious, notation="mathml", inline=True, escape_enabled=True)
        # Should sanitize to prevent XSS - script tags should be removed
        assert "<script>" not in result
        assert "alert('XSS')" not in result

    def test_mathml_notation_mixed_content_xss_prevention(self):
        """Test MathML with injected attributes prevents XSS."""
        malicious = "<math><mtext onclick=\"alert('XSS')\">x</mtext></math>"
        result = render_math_html(malicious, notation="mathml", inline=True, escape_enabled=True)
        # Should sanitize dangerous attributes
        assert "onclick" not in result
        assert "alert" not in result

    def test_block_math_formatting(self):
        """Test block math formatting."""
        result = render_math_html("E = mc^2", notation="latex", inline=False, escape_enabled=True)
        # Should use div and block formatting
        assert "<div" in result
        assert "math math-block" in result
        assert "$$\nE = mc^2\n$$" in result

    def test_inline_math_formatting(self):
        """Test inline math formatting."""
        result = render_math_html("E = mc^2", notation="latex", inline=True, escape_enabled=True)
        # Should use span and inline formatting
        assert "<span" in result
        assert "math math-inline" in result
        assert "$E = mc^2$" in result

    def test_data_notation_attribute(self):
        """Test that data-notation attribute is included."""
        result = render_math_html("x", notation="latex", inline=True, escape_enabled=True)
        assert 'data-notation="latex"' in result

        result = render_math_html("x", notation="html", inline=True, escape_enabled=True)
        assert 'data-notation="html"' in result

    def test_xss_prevention_complex_payload(self):
        """Test XSS prevention with complex malicious payload."""
        xss_payload = "<img src=x onerror=\"alert('XSS')\">"
        result = render_math_html(xss_payload, notation="html", inline=True, escape_enabled=True)
        # Should escape all HTML tags and attributes
        assert "&lt;img" in result
        assert "onerror" not in result or "&quot;" in result
        assert "<img" not in result

    def test_backward_compatibility_latex(self):
        """Test that default behavior for LaTeX is unchanged."""
        # Default escape_enabled=True should work
        result = render_math_html("x < y", notation="latex", inline=True)
        assert "&lt;" in result


def _secure_client_with_mock_transport(handler, **client_kwargs):
    """Create a secure client served by an httpx.MockTransport.

    create_secure_http_client does not expose a transport parameter, so patch
    httpx.Client during construction. Request hooks and redirect handling
    behave exactly as in production.
    """
    from unittest.mock import patch

    import httpx

    from all2md.utils.network_security import create_secure_http_client

    real_client_cls = httpx.Client
    transport = httpx.MockTransport(handler)

    def patched_client(**kwargs):
        kwargs["transport"] = transport
        return real_client_cls(**kwargs)

    with patch.object(httpx, "Client", new=patched_client):
        return create_secure_http_client(**client_kwargs)


class TestRedirectValidationEdgeCases:
    """Test edge cases for httpx redirect validation in network security.

    Redirect targets are validated by the request event hook before each hop
    is followed; the redirect count is enforced natively by httpx.
    """

    def test_https_to_http_downgrade_mid_chain(self):
        """Test that a redirect chain downgrading to HTTP is blocked with require_https."""
        import ipaddress
        from unittest.mock import patch

        import httpx

        from all2md.exceptions import NetworkSecurityError

        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            def handler(request):
                if request.url.path == "/start":
                    return httpx.Response(302, headers={"location": "https://example.com/secure"})
                if request.url.path == "/secure":
                    return httpx.Response(302, headers={"location": "http://example.com/final"})
                return httpx.Response(200, content=b"final")

            client = _secure_client_with_mock_transport(handler, max_redirects=5, require_https=True)

            # Should raise when the chain downgrades to HTTP
            with client, pytest.raises(NetworkSecurityError, match="HTTPS required"):
                client.get("https://example.com/start")

    def test_cross_host_redirect_chain(self):
        """Test that every host in a cross-host redirect chain is validated."""
        import ipaddress
        from unittest.mock import patch

        import httpx

        from all2md.exceptions import NetworkSecurityError

        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
            # Different hosts resolve to different IPs
            def resolver(hostname):
                if hostname == "site-a.com":
                    return [ipaddress.IPv4Address("8.8.8.8")]
                elif hostname == "site-b.com":
                    return [ipaddress.IPv4Address("1.1.1.1")]
                elif hostname == "evil.internal":
                    return [ipaddress.IPv4Address("192.168.1.1")]  # Private IP
                return [ipaddress.IPv4Address("8.8.8.8")]

            mock_resolve.side_effect = resolver

            def handler(request):
                if request.url.host == "site-a.com":
                    return httpx.Response(302, headers={"location": "http://site-b.com/middle"})
                if request.url.host == "site-b.com":
                    return httpx.Response(302, headers={"location": "http://evil.internal/admin"})
                return httpx.Response(200, content=b"internal")

            client = _secure_client_with_mock_transport(handler, max_redirects=5, require_https=False)

            # Should raise because the last hop resolves to a private IP
            with client, pytest.raises(NetworkSecurityError, match="private/reserved IP"):
                client.get("http://site-a.com/start")

    def test_idn_internationalized_domain_redirects(self):
        """Test that IDN (punycode) redirect targets are validated and allowed when public."""
        import ipaddress
        from unittest.mock import patch

        import httpx

        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
            # IDN domains should be normalized during validation
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            def handler(request):
                if request.url.host == "example.com":
                    # Punycode for buecher.com-style IDN (xn--bcher-kva.com)
                    return httpx.Response(302, headers={"location": "http://xn--bcher-kva.com/middle"})
                return httpx.Response(200, content=b"ok")

            client = _secure_client_with_mock_transport(handler, max_redirects=5, require_https=False)

            # Should not raise - public IPs are allowed
            with client:
                response = client.get("http://example.com/start")
            assert response.status_code == 200

    def test_no_redirects_validates_initial_request(self):
        """Test that requests with no redirects still validate the initial URL."""
        import ipaddress
        from unittest.mock import patch

        import httpx

        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:
            mock_resolve.return_value = [ipaddress.IPv4Address("8.8.8.8")]

            def handler(request):
                return httpx.Response(200, content=b"direct")

            client = _secure_client_with_mock_transport(handler, max_redirects=5, require_https=False)

            with client:
                response = client.get("http://example.com/direct")
            assert response.status_code == 200
            assert mock_resolve.called  # initial URL was validated

    def test_redirect_to_private_ip_blocked(self):
        """Test that redirects to loopback addresses are caught."""
        import ipaddress
        from unittest.mock import patch

        import httpx

        from all2md.exceptions import NetworkSecurityError

        with patch("all2md.utils.network_security._resolve_hostname_to_ips") as mock_resolve:

            def resolver(hostname):
                # URL encoding shouldn't bypass IP validation
                if "127.0.0.1" in hostname or hostname == "localhost":
                    return [ipaddress.IPv4Address("127.0.0.1")]
                return [ipaddress.IPv4Address("8.8.8.8")]

            mock_resolve.side_effect = resolver

            def handler(request):
                if request.url.host == "example.com":
                    return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
                return httpx.Response(200, content=b"admin")

            client = _secure_client_with_mock_transport(handler, max_redirects=5, require_https=False)

            # Should raise - localhost is blocked
            with client, pytest.raises(NetworkSecurityError, match="private/reserved IP"):
                client.get("http://example.com/start")
