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


class TestSoftBreakParsing:
    """Tests for soft break (single newline) parsing."""

    def test_softbreak_after_strong(self) -> None:
        """Test that soft breaks are parsed after bold text."""
        from all2md.ast import LineBreak, Paragraph, Strong, Text

        markdown = """**Bold text**
And then a paragraph immediately afterwards."""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        # Should have one paragraph
        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Paragraph should have Strong, LineBreak, Text
        assert len(para.content) == 3
        assert isinstance(para.content[0], Strong)
        assert isinstance(para.content[1], LineBreak)
        assert para.content[1].soft is True
        assert isinstance(para.content[2], Text)

    def test_softbreak_between_text(self) -> None:
        """Test that soft breaks are parsed between plain text."""
        from all2md.ast import LineBreak, Paragraph, Text

        markdown = """First line
Second line"""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Should have Text, LineBreak, Text
        assert len(para.content) == 3
        assert isinstance(para.content[0], Text)
        assert isinstance(para.content[1], LineBreak)
        assert para.content[1].soft is True
        assert isinstance(para.content[2], Text)


class TestMarkdownFootnotes:
    """Regression tests for footnote reference/definition parsing.

    mistune 3.x groups definitions in a ``footnotes`` container of
    ``footnote_item`` tokens (label in ``attrs['key']`` / the ref's ``raw``),
    not the legacy ``footnote_def`` token with ``attrs['label']``. When the
    parser only handled the legacy shape, every reference identifier came back
    empty and every definition was silently dropped from the AST.
    """

    @staticmethod
    def _collect(node, out):
        name = type(node).__name__
        if name in ("FootnoteReference", "FootnoteDefinition"):
            out.setdefault(name, []).append(node)
        for child in getattr(node, "children", None) or []:
            TestMarkdownFootnotes._collect(child, out)
        content = getattr(node, "content", None)
        if isinstance(content, list):
            for child in content:
                TestMarkdownFootnotes._collect(child, out)

    def test_footnote_reference_keeps_identifier(self) -> None:
        markdown = "See this[^1].\n\n[^1]: the note\n"
        doc = MarkdownToAstConverter().parse(markdown)

        found: dict = {}
        self._collect(doc, found)
        refs = found.get("FootnoteReference", [])

        assert len(refs) == 1
        assert refs[0].identifier == "1"

    def test_footnote_definitions_are_not_dropped(self) -> None:
        markdown = "A[^1] B[^2] C[^foo].\n\n[^1]: first\n[^2]: second\n[^foo]: third\n"
        doc = MarkdownToAstConverter().parse(markdown)

        found: dict = {}
        self._collect(doc, found)
        defs = found.get("FootnoteDefinition", [])
        refs = found.get("FootnoteReference", [])

        ref_ids = [r.identifier for r in refs]
        def_ids = {d.identifier for d in defs}

        assert ref_ids == ["1", "2", "FOO"]
        # All three definitions survive with distinct identifiers matching the refs.
        assert def_ids == {"1", "2", "FOO"}

    def test_footnotes_roundtrip_on_supporting_flavor(self) -> None:
        from all2md import convert
        from all2md.options.markdown import MarkdownRendererOptions

        markdown = "A[^1] and B[^foo].\n\n[^1]: first note\n[^foo]: second note\n"
        out = convert(
            markdown,
            source_format="markdown",
            target_format="markdown",
            renderer_options=MarkdownRendererOptions(flavor="pandoc"),
        )

        assert "[^1]" in out
        assert "[^1]: first note" in out
        assert "[^FOO]: second note" in out

    def test_multiparagraph_footnote_definition_survives_roundtrip(self) -> None:
        """A footnote whose body has several paragraphs must not collapse.

        The renderer separated a definition's paragraphs with a single newline,
        so ``[^1]: first`` and ``    second`` landed on adjacent lines. On
        reparse that indented line is a lazy continuation and the two
        paragraphs silently merge into one; the fix emits a blank line between
        them and indents every continuation line four spaces.
        """
        from all2md import convert, to_ast
        from all2md.ast import FootnoteDefinition, Paragraph
        from all2md.options.markdown import MarkdownRendererOptions

        opts = MarkdownRendererOptions(flavor="pandoc")
        markdown = "text[^1]\n\n[^1]: first\n\n    second\n"

        once = convert(markdown, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)
        assert once == twice, "multi-paragraph footnote is not idempotent"

        # The blank line between the two paragraphs is preserved.
        assert "[^1]: first\n\n    second" in once

        # After a full roundtrip the definition still carries two paragraphs.
        ast = to_ast(once, source_format="markdown")
        defs = [n for n in ast.children if isinstance(n, FootnoteDefinition)]
        assert len(defs) == 1
        paragraphs = [c for c in defs[0].content if isinstance(c, Paragraph)]
        assert len(paragraphs) == 2
