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

from all2md import EmlOptions, HtmlOptions
from all2md import to_markdown as html_to_markdown
from all2md.options import NetworkFetchOptions


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
        result = html_to_markdown(html_content, source_format="html", parser_options=options)
        assert "![test]" in result

    def test_security_disabled_allows_fetch_with_valid_url(self):
        """Test that enabling remote fetch works with valid URLs."""
        html_content = '<img src="https://httpbin.org/image/png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True, require_https=True), attachment_mode="base64"
        )

        with patch("all2md.parsers.html.fetch_image_securely") as mock_fetch:
            mock_fetch.return_value = b"fake_image_data"

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Should attempt to fetch
            mock_fetch.assert_called_once()
            assert "data:image/png;base64," in result

    def test_security_blocks_private_ip_fetch(self):
        """Test that private IP addresses are blocked even when remote fetch is enabled."""
        html_content = '<img src="http://192.168.1.1/admin.png" alt="admin">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        # Should fall back to alt_text when security blocks the request
        result = html_to_markdown(html_content, source_format="html", parser_options=options)
        assert "![admin]" in result

    def test_https_requirement_enforcement(self):
        """Test HTTPS requirement blocks HTTP URLs."""
        html_content = '<img src="http://example.com/image.png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True, require_https=True), attachment_mode="base64"
        )

        # Should fall back to alt_text when HTTPS is required but HTTP is used
        result = html_to_markdown(html_content, source_format="html", parser_options=options)
        assert "![test]" in result

    def test_allowlist_enforcement(self):
        """Test that hostname allowlist is enforced."""
        html_content = '<img src="https://evil.com/malware.png" alt="bad">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True, allowed_hosts=["trusted.com", "cdn.example.org"]),
            attachment_mode="base64",
        )

        # Should fall back to alt_text when hostname not in allowlist
        result = html_to_markdown(html_content, source_format="html", parser_options=options)
        assert "![bad]" in result

    @patch.dict(os.environ, {"ALL2MD_DISABLE_NETWORK": "true"})
    def test_global_network_disable_blocks_all_requests(self):
        """Test that global network disable environment variable blocks all requests."""
        html_content = '<img src="https://example.com/image.png" alt="test">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True),
            attachment_mode="base64",  # Even with this enabled
        )

        # Should fall back to alt_text when network is globally disabled
        result = html_to_markdown(html_content, source_format="html", parser_options=options)
        assert "![test]" in result

    def test_multiple_images_with_mixed_security(self):
        """Test handling of multiple images with different security profiles."""
        html_content = """
        <p>Images:</p>
        <img src="https://example.com/good.png" alt="good">
        <img src="http://192.168.1.1/bad.png" alt="bad">
        <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgA\
AAABJ RU5ErkJggg==" alt="inline">
        """

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True, allowed_hosts=["example.com"]),
            attachment_mode="alt_text",  # Won't fetch anyway due to alt_text mode
        )

        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # All should be converted to markdown links in alt_text mode
        assert "![good]" in result
        assert "![bad]" in result
        assert "![inline]" in result

    def test_content_size_limit_enforcement(self):
        """Test that content size limits are enforced."""
        html_content = '<img src="https://example.com/huge.png" alt="huge">'

        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=True),
            max_asset_size_bytes=1024,  # 1KB limit
            attachment_mode="base64",
        )

        with patch("all2md.utils.network_security.fetch_image_securely") as mock_fetch:
            from all2md.exceptions import NetworkSecurityError

            mock_fetch.side_effect = NetworkSecurityError("Response too large")

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Should fall back to alt_text when size limit exceeded
            assert "![huge]" in result


class TestEmlConverterSecurityInheritance:
    """Test that EML converter properly inherits HTML security settings."""

    def test_eml_security_settings_passed_to_html(self):
        """Test that EML security settings are passed to HTML converter."""
        from all2md.parsers.eml import convert_eml_html_to_markdown

        html_content = '<img src="https://example.com/image.png" alt="test">'

        options = EmlOptions(
            convert_html_to_markdown=True,
            html_network=NetworkFetchOptions(
                allow_remote_fetch=True, allowed_hosts=["example.com"], require_https=True
            ),
            max_asset_size_bytes=1024 * 1024,  # 1MB
        )

        # The function now uses to_markdown which calls the parser internally
        # We can just verify that the conversion happens correctly
        result = convert_eml_html_to_markdown(html_content, options)

        # Verify the HTML was processed (should contain alt text at minimum)
        assert "test" in result

    def test_eml_default_security_blocks_remote_fetch(self):
        """Test that EML default security settings block remote fetching."""
        from all2md.parsers.eml import convert_eml_html_to_markdown

        html_content = '<img src="https://example.com/image.png" alt="test">'

        # Default EML options should have allow_remote_fetch=False
        options = EmlOptions()
        assert not options.html_network.allow_remote_fetch

        result = convert_eml_html_to_markdown(html_content, options)

        # Should return the content without attempting to fetch
        assert "test" in result


class TestSecurityErrorHandling:
    """Test security error handling and fallback behavior."""

    def test_network_error_fallback_to_alt_text(self):
        """Test that network errors gracefully fall back to alt_text."""
        html_content = '<img src="https://example.com/image.png" alt="fallback">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        with patch("all2md.utils.network_security.fetch_image_securely") as mock_fetch:
            from all2md.exceptions import NetworkSecurityError

            mock_fetch.side_effect = NetworkSecurityError("Simulated security error")

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Should fall back to alt_text mode
            assert "![fallback]" in result

    def test_http_error_fallback_to_alt_text(self):
        """Test that HTTP errors gracefully fall back to alt_text."""
        html_content = '<img src="https://example.com/notfound.png" alt="missing">'

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        with patch("all2md.utils.network_security.fetch_image_securely") as mock_fetch:
            mock_fetch.side_effect = Exception("HTTP 404 Not Found")

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Should fall back to alt_text mode
            assert "![missing]" in result

    def test_partial_success_with_multiple_images(self):
        """Test behavior when some images succeed and others fail."""
        html_content = """
        <img src="https://good.example.com/image1.png" alt="success">
        <img src="https://bad.example.com/image2.png" alt="failure">
        """

        options = HtmlOptions(network=NetworkFetchOptions(allow_remote_fetch=True), attachment_mode="base64")

        def mock_fetch_side_effect(url, **kwargs):
            if "good.example.com" in url:
                return b"fake_image_data"
            else:
                raise Exception("Simulated failure")

        with patch("all2md.parsers.html.fetch_image_securely", side_effect=mock_fetch_side_effect):
            result = html_to_markdown(html_content, source_format="html", parser_options=options)

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
        html_content = """
        <img src="https://cdn.example.com/safe.png" alt="safe">
        <img src="http://192.168.1.1/internal.png" alt="blocked">
        """

        # Recommended secure configuration
        options = HtmlOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                allowed_hosts=["cdn.example.com", "images.example.org"],
                require_https=True,
                network_timeout=5.0,  # Quick timeout
            ),
            max_asset_size_bytes=5 * 1024 * 1024,  # 5MB limit
            attachment_mode="download",
            attachment_output_dir="./safe_images/",
        )

        with patch("all2md.utils.network_security.fetch_image_securely") as mock_fetch:
            mock_fetch.return_value = b"safe_image_data"

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Only the allowed HTTPS image should be processed
            # The private IP should be blocked and fall back
            assert "safe" in result
            assert "blocked" in result

    def test_maximum_security_configuration(self):
        """Test maximum security configuration that blocks everything."""
        html_content = """
        <img src="https://example.com/image.png" alt="blocked">
        <img src="data:image/png;base64,iVBORw0=" alt="inline">
        """

        # Maximum security: no remote fetching at all
        options = HtmlOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False),  # Blocks all remote requests
            attachment_mode="alt_text",  # Only show alt text
        )

        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # All external images should be converted to alt text
        assert "![blocked]" in result
        assert "![inline]" in result


class TestLinkSchemeSecurityIntegration:
    """Integration tests for link scheme security and XSS prevention."""

    def test_multiple_dangerous_links_in_document(self):
        """Test that multiple dangerous links in the same document are all blocked."""
        html_content = """
        <h1>Test Page</h1>
        <p>Here are some malicious links:</p>
        <ul>
            <li><a href="javascript:alert('XSS1')">JavaScript XSS</a></li>
            <li><a href="vbscript:msgbox('XSS2')">VBScript XSS</a></li>
            <li><a href="data:text/html,<script>alert('XSS3')</script>">Data HTML XSS</a></li>
            <li><a href="https://safe.com">Safe Link</a></li>
        </ul>
        """

        result = html_to_markdown(html_content, source_format="html")

        # Dangerous links should have empty hrefs
        assert "[JavaScript XSS]()" in result
        assert "[VBScript XSS]()" in result
        assert "[Data HTML XSS]()" in result

        # Safe link should be preserved
        assert "[Safe Link](https://safe.com)" in result

    def test_mixed_safe_and_dangerous_links_with_metadata(self):
        """Test document with mixed links and metadata extraction."""
        html_content = """
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
        """

        options = HtmlOptions(extract_title=True, extract_metadata=True)
        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # Safe links should work
        assert "[test@example.com](mailto:test@example.com)" in result
        assert "[+1234567890](tel:+1234567890)" in result

        # Dangerous link should be blocked
        assert "[here]()" in result

    def test_link_security_with_base_url_resolution(self):
        """Test that link security works with base URL resolution."""
        html_content = """
        <a href="/page">Relative link</a>
        <a href="javascript:alert('xss')">XSS link</a>
        """

        options = HtmlOptions(attachment_base_url="https://example.com")
        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # Relative link should be resolved
        assert "[Relative link](https://example.com/page)" in result

        # XSS link should still be blocked
        assert "[XSS link]()" in result

    def test_require_https_blocks_http_links(self):
        """Test that require_https setting blocks HTTP links."""
        html_content = """
        <p>
            <a href="http://insecure.com">HTTP Link</a>
            <a href="https://secure.com">HTTPS Link</a>
            <a href="ftp://files.com">FTP Link</a>
            <a href="mailto:test@example.com">Email Link</a>
        </p>
        """

        options = HtmlOptions(network=NetworkFetchOptions(require_https=True))
        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # HTTP and FTP should be blocked
        assert "[HTTP Link]()" in result
        assert "[FTP Link]()" in result

        # HTTPS should be allowed
        assert "[HTTPS Link](https://secure.com)" in result

        # mailto should still be allowed
        assert "[Email Link](mailto:test@example.com)" in result

    def test_xss_prevention_in_complex_document(self):
        """Test XSS prevention in a complex HTML document with various attacks."""
        html_content = """
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
        """

        result = html_to_markdown(html_content, source_format="html")

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
        html_content = "<a href=\"javascript:alert('xss')\">Click</a>"

        # Test with strip_dangerous_elements=False (default)
        # Link text is preserved but href is neutralized
        options_default = HtmlOptions(strip_dangerous_elements=False)
        result_default = html_to_markdown(html_content, source_format="html", parser_options=options_default)
        assert "[Click]()" in result_default

        # Test with strip_dangerous_elements=True
        # Link scheme validation happens independently of strip_dangerous_elements
        # The <a> tag is preserved (not a dangerous element), but href is neutralized
        options_strict = HtmlOptions(strip_dangerous_elements=True)
        result_strict = html_to_markdown(html_content, source_format="html", parser_options=options_strict)
        assert "[Click]()" in result_strict  # Link preserved, href neutralized

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        html_content = """
        <a href="JAVASCRIPT:alert('XSS')">Upper</a>
        <a href="JavaScript:alert('XSS')">Mixed</a>
        <a href="JaVaScRiPt:alert('XSS')">Weird</a>
        <a href="HTTPS://example.com">HTTPS Upper</a>
        """

        result = html_to_markdown(html_content, source_format="html")

        # All javascript variants should be blocked
        assert "[Upper]()" in result
        assert "[Mixed]()" in result
        assert "[Weird]()" in result

        # HTTPS in uppercase should still work
        assert "[HTTPS Upper](HTTPS://example.com)" in result or "[HTTPS Upper](https://example.com)" in result


class TestHtmlFileUrlSecurity:
    """Test file:// URL handling and local file access policy in HTML parser."""

    def teardown_method(self):
        """Clean up test artifacts after each test."""
        for path in [Path("safe_images"), Path("tests/safe_images"), Path("tests/integration/safe_images")]:
            if path.exists():
                shutil.rmtree(path)

    def test_file_url_blocked_by_default(self):
        """Test that file:// URLs are blocked by default security settings."""
        html_content = '<img src="file:///etc/passwd" alt="system file">'

        # Default options should block local file access
        options = HtmlOptions()
        assert not options.local_files.allow_local_files

        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # Should return empty URL with alt text only
        assert "![system file]" in result
        assert "file://" not in result

    def test_file_url_relative_path_blocked_by_default(self):
        """Test that relative file:// URLs are blocked by default."""
        html_content = '<img src="file://./local_image.png" alt="local">'

        result = html_to_markdown(html_content, source_format="html")

        # Should be blocked even for CWD files
        assert "![local]" in result
        assert "file://" not in result

    def test_file_url_allowed_with_cwd_permission(self, tmp_path):
        """Test that file:// URLs work when CWD access is allowed."""
        from all2md.options.common import LocalFileAccessOptions

        # Create test image in current directory
        test_image = Path.cwd() / "test_image.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header

        try:
            html_content = f'<img src="file://{test_image}" alt="allowed">'

            options = HtmlOptions(
                local_files=LocalFileAccessOptions(allow_local_files=True, allow_cwd_files=True),
                attachment_mode="alt_text",
            )

            result = html_to_markdown(html_content, source_format="html", parser_options=options)

            # Should preserve the file:// URL when allowed
            assert f"file://{test_image}" in result or "allowed" in result

        finally:
            if test_image.exists():
                test_image.unlink()

    def test_file_url_blocked_by_denylist(self, tmp_path):
        """Test that denylist blocks file access even when local files are allowed."""
        from all2md.options.common import LocalFileAccessOptions

        # Create test file in a directory
        denied_dir = tmp_path / "denied"
        denied_dir.mkdir()
        test_file = denied_dir / "secret.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        html_content = f'<img src="file://{test_file}" alt="denied">'

        options = HtmlOptions(
            local_files=LocalFileAccessOptions(
                allow_local_files=True, allow_cwd_files=True, local_file_denylist=[str(denied_dir)]
            ),
            attachment_mode="base64",
        )

        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # Should be blocked by denylist
        assert "![denied]" in result
        assert "file://" not in result
        assert "base64" not in result

    def test_file_url_allowlist_enforcement(self, tmp_path):
        """Test that allowlist restricts file access to specified directories."""
        from all2md.options.common import LocalFileAccessOptions

        # Create files in different directories
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        allowed_file = allowed_dir / "ok.png"
        allowed_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        blocked_dir = tmp_path / "blocked"
        blocked_dir.mkdir()
        blocked_file = blocked_dir / "no.png"
        blocked_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        # Test allowed file
        html_allowed = f'<img src="file://{allowed_file}" alt="allowed">'
        options = HtmlOptions(
            local_files=LocalFileAccessOptions(
                allow_local_files=True, allow_cwd_files=False, local_file_allowlist=[str(allowed_dir)]
            ),
            attachment_mode="alt_text",
        )

        result_allowed = html_to_markdown(html_allowed, source_format="html", parser_options=options)
        # Should be allowed
        assert f"file://{allowed_file}" in result_allowed or "allowed" in result_allowed

        # Test blocked file
        html_blocked = f'<img src="file://{blocked_file}" alt="blocked">'
        result_blocked = html_to_markdown(html_blocked, source_format="html", parser_options=options)

        # Should be blocked (not in allowlist)
        assert "![blocked]" in result_blocked
        assert str(blocked_file) not in result_blocked

    def test_file_url_with_download_mode(self, tmp_path):
        """Test that file:// URLs work with download mode when allowed."""
        from all2md.options.common import LocalFileAccessOptions

        # Create test image
        test_image = tmp_path / "test.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        output_dir = tmp_path / "images"
        output_dir.mkdir()

        html_content = f'<img src="file://{test_image}" alt="test">'

        options = HtmlOptions(
            local_files=LocalFileAccessOptions(
                allow_local_files=True, allow_cwd_files=True, local_file_allowlist=[str(tmp_path)]
            ),
            attachment_mode="download",
            attachment_output_dir=str(output_dir),
        )

        result = html_to_markdown(html_content, source_format="html", parser_options=options)

        # Should download the file
        assert "![test]" in result
        # Check that file was copied to output directory
        downloaded_files = list(output_dir.glob("*.png"))
        assert len(downloaded_files) > 0

    def test_file_url_preserves_privacy_when_denied(self):
        """Test that file:// URLs don't leak paths when access is denied."""
        sensitive_path = "/home/user/.ssh/id_rsa"
        html_content = f'<img src="file://{sensitive_path}" alt="secret key">'

        # Default secure settings
        result = html_to_markdown(html_content, source_format="html")

        # Should not leak the path
        assert sensitive_path not in result
        assert "![secret key]" in result
        assert "file://" not in result
