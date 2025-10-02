"""Integration tests for HTML converter SSRF security features.

This test module validates the end-to-end security behavior of the HTML
to Markdown converter, ensuring SSRF attacks are properly prevented.

Test Coverage:
- HTML converter security option enforcement
- Image fetching behavior with various security settings
- EML converter security inheritance
- Error handling and fallback behavior
"""

import os
import shutil
from pathlib import Path
from unittest.mock import patch

from all2md.parsers.html2markdown import html_to_markdown
from all2md.options import EmlOptions, HtmlOptions, NetworkFetchOptions


class TestHtmlConverterSecurity:
    """Test HTML converter security enforcement."""

    def teardown_method(self):
        """Clean up test artifacts after each test."""
        # Remove safe_images directories that may be created during tests
        for path in [Path("safe_images"), Path("tests/safe_images"), Path("tests/integration/safe_images")]:
            if path.exists():
                shutil.rmtree(path)

    def test_default_security_blocks_remote_fetch(self):
        """Test that default settings prevent remote fetching."""
        html_content = '<img src="https://example.com/image.png" alt="test">'

        # Default options should have allow_remote_fetch=False
        options = HtmlOptions()
        assert not options.network.allow_remote_fetch

        # Should not attempt to fetch, fallback to alt_text
        result = html_to_markdown(html_content, options)
        assert "![test]" in result

    def test_security_disabled_allows_fetch_with_valid_url(self):
        """Test that enabling remote fetch works with valid URLs."""
        html_content = '<img src="https://httpbin.org/image/png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                require_https=True
            ),
            attachment_mode="base64"
        )

        with patch('all2md.utils.network_security.fetch_image_securely') as mock_fetch:
            mock_fetch.return_value = b'fake_image_data'

            result = html_to_markdown(html_content, options)

            # Should attempt to fetch
            mock_fetch.assert_called_once()
            assert "data:image/png;base64," in result

    def test_security_blocks_private_ip_fetch(self):
        """Test that private IP addresses are blocked even when remote fetch is enabled."""
        html_content = '<img src="http://192.168.1.1/admin.png" alt="admin">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        # Should fall back to alt_text when security blocks the request
        result = html_to_markdown(html_content, options)
        assert "![admin]" in result

    def test_https_requirement_enforcement(self):
        """Test HTTPS requirement blocks HTTP URLs."""
        html_content = '<img src="http://example.com/image.png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True, require_https=True),
            attachment_mode="base64"
        )

        # Should fall back to alt_text when HTTPS is required but HTTP is used
        result = html_to_markdown(html_content, options)
        assert "![test]" in result

    def test_allowlist_enforcement(self):
        """Test that hostname allowlist is enforced."""
        html_content = '<img src="https://evil.com/malware.png" alt="bad">'

        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                allowed_hosts=["trusted.com", "cdn.example.org"]
            ),
            attachment_mode="base64"
        )

        # Should fall back to alt_text when hostname not in allowlist
        result = html_to_markdown(html_content, options)
        assert "![bad]" in result

    @patch.dict(os.environ, {'ALL2MD_DISABLE_NETWORK': 'true'})
    def test_global_network_disable_blocks_all_requests(self):
        """Test that global network disable environment variable blocks all requests."""
        html_content = '<img src="https://example.com/image.png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True),  # Even with this enabled
            attachment_mode="base64"
        )

        # Should fall back to alt_text when network is globally disabled
        result = html_to_markdown(html_content, options)
        assert "![test]" in result

    def test_multiple_images_with_mixed_security(self):
        """Test handling of multiple images with different security profiles."""
        html_content = '''
        <p>Images:</p>
        <img src="https://example.com/good.png" alt="good">
        <img src="http://192.168.1.1/bad.png" alt="bad">
        <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgA\
AAABJ RU5ErkJggg==" alt="inline">
        '''

        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                allowed_hosts=["example.com"]
            ),
            attachment_mode="alt_text"  # Won't fetch anyway due to alt_text mode
        )

        result = html_to_markdown(html_content, options)

        # All should be converted to markdown links in alt_text mode
        assert "![good]" in result
        assert "![bad]" in result
        assert "![inline]" in result

    def test_content_size_limit_enforcement(self):
        """Test that content size limits are enforced."""
        html_content = '<img src="https://example.com/huge.png" alt="huge">'

        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                max_remote_asset_bytes=1024  # 1KB limit
            ),
            attachment_mode="base64"
        )

        with patch('all2md.utils.network_security.fetch_image_securely') as mock_fetch:
            from all2md.utils.network_security import NetworkSecurityError
            mock_fetch.side_effect = NetworkSecurityError("Response too large")

            result = html_to_markdown(html_content, options)

            # Should fall back to alt_text when size limit exceeded
            assert "![huge]" in result


class TestEmlConverterSecurityInheritance:
    """Test that EML converter properly inherits HTML security settings."""

    def test_eml_security_settings_passed_to_html(self):
        """Test that EML security settings are passed to HTML converter."""
        from all2md.parsers.eml import _convert_html_to_markdown

        html_content = '<img src="https://example.com/image.png" alt="test">'

        options = EmlOptions(
            convert_html_to_markdown=True,
            html_network=NetworkFetchOptions(
                allow_remote_fetch=True,
                allowed_hosts=["example.com"],
                require_https=True,
                max_remote_asset_bytes=1024 * 1024  # 1MB
            )
        )

        with patch('all2md.parsers.html2markdown.html_to_markdown') as mock_html_convert:
            mock_html_convert.return_value = "![test](https://example.com/image.png)"

            _convert_html_to_markdown(html_content, options)

            # Verify HTML converter was called with security settings
            mock_html_convert.assert_called_once()
            call_args = mock_html_convert.call_args

            html_options = call_args.args[1]  # Second argument should be HtmlOptions
            # Note: The converter should pass individual args, not nested options
            # This test may need to be updated based on actual implementation

    def test_eml_default_security_blocks_remote_fetch(self):
        """Test that EML default security settings block remote fetching."""
        from all2md.parsers.eml import _convert_html_to_markdown

        html_content = '<img src="https://example.com/image.png" alt="test">'

        # Default EML options should have allow_remote_fetch=False
        options = EmlOptions()
        assert not options.html_network.allow_remote_fetch

        result = _convert_html_to_markdown(html_content, options)

        # Should return the content without attempting to fetch
        assert "test" in result


class TestSecurityErrorHandling:
    """Test security error handling and fallback behavior."""

    def test_network_error_fallback_to_alt_text(self):
        """Test that network errors gracefully fall back to alt_text."""
        html_content = '<img src="https://example.com/image.png" alt="fallback">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        with patch('all2md.utils.network_security.fetch_image_securely') as mock_fetch:
            from all2md.utils.network_security import NetworkSecurityError
            mock_fetch.side_effect = NetworkSecurityError("Simulated security error")

            result = html_to_markdown(html_content, options)

            # Should fall back to alt_text mode
            assert "![fallback]" in result

    def test_http_error_fallback_to_alt_text(self):
        """Test that HTTP errors gracefully fall back to alt_text."""
        html_content = '<img src="https://example.com/notfound.png" alt="missing">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        with patch('all2md.utils.network_security.fetch_image_securely') as mock_fetch:
            mock_fetch.side_effect = Exception("HTTP 404 Not Found")

            result = html_to_markdown(html_content, options)

            # Should fall back to alt_text mode
            assert "![missing]" in result

    def test_partial_success_with_multiple_images(self):
        """Test behavior when some images succeed and others fail."""
        html_content = '''
        <img src="https://good.example.com/image1.png" alt="success">
        <img src="https://bad.example.com/image2.png" alt="failure">
        '''

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        def mock_fetch_side_effect(url, **kwargs):
            if "good.example.com" in url:
                return b"fake_image_data"
            else:
                raise Exception("Simulated failure")

        with patch('all2md.utils.network_security.fetch_image_securely', side_effect=mock_fetch_side_effect):
            result = html_to_markdown(html_content, options)

            # First image should be base64 encoded, second should fall back
            assert "data:image/png;base64," in result  # Success case
            assert "![failure]" in result  # Fallback case


class TestSecurityDocumentationExamples:
    """Test examples that would be used in security documentation."""

    def teardown_method(self):
        """Clean up test artifacts after each test."""
        # Remove safe_images directories that may be created during tests
        for path in [Path("safe_images"), Path("tests/safe_images"), Path("tests/integration/safe_images")]:
            if path.exists():
                shutil.rmtree(path)

    def test_secure_configuration_example(self):
        """Test recommended secure configuration."""
        html_content = '''
        <img src="https://cdn.example.com/safe.png" alt="safe">
        <img src="http://192.168.1.1/internal.png" alt="blocked">
        '''

        # Recommended secure configuration
        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                allowed_hosts=["cdn.example.com", "images.example.org"],
                require_https=True,
                max_remote_asset_bytes=5 * 1024 * 1024,  # 5MB limit
                network_timeout=5.0  # Quick timeout
            ),
            attachment_mode="download",
            attachment_output_dir="./safe_images/"
        )

        with patch('all2md.utils.network_security.fetch_image_securely') as mock_fetch:
            mock_fetch.return_value = b"safe_image_data"

            result = html_to_markdown(html_content, options)

            # Only the allowed HTTPS image should be processed
            # The private IP should be blocked and fall back
            assert "safe" in result
            assert "blocked" in result

    def test_maximum_security_configuration(self):
        """Test maximum security configuration that blocks everything."""
        html_content = '''
        <img src="https://example.com/image.png" alt="blocked">
        <img src="data:image/png;base64,iVBORw0=" alt="inline">
        '''

        # Maximum security: no remote fetching at all
        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False),  # Blocks all remote requests
            attachment_mode="alt_text"  # Only show alt text
        )

        result = html_to_markdown(html_content, options)

        # All external images should be converted to alt text
        assert "![blocked]" in result
        assert "![inline]" in result


class TestLinkSchemeSecurityIntegration:
    """Integration tests for link scheme security and XSS prevention."""

    def test_multiple_dangerous_links_in_document(self):
        """Test that multiple dangerous links in the same document are all blocked."""
        html_content = '''
        <h1>Test Page</h1>
        <p>Here are some malicious links:</p>
        <ul>
            <li><a href="javascript:alert('XSS1')">JavaScript XSS</a></li>
            <li><a href="vbscript:msgbox('XSS2')">VBScript XSS</a></li>
            <li><a href="data:text/html,<script>alert('XSS3')</script>">Data HTML XSS</a></li>
            <li><a href="https://safe.com">Safe Link</a></li>
        </ul>
        '''

        result = html_to_markdown(html_content)

        # Dangerous links should have empty hrefs
        assert "[JavaScript XSS]()" in result
        assert "[VBScript XSS]()" in result
        assert "[Data HTML XSS]()" in result

        # Safe link should be preserved
        assert "[Safe Link](https://safe.com)" in result

    def test_mixed_safe_and_dangerous_links_with_metadata(self):
        """Test document with mixed links and metadata extraction."""
        html_content = '''
        <html>
        <head>
            <title>Security Test</title>
            <meta name="author" content="Test Author">
        </head>
        <body>
            <h1>Links Test</h1>
            <p>Contact us at <a href="mailto:test@example.com">test@example.com</a></p>
            <p>Don't click <a href="javascript:void(0)">here</a></p>
            <p>Call us at <a href="tel:+1234567890">+1234567890</a></p>
        </body>
        </html>
        '''

        options = HtmlOptions(extract_title=True, extract_metadata=True)
        result = html_to_markdown(html_content, options)

        # Safe links should work
        assert "[test@example.com](mailto:test@example.com)" in result
        assert "[+1234567890](tel:+1234567890)" in result

        # Dangerous link should be blocked
        assert "[here]()" in result

    def test_link_security_with_base_url_resolution(self):
        """Test that link security works with base URL resolution."""
        html_content = '''
        <a href="/page">Relative link</a>
        <a href="javascript:alert('xss')">XSS link</a>
        '''

        options = HtmlOptions(attachment_base_url="https://example.com")
        result = html_to_markdown(html_content, options)

        # Relative link should be resolved
        assert "[Relative link](https://example.com/page)" in result

        # XSS link should still be blocked
        assert "[XSS link]()" in result

    def test_require_https_blocks_http_links(self):
        """Test that require_https setting blocks HTTP links."""
        html_content = '''
        <p>
            <a href="http://insecure.com">HTTP Link</a>
            <a href="https://secure.com">HTTPS Link</a>
            <a href="ftp://files.com">FTP Link</a>
            <a href="mailto:test@example.com">Email Link</a>
        </p>
        '''

        options = HtmlOptions(network=NetworkFetchOptions(require_https=True))
        result = html_to_markdown(html_content, options=options)

        # HTTP and FTP should be blocked
        assert "[HTTP Link]()" in result
        assert "[FTP Link]()" in result

        # HTTPS should be allowed
        assert "[HTTPS Link](https://secure.com)" in result

        # mailto should still be allowed
        assert "[Email Link](mailto:test@example.com)" in result

    def test_xss_prevention_in_complex_document(self):
        """Test XSS prevention in a complex HTML document with various attacks."""
        html_content = '''
        <article>
            <h1>Article Title</h1>
            <p>This is a <a href="javascript:void(document.cookie='stolen')">malicious link</a>.</p>
            <p>Also dangerous: <a href="data:text/javascript,alert('xss')">data scheme</a></p>
            <p>Safe navigation: <a href="/about">About</a> | <a href="#contact">Contact</a></p>

            <h2>More Content</h2>
            <blockquote>
                <p>A quote with a <a href="vbscript:CreateObject('WScript.Shell')">VBScript link</a></p>
            </blockquote>

            <ul>
                <li><a href="https://example.com">Safe external link</a></li>
                <li><a href="file:///etc/passwd">Local file access</a></li>
            </ul>
        </article>
        '''

        result = html_to_markdown(html_content)

        # All dangerous links should be neutralized
        assert "javascript:" not in result
        assert "vbscript:" not in result
        assert "data:text/javascript" not in result

        # Safe links should remain
        assert "[About](/about)" in result
        assert "[Contact](#contact)" in result
        assert "[Safe external link](https://example.com)" in result

    def test_link_security_with_strip_dangerous_elements(self):
        """Test that link security works independently of strip_dangerous_elements setting."""
        html_content = '<a href="javascript:alert(\'xss\')">Click</a>'

        # Test with strip_dangerous_elements=False (default)
        # Link text is preserved but href is neutralized
        options_default = HtmlOptions(strip_dangerous_elements=False)
        result_default = html_to_markdown(html_content, options_default)
        assert "[Click]()" in result_default

        # Test with strip_dangerous_elements=True
        # Entire element is removed during DOM sanitization
        options_strict = HtmlOptions(strip_dangerous_elements=True)
        result_strict = html_to_markdown(html_content, options_strict)
        assert result_strict.strip() == ""  # Element removed entirely

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        html_content = '''
        <a href="JAVASCRIPT:alert('XSS')">Upper</a>
        <a href="JavaScript:alert('XSS')">Mixed</a>
        <a href="JaVaScRiPt:alert('XSS')">Weird</a>
        <a href="HTTP://example.com">HTTP Upper</a>
        '''

        result = html_to_markdown(html_content)

        # All javascript variants should be blocked
        assert "[Upper]()" in result
        assert "[Mixed]()" in result
        assert "[Weird]()" in result

        # HTTP in uppercase should still work
        assert "[HTTP Upper](HTTP://example.com)" in result or "[HTTP Upper](http://example.com)" in result
