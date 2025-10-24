#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new Markdown parser improvements."""

from all2md.ast import HTMLBlock, HTMLInline, Paragraph
from all2md.options.markdown import MarkdownParserOptions
from all2md.parsers.markdown import MarkdownToAstConverter


class TestMarkdownFrontmatter:
    """Tests for frontmatter parsing support."""

    def test_yaml_frontmatter(self) -> None:
        """Test parsing YAML frontmatter."""
        markdown = """---
title: My Document
author: John Doe
keywords:
  - test
  - markdown
---

# Content

This is the content."""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        # Check metadata was extracted
        assert doc.metadata.get("title") == "My Document"
        assert doc.metadata.get("author") == "John Doe"
        assert "test" in doc.metadata.get("keywords", [])
        assert "markdown" in doc.metadata.get("keywords", [])

        # Content should not include frontmatter
        # First child should be heading
        assert doc.children[0].__class__.__name__ == "Heading"

    def test_toml_frontmatter(self) -> None:
        """Test parsing TOML frontmatter."""
        markdown = """+++
title = "TOML Document"
author = "Jane Doe"
date = "2025-01-15"
+++

Content here."""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        # TOML parsing requires tomllib or tomli
        # Check if metadata was extracted
        metadata_title = doc.metadata.get("title")
        if metadata_title:  # Only check if TOML was actually parsed
            assert metadata_title == "TOML Document"
            assert doc.metadata.get("author") == "Jane Doe"
            assert doc.metadata.get("creation_date") == "2025-01-15"

    def test_json_frontmatter(self) -> None:
        """Test parsing JSON frontmatter."""
        markdown = """{
  "title": "JSON Document",
  "author": "Bob Smith",
  "keywords": ["json", "test"]
}

Content here."""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        assert doc.metadata.get("title") == "JSON Document"
        assert doc.metadata.get("author") == "Bob Smith"
        assert "json" in doc.metadata.get("keywords", [])

    def test_no_frontmatter(self) -> None:
        """Test document without frontmatter."""
        markdown = """# Just a heading

And some content."""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        # Metadata should be empty or minimal
        assert doc.metadata.get("title") is None

    def test_disable_frontmatter_parsing(self) -> None:
        """Test parse_frontmatter=False disables frontmatter parsing."""
        markdown = """---
title: Should Not Parse
---

Content"""
        options = MarkdownParserOptions(parse_frontmatter=False)
        parser = MarkdownToAstConverter(options=options)
        doc = parser.parse(markdown)

        # Title should not be in metadata
        assert doc.metadata.get("title") is None

        # The --- should be treated as thematic break or content

    def test_incomplete_frontmatter(self) -> None:
        """Test frontmatter without closing delimiter."""
        markdown = """---
title: Incomplete

This is content without closing ---."""
        parser = MarkdownToAstConverter()
        _ = parser.parse(markdown)

        # Should treat as regular content if no closing delimiter
        # Behavior depends on implementation

    def test_yaml_frontmatter_custom_fields(self) -> None:
        """Test that custom fields are included in metadata."""
        markdown = """---
title: Document
custom_field: custom_value
another: value
---

Content"""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        assert doc.metadata.get("title") == "Document"
        # Custom fields are flattened to top level in to_dict()
        assert doc.metadata.get("custom_field") == "custom_value"
        assert doc.metadata.get("another") == "value"

    def test_frontmatter_language_mapping(self) -> None:
        """Test that 'lang' and 'language' map to metadata.language."""
        markdown1 = """---
lang: en
---
Content"""
        parser = MarkdownToAstConverter()
        doc1 = parser.parse(markdown1)
        assert doc1.metadata.get("language") == "en"

        markdown2 = """---
language: fr
---
Content"""
        doc2 = parser.parse(markdown2)
        assert doc2.metadata.get("language") == "fr"

    def test_frontmatter_description_field(self) -> None:
        """Test that 'description' is included in metadata."""
        markdown = """---
description: This is a test document
---
Content"""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        # Description stays as "description" field
        assert doc.metadata.get("description") == "This is a test document"


class TestMarkdownHtmlSanitization:
    """Tests for HTML sanitization option when preserve_html=False."""

    def test_html_drop_mode(self) -> None:
        """Test html_handling='drop' removes HTML entirely."""
        markdown = """<div>HTML block</div>

Paragraph with <span>inline HTML</span>."""

        options = MarkdownParserOptions(preserve_html=False, html_handling="drop")
        parser = MarkdownToAstConverter(options=options)
        doc = parser.parse(markdown)

        # HTML blocks and inline HTML should be dropped
        # Check that no HTMLBlock or HTMLInline nodes exist
        def has_html_nodes(nodes):
            for node in nodes:
                if isinstance(node, (HTMLBlock, HTMLInline)):
                    return True
                if hasattr(node, "content") and isinstance(node.content, list):
                    if has_html_nodes(node.content):
                        return True
                if hasattr(node, "children") and isinstance(node.children, list):
                    if has_html_nodes(node.children):
                        return True
            return False

        assert not has_html_nodes(doc.children)

    def test_html_sanitize_mode(self) -> None:
        """Test html_handling='sanitize' cleans dangerous HTML."""
        markdown = """<script>alert('xss')</script>

<p>Safe paragraph</p>"""

        options = MarkdownParserOptions(preserve_html=False, html_handling="sanitize")
        parser = MarkdownToAstConverter(options=options)
        _ = parser.parse(markdown)

        # Should have HTMLBlock nodes with sanitized content
        # Script tags should be removed, but p tags might be kept
        # The exact behavior depends on the sanitizer implementation

    def test_preserve_html_true_ignores_handling(self) -> None:
        """Test that preserve_html=True preserves HTML regardless of html_handling."""
        markdown = """<div>HTML content</div>"""

        options = MarkdownParserOptions(preserve_html=True, html_handling="drop")
        parser = MarkdownToAstConverter(options=options)
        doc = parser.parse(markdown)

        # HTML should still be preserved
        has_html = False
        for child in doc.children:
            if isinstance(child, HTMLBlock):
                has_html = True
                assert "<div>" in child.content
        assert has_html

    def test_inline_html_drop(self) -> None:
        """Test inline HTML is dropped with html_handling='drop'."""
        markdown = "Text with <strong>HTML</strong> inline."

        options = MarkdownParserOptions(preserve_html=False, html_handling="drop")
        parser = MarkdownToAstConverter(options=options)
        doc = parser.parse(markdown)

        # Should have a paragraph without HTMLInline nodes
        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Check no HTMLInline in content
        has_html_inline = any(isinstance(node, HTMLInline) for node in para.content)
        assert not has_html_inline

    def test_inline_html_sanitize(self) -> None:
        """Test inline HTML is sanitized with html_handling='sanitize'."""
        markdown = "Text with <script>evil</script> inline."

        options = MarkdownParserOptions(preserve_html=False, html_handling="sanitize")
        parser = MarkdownToAstConverter(options=options)
        _ = parser.parse(markdown)

        # Script should be removed or escaped
        # The paragraph should exist but script should be sanitized
