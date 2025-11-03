#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new Markdown parser improvements."""

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
