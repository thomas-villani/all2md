#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for HTML sanitization utilities.

This module tests the security-critical HTML sanitization functions in
all2md.utils.html_sanitizer, including content sanitization, URL validation,
and element safety checks.
"""

import pytest

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

from all2md.utils.html_sanitizer import (
    is_element_safe,
    is_url_safe,
    sanitize_html_content,
    sanitize_url,
    strip_html_tags,
)


class TestSanitizeHtmlContent:
    """Test suite for sanitize_html_content function."""

    def test_pass_through_mode_unchanged(self):
        """Test that pass-through mode returns content unchanged."""
        content = '<script>alert("xss")</script>'
        result = sanitize_html_content(content, mode="pass-through")
        assert result == content

    def test_escape_mode_escapes_html(self):
        """Test that escape mode HTML-escapes all content."""
        content = '<script>alert("xss")</script>'
        result = sanitize_html_content(content, mode="escape")
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        assert "alert" in result

    def test_drop_mode_removes_all(self):
        """Test that drop mode returns empty string."""
        content = '<script>alert("xss")</script>'
        result = sanitize_html_content(content, mode="drop")
        assert result == ""

    def test_sanitize_mode_removes_dangerous_tags(self):
        """Test that sanitize mode removes dangerous elements."""
        content = '<script>alert("xss")</script><p>Safe content</p>'
        result = sanitize_html_content(content, mode="sanitize")
        # Script should be removed
        assert "script" not in result.lower() or "&lt;script" in result
        # Safe content might be preserved (depends on bleach availability)
        assert "Safe content" in result or "safe content" in result.lower()

    def test_sanitize_mode_removes_dangerous_attributes(self):
        """Test that sanitize mode removes dangerous attributes."""
        content = '<div onclick="alert()">Click me</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # onclick should be removed
        assert "onclick" not in result

    def test_sanitize_mode_preserves_safe_html(self):
        """Test that sanitize mode preserves safe HTML elements."""
        content = '<p>Hello <strong>world</strong></p>'
        result = sanitize_html_content(content, mode="sanitize")
        # Should contain the text content
        assert "Hello" in result
        assert "world" in result

    def test_sanitize_mode_removes_javascript_urls(self):
        """Test that sanitize mode removes javascript: URLs."""
        content = '<a href="javascript:alert()">Click</a>'
        result = sanitize_html_content(content, mode="sanitize")
        # javascript: URL should be removed or neutralized
        assert "javascript:alert()" not in result

    def test_unknown_mode_defaults_to_passthrough(self):
        """Test that unknown mode defaults to pass-through."""
        content = '<script>test</script>'
        result = sanitize_html_content(content, mode="unknown_mode")  # type: ignore
        assert result == content

    def test_empty_content(self):
        """Test handling of empty content."""
        assert sanitize_html_content("", mode="pass-through") == ""
        assert sanitize_html_content("", mode="escape") == ""
        assert sanitize_html_content("", mode="drop") == ""
        assert sanitize_html_content("", mode="sanitize") == ""

    def test_sanitize_mode_iframe_removal(self):
        """Test that sanitize mode removes iframe elements."""
        content = '<iframe src="http://evil.com"></iframe><p>Text</p>'
        result = sanitize_html_content(content, mode="sanitize")
        assert "iframe" not in result.lower() or "&lt;iframe" in result
        assert "Text" in result


class TestStripHtmlTags:
    """Test suite for strip_html_tags function."""

    def test_strip_simple_tags(self):
        """Test stripping simple HTML tags."""
        content = '<p>Hello world</p>'
        result = strip_html_tags(content)
        assert result == 'Hello world'

    def test_strip_nested_tags(self):
        """Test stripping nested HTML tags."""
        content = '<p>Hello <strong>bold</strong> world</p>'
        result = strip_html_tags(content)
        assert result == 'Hello bold world'

    def test_decode_html_entities(self):
        """Test that HTML entities are decoded."""
        content = '<p>Hello &amp; goodbye</p>'
        result = strip_html_tags(content)
        assert result == 'Hello & goodbye'

    def test_plain_text_unchanged(self):
        """Test that plain text without tags is unchanged."""
        content = 'Plain text'
        result = strip_html_tags(content)
        assert result == 'Plain text'

    def test_self_closing_tags(self):
        """Test handling of self-closing tags."""
        content = '<p>Text<br/>More text</p>'
        result = strip_html_tags(content)
        assert result == 'TextMore text'

    def test_multiple_spaces_preserved(self):
        """Test that multiple spaces are preserved in output."""
        content = '<p>Hello    world</p>'
        result = strip_html_tags(content)
        assert result == 'Hello    world'

    def test_complex_html_to_text(self):
        """Test conversion of complex HTML to plain text."""
        content = '<h1>Title</h1><p>Para <em>italic</em> text</p>'
        result = strip_html_tags(content)
        assert result == 'TitlePara italic text'

    def test_html_with_attributes(self):
        """Test stripping tags with attributes."""
        content = '<a href="http://example.com" class="link">Link</a>'
        result = strip_html_tags(content)
        assert result == 'Link'
        assert 'href' not in result
        assert 'example.com' not in result


@pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
class TestIsElementSafe:
    """Test suite for is_element_safe function (requires BeautifulSoup)."""

    def test_safe_element_returns_true(self):
        """Test that safe elements return True."""
        soup = BeautifulSoup('<p>Safe content</p>', 'html.parser')
        assert is_element_safe(soup.p) is True

    def test_script_element_returns_false(self):
        """Test that script elements return False."""
        soup = BeautifulSoup('<script>alert("xss")</script>', 'html.parser')
        assert is_element_safe(soup.script) is False

    def test_iframe_element_returns_false(self):
        """Test that iframe elements return False."""
        soup = BeautifulSoup('<iframe src="evil.com"></iframe>', 'html.parser')
        assert is_element_safe(soup.iframe) is False

    def test_dangerous_onclick_attribute_returns_false(self):
        """Test that elements with onclick return False."""
        soup = BeautifulSoup('<div onclick="alert()">Click</div>', 'html.parser')
        assert is_element_safe(soup.div) is False

    def test_dangerous_onerror_attribute_returns_false(self):
        """Test that elements with onerror return False."""
        soup = BeautifulSoup('<img src="x" onerror="alert()">', 'html.parser')
        assert is_element_safe(soup.img) is False

    def test_javascript_href_returns_false(self):
        """Test that javascript: URLs in href return False."""
        soup = BeautifulSoup('<a href="javascript:alert()">Link</a>', 'html.parser')
        assert is_element_safe(soup.a) is False

    def test_data_url_in_src_returns_false(self):
        """Test that data: URLs in src return False."""
        soup = BeautifulSoup('<img src="data:text/html,<script>alert()</script>">', 'html.parser')
        assert is_element_safe(soup.img) is False

    def test_style_with_javascript_returns_false(self):
        """Test that style attributes with javascript: return False."""
        soup = BeautifulSoup('<div style="background:url(javascript:alert())">Text</div>', 'html.parser')
        assert is_element_safe(soup.div) is False

    def test_safe_link_returns_true(self):
        """Test that safe links return True."""
        soup = BeautifulSoup('<a href="https://example.com">Link</a>', 'html.parser')
        assert is_element_safe(soup.a) is True

    def test_safe_image_returns_true(self):
        """Test that safe images return True."""
        soup = BeautifulSoup('<img src="https://example.com/image.png" alt="Image">', 'html.parser')
        assert is_element_safe(soup.img) is True

    def test_text_node_returns_true(self):
        """Test that text nodes return True."""
        soup = BeautifulSoup('Plain text', 'html.parser')
        text_node = soup.contents[0]
        assert is_element_safe(text_node) is True


class TestIsUrlSafe:
    """Test suite for is_url_safe function."""

    def test_https_url_is_safe(self):
        """Test that HTTPS URLs are safe."""
        assert is_url_safe("https://example.com") is True

    def test_http_url_is_safe(self):
        """Test that HTTP URLs are safe."""
        assert is_url_safe("http://example.com") is True

    def test_javascript_url_is_unsafe(self):
        """Test that javascript: URLs are unsafe."""
        assert is_url_safe("javascript:alert('xss')") is False

    def test_data_url_is_unsafe(self):
        """Test that data: URLs are unsafe."""
        assert is_url_safe("data:text/html,<script>alert()</script>") is False

    def test_vbscript_url_is_unsafe(self):
        """Test that vbscript: URLs are unsafe."""
        assert is_url_safe("vbscript:msgbox()") is False

    def test_relative_url_is_safe(self):
        """Test that relative URLs are safe."""
        assert is_url_safe("/path/to/page") is True
        assert is_url_safe("./relative/path") is True
        assert is_url_safe("../parent/path") is True

    def test_anchor_url_is_safe(self):
        """Test that anchor links are safe."""
        assert is_url_safe("#section") is True

    def test_mailto_url_is_safe(self):
        """Test that mailto: URLs are safe."""
        assert is_url_safe("mailto:user@example.com") is True

    def test_ftp_url_is_safe(self):
        """Test that FTP URLs are safe."""
        assert is_url_safe("ftp://ftp.example.com/file.txt") is True

    def test_empty_url_is_safe(self):
        """Test that empty URLs are considered safe."""
        assert is_url_safe("") is True
        assert is_url_safe("   ") is True

    def test_case_insensitive_javascript(self):
        """Test that JavaScript detection is case-insensitive."""
        assert is_url_safe("JavaScript:alert()") is False
        assert is_url_safe("JAVASCRIPT:alert()") is False

    def test_case_insensitive_data(self):
        """Test that data URL detection is case-insensitive."""
        assert is_url_safe("Data:text/html,test") is False
        assert is_url_safe("DATA:text/html,test") is False


class TestSanitizeUrl:
    """Test suite for sanitize_url function."""

    def test_safe_url_unchanged(self):
        """Test that safe URLs are returned unchanged."""
        url = "https://example.com"
        assert sanitize_url(url) == url

    def test_javascript_url_returns_empty(self):
        """Test that javascript: URLs return empty string."""
        assert sanitize_url("javascript:alert()") == ""

    def test_data_url_returns_empty(self):
        """Test that data: URLs return empty string."""
        assert sanitize_url("data:text/html,test") == ""

    def test_relative_url_unchanged(self):
        """Test that relative URLs are unchanged."""
        assert sanitize_url("/path/to/page") == "/path/to/page"

    def test_empty_url_returns_empty(self):
        """Test that empty URLs return empty string."""
        assert sanitize_url("") == ""

    def test_mailto_unchanged(self):
        """Test that mailto: URLs are unchanged."""
        url = "mailto:user@example.com"
        assert sanitize_url(url) == url


class TestSanitizationIntegration:
    """Integration tests for combined sanitization features."""

    def test_sanitize_then_strip(self):
        """Test sanitizing then stripping HTML tags."""
        content = '<script>alert()</script><p>Safe <strong>text</strong></p>'
        sanitized = sanitize_html_content(content, mode="sanitize")
        stripped = strip_html_tags(sanitized)
        assert "alert" not in stripped or "script" not in stripped.lower()
        assert "Safe" in stripped
        assert "text" in stripped

    def test_escape_preserves_text_after_strip(self):
        """Test that escaped content preserves text after stripping."""
        content = '<p>Hello <em>world</em></p>'
        escaped = sanitize_html_content(content, mode="escape")
        stripped = strip_html_tags(escaped)
        # After escaping and stripping, should still contain the text
        assert "Hello" in stripped
        assert "world" in stripped

    @pytest.mark.skipif(not BEAUTIFULSOUP_AVAILABLE, reason="BeautifulSoup not available")
    def test_element_safety_matches_sanitization(self):
        """Test that element safety check matches sanitization behavior."""
        dangerous_content = '<script>alert()</script>'
        soup = BeautifulSoup(dangerous_content, 'html.parser')

        # Element should be marked as unsafe
        assert is_element_safe(soup.script) is False

        # Sanitization should remove it
        sanitized = sanitize_html_content(dangerous_content, mode="sanitize")
        assert "script" not in sanitized.lower() or "&lt;script" in sanitized


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        content = '<p>Unclosed paragraph'
        result = strip_html_tags(content)
        assert "Unclosed paragraph" in result

    def test_nested_dangerous_tags(self):
        """Test handling of nested dangerous tags."""
        content = '<div><script><iframe></iframe></script></div>'
        result = sanitize_html_content(content, mode="sanitize")
        assert "script" not in result.lower() or "&lt;script" in result
        assert "iframe" not in result.lower() or "&lt;iframe" in result

    def test_html_entities_in_attributes(self):
        """Test handling of HTML entities in attributes."""
        content = '<a href="page.html?a=1&amp;b=2">Link</a>'
        stripped = strip_html_tags(content)
        assert "Link" in stripped

    def test_unicode_content(self):
        """Test handling of Unicode content."""
        content = '<p>Hello 世界 🌍</p>'
        result = strip_html_tags(content)
        assert "Hello 世界 🌍" in result

    def test_very_long_url(self):
        """Test handling of very long URLs."""
        long_url = "https://example.com/" + "a" * 10000
        # Should not crash
        result = is_url_safe(long_url)
        assert isinstance(result, bool)

    def test_url_with_query_params(self):
        """Test URLs with query parameters."""
        url = "https://example.com/page?param=value&other=123"
        assert is_url_safe(url) is True
        assert sanitize_url(url) == url

    def test_url_with_fragment(self):
        """Test URLs with fragments."""
        url = "https://example.com/page#section"
        assert is_url_safe(url) is True
        assert sanitize_url(url) == url


class TestStyleAttributeSanitization:
    """Test suite for CSS style attribute sanitization."""

    def test_safe_style_preserved(self):
        """Test that safe CSS styles are preserved."""
        content = '<div style="color: red; font-size: 12px;">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        assert "color: red" in result or "color:red" in result
        assert "Text" in result

    def test_expression_in_style_removed(self):
        """Test that style with expression() is removed."""
        content = '<div style="width: expression(alert(1));">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # Style attribute should be removed
        assert "expression" not in result.lower() or "expression" not in result
        assert "Text" in result

    def test_javascript_url_in_style_removed(self):
        """Test that style with url(javascript:...) is removed."""
        content = '<div style="background: url(javascript:alert(1));">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # Style attribute should be removed
        assert "javascript:" not in result.lower()
        assert "Text" in result

    def test_data_url_in_style_removed(self):
        """Test that style with url(data:text/html,...) is removed."""
        content = '<div style="background: url(data:text/html,<script>alert(1)</script>);">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # Style attribute should be removed
        assert "data:text/html" not in result.lower()
        assert "Text" in result

    def test_safe_url_in_style_preserved(self):
        """Test that style with safe url() is preserved."""
        content = '<div style="background: url(https://example.com/image.png);">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # Safe URL should be preserved
        assert "example.com" in result or "background" in result
        assert "Text" in result

    def test_expression_with_space_removed(self):
        """Test that expression with space is also detected."""
        content = '<div style="width: expression (alert(1));">Text</div>'
        result = sanitize_html_content(content, mode="sanitize")
        # Style attribute should be removed
        assert "expression" not in result.lower()
        assert "Text" in result


class TestSrcsetSanitization:
    """Test suite for srcset attribute sanitization."""

    def test_safe_srcset_preserved(self):
        """Test that safe srcset is preserved."""
        content = '<img srcset="image1.jpg 1x, image2.jpg 2x" alt="Test">'
        result = sanitize_html_content(content, mode="sanitize")
        assert "image1.jpg" in result
        assert "image2.jpg" in result

    def test_javascript_in_srcset_removed(self):
        """Test that srcset with javascript: URL is removed."""
        content = '<img srcset="javascript:alert(1) 1x" alt="Test">'
        result = sanitize_html_content(content, mode="sanitize")
        # srcset should be removed or javascript should not be present
        assert "javascript:" not in result.lower()

    def test_mixed_srcset_sanitized(self):
        """Test that srcset with mixed safe and unsafe URLs is sanitized."""
        content = '<img srcset="safe.jpg 1x, javascript:alert(1) 2x, image.png 3x" alt="Test">'
        result = sanitize_html_content(content, mode="sanitize")
        # Safe URLs should be preserved
        assert "safe.jpg" in result or "image.png" in result
        # Unsafe URL should be removed
        assert "javascript:" not in result.lower()

    def test_data_url_in_srcset_removed(self):
        """Test that srcset with data:text/html URL is removed."""
        content = '<img srcset="data:text/html,<script>alert(1)</script> 1x" alt="Test">'
        result = sanitize_html_content(content, mode="sanitize")
        # data:text/html should be removed
        assert "data:text/html" not in result.lower()

    def test_srcset_with_descriptors_preserved(self):
        """Test that srcset with various descriptors is handled correctly."""
        content = '<img srcset="small.jpg 480w, medium.jpg 800w, large.jpg 1200w" alt="Test">'
        result = sanitize_html_content(content, mode="sanitize")
        # URLs should be preserved
        assert "small.jpg" in result or "medium.jpg" in result or "large.jpg" in result
