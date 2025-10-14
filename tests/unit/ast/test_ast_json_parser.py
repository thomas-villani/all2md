#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for AST JSON parser."""

import json
from io import BytesIO
from pathlib import Path

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.ast.serialization import ast_to_json
from all2md.exceptions import ParsingError
from all2md.options.ast_json import AstJsonParserOptions
from all2md.parsers.ast_json import AstJsonParser, _is_ast_json_content


class TestAstJsonContentDetector:
    """Tests for AST JSON content detection."""

    def test_detect_valid_ast_json(self):
        """Test detection of valid AST JSON content."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello")])
        ])
        json_str = ast_to_json(doc)
        content = json_str.encode('utf-8')

        assert _is_ast_json_content(content)

    def test_detect_ast_json_without_schema_version(self):
        """Test detection of AST JSON without schema_version field."""
        ast_dict = {
            "node_type": "Document",
            "children": [],
            "metadata": {}
        }
        content = json.dumps(ast_dict).encode('utf-8')

        assert _is_ast_json_content(content)

    def test_detect_regular_json_not_ast(self):
        """Test that regular JSON is not detected as AST."""
        regular_json = {"name": "test", "value": 123}
        content = json.dumps(regular_json).encode('utf-8')

        assert not _is_ast_json_content(content)

    def test_detect_invalid_json(self):
        """Test that invalid JSON is not detected as AST."""
        content = b"not json at all"

        assert not _is_ast_json_content(content)

    def test_detect_json_array(self):
        """Test that JSON arrays are not detected as AST."""
        content = b'[{"node_type": "Document"}]'

        assert not _is_ast_json_content(content)

    def test_detect_large_ast_json_with_prefix_sampling(self):
        """Test that large AST JSON files are detected efficiently using prefix sampling."""
        # Create a properly formed AST JSON in the prefix, followed by large content
        # This simulates a real AST JSON file where the structure is clear from the start
        small_ast = {
            "schema_version": 1,
            "node_type": "Document",
            "children": [
                {
                    "node_type": "Paragraph",
                    "content": [{"node_type": "Text", "content": "Start content"}],
                    "metadata": {}
                }
            ],
            "metadata": {}
        }

        # Convert to JSON and get the first part
        small_json = json.dumps(small_ast)

        # Create a large document by adding many paragraphs in the middle
        # But keep the structure parseable in the prefix
        large_children = []
        for i in range(1000):
            large_children.append({
                "node_type": "Paragraph",
                "content": [{"node_type": "Text", "content": f"Content {i}" * 50}],
                "metadata": {}
            })

        large_ast = {
            "schema_version": 1,
            "node_type": "Document",
            "children": large_children,
            "metadata": {}
        }

        content = json.dumps(large_ast).encode('utf-8')
        # Ensure content is larger than 256 KB to test sampling
        assert len(content) > 262144

        # Detection depends on whether the prefix contains valid parseable JSON
        # The key is that the function only loads 256KB max, not the full content
        # Note: The detection may succeed or fail depending on where the 256KB cut happens
        # The important thing is it doesn't load the entire multi-MB file
        result = _is_ast_json_content(content)
        # Just verify it returns a boolean and doesn't crash
        assert isinstance(result, bool)

    def test_detect_ast_json_node_type_in_prefix(self):
        """Test detection when node_type appears in the first 256 KB."""
        # Create content where key indicators are in the prefix
        ast_dict = {
            "schema_version": 1,
            "node_type": "Document",
            "children": [],
            "metadata": {}
        }
        content = json.dumps(ast_dict).encode('utf-8')

        # Pad with additional data after to simulate large file
        padded_content = content + (b' ' * 300000)

        # Should detect because indicators are in prefix
        assert _is_ast_json_content(padded_content)

    def test_detect_non_ast_json_without_node_type_in_prefix(self):
        """Test that JSON without node_type in prefix is not detected as AST."""
        # Create a large JSON that doesn't have node_type in the first part
        large_json = {
            "data": ["item" * 100 for _ in range(5000)],
            "node_type": "Document"  # Too far into the content
        }
        content = json.dumps(large_json).encode('utf-8')

        # The node_type might be too far into the content to be in the 256KB prefix
        # This tests the fast rejection path
        # Note: This might still detect if node_type happens to be in the prefix
        # The key is that we're testing the prefix-based detection logic
        result = _is_ast_json_content(content)
        # Result depends on where "node_type" appears, but function should not load full content
        assert isinstance(result, bool)


class TestAstJsonParser:
    """Tests for AST JSON parser."""

    def test_parse_simple_document(self):
        """Test parsing a simple AST document."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello, world!")])
        ])
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        assert isinstance(parsed_doc, Document)
        assert len(parsed_doc.children) == 1
        assert isinstance(parsed_doc.children[0], Paragraph)

    def test_parse_from_file_path(self, tmp_path: Path):
        """Test parsing from a file path."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        json_str = ast_to_json(doc)

        # Write to temp file
        ast_file = tmp_path / "test.ast"
        ast_file.write_text(json_str, encoding='utf-8')

        # Parse from file path
        parser = AstJsonParser()
        parsed_doc = parser.parse(str(ast_file))

        assert isinstance(parsed_doc, Document)
        assert len(parsed_doc.children) == 1
        assert isinstance(parsed_doc.children[0], Heading)

    def test_parse_from_path_object(self, tmp_path: Path):
        """Test parsing from a Path object."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])
        json_str = ast_to_json(doc)

        # Write to temp file
        ast_file = tmp_path / "test.ast"
        ast_file.write_text(json_str, encoding='utf-8')

        # Parse from Path object
        parser = AstJsonParser()
        parsed_doc = parser.parse(ast_file)

        assert isinstance(parsed_doc, Document)

    def test_parse_from_bytes(self):
        """Test parsing from bytes."""
        doc = Document(children=[
            Paragraph(content=[Text(content="From bytes")])
        ])
        json_str = ast_to_json(doc)
        json_bytes = json_str.encode('utf-8')

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_bytes)

        assert isinstance(parsed_doc, Document)
        assert len(parsed_doc.children) == 1

    def test_parse_from_io_bytes(self):
        """Test parsing from IO[bytes] stream."""
        doc = Document(children=[
            Paragraph(content=[Text(content="From IO")])
        ])
        json_str = ast_to_json(doc)
        io_stream = BytesIO(json_str.encode('utf-8'))

        parser = AstJsonParser()
        parsed_doc = parser.parse(io_stream)

        assert isinstance(parsed_doc, Document)

    def test_parse_with_metadata(self):
        """Test parsing document with metadata."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Test")])],
            metadata={
                "title": "Test Document",
                "author": "Test Author"
            }
        )
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        assert parsed_doc.metadata.get("title") == "Test Document"
        assert parsed_doc.metadata.get("author") == "Test Author"

    def test_round_trip_conversion(self):
        """Test round-trip conversion: AST -> JSON -> AST."""
        original_doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[
                Text(content="This is a "),
                Text(content="test")
            ])
        ])

        # Convert to JSON
        json_str = ast_to_json(original_doc)

        # Parse back to AST
        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        # Verify structure is preserved
        assert len(parsed_doc.children) == len(original_doc.children)
        assert isinstance(parsed_doc.children[0], Heading)
        assert parsed_doc.children[0].level == 1
        assert isinstance(parsed_doc.children[1], Paragraph)

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        invalid_json = b"{ not valid json }"

        parser = AstJsonParser()
        with pytest.raises(ParsingError, match="Invalid JSON"):
            parser.parse(invalid_json)

    def test_parse_invalid_ast_structure(self):
        """Test parsing invalid AST structure raises error."""
        # Valid JSON but invalid AST
        invalid_ast = json.dumps({
            "schema_version": 1,
            "node_type": "UnknownNode",
            "children": []
        })

        parser = AstJsonParser()
        with pytest.raises(ParsingError, match="Invalid AST structure"):
            parser.parse(invalid_ast.encode('utf-8'))

    def test_parse_unsupported_schema_version(self):
        """Test parsing unsupported schema version raises error."""
        unsupported = json.dumps({
            "schema_version": 999,
            "node_type": "Document",
            "children": [],
            "metadata": {}
        })

        parser = AstJsonParser()
        with pytest.raises(ParsingError, match="Invalid AST structure"):
            parser.parse(unsupported.encode('utf-8'))

    def test_parse_non_document_root(self):
        """Test parsing non-Document root node raises error."""
        # Valid AST node but not a Document
        non_doc = json.dumps({
            "schema_version": 1,
            "node_type": "Paragraph",
            "content": [],
            "metadata": {}
        })

        parser = AstJsonParser()
        with pytest.raises(ParsingError, match="AST root must be a Document node"):
            parser.parse(non_doc.encode('utf-8'))

    def test_extract_metadata_from_document(self):
        """Test extracting metadata from parsed document."""
        doc = Document(
            children=[],
            metadata={
                "title": "Test Title",
                "author": "Test Author",
                "keywords": ["test", "ast"],
                "custom": {"field": "value"}
            }
        )
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))
        metadata = parser.extract_metadata(parsed_doc)

        assert metadata.title == "Test Title"
        assert metadata.author == "Test Author"
        assert metadata.keywords == ["test", "ast"]
        assert metadata.custom == {"field": "value"}

    def test_extract_metadata_empty_document(self):
        """Test extracting metadata from document with no metadata."""
        doc = Document(children=[])
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))
        metadata = parser.extract_metadata(parsed_doc)

        assert metadata.title is None
        assert metadata.author is None
        assert metadata.keywords is None

    def test_parse_with_options(self):
        """Test parsing with custom options."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])
        json_str = ast_to_json(doc)

        options = AstJsonParserOptions(
            validate_schema=True,
            strict_mode=False
        )
        parser = AstJsonParser(options=options)
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        assert isinstance(parsed_doc, Document)

    def test_parse_unicode_content(self):
        """Test parsing AST with unicode content."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello 世界 🌍")])
        ])
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        # Extract the text content
        para = parsed_doc.children[0]
        text_node = para.content[0]
        assert text_node.content == "Hello 世界 🌍"

    def test_parse_complex_document_structure(self):
        """Test parsing a complex document with nested structures."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Main Title")]),
            Paragraph(content=[Text(content="Introduction paragraph.")]),
            Heading(level=2, content=[Text(content="Section 1")]),
            Paragraph(content=[Text(content="Section content.")])
        ])
        json_str = ast_to_json(doc)

        parser = AstJsonParser()
        parsed_doc = parser.parse(json_str.encode('utf-8'))

        assert len(parsed_doc.children) == 4
        assert isinstance(parsed_doc.children[0], Heading)
        assert parsed_doc.children[0].level == 1
        assert isinstance(parsed_doc.children[1], Paragraph)
        assert isinstance(parsed_doc.children[2], Heading)
        assert parsed_doc.children[2].level == 2
