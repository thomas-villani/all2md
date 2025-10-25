"""Tests for M10: BeautifulSoup parser choice option.

This module tests that the html_parser option allows users to choose
different BeautifulSoup parsers (html.parser, html5lib, lxml) with
appropriate trade-offs between speed and standards compliance.
"""

import pytest

from all2md import to_markdown
from all2md.exceptions import DependencyError
from all2md.options.html import HtmlOptions


class TestHtmlParserChoice:
    """Test HTML parser choice option."""

    def test_default_parser_is_html_parser(self):
        """Test that the default parser is html.parser."""
        options = HtmlOptions()
        assert options.html_parser == "html.parser"

    def test_html_parser_option_works(self):
        """Test that html.parser option works correctly."""
        html = "<p>Test content</p>"

        options = HtmlOptions(html_parser="html.parser")
        result = to_markdown(html, source_format="html", parser_options=options)

        assert "Test content" in result

    def test_html5lib_parser_option(self):
        """Test that html5lib parser option works if available."""
        html = "<p>Test content</p>"

        try:
            options = HtmlOptions(html_parser="html5lib")
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "Test content" in result
        except DependencyError:
            # html5lib may not be installed
            pytest.skip("html5lib not available")

    def test_lxml_parser_option(self):
        """Test that lxml parser option works if available."""
        html = "<p>Test content</p>"

        try:
            options = HtmlOptions(html_parser="lxml")
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "Test content" in result
        except DependencyError:
            # lxml may not be installed
            pytest.skip("lxml not available")

    def test_malformed_html_with_html_parser(self):
        """Test malformed HTML with html.parser."""
        # HTML with unclosed tags
        html = "<p>Unclosed paragraph<p>Another one"

        options = HtmlOptions(html_parser="html.parser")
        result = to_markdown(html, source_format="html", parser_options=options)

        # Should parse without crashing
        assert "Unclosed paragraph" in result or "Another one" in result

    def test_malformed_html_with_html5lib(self):
        """Test that html5lib handles malformed HTML more like browsers."""
        # HTML with unclosed tags
        html = "<p>Unclosed paragraph<p>Another one"

        try:
            options = HtmlOptions(html_parser="html5lib")
            result = to_markdown(html, source_format="html", parser_options=options)

            # Should parse without crashing and handle malformed HTML better
            assert "Unclosed paragraph" in result or "Another one" in result
        except DependencyError:
            pytest.skip("html5lib not available")

    def test_parser_choice_with_sanitization(self):
        """Test that parser choice works with HTML sanitization enabled."""
        html = '<p>Content</p><script>alert("xss")</script>'

        options = HtmlOptions(html_parser="html.parser", strip_dangerous_elements=True)

        result = to_markdown(html, source_format="html", parser_options=options)

        # Should parse and sanitize correctly
        assert "Content" in result
        # Script should be removed
        assert "alert" not in result

    def test_nested_tags_with_different_parsers(self):
        """Test that nested tags work with different parsers."""
        html = "<div><p>Outer <strong>bold <em>and italic</em> text</strong> here</p></div>"

        # Test with html.parser
        options1 = HtmlOptions(html_parser="html.parser")
        result1 = to_markdown(html, source_format="html", parser_options=options1)
        assert "bold" in result1 or "italic" in result1

        # Test with html5lib if available
        try:
            options2 = HtmlOptions(html_parser="html5lib")
            result2 = to_markdown(html, source_format="html", parser_options=options2)
            assert "bold" in result2 or "italic" in result2
        except DependencyError:
            pytest.skip("html5lib not available")

    def test_table_parsing_with_different_parsers(self):
        """Test that table parsing works with different parsers."""
        html = """
        <table>
            <thead><tr><th>Header 1</th><th>Header 2</th></tr></thead>
            <tbody><tr><td>Cell 1</td><td>Cell 2</td></tr></tbody>
        </table>
        """

        # Test with html.parser
        options1 = HtmlOptions(html_parser="html.parser")
        result1 = to_markdown(html, source_format="html", parser_options=options1)
        assert "Header 1" in result1 or "Cell 1" in result1

        # Test with html5lib if available
        try:
            options2 = HtmlOptions(html_parser="html5lib")
            result2 = to_markdown(html, source_format="html", parser_options=options2)
            assert "Header 1" in result2 or "Cell 1" in result2
        except DependencyError:
            pytest.skip("html5lib not available")

    def test_self_closing_tags_with_parsers(self):
        """Test that self-closing tags are handled correctly by different parsers."""
        html = "<p>Line 1<br/>Line 2<hr/>Line 3</p>"

        # Test with html.parser
        options1 = HtmlOptions(html_parser="html.parser")
        result1 = to_markdown(html, source_format="html", parser_options=options1)
        assert "Line 1" in result1

        # Test with html5lib if available (may handle self-closing tags differently)
        try:
            options2 = HtmlOptions(html_parser="html5lib")
            result2 = to_markdown(html, source_format="html", parser_options=options2)
            assert "Line 1" in result2
        except DependencyError:
            pytest.skip("html5lib not available")

    def test_invalid_parser_name_raises_error(self):
        """Test that using an invalid parser name raises an appropriate error."""
        html = "<p>Test</p>"

        # BeautifulSoup will raise an error for invalid parser names
        options = HtmlOptions(html_parser="invalid_parser")  # type: ignore

        with pytest.raises(Exception):
            # This should fail when BeautifulSoup tries to use the invalid parser
            to_markdown(html, source_format="html", parser_options=options)
