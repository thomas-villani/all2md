"""Tests for M8: NULL byte and zero-width character sanitization.

This module tests that dangerous null-like and zero-width characters
are properly removed to prevent XSS filter bypass attacks.
"""

from all2md import to_markdown
from all2md.utils.security import sanitize_null_bytes


class TestNullByteSanitization:
    """Test null byte and zero-width character removal."""

    def test_null_byte_removed(self):
        """Test that \\x00 null bytes are removed."""
        html = "Hello\x00World<p>Test\x00Content</p>"

        result = to_markdown(html, source_format="html")
        assert "\x00" not in result
        assert "HelloWorld" in result or "Test" in result

    def test_bom_removed(self):
        """Test that \\ufeff (BOM/Zero Width No-Break Space) is removed."""
        html = "Hello\ufeffWorld<p>Test\ufeffContent</p>"

        result = to_markdown(html, source_format="html")
        assert "\ufeff" not in result

    def test_zero_width_space_removed(self):
        """Test that \\u200b (Zero Width Space) is removed."""
        html = "Hello\u200bWorld<p>Test\u200bContent</p>"

        result = to_markdown(html, source_format="html")
        assert "\u200b" not in result

    def test_zero_width_non_joiner_removed(self):
        """Test that \\u200c (Zero Width Non-Joiner) is removed."""
        html = "Hello\u200cWorld<p>Test\u200cContent</p>"

        result = to_markdown(html, source_format="html")
        assert "\u200c" not in result

    def test_zero_width_joiner_removed(self):
        """Test that \\u200d (Zero Width Joiner) is removed."""
        html = "Hello\u200dWorld<p>Test\u200dContent</p>"

        result = to_markdown(html, source_format="html")
        assert "\u200d" not in result

    def test_word_joiner_removed(self):
        """Test that \\u2060 (Word Joiner) is removed."""
        html = "Hello\u2060World<p>Test\u2060Content</p>"

        result = to_markdown(html, source_format="html")
        assert "\u2060" not in result

    def test_multiple_dangerous_chars_removed(self):
        """Test that multiple dangerous characters are all removed."""
        html = "A\x00B\ufeffC\u200bD\u200cE\u200dF\u2060G"

        result = to_markdown(html, source_format="html")
        # All dangerous characters should be removed
        assert "\x00" not in result
        assert "\ufeff" not in result
        assert "\u200b" not in result
        assert "\u200c" not in result
        assert "\u200d" not in result
        assert "\u2060" not in result

    def test_xss_bypass_attempt_blocked(self):
        """Test that XSS bypass attempts using null bytes are blocked."""
        # Attempt to bypass XSS filters using null bytes in script tags
        html = '<script\x00>alert("xss")</script>'

        result = to_markdown(html, source_format="html")
        # Null byte should be removed, and script tag should be handled
        assert "\x00" not in result

    def test_normal_text_preserved(self):
        """Test that normal text without dangerous characters is preserved."""
        html = "<p>This is normal text with spaces and punctuation!</p>"

        result = to_markdown(html, source_format="html")
        assert "normal text" in result

    def test_sanitize_null_bytes_function_directly(self):
        """Test the sanitize_null_bytes function directly."""
        # Test each dangerous character individually
        assert sanitize_null_bytes("Hello\x00World") == "HelloWorld"
        assert sanitize_null_bytes("Test\ufeffContent") == "TestContent"
        assert sanitize_null_bytes("Zero\u200bWidth") == "ZeroWidth"
        assert sanitize_null_bytes("Non\u200cJoiner") == "NonJoiner"
        assert sanitize_null_bytes("Joiner\u200dTest") == "JoinerTest"
        assert sanitize_null_bytes("Word\u2060Joiner") == "WordJoiner"

        # Test multiple characters
        assert sanitize_null_bytes("A\x00B\ufeffC") == "ABC"

        # Test normal text
        assert sanitize_null_bytes("Normal text") == "Normal text"

        # Test empty string
        assert sanitize_null_bytes("") == ""

    def test_in_attributes_removed(self):
        """Test that dangerous characters in HTML attributes are removed."""
        html = '<a href="http://example.com\x00/path">Link\u200b</a>'

        result = to_markdown(html, source_format="html")
        assert "\x00" not in result
        assert "\u200b" not in result
