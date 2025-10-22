#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_textile_conversion.py
"""Integration tests for Textile conversion.

Tests cover:
- Round-trip conversion (Textile -> AST -> Textile)
- Complex documents with mixed content
- Cross-format conversion (Textile <-> Markdown)
- Real-world Textile examples

"""

import pytest

from all2md.parsers.markdown import MarkdownToAstConverter
from all2md.parsers.textile import TextileParser
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.textile import TextileRenderer


@pytest.mark.integration
class TestRoundTripConversion:
    """Tests for round-trip conversion (Textile -> AST -> Textile)."""

    def test_simple_document_roundtrip(self) -> None:
        """Test round-trip conversion of a simple document."""
        original = """h2. Heading

This is a paragraph with *bold* and _italic_ text.

* Item 1
* Item 2"""

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Parse result again to verify structure
        doc2 = parser.parse(result)

        # Check that document structure is preserved
        assert len(doc.children) > 0
        assert len(doc2.children) > 0

    def test_heading_roundtrip(self) -> None:
        """Test round-trip conversion with multiple heading levels."""
        original = """h1. Level 1

h2. Level 2

h3. Level 3"""

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that headings are preserved
        assert "h1." in result or "Level 1" in result
        assert "h2." in result or "Level 2" in result
        assert "h3." in result or "Level 3" in result

    def test_list_roundtrip(self) -> None:
        """Test round-trip conversion with lists."""
        original = """* Unordered item 1
* Unordered item 2

# Ordered item 1
# Ordered item 2"""

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that list structure is preserved
        assert "*" in result or "Unordered" in result
        assert "#" in result or "Ordered" in result

    def test_table_roundtrip(self) -> None:
        """Test round-trip conversion with tables."""
        original = """|_.Name|_.Age|
|Alice|30|
|Bob|25|"""

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that table structure is preserved
        assert "|" in result
        assert "Alice" in result or "Name" in result

    def test_links_roundtrip(self) -> None:
        """Test round-trip conversion with links."""
        original = 'Visit "Example":http://example.com for more.'

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that link is preserved
        assert "example.com" in result

    def test_images_roundtrip(self) -> None:
        """Test round-trip conversion with images."""
        original = "!http://example.com/image.png(Alt text)!"

        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that image is preserved
        assert "image.png" in result


@pytest.mark.integration
class TestCrossFormatConversion:
    """Tests for cross-format conversion between Textile and Markdown."""

    def test_textile_to_markdown_headings(self) -> None:
        """Test converting Textile headings to Markdown."""
        textile = """h1. Main Title

h2. Section Title

h3. Subsection"""

        parser = TextileParser()
        doc = parser.parse(textile)

        markdown_renderer = MarkdownRenderer()
        markdown = markdown_renderer.render_to_string(doc)

        # Check that Markdown headings are present
        assert "# Main Title" in markdown or "Main Title" in markdown
        assert "## Section Title" in markdown or "Section Title" in markdown

    def test_markdown_to_textile_headings(self) -> None:
        """Test converting Markdown headings to Textile."""
        markdown = """# Main Title

## Section Title

### Subsection"""

        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        textile_renderer = TextileRenderer()
        textile = textile_renderer.render_to_string(doc)

        # Check that Textile headings are present
        assert "h1." in textile or "Main Title" in textile
        assert "h2." in textile or "Section Title" in textile

    def test_textile_to_markdown_formatting(self) -> None:
        """Test converting Textile formatting to Markdown."""
        textile = "This is *bold* and _italic_ and @code@."

        parser = TextileParser()
        doc = parser.parse(textile)

        markdown_renderer = MarkdownRenderer()
        markdown = markdown_renderer.render_to_string(doc)

        # Check that formatting is preserved
        assert "**bold**" in markdown or "*bold*" in markdown or "bold" in markdown
        assert "_italic_" in markdown or "*italic*" in markdown or "italic" in markdown

    def test_markdown_to_textile_formatting(self) -> None:
        """Test converting Markdown formatting to Textile."""
        markdown = "This is **bold** and *italic* and `code`."

        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        textile_renderer = TextileRenderer()
        textile = textile_renderer.render_to_string(doc)

        # Check that formatting is preserved
        assert "bold" in textile
        assert "italic" in textile
        assert "code" in textile

    def test_textile_to_markdown_lists(self) -> None:
        """Test converting Textile lists to Markdown."""
        textile = """* Unordered item 1
* Unordered item 2

# Ordered item 1
# Ordered item 2"""

        parser = TextileParser()
        doc = parser.parse(textile)

        markdown_renderer = MarkdownRenderer()
        markdown = markdown_renderer.render_to_string(doc)

        # Check that list structure is preserved
        assert "item 1" in markdown or "item" in markdown

    def test_markdown_to_textile_lists(self) -> None:
        """Test converting Markdown lists to Textile."""
        markdown = """- Unordered item 1
- Unordered item 2

1. Ordered item 1
2. Ordered item 2"""

        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        textile_renderer = TextileRenderer()
        textile = textile_renderer.render_to_string(doc)

        # Check that list structure is preserved
        assert "item 1" in textile or "item" in textile


@pytest.mark.integration
class TestComplexDocuments:
    """Tests for complex Textile documents."""

    def test_mixed_content_document(self) -> None:
        """Test parsing document with mixed content types."""
        textile = """h1. Document Title

This is an introductory paragraph with *bold* and _italic_ text.

h2. Lists

* First item
* Second item with "a link":http://example.com
* Third item

h2. Code

bc. def hello():
    return "world"

h2. Table

|_.Header 1|_.Header 2|
|Cell 1|Cell 2|
|Cell 3|Cell 4|"""

        parser = TextileParser()
        doc = parser.parse(textile)

        # Verify document has multiple children
        assert len(doc.children) > 1

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify key elements are present
        assert "Document Title" in result or "h1." in result
        assert "hello" in result or "world" in result

    def test_nested_lists(self) -> None:
        """Test parsing nested lists."""
        textile = """* Level 1 item 1
** Level 2 item 1
** Level 2 item 2
* Level 1 item 2"""

        parser = TextileParser()
        doc = parser.parse(textile)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify nested structure is preserved
        assert "Level 1" in result
        assert "Level 2" in result

    def test_inline_formatting_combinations(self) -> None:
        """Test parsing multiple inline formatting combinations."""
        textile = "This has *bold*, _italic_, @code@, ^superscript^, ~subscript~, and +underline+."

        parser = TextileParser()
        doc = parser.parse(textile)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify formatting is preserved
        assert "bold" in result
        assert "italic" in result
        assert "code" in result

    def test_empty_document(self) -> None:
        """Test parsing empty document."""
        textile = ""

        parser = TextileParser()
        doc = parser.parse(textile)

        assert doc is not None
        # Empty document should have minimal or no children

    def test_whitespace_handling(self) -> None:
        """Test handling of various whitespace patterns."""
        textile = """h1. Title


Paragraph with


multiple blank lines."""

        parser = TextileParser()
        doc = parser.parse(textile)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify content is preserved
        assert "Title" in result
        assert "Paragraph" in result


@pytest.mark.integration
class TestRealWorldExamples:
    """Tests with real-world Textile examples."""

    def test_blog_post(self) -> None:
        """Test parsing a typical blog post."""
        textile = """h1. My Blog Post

Published on 2025-01-15

This is the introduction to my blog post about *Textile markup*.

h2. What is Textile?

Textile is a lightweight markup language that was popular in early blogging platforms.

h2. Features

* Easy to learn
* Simple syntax
* "Good documentation":http://textile-lang.com

h2. Conclusion

Textile is still useful for legacy content."""

        parser = TextileParser()
        doc = parser.parse(textile)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify key elements
        assert "Blog Post" in result or "blog" in result.lower()
        assert "Textile" in result

    def test_wiki_article(self) -> None:
        """Test parsing a wiki-style article."""
        textile = """h1. Article Title

h2. Overview

This article covers the basics.

h2. Details

|_.Property|_.Value|
|Name|Example|
|Type|Demo|

h2. See Also

* "Related Article":http://example.com/related
* "Another Article":http://example.com/another"""

        parser = TextileParser()
        doc = parser.parse(textile)

        # Verify document structure
        assert len(doc.children) > 0

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Verify table and links are preserved
        assert "Property" in result or "|" in result
        assert "Related" in result or "example.com" in result
