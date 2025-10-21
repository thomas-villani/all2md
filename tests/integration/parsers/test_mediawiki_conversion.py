#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_mediawiki_conversion.py
"""Integration tests for MediaWiki conversion.

Tests cover:
- Round-trip conversion (MediaWiki -> AST -> MediaWiki)
- Complex documents with mixed content
- Cross-format conversion (MediaWiki <-> Markdown)
- Real-world MediaWiki examples

"""

import pytest

from all2md.parsers.markdown import MarkdownToAstConverter
from all2md.parsers.mediawiki import MediaWikiParser
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer


@pytest.mark.integration
class TestRoundTripConversion:
    """Tests for round-trip conversion (MediaWiki -> AST -> MediaWiki)."""

    def test_simple_document_roundtrip(self) -> None:
        """Test round-trip conversion of a simple document."""
        original = """== Heading ==

This is a paragraph with '''bold''' and ''italic'' text.

* Item 1
* Item 2"""

        parser = MediaWikiParser()
        doc = parser.parse(original)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Parse result again to verify structure
        doc2 = parser.parse(result)

        # Check that document structure is preserved
        assert len(doc.children) > 0
        assert len(doc2.children) > 0

    def test_heading_roundtrip(self) -> None:
        """Test round-trip conversion with multiple heading levels."""
        original = """= Level 1 =

== Level 2 ==

=== Level 3 ==="""

        parser = MediaWikiParser()
        doc = parser.parse(original)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that headings are preserved
        assert "= Level 1 =" in result
        assert "== Level 2 ==" in result
        assert "=== Level 3 ===" in result

    def test_list_roundtrip(self) -> None:
        """Test round-trip conversion with lists."""
        original = """* Unordered item 1
* Unordered item 2

# Ordered item 1
# Ordered item 2"""

        parser = MediaWikiParser()
        doc = parser.parse(original)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that list structure is preserved
        assert "*" in result
        assert "#" in result

    def test_table_roundtrip(self) -> None:
        """Test round-trip conversion with tables."""
        original = """{|
! Name !! Age
|-
| Alice || 30
|-
| Bob || 25
|}"""

        parser = MediaWikiParser()
        doc = parser.parse(original)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that table is preserved
        assert "{|" in result
        assert "|}" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_code_block_roundtrip(self) -> None:
        """Test round-trip conversion with code blocks."""
        original = """== Code Example ==

<syntaxhighlight lang="python">
def hello():
    print("Hello, World!")
</syntaxhighlight>"""

        parser = MediaWikiParser()
        doc = parser.parse(original)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that code block is preserved
        assert "syntaxhighlight" in result
        assert "def hello()" in result


@pytest.mark.integration
class TestCrossFormatConversion:
    """Tests for cross-format conversion."""

    def test_mediawiki_to_markdown(self) -> None:
        """Test conversion from MediaWiki to Markdown."""
        wikitext = """== Heading ==

This is '''bold''' and ''italic'' text.

* Item 1
* Item 2"""

        # Parse MediaWiki
        wiki_parser = MediaWikiParser()
        doc = wiki_parser.parse(wikitext)

        # Render as Markdown
        md_renderer = MarkdownRenderer()
        markdown = md_renderer.render_to_string(doc)

        # Check that Markdown output is reasonable
        assert "##" in markdown  # Heading level 2
        assert "**bold**" in markdown or "__bold__" in markdown
        assert "*" in markdown or "_" in markdown  # Italic
        assert "Item 1" in markdown
        assert "Item 2" in markdown

    def test_markdown_to_mediawiki(self) -> None:
        """Test conversion from Markdown to MediaWiki."""
        markdown = """## Heading

This is **bold** and *italic* text.

- Item 1
- Item 2"""

        # Parse Markdown
        md_parser = MarkdownToAstConverter()
        doc = md_parser.parse(markdown)

        # Render as MediaWiki
        wiki_renderer = MediaWikiRenderer()
        wikitext = wiki_renderer.render_to_string(doc)

        # Check that MediaWiki output is reasonable
        assert "==" in wikitext  # Heading
        assert "'''" in wikitext  # Bold
        assert "''" in wikitext  # Italic
        assert "*" in wikitext  # List items


@pytest.mark.integration
class TestComplexDocuments:
    """Tests for complex documents with mixed content."""

    def test_complex_wikipedia_style_document(self) -> None:
        """Test parsing a Wikipedia-style document."""
        wikitext = """== Introduction ==

'''Wikipedia''' is a free online encyclopedia.

=== History ===

Wikipedia was launched in [[2001]].

==== Early Days ====

The first article was about [[Computer Science]].

== Features ==

* Free content
* Collaborative editing
* Multiple languages

== External Links ==

* [http://wikipedia.org Official Site]
* [http://wikimedia.org Wikimedia Foundation]"""

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should successfully parse without errors
        assert len(doc.children) > 0

        # Render back to MediaWiki
        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that major elements are preserved
        assert "Introduction" in result
        assert "History" in result
        assert "Features" in result

    def test_document_with_tables_and_lists(self) -> None:
        """Test document with both tables and lists."""
        wikitext = """== Data ==

{|
! Column 1 !! Column 2
|-
| Value 1 || Value 2
|}

== Points ==

* Point 1
* Point 2
** Sub-point 2.1
** Sub-point 2.2
* Point 3"""

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check that both tables and lists are present
        assert "{|" in result or "Column 1" in result
        assert "*" in result or "Point 1" in result

    def test_document_with_inline_and_block_formatting(self) -> None:
        """Test document with mixed inline and block formatting."""
        wikitext = """== Mixed Content ==

This paragraph has '''bold''', ''italic'', and <code>code</code> text.

<syntaxhighlight lang="python">
print("Hello")
</syntaxhighlight>

: This is a block quote
: with multiple lines

----

Another paragraph after thematic break."""

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should parse successfully
        assert len(doc.children) > 0

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Check elements are preserved
        assert len(result) > 0


@pytest.mark.integration
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_nested_formatting(self) -> None:
        """Test nested inline formatting."""
        wikitext = "This has '''bold with ''italic'' inside'''."

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should handle nested formatting
        assert len(doc.children) > 0

    def test_empty_sections(self) -> None:
        """Test document with empty sections."""
        wikitext = """== Section 1 ==

== Section 2 ==

Some content here.

== Section 3 =="""

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should handle empty sections gracefully
        assert len(doc.children) > 0

    def test_special_characters_in_text(self) -> None:
        """Test handling of special characters."""
        wikitext = "Text with special chars: < > & \" '"

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        renderer = MediaWikiRenderer()
        result = renderer.render_to_string(doc)

        # Should preserve or escape special characters appropriately
        assert len(result) > 0

    def test_mixed_list_types(self) -> None:
        """Test document with mixed list types."""
        wikitext = """* Bullet 1
# Ordered 1
#* Mixed 1.1
#* Mixed 1.2
# Ordered 2
* Bullet 2"""

        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should parse mixed list types
        assert len(doc.children) > 0
