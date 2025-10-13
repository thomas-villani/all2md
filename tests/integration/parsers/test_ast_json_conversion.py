#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for AST JSON format with full conversion pipeline."""

import json
from pathlib import Path

import pytest

from all2md import convert, from_ast, to_ast, to_markdown
from all2md.ast import Document, Heading, Paragraph, Text
from all2md.ast.serialization import ast_to_json, json_to_ast


@pytest.mark.integration
class TestAstJsonIntegration:
    """Integration tests for AST JSON format."""

    def test_markdown_to_ast_json(self, tmp_path: Path):
        """Test converting Markdown to AST JSON."""
        # Create markdown file
        md_file = tmp_path / "input.md"
        md_file.write_text("# Title\n\nParagraph content.", encoding='utf-8')

        # Convert to AST JSON
        ast_json = convert(
            str(md_file),
            source_format="markdown",
            target_format="ast"
        )

        # Verify it's a str
        assert isinstance(ast_json, str)

        # Verify it's valid JSON
        data = json.loads(ast_json)
        assert data["schema_version"] == 1
        assert data["node_type"] == "Document"
        assert len(data["children"]) >= 1

    def test_ast_json_to_markdown(self, tmp_path: Path):
        """Test converting AST JSON to Markdown."""
        # Create AST document
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Test Title")]),
            Paragraph(content=[Text(content="Test paragraph.")])
        ])

        # Save as AST JSON
        ast_file = tmp_path / "document.ast.json"
        json_str = ast_to_json(doc)
        ast_file.write_text(json_str, encoding='utf-8')

        # Convert to markdown
        markdown = convert(
            str(ast_file),
            source_format="ast",
            target_format="markdown"
        )

        # Verify it's a str
        assert isinstance(markdown, str)

        # Verify markdown content
        assert "# Test Title" in markdown
        assert "Test paragraph." in markdown

    def test_round_trip_markdown_ast_markdown(self, tmp_path: Path):
        """Test round-trip: Markdown -> AST JSON -> Markdown."""
        original_markdown = "# Hello World\n\nThis is a test paragraph."

        # Create markdown file
        md_file = tmp_path / "input.md"
        md_file.write_text(original_markdown, encoding='utf-8')

        # Convert to AST JSON
        ast_json = convert(
            str(md_file),
            source_format="markdown",
            target_format="ast"
        )

        # Verify it's a str
        assert isinstance(ast_json, str)

        # Parse AST JSON
        doc = json_to_ast(ast_json)

        # Convert back to markdown
        result_markdown = from_ast(doc, target_format="markdown")

        # Verify it's a str
        assert isinstance(result_markdown, str)

        # Verify content is preserved (structure may vary slightly)
        assert "Hello World" in result_markdown
        assert "test paragraph" in result_markdown

    def test_convert_to_ast_json_with_output_file(self, tmp_path: Path):
        """Test converting to AST JSON with output file."""
        # Create markdown file
        md_file = tmp_path / "input.md"
        md_file.write_text("# Document\n\nContent.", encoding='utf-8')

        # Convert to AST JSON with output file
        output_file = tmp_path / "output.ast"
        convert(
            str(md_file),
            output=str(output_file),
            source_format="markdown",
            target_format="ast"
        )

        # Verify output file exists and is valid
        assert output_file.exists()
        content = output_file.read_text(encoding='utf-8')
        data = json.loads(content)
        assert data["node_type"] == "Document"

    def test_convert_from_ast_json_with_output_file(self, tmp_path: Path):
        """Test converting from AST JSON with output file."""
        # Create AST JSON file
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Content")])
        ])
        ast_file = tmp_path / "input.ast"
        ast_file.write_text(ast_to_json(doc), encoding='utf-8')

        # Convert to markdown with output file
        output_file = tmp_path / "output.md"
        convert(
            str(ast_file),
            output=str(output_file),
            source_format="ast",
            target_format="markdown"
        )

        # Verify output file exists and has content
        assert output_file.exists()
        content = output_file.read_text(encoding='utf-8')
        assert "Title" in content
        assert "Content" in content

    def test_to_ast_then_convert_to_json(self):
        """Test using to_ast() and then converting to JSON."""
        # Create a markdown string
        markdown = "# Header\n\nParagraph text."

        # Convert to AST
        doc = to_ast(markdown.encode('utf-8'), source_format="markdown")

        # Convert AST to JSON using from_ast
        json_str = from_ast(doc, target_format="ast")

        # Verify it's a str
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["node_type"] == "Document"

    def test_json_string_to_ast_via_convert(self):
        """Test converting JSON string to AST via convert function."""
        # Create AST JSON string
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])
        json_str = ast_to_json(doc)

        # Convert to markdown
        markdown = convert(
            json_str.encode('utf-8'),
            source_format="ast",
            target_format="markdown"
        )

        assert isinstance(markdown, str)
        assert "Test" in markdown

    def test_format_auto_detection_ast_json(self, tmp_path: Path):
        """Test automatic format detection for .ast files."""
        # Create AST JSON file
        doc = Document(children=[
            Paragraph(content=[Text(content="Auto-detected")])
        ])
        ast_file = tmp_path / "test.ast"
        ast_file.write_text(ast_to_json(doc), encoding='utf-8')

        # Convert without specifying source format
        markdown = convert(
            str(ast_file),
            target_format="markdown"
        )

        assert isinstance(markdown, str)
        assert "Auto-detected" in markdown

    def test_ast_json_with_transforms(self):
        """Test applying transforms during AST JSON conversion."""
        # Create markdown with an image
        markdown = "# Title\n\n![alt text](image.png)\n\nParagraph."

        # Convert to AST JSON (should preserve image)
        ast_json = convert(
            markdown.encode('utf-8'),
            source_format="markdown",
            target_format="ast"
        )

        # Verify it's a str
        assert isinstance(ast_json, str)

        # Verify image is in AST
        data = json.loads(ast_json)
        ast_str = json.dumps(data)
        assert "Image" in ast_str

        # Convert back with transform to remove images
        doc = json_to_ast(ast_json)
        markdown_no_images = from_ast(
            doc,
            target_format="markdown",
            transforms=["remove-images"]
        )

        # Verify it's a str
        assert isinstance(markdown_no_images, str)

        # Verify image is removed
        assert "![alt text]" not in markdown_no_images
        assert "Paragraph." in markdown_no_images

    def test_ast_json_preserves_metadata(self, tmp_path: Path):
        """Test that AST JSON preserves document metadata."""
        # Create markdown with metadata
        markdown_with_meta = """---
title: Test Document
author: Test Author
---

# Content

Test paragraph."""

        md_file = tmp_path / "input.md"
        md_file.write_text(markdown_with_meta, encoding='utf-8')

        # Convert to AST JSON
        ast_json = convert(
            str(md_file),
            source_format="markdown",
            target_format="ast"
        )

        # Verify it's a str
        assert isinstance(ast_json, str)

        # Check metadata is preserved
        # Metadata might be in document metadata or in a separate node
        # depending on how markdown parser handles frontmatter
        assert "Test Document" in ast_json or "Test Author" in ast_json

    def test_to_markdown_with_ast_intermediate(self):
        """Test using to_markdown with AST as intermediate format."""
        # Create simple markdown
        original = "# Title\n\nContent."

        # Convert through AST
        doc = to_ast(original.encode('utf-8'), source_format="markdown")
        markdown = to_markdown(ast_to_json(doc).encode('utf-8'), source_format="ast")

        # Verify content is preserved
        assert "Title" in markdown
        assert "Content" in markdown

    def test_complex_document_through_ast_json(self):
        """Test complex document structure through AST JSON."""
        # Create complex markdown
        complex_md = """# Main Title

Introduction paragraph.

## Section 1

Section content with **bold** and *italic*.

### Subsection

- List item 1
- List item 2

## Section 2

Final paragraph."""

        # Convert to AST JSON
        ast_json = convert(
            complex_md.encode('utf-8'),
            source_format="markdown",
            target_format="ast"
        )

        # Verify it's a str
        assert isinstance(ast_json, str)

        # Verify structure
        data = json.loads(ast_json)
        assert data["node_type"] == "Document"
        assert len(data["children"]) > 5  # Multiple elements

        # Convert back to markdown
        markdown = convert(
            ast_json.encode('utf-8'),
            source_format="ast",
            target_format="markdown"
        )

        # Verify it's a str
        assert isinstance(markdown, str)

        # Verify content is preserved
        assert "Main Title" in markdown
        assert "Section 1" in markdown
        assert "Subsection" in markdown

    def test_ast_json_compact_format(self, tmp_path: Path):
        """Test AST JSON with compact formatting."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        # Convert to compact JSON
        from all2md.options.ast_json import AstJsonRendererOptions
        json_str = from_ast(
            doc,
            target_format="ast",
            renderer_options=AstJsonRendererOptions(indent=None)
        )

        # Verify it's a str
        assert isinstance(json_str, str)

        # Verify it's compact (minimal whitespace)
        lines = json_str.split('\n')
        assert len([line for line in lines if line.strip()]) <= 2

        # Verify it's still valid and parseable
        parsed_doc = json_to_ast(json_str)
        assert isinstance(parsed_doc, Document)
