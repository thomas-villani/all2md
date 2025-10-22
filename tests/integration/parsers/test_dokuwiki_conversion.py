#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_dokuwiki_conversion.py
"""Integration tests for DokuWiki conversion.

Tests cover:
- Round-trip conversion (DokuWiki -> AST -> DokuWiki)
- Complex documents with mixed content
- Cross-format conversion (DokuWiki <-> Markdown)
- Real-world DokuWiki examples

"""

import pytest

from all2md.parsers.dokuwiki import DokuWikiParser
from all2md.parsers.markdown import MarkdownToAstConverter
from all2md.renderers.dokuwiki import DokuWikiRenderer
from all2md.renderers.markdown import MarkdownRenderer


@pytest.mark.integration
class TestRoundTripConversion:
    """Tests for round-trip conversion (DokuWiki -> AST -> DokuWiki)."""

    def test_simple_document_roundtrip(self) -> None:
        """Test round-trip conversion of a simple document."""
        original = """====== Heading ======

This is a paragraph with **bold** and //italic// text.

* Item 1
* Item 2"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Parse result again to verify structure
        doc2 = parser.parse(result)

        # Check that document structure is preserved
        assert len(doc.children) > 0
        assert len(doc2.children) > 0
        # Should have same number of top-level elements
        assert len(doc.children) == len(doc2.children)

    def test_heading_roundtrip(self) -> None:
        """Test round-trip conversion with multiple heading levels."""
        original = """====== Level 1 ======

===== Level 2 =====

==== Level 3 ====

=== Level 4 ===

== Level 5 =="""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that headings are preserved
        assert "====== Level 1 ======" in result
        assert "===== Level 2 =====" in result
        assert "==== Level 3 ====" in result
        assert "=== Level 4 ===" in result
        assert "== Level 5 ==" in result

    def test_list_roundtrip(self) -> None:
        """Test round-trip conversion with lists."""
        original = """* Unordered item 1
* Unordered item 2

- Ordered item 1
- Ordered item 2"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that list structure is preserved
        assert "*" in result  # Unordered
        assert "-" in result  # Ordered

    def test_nested_list_roundtrip(self) -> None:
        """Test round-trip conversion with nested lists."""
        original = """* Item 1
  * Nested item 1
  * Nested item 2
* Item 2"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check for nested structure
        assert "* Item 1" in result
        assert "  * Nested" in result
        assert "* Item 2" in result

    def test_table_roundtrip(self) -> None:
        """Test round-trip conversion with tables."""
        original = """^ Name ^ Age ^
| Alice | 30 |
| Bob | 25 |"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that table is preserved
        assert "^" in result  # Header delimiter
        assert "|" in result  # Cell delimiter
        assert "Alice" in result
        assert "Bob" in result

    def test_code_block_roundtrip(self) -> None:
        """Test round-trip conversion with code blocks."""
        original = """====== Code Example ======

<code python>
def hello():
    print("Hello, World!")
</code>"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that code block is preserved
        assert "<code python>" in result
        assert "def hello()" in result
        assert "</code>" in result

    def test_inline_formatting_roundtrip(self) -> None:
        """Test round-trip conversion with inline formatting."""
        original = """Text with **bold**, //italic//, __underline__, ''monospace'', <del>strikethrough</del>, H<sub>2</sub>O, E=mc<sup>2</sup>."""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that all formatting is preserved
        assert "**bold**" in result
        assert "//italic//" in result
        assert "__underline__" in result
        assert "''monospace''" in result
        assert "<del>strikethrough</del>" in result
        assert "<sub>2</sub>" in result
        assert "<sup>2</sup>" in result

    def test_link_roundtrip(self) -> None:
        """Test round-trip conversion with links."""
        original = """Links: [[page:name]], [[page:name|Custom Text]], [[http://example.com|External]]"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that links are preserved
        assert "[[page:name]]" in result
        assert "[[page:name|Custom Text]]" in result
        assert "[[http://example.com|External]]" in result

    def test_image_roundtrip(self) -> None:
        """Test round-trip conversion with images."""
        original = """Images: {{image.png}}, {{photo.jpg|Photo caption}}"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that images are preserved
        assert "{{image.png}}" in result
        assert "{{photo.jpg|Photo caption}}" in result

    def test_blockquote_roundtrip(self) -> None:
        """Test round-trip conversion with blockquotes."""
        original = """> This is a quote
> Spanning multiple lines"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that blockquote is preserved
        assert "> " in result

    def test_horizontal_rule_roundtrip(self) -> None:
        """Test round-trip conversion with horizontal rules."""
        original = """Text before

----

Text after"""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that horizontal rule is preserved
        assert "----" in result

    def test_complex_document_roundtrip(self) -> None:
        """Test round-trip conversion with complex mixed content."""
        original = """====== Main Document ======

===== Introduction =====

This is an introduction with **bold** and //italic// text, plus a [[link]].

===== Lists =====

* First item
* Second item
  * Nested item
* Third item

===== Table =====

^ Column 1 ^ Column 2 ^
| Data 1   | Data 2   |
| Data 3   | Data 4   |

===== Code =====

<code python>
def example():
    return "Hello"
</code>

===== Blockquote =====

> This is a quoted section
> With multiple lines

----

End of document."""

        parser = DokuWikiParser()
        doc = parser.parse(original)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Parse again to verify structure
        doc2 = parser.parse(result)

        # Verify structure is maintained
        assert len(doc.children) > 5
        assert len(doc2.children) > 5


@pytest.mark.integration
class TestCrossFormatConversion:
    """Tests for cross-format conversion."""

    def test_dokuwiki_to_markdown(self) -> None:
        """Test conversion from DokuWiki to Markdown."""
        dokuwiki = """====== Heading ======

This is **bold** and //italic// text.

* Item 1
* Item 2"""

        # Parse DokuWiki
        wiki_parser = DokuWikiParser()
        doc = wiki_parser.parse(dokuwiki)

        # Render as Markdown
        md_renderer = MarkdownRenderer()
        markdown = md_renderer.render_to_string(doc)

        # Check that Markdown output is reasonable
        assert "#" in markdown  # Heading
        assert "**bold**" in markdown or "__bold__" in markdown
        assert "*" in markdown or "-" in markdown  # List markers

    def test_markdown_to_dokuwiki(self) -> None:
        """Test conversion from Markdown to DokuWiki."""
        markdown = """# Heading

This is **bold** and *italic* text.

* Item 1
* Item 2"""

        # Parse Markdown
        md_parser = MarkdownToAstConverter()
        doc = md_parser.parse(markdown)

        # Render as DokuWiki
        wiki_renderer = DokuWikiRenderer()
        dokuwiki = wiki_renderer.render_to_string(doc)

        # Check that DokuWiki output is reasonable
        assert "======" in dokuwiki  # Heading level 1
        assert "**bold**" in dokuwiki
        assert "//" in dokuwiki  # Italic
        assert "*" in dokuwiki  # List

    def test_dokuwiki_table_to_markdown(self) -> None:
        """Test table conversion from DokuWiki to Markdown."""
        dokuwiki = """^ Name ^ Age ^
| Alice | 30 |
| Bob | 25 |"""

        wiki_parser = DokuWikiParser()
        doc = wiki_parser.parse(dokuwiki)

        md_renderer = MarkdownRenderer()
        markdown = md_renderer.render_to_string(doc)

        # Markdown tables use pipes
        assert "|" in markdown
        assert "Alice" in markdown
        assert "Bob" in markdown

    def test_dokuwiki_code_to_markdown(self) -> None:
        """Test code block conversion from DokuWiki to Markdown."""
        dokuwiki = """<code python>
def hello():
    pass
</code>"""

        wiki_parser = DokuWikiParser()
        doc = wiki_parser.parse(dokuwiki)

        md_renderer = MarkdownRenderer()
        markdown = md_renderer.render_to_string(doc)

        # Markdown code blocks use backticks or indentation
        assert "```" in markdown or "    " in markdown
        assert "def hello()" in markdown


@pytest.mark.integration
class TestRealWorldExamples:
    """Tests with real-world DokuWiki examples."""

    def test_documentation_page(self) -> None:
        """Test parsing a typical documentation page."""
        dokuwiki = """====== Installation Guide ======

This guide will help you install the software.

===== Prerequisites =====

Before you begin, ensure you have:

* Python 3.8 or higher
* pip package manager
* Git (optional)

===== Installation Steps =====

- Download the package
- Extract to your directory
- Run the installer

===== Configuration =====

Edit the config file:

<code ini>
[settings]
debug = false
port = 8080
</code>

For more information, see [[docs:advanced|Advanced Configuration]].

===== Troubleshooting =====

> **Note:** If you encounter errors, check the log files first.

Common issues:

^ Error Code ^ Solution ^
| ERR001 | Restart the service |
| ERR002 | Check permissions |

----

For support, visit [[https://example.com/support|our support page]]."""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        # Verify document structure
        assert len(doc.children) > 10

        # Verify it can be rendered back
        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Key elements should be present
        assert "Installation Guide" in result
        assert "Prerequisites" in result
        assert "**" in result or "//" in result  # Some formatting
        assert "*" in result or "-" in result  # Lists
        assert "^" in result or "|" in result  # Table

    def test_wiki_article(self) -> None:
        """Test parsing a wiki-style article."""
        dokuwiki = """====== Topic Name ======

This is the introduction paragraph with [[links]] and **emphasis**.

===== Section 1 =====

Content with:
* Bullet points
* More items
  * Nested items

===== Section 2 =====

Some code example:

<code javascript>
function example() {
    return true;
}
</code>

===== See Also =====

* [[related:page1|Related Page 1]]
* [[related:page2|Related Page 2]]
* [[wp>Wikipedia Article|External Reference]]"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        # Should parse without errors
        assert len(doc.children) > 0

        # Render and verify
        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        assert "Topic Name" in result
        assert "Section 1" in result
        assert "code" in result.lower()


@pytest.mark.integration
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_elements(self) -> None:
        """Test handling of empty elements."""
        dokuwiki = """====== Title ======



* Item with empty lines

- Another list"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Should handle gracefully
        assert "Title" in result

    def test_special_characters_in_text(self) -> None:
        """Test handling of special characters."""
        dokuwiki = """Text with special chars: * / _ [ ] { } \\ < >"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Should preserve or escape appropriately
        assert len(result) > 0

    def test_mixed_list_types(self) -> None:
        """Test document with both ordered and unordered lists."""
        dokuwiki = """* Unordered 1
* Unordered 2

- Ordered 1
- Ordered 2

* Back to unordered"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        # Should create separate lists
        assert len(doc.children) >= 3

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        assert "*" in result
        assert "-" in result

    def test_table_with_formatted_cells(self) -> None:
        """Test table with formatting inside cells."""
        dokuwiki = """^ Header 1 ^ Header 2 ^
| **Bold cell** | //Italic cell// |
| Normal | [[link]] |"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # Formatting in cells should be preserved
        assert "^" in result
        assert "|" in result

    def test_consecutive_formatting(self) -> None:
        """Test consecutive inline formatting markers."""
        dokuwiki = """**bold1** and **bold2** plus //italic1// and //italic2//"""

        parser = DokuWikiParser()
        doc = parser.parse(dokuwiki)

        renderer = DokuWikiRenderer()
        result = renderer.render_to_string(doc)

        # All formatting should be preserved
        assert result.count("**") >= 4  # 2 pairs for 2 bold sections
        assert result.count("//") >= 4  # 2 pairs for 2 italic sections
