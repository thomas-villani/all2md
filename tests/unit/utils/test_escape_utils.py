#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_escape_utils.py
"""Unit tests for format-specific escape utilities."""

from __future__ import annotations

from all2md.utils.escape import (
    escape_asciidoc,
    escape_asciidoc_attribute,
    escape_html_entities,
    escape_inline_code,
    escape_markdown_context_aware,
    escape_mediawiki,
    escape_rst,
)


class TestEscapeAsciiDoc:
    """Test AsciiDoc escaping functions."""

    def test_escape_basic_text(self) -> None:
        """Test escaping basic text with special characters."""
        text = "Text with [brackets] and *stars*"
        result = escape_asciidoc(text)
        assert result == r"Text with \[brackets\] and \*stars\*"

    def test_escape_multiple_special_chars(self) -> None:
        """Test escaping multiple special characters."""
        text = "Special: [test], `code`, +plus+, #hash, |pipe|, :colon:"
        result = escape_asciidoc(text)
        assert r"\[test\]" in result
        assert r"\`code\`" in result
        assert r"\+plus\+" in result
        assert r"\#hash" in result
        assert r"\|pipe\|" in result
        assert r"\:colon\:" in result

    def test_escape_underscores(self) -> None:
        """Test escaping underscores for emphasis."""
        text = "word_with_underscores"
        result = escape_asciidoc(text)
        assert result == r"word\_with\_underscores"

    def test_escape_empty_string(self) -> None:
        """Test escaping empty string."""
        assert escape_asciidoc("") == ""

    def test_escape_no_special_chars(self) -> None:
        """Test text with no special characters."""
        text = "Plain text without special characters"
        result = escape_asciidoc(text)
        assert result == text


class TestEscapeAsciiDocAttribute:
    """Test AsciiDoc attribute escaping."""

    def test_escape_quotes(self) -> None:
        """Test escaping quotes in attribute values."""
        text = 'Title: A "Special" Document'
        result = escape_asciidoc_attribute(text)
        assert '\\"Special\\"' in result

    def test_escape_newlines(self) -> None:
        """Test escaping newlines in attributes."""
        text = "Line 1\nLine 2\rLine 3"
        result = escape_asciidoc_attribute(text)
        assert "\\n" in result
        assert "\\r" in result

    def test_escape_backslashes(self) -> None:
        """Test escaping backslashes in attributes."""
        text = "Path: C:\\Users\\test"
        result = escape_asciidoc_attribute(text)
        assert "\\\\" in result

    def test_escape_empty(self) -> None:
        """Test escaping empty attribute."""
        assert escape_asciidoc_attribute("") == ""


class TestEscapeRst:
    """Test reStructuredText escaping."""

    def test_escape_emphasis_chars(self) -> None:
        """Test escaping emphasis characters."""
        text = "Text with *emphasis* and _underline_"
        result = escape_rst(text)
        assert result == r"Text with \*emphasis\* and \_underline\_"

    def test_escape_code_backticks(self) -> None:
        """Test escaping backticks for code."""
        text = "Code: `inline code`"
        result = escape_rst(text)
        assert r"\`inline code\`" in result

    def test_escape_brackets(self) -> None:
        """Test escaping square brackets."""
        text = "Reference [1] and citation [Doe2024]"
        result = escape_rst(text)
        assert r"\[1\]" in result
        assert r"\[Doe2024\]" in result

    def test_escape_angle_brackets(self) -> None:
        """Test escaping angle brackets."""
        text = "URI: <http://example.com>"
        result = escape_rst(text)
        # Check that angle brackets and colon are escaped
        assert r"\<" in result
        assert r"\>" in result
        assert r"\:" in result

    def test_escape_pipes(self) -> None:
        """Test escaping pipe characters."""
        text = "Substitution: |version|"
        result = escape_rst(text)
        assert r"\|version\|" in result

    def test_escape_empty(self) -> None:
        """Test escaping empty string."""
        assert escape_rst("") == ""


class TestEscapeMarkdownContextAware:
    """Test context-aware markdown escaping."""

    def test_escape_text_context(self) -> None:
        """Test escaping in text context."""
        text = "Text with [brackets] and *stars*"
        result = escape_markdown_context_aware(text, "text")
        assert r"\[brackets\]" in result
        assert r"\*stars\*" in result

    def test_escape_table_context(self) -> None:
        """Test escaping in table context."""
        text = "Cell | with | pipes"
        result = escape_markdown_context_aware(text, "table")
        assert result == r"Cell \| with \| pipes"

    def test_escape_link_context(self) -> None:
        """Test escaping in link text context."""
        text = "Link text [with brackets]"
        result = escape_markdown_context_aware(text, "link")
        assert r"\[with brackets\]" in result

    def test_escape_image_alt_context(self) -> None:
        """Test escaping in image alt text context."""
        text = "Alt [with] brackets"
        result = escape_markdown_context_aware(text, "image_alt")
        assert r"\[with\]" in result

    def test_escape_empty(self) -> None:
        """Test escaping empty string."""
        assert escape_markdown_context_aware("", "text") == ""


class TestEscapeInlineCode:
    """Test inline code escaping and delimiter selection."""

    def test_simple_code(self) -> None:
        """Test simple code without backticks."""
        code = "simple code"
        escaped, delimiter = escape_inline_code(code, "`")
        assert escaped == "simple code"
        assert delimiter == "`"

    def test_code_with_single_backtick(self) -> None:
        """Test code containing a single backtick."""
        code = "code with ` backtick"
        escaped, delimiter = escape_inline_code(code, "`")
        # Backtick in middle doesn't need spaces, just longer delimiter
        assert escaped == "code with ` backtick"
        assert delimiter == "``"

    def test_code_with_double_backticks(self) -> None:
        """Test code containing double backticks."""
        code = "code with `` double"
        escaped, delimiter = escape_inline_code(code, "`")
        # Backticks in middle don't need spaces, just longer delimiter
        assert escaped == "code with `` double"
        assert delimiter == "```"

    def test_code_starting_with_backtick(self) -> None:
        """Test code starting with backtick."""
        code = "`start"
        escaped, delimiter = escape_inline_code(code, "`")
        assert escaped == " `start "
        assert delimiter == "``"

    def test_code_ending_with_backtick(self) -> None:
        """Test code ending with backtick."""
        code = "end`"
        escaped, delimiter = escape_inline_code(code, "`")
        assert escaped == " end` "
        assert delimiter == "``"

    def test_empty_code(self) -> None:
        """Test empty code string."""
        code = ""
        escaped, delimiter = escape_inline_code(code, "`")
        assert escaped == ""
        assert delimiter == "`"


class TestEscapeMediaWiki:
    """Test MediaWiki escaping."""

    def test_escape_basic_text(self) -> None:
        """Test escaping basic text."""
        text = "Normal text"
        result = escape_mediawiki(text)
        # MediaWiki is lenient, should return as-is
        assert result == text

    def test_escape_apostrophes(self) -> None:
        """Test handling apostrophes (MediaWiki formatting)."""
        # MediaWiki uses '' for italic and ''' for bold
        # Our simple implementation just returns the text as-is
        text = "Text with ''quotes''"
        result = escape_mediawiki(text)
        # Current implementation is lenient
        assert isinstance(result, str)

    def test_escape_empty(self) -> None:
        """Test escaping empty string."""
        assert escape_mediawiki("") == ""


class TestEscapeHtmlEntities:
    """Test HTML entity escaping."""

    def test_escape_basic_entities(self) -> None:
        """Test escaping basic HTML special characters."""
        text = "<div>Test & 'quote' \"test\"</div>"
        result = escape_html_entities(text)
        assert result == "&lt;div&gt;Test &amp; &#x27;quote&#x27; &quot;test&quot;&lt;/div&gt;"

    def test_escape_script_tag(self) -> None:
        """Test escaping script tags."""
        text = "<script>alert('XSS')</script>"
        result = escape_html_entities(text)
        assert result == "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

    def test_escape_ampersand_first(self) -> None:
        """Test that ampersands are escaped without double-escaping."""
        text = "A & B"
        result = escape_html_entities(text)
        assert result == "A &amp; B"

    def test_escape_empty(self) -> None:
        """Test escaping empty string."""
        assert escape_html_entities("") == ""

    def test_escape_no_special_chars(self) -> None:
        """Test text without special characters."""
        text = "Plain text"
        result = escape_html_entities(text)
        assert result == text


class TestIntegration:
    """Integration tests for escape utilities."""

    def test_asciidoc_roundtrip(self) -> None:
        """Test that escaping doesn't break normal text."""
        text = "Normal text with some words"
        escaped = escape_asciidoc(text)
        assert "Normal" in escaped
        assert "text" in escaped

    def test_rst_roundtrip(self) -> None:
        """Test that escaping doesn't break normal text."""
        text = "Normal text with some words"
        escaped = escape_rst(text)
        assert "Normal" in escaped
        assert "text" in escaped

    def test_multiple_escaping_contexts(self) -> None:
        """Test escaping the same text in different contexts."""
        text = "Text | with [special] chars"

        # Different contexts should escape differently
        table_escaped = escape_markdown_context_aware(text, "table")
        link_escaped = escape_markdown_context_aware(text, "link")

        # Table should escape pipes
        assert r"\|" in table_escaped

        # Link should escape brackets
        assert r"\[" in link_escaped or r"\]" in link_escaped
