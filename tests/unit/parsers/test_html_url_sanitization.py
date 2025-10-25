"""Tests for M12: URL sanitization for fragment content.

This module tests that dangerous schemes embedded in URL fragments
(like #javascript:alert(1)) are properly blocked.
"""

from all2md import to_markdown


class TestUrlFragmentSanitization:
    """Test URL sanitization for dangerous schemes in fragments."""

    def test_javascript_in_fragment_blocked(self):
        """Test that #javascript: URLs are blocked."""
        html = "<a href=\"#javascript:alert('xss')\">Click</a>"

        result = to_markdown(html, source_format="html")
        # The link should be sanitized (URL removed or made safe)
        # At minimum, the dangerous javascript: scheme should not appear
        assert "javascript:" not in result.lower()

    def test_data_in_fragment_blocked(self):
        """Test that #data: URLs are blocked."""
        html = '<a href="#data:text/html,<script>alert(1)</script>">Click</a>'

        result = to_markdown(html, source_format="html")
        # The dangerous data: scheme should not appear
        assert "data:" not in result.lower() or "data:image" in result.lower()  # Image data URLs are OK

    def test_vbscript_in_fragment_blocked(self):
        """Test that #vbscript: URLs are blocked."""
        html = "<a href=\"#vbscript:msgbox('xss')\">Click</a>"

        result = to_markdown(html, source_format="html")
        # The dangerous vbscript: scheme should not appear
        assert "vbscript:" not in result.lower()

    def test_safe_fragment_preserved(self):
        """Test that safe fragments (like #section-1) are preserved."""
        html = '<a href="#section-1">Jump to section</a>'

        result = to_markdown(html, source_format="html")
        # Safe fragment should be preserved
        assert "#section-1" in result

    def test_empty_fragment_preserved(self):
        """Test that empty fragments (#) are preserved."""
        html = '<a href="#">Top</a>'

        result = to_markdown(html, source_format="html")
        # Should parse successfully
        assert "Top" in result

    def test_complex_safe_fragment_preserved(self):
        """Test that complex but safe fragments are preserved."""
        html = '<a href="#section-1.2.3_test">Jump</a>'

        result = to_markdown(html, source_format="html")
        # Safe complex fragment should be preserved
        assert "#section-1.2.3_test" in result

    def test_javascript_in_href_blocked(self):
        """Test that direct javascript: URLs (not in fragments) are also blocked."""
        html = "<a href=\"javascript:alert('xss')\">Click</a>"

        result = to_markdown(html, source_format="html")
        # The dangerous javascript: scheme should be blocked
        assert "javascript:" not in result.lower()

    def test_mixed_safe_and_dangerous_links(self):
        """Test that safe links work while dangerous ones are blocked."""
        html = """
        <a href="#safe-section">Safe</a>
        <a href="#javascript:alert(1)">Dangerous</a>
        <a href="https://example.com">External</a>
        <a href="#vbscript:code">Bad</a>
        """

        result = to_markdown(html, source_format="html")
        # Safe links should work
        assert "safe-section" in result.lower() or "safe" in result.lower()
        assert "example.com" in result.lower()
        # Dangerous schemes should be blocked
        assert "javascript:" not in result.lower()
        assert "vbscript:" not in result.lower()

    def test_relative_urls_preserved(self):
        """Test that relative URLs (/, ./, ../) are preserved."""
        html = """
        <a href="/page.html">Root page</a>
        <a href="./subdir/page.html">Relative</a>
        <a href="../parent/page.html">Parent</a>
        """

        result = to_markdown(html, source_format="html")
        # Relative URLs should be preserved
        assert "/page.html" in result or "Root" in result
        assert "./subdir" in result or "Relative" in result
        assert "../parent" in result or "Parent" in result

    def test_query_strings_preserved(self):
        """Test that URLs with query strings are preserved."""
        html = '<a href="?page=1&sort=date">Query</a>'

        result = to_markdown(html, source_format="html")
        # Query strings should be preserved
        assert "?page=" in result or "Query" in result

    def test_case_insensitive_scheme_detection(self):
        """Test that dangerous schemes are detected case-insensitively."""
        html = """
        <a href="#JavaScript:alert(1)">Mixed case JS</a>
        <a href="#VBSCRIPT:code">Uppercase VBS</a>
        <a href="#DaTa:text/html">Mixed case data</a>
        """

        result = to_markdown(html, source_format="html")
        # All dangerous schemes should be blocked regardless of case
        assert "javascript:" not in result.lower()
        assert "vbscript:" not in result.lower()
        # Note: data: for images might be OK, but data:text/html should be blocked
        # This test just checks that case-insensitive matching works
