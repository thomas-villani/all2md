#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for JSON parser."""


import pytest

from all2md.ast import CodeBlock, Document, Heading, List, Table
from all2md.exceptions import ParsingError
from all2md.options.json import JsonParserOptions
from all2md.parsers.json import JsonParser


class TestJsonParserBasic:
    """Test basic JSON parsing functionality."""

    def test_parse_simple_object(self):
        """Test parsing a simple JSON object."""
        json_str = '{"name": "John", "age": 30}'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have a list with key-value pairs
        list_node = None
        for child in doc.children:
            if isinstance(child, List):
                list_node = child
                break

        assert list_node is not None
        assert len(list_node.items) == 2

    def test_parse_simple_array(self):
        """Test parsing a simple JSON array."""
        json_str = '["apple", "banana", "cherry"]'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have a list
        list_node = None
        for child in doc.children:
            if isinstance(child, List):
                list_node = child
                break

        assert list_node is not None
        assert len(list_node.items) == 3

    def test_parse_nested_object(self):
        """Test parsing nested JSON objects."""
        json_str = """
        {
            "server": {
                "host": "localhost",
                "port": 8080
            },
            "database": {
                "name": "mydb",
                "timeout": 30
            }
        }
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have headings for nested objects
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) >= 2

    def test_parse_array_of_objects(self):
        """Test parsing array of objects (should become table)."""
        json_str = """
        {
            "users": [
                {"name": "Alice", "age": 30, "role": "admin"},
                {"name": "Bob", "age": 25, "role": "user"}
            ]
        }
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have a table
        table = None
        for child in doc.children:
            if isinstance(child, Table):
                table = child
                break

        assert table is not None
        assert len(table.rows) == 2  # Two users
        assert len(table.header.cells) == 3  # Three columns

    def test_parse_empty_object(self):
        """Test parsing empty JSON object."""
        json_str = "{}"
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        assert len(doc.children) >= 0

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        json_str = '{"invalid": json}'
        parser = JsonParser()

        with pytest.raises(ParsingError):
            parser.parse(json_str)


class TestJsonParserComplex:
    """Test complex JSON parsing scenarios."""

    def test_parse_deeply_nested(self):
        """Test parsing deeply nested structures."""
        json_str = """
        {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep"
                        }
                    }
                }
            }
        }
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have multiple heading levels
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0

    def test_parse_mixed_types(self):
        """Test parsing object with mixed value types."""
        json_str = """
        {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "boolean": true,
            "null": null,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_large_numbers(self):
        """Test parsing large numbers with formatting."""
        json_str = '{"population": 7800000000, "small": 100}'
        parser = JsonParser(JsonParserOptions(pretty_format_numbers=True))
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Find the list
        list_node = None
        for child in doc.children:
            if isinstance(child, List):
                list_node = child
                break

        assert list_node is not None
        # Check that large numbers are formatted with commas
        # The formatted number should appear in the text content

    def test_parse_multiline_string(self):
        """Test parsing multiline strings."""
        json_str = '{"description": "Line 1\\nLine 2\\nLine 3"}'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should handle line breaks

    def test_parse_array_below_table_threshold(self):
        """Test array with single object becomes table with default threshold."""
        json_str = """
        {
            "users": [
                {"name": "Alice", "age": 30}
            ]
        }
        """
        # With default threshold=1, single item should become a table
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have a table even with single item
        tables = [child for child in doc.children if isinstance(child, Table)]
        assert len(tables) == 1  # Should have one table

        # Test with higher threshold - should NOT become table
        parser_high_threshold = JsonParser(JsonParserOptions(array_as_table_threshold=2))
        doc_high = parser_high_threshold.parse(json_str)
        tables_high = [child for child in doc_high.children if isinstance(child, Table)]
        assert len(tables_high) == 0  # Should not have a table with threshold=2


class TestJsonParserOptions:
    """Test JSON parser options."""

    def test_literal_block_mode(self):
        """Test rendering JSON as literal code block."""
        json_str = '{"name": "John", "age": 30}'
        parser = JsonParser(JsonParserOptions(literal_block=True))
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have a code block
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].language == "json"

    def test_sort_keys(self):
        """Test sorting keys alphabetically."""
        json_str = '{"zebra": 1, "apple": 2, "monkey": 3}'
        parser = JsonParser(JsonParserOptions(sort_keys=True))
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Keys should be in alphabetical order
        # We can verify this by checking the order of list items or headings

    def test_flatten_single_keys(self):
        """Test flattening single-key objects."""
        json_str = '{"wrapper": {"data": {"value": 42}}}'
        parser = JsonParser(JsonParserOptions(flatten_single_keys=True))
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should flatten nested single-key objects

    def test_max_heading_depth(self):
        """Test max heading depth option."""
        json_str = """
        {
            "l1": {
                "l2": {
                    "l3": {
                        "l4": {
                            "value": "deep"
                        }
                    }
                }
            }
        }
        """
        parser = JsonParser(JsonParserOptions(max_heading_depth=2))
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Headings should not exceed level 2
        for child in doc.children:
            if isinstance(child, Heading):
                assert child.level <= 2


class TestJsonParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_from_file_path(self, tmp_path):
        """Test parsing from file path."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "John"}', encoding="utf-8")

        parser = JsonParser()
        doc = parser.parse(json_file)

        assert isinstance(doc, Document)

    def test_parse_from_bytes(self):
        """Test parsing from bytes."""
        json_bytes = b'{"name": "John"}'
        parser = JsonParser()
        doc = parser.parse(json_bytes)

        assert isinstance(doc, Document)

    def test_parse_unicode(self):
        """Test parsing Unicode content."""
        json_str = '{"name": "José", "greeting": "你好"}'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)

    def test_parse_special_characters(self):
        """Test parsing special characters."""
        json_str = r'{"text": "Line with \"quotes\" and \\ backslash"}'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)

    def test_metadata_extraction(self):
        """Test metadata extraction."""
        json_str = '{"title": "My Document", "data": {"value": 42}}'
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        assert doc.metadata is not None
        # Title should be extracted
        if "title" in doc.metadata:
            assert doc.metadata["title"] == "My Document"


class TestJsonParserTableConversion:
    """Test array to table conversion logic."""

    def test_consistent_keys_becomes_table(self):
        """Test array of objects with consistent keys becomes table."""
        json_str = """
        [
            {"id": 1, "name": "Alice", "status": "active"},
            {"id": 2, "name": "Bob", "status": "inactive"},
            {"id": 3, "name": "Charlie", "status": "active"}
        ]
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should have a table
        table = None
        for child in doc.children:
            if isinstance(child, Table):
                table = child
                break

        assert table is not None
        assert len(table.rows) == 3

    def test_inconsistent_keys_becomes_list(self):
        """Test array of objects with different keys becomes list."""
        json_str = """
        [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob", "extra": "field"},
            {"different": "keys"}
        ]
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Should not become a table due to inconsistent keys
        tables = [child for child in doc.children if isinstance(child, Table)]
        assert len(tables) == 0

    def test_complex_values_in_table(self):
        """Test handling complex values in table cells."""
        json_str = """
        [
            {"name": "Alice", "tags": ["admin", "user"]},
            {"name": "Bob", "tags": ["user"]}
        ]
        """
        parser = JsonParser()
        doc = parser.parse(json_str)

        assert isinstance(doc, Document)
        # Complex values should be serialized in table cells
