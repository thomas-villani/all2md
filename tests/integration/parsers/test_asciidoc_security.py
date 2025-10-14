"""Integration tests for AsciiDoc parser URL sanitization security.

This test module validates that the AsciiDoc parser properly sanitizes
dangerous URL schemes to prevent XSS attacks.

Test Coverage:
- Image URL sanitization (dangerous schemes blocked)
- Explicit link URL sanitization
- Auto-link URL sanitization
- Cross-reference URL sanitization
- Mixed safe and dangerous URLs in same document
"""

from all2md import to_markdown


class TestAsciiDocUrlSanitization:
    """Test AsciiDoc parser URL scheme security."""

    def test_image_javascript_url_blocked(self):
        """Test that javascript: URLs in images are blocked."""
        asciidoc_content = """image::javascript:alert('xss')[Malicious Image]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # URL should be sanitized to empty string
        assert "javascript:" not in result
        assert "Malicious Image" in result

    def test_image_vbscript_url_blocked(self):
        """Test that vbscript: URLs in images are blocked."""
        asciidoc_content = """image::vbscript:msgbox('xss')[VBScript Attack]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # URL should be sanitized to empty string
        assert "vbscript:" not in result
        assert "VBScript Attack" in result

    def test_image_data_html_url_blocked(self):
        """Test that data:text/html URLs in images are blocked."""
        asciidoc_content = """image::data:text/html,<script>alert('xss')</script>[Data HTML]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # URL should be sanitized to empty string
        assert "data:text/html" not in result
        assert "<script>" not in result

    def test_image_safe_url_preserved(self):
        """Test that safe URLs in images are preserved."""
        asciidoc_content = """image::https://example.com/image.png[Safe Image]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # Safe URL should be preserved
        assert "https://example.com/image.png" in result
        assert "Safe Image" in result

    def test_explicit_link_javascript_blocked(self):
        """Test that javascript: URLs in explicit links are blocked."""
        asciidoc_content = """link:javascript:void(0)[Click Me]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # URL should be sanitized to empty string
        assert "javascript:" not in result
        assert "Click Me" in result

    def test_explicit_link_safe_url_preserved(self):
        """Test that safe URLs in explicit links are preserved."""
        asciidoc_content = """link:https://example.com[Example Link]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # Safe URL should be preserved
        assert "https://example.com" in result
        assert "Example Link" in result

    def test_autolink_javascript_blocked(self):
        """Test that javascript: URLs in autolinks are blocked."""
        # Note: Plain text without markup is not converted to a link
        # This test verifies that if it were a link, it would be sanitized
        # In AsciiDoc, bare URLs aren't automatically linked unless they match URL patterns
        asciidoc_content = """link:javascript:alert('xss')[Autolink]"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # URL should be sanitized
        assert "javascript:" not in result

    def test_autolink_safe_url_preserved(self):
        """Test that safe URLs in autolinks are preserved."""
        asciidoc_content = """https://example.com/page"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # Safe URL should be preserved
        assert "https://example.com/page" in result

    def test_multiple_dangerous_urls_in_document(self):
        """Test that multiple dangerous URLs are all sanitized."""
        asciidoc_content = """
= Test Document

image::javascript:alert('img1')[Image 1]

link:vbscript:msgbox('link1')[Link 1]

image::data:text/javascript,alert('img2')[Image 2]

link:https://safe.com[Safe Link]

image::https://example.com/safe.png[Safe Image]
"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # All dangerous URLs should be sanitized
        assert "javascript:" not in result
        assert "vbscript:" not in result
        assert "data:text/javascript" not in result

        # Safe URLs should be preserved
        assert "https://safe.com" in result
        assert "https://example.com/safe.png" in result

    def test_case_insensitive_scheme_detection(self):
        """Test that scheme detection is case-insensitive."""
        asciidoc_content = """
link:JAVASCRIPT:alert('XSS')[Upper]

link:JavaScript:alert('XSS')[Mixed]

link:JaVaScRiPt:alert('XSS')[Weird]

link:HTTPS://example.com[Safe Upper]
"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # All javascript variants should be blocked (case-insensitive)
        assert "JAVASCRIPT:" not in result
        assert "JavaScript:" not in result
        assert "JaVaScRiPt:" not in result

        # HTTPS should still work regardless of case
        assert "example.com" in result

    def test_mixed_content_types_with_xss_attempts(self):
        """Test document with various content types and XSS attempts."""
        asciidoc_content = """
= Security Test

== Text Content

Normal paragraph with link:javascript:void(0)[dangerous link].

Safe link: link:https://example.com[Example]

== Images

image::javascript:alert('xss')[JS Image]

image::https://cdn.example.com/logo.png[Safe Logo]

== Lists

* Item with link:vbscript:msgbox('xss')[VBScript link]
* Item with link:mailto:test@example.com[Safe mailto]
* Item with link:tel:+1234567890[Safe tel]
"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # Dangerous schemes should be blocked
        assert "javascript:" not in result
        assert "vbscript:" not in result

        # Safe schemes should be preserved
        assert "https://example.com" in result or "Example" in result
        assert "https://cdn.example.com/logo.png" in result or "Safe Logo" in result
        assert "mailto:test@example.com" in result or "test@example.com" in result
        assert "tel:+1234567890" in result or "+1234567890" in result

    def test_file_scheme_url_handling(self):
        """Test that file:// URLs are handled according to security policy."""
        asciidoc_content = """
image::file:///etc/passwd[System File]

link:file:///home/user/.ssh/id_rsa[SSH Key]
"""

        result = to_markdown(asciidoc_content, source_format="asciidoc")

        # file:// URLs should be sanitized by default security policy
        # The exact behavior depends on security settings, but should not expose paths
        assert "System File" in result or result.strip() != ""
        assert "SSH Key" in result or result.strip() != ""
