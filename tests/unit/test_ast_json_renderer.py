#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for AST JSON renderer."""

import json
from io import BytesIO
from pathlib import Path

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.ast.serialization import json_to_ast
from all2md.options.ast_json import AstJsonRendererOptions
from all2md.renderers.ast_json import AstJsonRenderer


class TestAstJsonRenderer:
    """Tests for AST JSON renderer."""

    def test_render_simple_document_to_string(self):
        """Test rendering a simple document to JSON string."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello, world!")])
        ])

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["schema_version"] == 1
        assert data["node_type"] == "Document"
        assert len(data["children"]) == 1

    def test_render_with_default_indent(self):
        """Test rendering with default indentation."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Default indent is 2, so check for indentation
        assert '\n' in json_str
        assert '  ' in json_str

    def test_render_with_custom_indent(self):
        """Test rendering with custom indentation."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        options = AstJsonRendererOptions(indent=4)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Check for 4-space indentation
        assert '\n' in json_str
        assert '    ' in json_str

    def test_render_compact_no_indent(self):
        """Test rendering compact JSON without indentation."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        options = AstJsonRendererOptions(indent=None)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Compact JSON should have no newlines or indentation
        # (except possibly in string values)
        lines = json_str.split('\n')
        # Compact JSON is typically a single line
        assert len([line for line in lines if line.strip()]) <= 2

    def test_render_with_ensure_ascii(self):
        """Test rendering with ensure_ascii option."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello 世界")])
        ])

        options = AstJsonRendererOptions(ensure_ascii=True)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Unicode characters should be escaped
        assert '\\u' in json_str
        # The actual unicode characters should not appear
        assert '世界' not in json_str

    def test_render_without_ensure_ascii(self):
        """Test rendering without ensure_ascii (preserve unicode)."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello 世界")])
        ])

        options = AstJsonRendererOptions(ensure_ascii=False)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Unicode characters should be preserved
        assert '世界' in json_str

    def test_render_with_sort_keys(self):
        """Test rendering with sort_keys option."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        options = AstJsonRendererOptions(sort_keys=True, indent=2)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Parse and verify keys are sorted
        data = json.loads(json_str)
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_render_to_file_path(self, tmp_path: Path):
        """Test rendering to a file path."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])

        output_file = tmp_path / "output.ast"
        renderer = AstJsonRenderer()
        renderer.render(doc, str(output_file))

        # Verify file was created
        assert output_file.exists()

        # Verify content is valid JSON
        content = output_file.read_text(encoding='utf-8')
        data = json.loads(content)
        assert data["node_type"] == "Document"

    def test_render_to_path_object(self, tmp_path: Path):
        """Test rendering to a Path object."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        output_file = tmp_path / "output.ast"
        renderer = AstJsonRenderer()
        renderer.render(doc, output_file)

        # Verify file was created and is valid
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding='utf-8'))
        assert data["node_type"] == "Document"

    def test_render_to_io_bytes(self):
        """Test rendering to IO[bytes] stream."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        io_stream = BytesIO()
        renderer = AstJsonRenderer()
        renderer.render(doc, io_stream)

        # Get content from stream
        io_stream.seek(0)
        content = io_stream.read().decode('utf-8')

        # Verify it's valid JSON
        data = json.loads(content)
        assert data["node_type"] == "Document"

    def test_render_with_metadata(self):
        """Test rendering document with metadata."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Test")])],
            metadata={
                "title": "Test Document",
                "author": "Test Author"
            }
        )

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Verify metadata is preserved
        data = json.loads(json_str)
        assert data["metadata"]["title"] == "Test Document"
        assert data["metadata"]["author"] == "Test Author"

    def test_render_complex_document(self):
        """Test rendering a complex document structure."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Main Title")]),
            Paragraph(content=[Text(content="Introduction.")]),
            Heading(level=2, content=[Text(content="Section 1")]),
            Paragraph(content=[Text(content="Content.")])
        ])

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Verify structure is preserved
        data = json.loads(json_str)
        assert len(data["children"]) == 4
        assert data["children"][0]["node_type"] == "Heading"
        assert data["children"][0]["level"] == 1
        assert data["children"][1]["node_type"] == "Paragraph"

    def test_round_trip_through_renderer(self):
        """Test round-trip: Document -> JSON -> Document."""
        original_doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Content")])
        ])

        # Render to JSON
        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(original_doc)

        # Parse back to Document
        parsed_doc = json_to_ast(json_str)

        # Verify structure matches
        assert len(parsed_doc.children) == len(original_doc.children)
        assert isinstance(parsed_doc.children[0], Heading)
        assert parsed_doc.children[0].level == 1

    def test_render_empty_document(self):
        """Test rendering an empty document."""
        doc = Document(children=[])

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Verify it's valid and has correct structure
        data = json.loads(json_str)
        assert data["schema_version"] == 1
        assert data["node_type"] == "Document"
        assert data["children"] == []

    def test_render_with_all_options(self):
        """Test rendering with all options configured."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test 测试")])
        ])

        options = AstJsonRendererOptions(
            indent=4,
            ensure_ascii=False,
            sort_keys=True
        )
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Verify options are applied
        assert '    ' in json_str  # indent=4
        assert '测试' in json_str  # ensure_ascii=False
        data = json.loads(json_str)
        keys = list(data.keys())
        assert keys == sorted(keys)  # sort_keys=True

    def test_schema_version_included(self):
        """Test that schema_version is always included in output."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        renderer = AstJsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "schema_version" in data
        assert data["schema_version"] == 1

    def test_render_unicode_emoji(self):
        """Test rendering document with emoji characters."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello 🌍 🚀")])
        ])

        options = AstJsonRendererOptions(ensure_ascii=False)
        renderer = AstJsonRenderer(options=options)
        json_str = renderer.render_to_string(doc)

        # Verify emojis are preserved
        assert '🌍' in json_str
        assert '🚀' in json_str

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["node_type"] == "Document"
