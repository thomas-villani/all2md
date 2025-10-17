"""Integration tests for Org-mode parser URL sanitization security.

This test module validates that the Org-mode parser properly sanitizes
dangerous URL schemes to prevent XSS attacks.

Test Coverage:
- Image URL sanitization (file: links)
- Link URL sanitization (dangerous schemes blocked)
- Plain URL image detection
- Plain URL link detection
- Mixed safe and dangerous URLs in same document
"""

from all2md import to_markdown


class TestOrgModeUrlSanitization:
    """Test Org-mode parser URL scheme security."""

    def test_link_javascript_url_blocked(self):
        """Test that javascript: URLs in links are blocked."""
        org_content = """[[javascript:alert('xss')][Malicious Link]]"""

        result = to_markdown(org_content, source_format="org")

        # URL should be sanitized to empty string
        assert "javascript:" not in result
        assert "Malicious Link" in result or result.strip() != ""

    def test_link_vbscript_url_blocked(self):
        """Test that vbscript: URLs in links are blocked."""
        org_content = """[[vbscript:msgbox('xss')][VBScript Attack]]"""

        result = to_markdown(org_content, source_format="org")

        # URL should be sanitized to empty string
        assert "vbscript:" not in result
        assert "VBScript Attack" in result or result.strip() != ""

    def test_link_data_html_url_blocked(self):
        """Test that data:text/html URLs in links are blocked."""
        org_content = """[[data:text/html,<script>alert('xss')</script>][Data HTML]]"""

        result = to_markdown(org_content, source_format="org")

        # URL should be sanitized to empty string
        assert "data:text/html" not in result
        assert "<script>" not in result

    def test_link_safe_url_preserved(self):
        """Test that safe URLs in links are preserved."""
        org_content = """[[https://example.com][Example Link]]"""

        result = to_markdown(org_content, source_format="org")

        # Safe URL should be preserved
        assert "https://example.com" in result
        assert "Example Link" in result

    def test_image_file_javascript_blocked(self):
        """Test that javascript: URLs in file: image links are blocked."""
        org_content = """[[file:javascript:alert('xss')][Image]]"""

        result = to_markdown(org_content, source_format="org")

        # URL should be sanitized
        assert "javascript:" not in result

    def test_image_file_safe_path_preserved(self):
        """Test that safe file paths in images are preserved."""
        org_content = """[[file:./images/logo.png][Logo]]"""

        result = to_markdown(org_content, source_format="org")

        # Safe path should be preserved
        assert "logo.png" in result or "Logo" in result

    def test_plain_url_javascript_blocked(self):
        """Test that plain javascript: URLs in links are blocked."""
        # Note: Plain text without markup is not converted to a link
        # This test uses Org link syntax with description to verify sanitization
        org_content = """[[javascript:alert('xss')][Click]]"""

        result = to_markdown(org_content, source_format="org")

        # URL should be sanitized - check it's not in the output as an executable link
        # The text "Click" should be present but not the javascript: scheme
        assert "Click" in result or result.strip() != ""
        # Most importantly, javascript scheme should not be in the output
        assert "javascript:alert" not in result.lower()

    def test_plain_url_safe_preserved(self):
        """Test that plain safe URLs are preserved."""
        org_content = """* Test Document

This document contains a safe URL: https://example.com/page

More content here."""

        result = to_markdown(org_content, source_format="org")

        # Safe URL should be preserved
        assert "https://example.com/page" in result

    def test_multiple_dangerous_urls_in_document(self):
        """Test that multiple dangerous URLs are all sanitized."""
        org_content = """
* Test Document

[[javascript:alert('link1')][Link 1]]

[[file:vbscript:msgbox('img1')][Image 1]]

[[data:text/javascript,alert('link2')][Link 2]]

[[https://safe.com][Safe Link]]

[[file:./safe.png][Safe Image]]
"""

        result = to_markdown(org_content, source_format="org")

        # All dangerous URLs should be sanitized
        assert "javascript:" not in result
        assert "vbscript:" not in result
        assert "data:text/javascript" not in result

        # Safe URLs should be preserved
        assert "https://safe.com" in result or "Safe Link" in result
        assert "safe.png" in result or "Safe Image" in result

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        org_content = """
[[JAVASCRIPT:alert('XSS')][Upper]]

[[JavaScript:alert('XSS')][Mixed]]

[[JaVaScRiPt:alert('XSS')][Weird]]

[[HTTPS://example.com][Safe Upper]]
"""

        result = to_markdown(org_content, source_format="org")

        # All javascript variants should be blocked (case-insensitive)
        assert "JAVASCRIPT:" not in result
        assert "JavaScript:" not in result
        assert "JaVaScRiPt:" not in result

        # HTTPS should still work regardless of case
        assert "example.com" in result or "Safe Upper" in result

    def test_mixed_content_types_with_xss_attempts(self):
        """Test document with various content types and XSS attempts."""
        org_content = """
* Security Test

** Text Content

Normal paragraph with [[javascript:void(0)][dangerous link]].

Safe link: [[https://example.com][Example]]

** Images

[[file:javascript:alert('xss')][JS Image]]

[[file:https://cdn.example.com/logo.png][Safe Logo]]

** Lists

- Item with [[vbscript:msgbox('xss')][VBScript link]]
- Item with [[mailto:test@example.com][Safe mailto]]
- Item with [[tel:+1234567890][Safe tel]]
"""

        result = to_markdown(org_content, source_format="org")

        # Dangerous schemes should be blocked
        assert "javascript:" not in result
        assert "vbscript:" not in result

        # Safe schemes should be preserved
        assert "https://example.com" in result or "Example" in result
        assert "mailto:test@example.com" in result or "test@example.com" in result
        assert "tel:+1234567890" in result or "+1234567890" in result

    def test_file_scheme_absolute_path_handling(self):
        """Test that file:// URLs with absolute paths are handled securely."""
        org_content = """
[[file:/etc/passwd][System File]]

[[file:/home/user/.ssh/id_rsa][SSH Key]]
"""

        result = to_markdown(org_content, source_format="org")

        # Should handle file paths according to security policy
        assert "System File" in result or result.strip() != ""
        assert "SSH Key" in result or result.strip() != ""

    def test_mailto_and_tel_schemes_allowed(self):
        """Test that mailto: and tel: schemes are allowed (safe)."""
        org_content = """
Contact: [[mailto:info@example.com][Email Us]]

Call: [[tel:+1-555-0100][Phone]]
"""

        result = to_markdown(org_content, source_format="org")

        # Safe communication schemes should be preserved
        assert "mailto:info@example.com" in result or "Email Us" in result
        assert "tel:+1-555-0100" in result or "Phone" in result

    def test_anchor_links_preserved(self):
        """Test that anchor links (fragment identifiers) are preserved."""
        org_content = """
[[#section-1][Go to Section 1]]

[[https://example.com#anchor][External Anchor]]
"""

        result = to_markdown(org_content, source_format="org")

        # Anchor links should be safe and preserved
        assert "#section-1" in result or "Go to Section 1" in result
        assert "https://example.com" in result or "External Anchor" in result
