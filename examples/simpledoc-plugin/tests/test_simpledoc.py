# Copyright (c) 2025 All2md Contributors
"""Tests for SimpleDoc plugin.

This test suite demonstrates comprehensive testing of an all2md plugin,
including parser, renderer, options, and integration with the registry.
"""
import io

import pytest

from all2md.ast import CodeBlock, Document, Heading, List, ListItem, Paragraph, Text
from all2md.exceptions import ParsingError
from all2md.utils.metadata import DocumentMetadata
from all2md_simpledoc import CONVERTER_METADATA, SimpleDocOptions, SimpleDocParser, SimpleDocRenderer


class TestSimpleDocParser:
    """Test the SimpleDoc parser."""

    def test_parser_instantiation(self):
        """Test that parser can be instantiated."""
        parser = SimpleDocParser()
        assert parser is not None
        assert isinstance(parser.options, SimpleDocOptions)

    def test_parse_from_bytes(self):
        """Test parsing from bytes input."""
        parser = SimpleDocParser()
        content = b"@@ Test Heading\n\nTest paragraph."
        result = parser.parse(content)

        assert isinstance(result, Document)
        assert len(result.children) == 2
        assert isinstance(result.children[0], Heading)
        assert isinstance(result.children[1], Paragraph)

    def test_parse_from_string_path(self, tmp_path):
        """Test parsing from file path as string."""
        # Create test file
        test_file = tmp_path / "test.sdoc"
        test_file.write_text("@@ Heading\n\nParagraph text.")

        # Parse
        parser = SimpleDocParser()
        result = parser.parse(str(test_file))

        assert isinstance(result, Document)
        assert len(result.children) == 2

    def test_parse_from_path_object(self, tmp_path):
        """Test parsing from Path object."""
        # Create test file
        test_file = tmp_path / "test.sdoc"
        test_file.write_text("@@ Heading\n\nParagraph text.")

        # Parse
        parser = SimpleDocParser()
        result = parser.parse(test_file)

        assert isinstance(result, Document)
        assert len(result.children) == 2

    def test_parse_from_file_like_object(self):
        """Test parsing from file-like object."""
        content = b"@@ Test\n\nContent here."
        file_obj = io.BytesIO(content)

        parser = SimpleDocParser()
        result = parser.parse(file_obj)

        assert isinstance(result, Document)
        assert len(result.children) == 2

    def test_parse_frontmatter(self):
        """Test parsing frontmatter metadata."""
        content = """---
title: Test Document
author: John Doe
date: 2025-01-15
tags: test, example
---

@@ Introduction

Some content here.
"""
        parser = SimpleDocParser()
        result = parser.parse(content.encode())

        # Check metadata
        assert result.metadata.get("title") == "Test Document"
        assert result.metadata.get("author") == "John Doe"
        assert result.metadata.get("date") == "2025-01-15"
        assert "test" in result.metadata.get("keywords", [])
        assert "example" in result.metadata.get("keywords", [])

        # Check content was parsed
        assert len(result.children) == 2  # Heading + Paragraph

    def test_parse_without_frontmatter(self):
        """Test parsing document without frontmatter."""
        content = "@@ Heading\n\nParagraph text."
        parser = SimpleDocParser()
        result = parser.parse(content.encode())

        assert isinstance(result, Document)
        assert len(result.children) == 2

    def test_parse_code_block(self):
        """Test parsing code blocks."""
        content = """@@ Code Example

```python
def hello():
    print("Hello!")
```

More text.
"""
        parser = SimpleDocParser()
        result = parser.parse(content.encode())

        # Find the code block
        code_block = None
        for child in result.children:
            if isinstance(child, CodeBlock):
                code_block = child
                break

        assert code_block is not None
        assert code_block.language == "python"
        assert "def hello():" in code_block.content

    def test_parse_list(self):
        """Test parsing lists."""
        content = """@@ List Example

- Item one
- Item two
- Item three
"""
        parser = SimpleDocParser()
        result = parser.parse(content.encode())

        # Find the list
        list_node = None
        for child in result.children:
            if isinstance(child, List):
                list_node = child
                break

        assert list_node is not None
        assert len(list_node.items) == 3
        assert not list_node.ordered  # Unordered list

    def test_parse_with_options(self):
        """Test parsing with custom options."""
        content = "- Item one\n- Item two"

        # Parse with lists disabled
        options = SimpleDocOptions(parse_lists=False)
        parser = SimpleDocParser(options=options)
        result = parser.parse(content.encode())

        # Should be parsed as paragraphs instead of list
        assert all(isinstance(child, Paragraph) for child in result.children)

    def test_extract_metadata(self):
        """Test metadata extraction."""
        content = """---
title: Test
author: Jane
---

Content
"""
        parser = SimpleDocParser()
        metadata = parser.extract_metadata(content.encode())

        assert isinstance(metadata, DocumentMetadata)
        assert metadata.title == "Test"
        assert metadata.author == "Jane"

    def test_unclosed_code_block_strict_mode(self):
        """Test that unclosed code block raises error in strict mode."""
        content = "```python\ndef test():\n    pass\n"  # No closing backticks

        options = SimpleDocOptions(strict_mode=True)
        parser = SimpleDocParser(options=options)

        with pytest.raises(ParsingError, match="Code block not closed"):
            parser.parse(content.encode())

    def test_unclosed_code_block_lenient_mode(self):
        """Test that unclosed code block is handled gracefully in lenient mode."""
        content = "```python\ndef test():\n    pass\n"  # No closing backticks

        options = SimpleDocOptions(strict_mode=False)
        parser = SimpleDocParser(options=options)

        # Should not raise, but include the code
        result = parser.parse(content.encode())
        assert isinstance(result, Document)


class TestSimpleDocRenderer:
    """Test the SimpleDoc renderer."""

    def test_renderer_instantiation(self):
        """Test that renderer can be instantiated."""
        renderer = SimpleDocRenderer()
        assert renderer is not None

    def test_render_to_string(self):
        """Test rendering to string."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Test")]), Paragraph(content=[Text(content="Content")])]
        )

        renderer = SimpleDocRenderer()
        output = renderer.render_to_string(doc)

        assert isinstance(output, str)
        assert "@@ Test" in output
        assert "Content" in output

    def test_render_to_file(self, tmp_path):
        """Test rendering to file."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Test")])])

        output_file = tmp_path / "output.sdoc"
        renderer = SimpleDocRenderer()
        renderer.render(doc, output_file)

        # Verify file was created and contains expected content
        assert output_file.exists()
        content = output_file.read_text()
        assert "@@ Test" in content

    def test_render_frontmatter(self):
        """Test rendering frontmatter metadata."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"title": "Test Doc", "author": "Jane Doe", "date": "2025-01-15", "keywords": ["test", "demo"]},
        )

        renderer = SimpleDocRenderer()
        output = renderer.render_to_string(doc)

        assert "---" in output
        assert "title: Test Doc" in output
        assert "author: Jane Doe" in output
        assert "date: 2025-01-15" in output
        assert "tags: test, demo" in output

    def test_render_code_block(self):
        """Test rendering code blocks."""
        doc = Document(children=[CodeBlock(language="python", content='def hello():\n    print("Hello!")')])

        renderer = SimpleDocRenderer()
        output = renderer.render_to_string(doc)

        assert "```python" in output
        assert "def hello():" in output
        assert "```" in output.split("```python")[1]  # Closing backticks

    def test_render_list(self):
        """Test rendering lists."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )

        renderer = SimpleDocRenderer()
        output = renderer.render_to_string(doc)

        assert "- Item 1" in output
        assert "- Item 2" in output


class TestRoundTrip:
    """Test round-trip conversion (parse -> render -> parse)."""

    def test_simple_round_trip(self):
        """Test that parsing and rendering produces consistent results."""
        original = """@@ Test Heading

This is a paragraph of text.

@@ Another Heading

More content here.
"""

        # Parse
        parser = SimpleDocParser()
        ast_doc = parser.parse(original.encode())

        # Render
        renderer = SimpleDocRenderer()
        rendered = renderer.render_to_string(ast_doc)

        # Parse again
        ast_doc2 = parser.parse(rendered.encode())

        # Compare AST structure
        assert len(ast_doc.children) == len(ast_doc2.children)
        assert all(type(a) == type(b) for a, b in zip(ast_doc.children, ast_doc2.children))

    def test_round_trip_with_metadata(self):
        """Test round-trip with frontmatter metadata."""
        original = """---
title: Test Document
author: John Doe
---

@@ Content

Some text here.
"""

        parser = SimpleDocParser()
        renderer = SimpleDocRenderer()

        # Parse -> Render -> Parse
        ast1 = parser.parse(original.encode())
        rendered = renderer.render_to_string(ast1)
        ast2 = parser.parse(rendered.encode())

        # Verify metadata preserved
        assert ast1.metadata.get("title") == ast2.metadata.get("title")
        assert ast1.metadata.get("author") == ast2.metadata.get("author")


class TestConverterMetadata:
    """Test converter metadata registration."""

    def test_metadata_exists(self):
        """Test that CONVERTER_METADATA is properly defined."""
        assert CONVERTER_METADATA is not None
        assert CONVERTER_METADATA.format_name == "simpledoc"

    def test_extensions(self):
        """Test file extensions."""
        assert ".sdoc" in CONVERTER_METADATA.extensions
        assert ".simpledoc" in CONVERTER_METADATA.extensions

    def test_mime_types(self):
        """Test MIME types."""
        assert "text/x-simpledoc" in CONVERTER_METADATA.mime_types

    def test_magic_bytes(self):
        """Test magic bytes detection."""
        assert len(CONVERTER_METADATA.magic_bytes) > 0
        # Check for frontmatter detection
        assert any(b"---" in magic[0] for magic in CONVERTER_METADATA.magic_bytes)

    def test_parser_class(self):
        """Test parser class reference."""
        assert CONVERTER_METADATA.parser_class == SimpleDocParser

    def test_renderer_class(self):
        """Test renderer class reference."""
        assert CONVERTER_METADATA.renderer_class == SimpleDocRenderer

    def test_options_classes(self):
        """Test options class references."""
        assert CONVERTER_METADATA.parser_options_class == SimpleDocOptions
