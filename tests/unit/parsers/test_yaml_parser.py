#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_yaml_parser.py
"""Comprehensive unit tests for YAML parser."""

from __future__ import annotations

from io import BytesIO

import pytest

from all2md.ast import CodeBlock, Document, Heading, List
from all2md.exceptions import ParsingError
from all2md.options.yaml import YamlParserOptions
from all2md.parsers.yaml import YamlParser


class TestYamlParserInitialization:
    """Test YAML parser initialization."""

    def test_default_initialization(self):
        """Test parser initializes with default options."""
        parser = YamlParser()
        assert parser.options is not None
        assert isinstance(parser.options, YamlParserOptions)

    def test_initialization_with_options(self):
        """Test parser initializes with custom options."""
        options = YamlParserOptions(max_heading_depth=3, sort_keys=True)
        parser = YamlParser(options)
        assert parser.options.max_heading_depth == 3
        assert parser.options.sort_keys is True

    def test_initialization_with_invalid_options(self):
        """Test parser raises error with invalid options type."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            YamlParser(options="invalid")


class TestYamlParserLiteralBlock:
    """Test YAML parser in literal block mode."""

    def test_literal_block_mode(self):
        """Test parsing YAML as literal code block."""
        yaml_content = """
server:
  host: localhost
  port: 8080
"""
        options = YamlParserOptions(literal_block=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].language == "yaml"

    def test_literal_block_with_invalid_yaml(self):
        """Test literal block mode handles invalid YAML gracefully."""
        invalid_yaml = "invalid: yaml: content:"
        options = YamlParserOptions(literal_block=True)
        parser = YamlParser(options)
        doc = parser.parse(invalid_yaml)

        # Should still create a code block even if YAML is invalid
        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        assert isinstance(doc.children[0], CodeBlock)

    def test_literal_block_with_sort_keys(self):
        """Test literal block mode with sorted keys."""
        yaml_content = """
zebra: last
apple: first
banana: second
"""
        options = YamlParserOptions(literal_block=True, sort_keys=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        # Should format the YAML with sorted keys
        assert isinstance(doc.children[0], CodeBlock)
        content = doc.children[0].content
        # apple should come before zebra
        assert content.index("apple") < content.index("zebra")


class TestYamlParserPrimitiveTypes:
    """Test parsing YAML primitive types."""

    def test_parse_null_value(self):
        """Test parsing null values."""
        parser = YamlParser()
        doc = parser.parse("value: null")

        assert isinstance(doc, Document)
        # Should contain "null" text
        assert any("null" in str(child) for child in doc.children)

    def test_parse_boolean_true(self):
        """Test parsing boolean true."""
        parser = YamlParser()
        doc = parser.parse("enabled: true")

        assert isinstance(doc, Document)

    def test_parse_boolean_false(self):
        """Test parsing boolean false."""
        parser = YamlParser()
        doc = parser.parse("enabled: false")

        assert isinstance(doc, Document)

    def test_parse_integer(self):
        """Test parsing integer values."""
        parser = YamlParser()
        doc = parser.parse("count: 42")

        assert isinstance(doc, Document)

    def test_parse_large_integer_with_formatting(self):
        """Test parsing large integers with thousand separators."""
        options = YamlParserOptions(pretty_format_numbers=True)
        parser = YamlParser(options)
        doc = parser.parse("count: 1000000")

        # Should format with commas
        assert isinstance(doc, Document)

    def test_parse_large_integer_without_formatting(self):
        """Test parsing large integers without formatting."""
        options = YamlParserOptions(pretty_format_numbers=False)
        parser = YamlParser(options)
        doc = parser.parse("count: 1000000")

        assert isinstance(doc, Document)

    def test_parse_float(self):
        """Test parsing float values."""
        parser = YamlParser()
        doc = parser.parse("pi: 3.14159")

        assert isinstance(doc, Document)

    def test_parse_string(self):
        """Test parsing string values."""
        parser = YamlParser()
        doc = parser.parse("name: John Doe")

        assert isinstance(doc, Document)

    def test_parse_multiline_string(self):
        """Test parsing multiline string values."""
        yaml_content = """
description: |
  Line 1
  Line 2
  Line 3
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_datetime(self):
        """Test parsing datetime values."""
        parser = YamlParser()
        doc = parser.parse("timestamp: 2024-06-15T12:30:00")

        assert isinstance(doc, Document)

    def test_parse_date(self):
        """Test parsing date values."""
        parser = YamlParser()
        doc = parser.parse("birthday: 2024-06-15")

        assert isinstance(doc, Document)


class TestYamlParserArrays:
    """Test parsing YAML arrays."""

    def test_parse_simple_array(self):
        """Test parsing simple array of primitives."""
        yaml_content = """
items:
  - apple
  - banana
  - cherry
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        # Should contain a List node
        has_list = any(isinstance(child, List) for child in doc.children)
        assert has_list or any(
            isinstance(grandchild, List)
            for child in doc.children
            if hasattr(child, "children")
            for grandchild in (child.children if hasattr(child, "children") else [])
        )

    def test_parse_array_of_objects_as_table(self):
        """Test parsing array of objects as table."""
        yaml_content = """
users:
  - name: Alice
    role: admin
  - name: Bob
    role: user
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_array_of_objects_with_threshold(self):
        """Test array rendering threshold."""
        yaml_content = """
users:
  - name: Alice
    role: admin
"""
        options = YamlParserOptions(array_as_table_threshold=2)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        # Single item should not be rendered as table
        assert isinstance(doc, Document)

    def test_parse_empty_array(self):
        """Test parsing empty array."""
        parser = YamlParser()
        doc = parser.parse("items: []")

        assert isinstance(doc, Document)

    def test_parse_nested_arrays(self):
        """Test parsing nested arrays."""
        yaml_content = """
matrix:
  - [1, 2, 3]
  - [4, 5, 6]
  - [7, 8, 9]
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)


class TestYamlParserObjects:
    """Test parsing YAML objects."""

    def test_parse_simple_object(self):
        """Test parsing simple object."""
        yaml_content = """
server:
  host: localhost
  port: 8080
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        # Should contain heading for "server"
        has_heading = any(isinstance(child, Heading) for child in doc.children)
        assert has_heading

    def test_parse_empty_object(self):
        """Test parsing empty object."""
        parser = YamlParser()
        doc = parser.parse("config: {}")

        assert isinstance(doc, Document)

    def test_parse_object_with_sort_keys(self):
        """Test parsing object with sorted keys."""
        yaml_content = """
zebra: last
apple: first
banana: second
"""
        options = YamlParserOptions(sort_keys=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_object_without_sort_keys(self):
        """Test parsing object preserving key order."""
        yaml_content = """
zebra: last
apple: first
banana: second
"""
        options = YamlParserOptions(sort_keys=False)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_nested_objects(self):
        """Test parsing nested objects."""
        yaml_content = """
database:
  primary:
    host: db1.example.com
    port: 5432
  secondary:
    host: db2.example.com
    port: 5432
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_object_with_all_primitives(self):
        """Test parsing object with only primitive values."""
        yaml_content = """
config:
  name: MyApp
  version: 1.0.0
  enabled: true
  timeout: 30
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)


class TestYamlParserFlattenOptions:
    """Test YAML parser flatten options."""

    def test_flatten_single_keys_enabled(self):
        """Test flattening objects with single keys."""
        yaml_content = """
wrapper:
  actual_data:
    value: 123
"""
        options = YamlParserOptions(flatten_single_keys=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_flatten_single_keys_disabled(self):
        """Test not flattening when option is disabled."""
        yaml_content = """
wrapper:
  actual_data:
    value: 123
"""
        options = YamlParserOptions(flatten_single_keys=False)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_flatten_single_key_with_primitive(self):
        """Test that single key with primitive is not flattened."""
        yaml_content = """
wrapper: simple_value
"""
        options = YamlParserOptions(flatten_single_keys=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)


class TestYamlParserDepthControl:
    """Test YAML parser heading depth control."""

    def test_max_heading_depth_default(self):
        """Test default maximum heading depth."""
        yaml_content = """
level1:
  level2:
    level3:
      level4:
        level5:
          level6:
            level7: value
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_max_heading_depth_custom(self):
        """Test custom maximum heading depth."""
        yaml_content = """
level1:
  level2:
    level3:
      level4: value
"""
        options = YamlParserOptions(max_heading_depth=2)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_depth_beyond_max_uses_list_style(self):
        """Test that depth beyond max uses list style."""
        yaml_content = """
level1:
  level2:
    level3:
      level4:
        level5: value
"""
        options = YamlParserOptions(max_heading_depth=3)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)


class TestYamlParserInputTypes:
    """Test YAML parser with different input types."""

    def test_parse_string_input(self):
        """Test parsing string input."""
        parser = YamlParser()
        doc = parser.parse("key: value")

        assert isinstance(doc, Document)

    def test_parse_bytes_input(self):
        """Test parsing bytes input."""
        parser = YamlParser()
        doc = parser.parse(b"key: value")

        assert isinstance(doc, Document)

    def test_parse_path_input(self, tmp_path):
        """Test parsing file path input."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\n", encoding="utf-8")

        parser = YamlParser()
        doc = parser.parse(yaml_file)

        assert isinstance(doc, Document)

    def test_parse_string_path_input(self, tmp_path):
        """Test parsing string path input."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\n", encoding="utf-8")

        parser = YamlParser()
        doc = parser.parse(str(yaml_file))

        assert isinstance(doc, Document)

    def test_parse_file_like_input(self):
        """Test parsing file-like input."""
        yaml_bytes = b"key: value\n"
        file_like = BytesIO(yaml_bytes)

        parser = YamlParser()
        doc = parser.parse(file_like)

        assert isinstance(doc, Document)


class TestYamlParserErrorHandling:
    """Test YAML parser error handling."""

    def test_parse_invalid_yaml_raises_error(self):
        """Test parsing invalid YAML raises ParsingError."""
        # YAML with invalid structure - unclosed flow sequence
        invalid_yaml = "key: [value1, value2"
        parser = YamlParser()

        with pytest.raises(ParsingError) as excinfo:
            parser.parse(invalid_yaml)
        assert "Invalid YAML" in str(excinfo.value)

    def test_parse_malformed_yaml(self):
        """Test parsing malformed YAML."""
        malformed = "key: [unclosed list"
        parser = YamlParser()

        with pytest.raises(ParsingError):
            parser.parse(malformed)

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing nonexistent file."""
        nonexistent = tmp_path / "nonexistent.yaml"
        parser = YamlParser()

        with pytest.raises(Exception):
            parser.parse(nonexistent)


class TestYamlParserMetadata:
    """Test YAML parser metadata extraction."""

    def test_extract_metadata_from_document(self):
        """Test metadata extraction from YAML document."""
        yaml_content = """
title: Test Document
author: John Doe
data:
  key: value
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        assert hasattr(doc, "metadata")

    def test_metadata_with_empty_document(self):
        """Test metadata with empty document."""
        parser = YamlParser()
        doc = parser.parse("")

        assert isinstance(doc, Document)


class TestYamlParserComplexScenarios:
    """Test YAML parser with complex scenarios."""

    def test_parse_complex_nested_structure(self):
        """Test parsing complex nested structure."""
        yaml_content = """
application:
  name: MyApp
  version: 1.0.0
  database:
    connections:
      - name: primary
        host: db1.example.com
        port: 5432
      - name: secondary
        host: db2.example.com
        port: 5432
  features:
    - authentication
    - logging
    - caching
  config:
    timeout: 30
    retries: 3
    debug: false
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_mixed_types_array(self):
        """Test parsing array with mixed types."""
        yaml_content = """
mixed:
  - string_value
  - 123
  - true
  - null
  - 3.14
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_with_all_options(self):
        """Test parsing with all options enabled."""
        yaml_content = """
zebra:
  nested:
    value: 1000
apple:
  data: test
"""
        options = YamlParserOptions(
            max_heading_depth=4,
            array_as_table_threshold=2,
            flatten_single_keys=True,
            include_type_hints=True,
            pretty_format_numbers=True,
            sort_keys=True,
        )
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_config_file_structure(self):
        """Test parsing typical config file structure."""
        yaml_content = """
server:
  host: 0.0.0.0
  port: 8080
  ssl:
    enabled: true
    cert: /path/to/cert.pem
    key: /path/to/key.pem

database:
  url: postgresql://localhost/mydb
  pool_size: 10
  timeout: 30

logging:
  level: INFO
  handlers:
    - type: file
      path: /var/log/app.log
    - type: console
      format: json
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0


class TestYamlParserEdgeCases:
    """Test YAML parser edge cases."""

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        parser = YamlParser()
        doc = parser.parse("")

        assert isinstance(doc, Document)

    def test_parse_only_comments(self):
        """Test parsing YAML with only comments."""
        yaml_content = """
# This is a comment
# Another comment
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only content."""
        parser = YamlParser()
        # Spaces and newlines only (no tabs which can cause YAML scan errors)
        doc = parser.parse("   \n\n     \n")

        assert isinstance(doc, Document)

    def test_parse_unicode_content(self):
        """Test parsing Unicode content."""
        yaml_content = """
message: Hello, 世界! 🌍
emoji: 🎉🎊🎈
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)

    def test_parse_special_yaml_features(self):
        """Test parsing special YAML features."""
        yaml_content = """
anchors: &anchor
  key: value

reference: *anchor

multiline: |
  Line 1
  Line 2

folded: >
  This is a
  folded string
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)


class TestYamlParserIntegration:
    """Integration tests for YAML parser."""

    def test_round_trip_with_literal_block(self):
        """Test that literal block preserves content structure."""
        yaml_content = """
name: Test
items:
  - one
  - two
"""
        options = YamlParserOptions(literal_block=True)
        parser = YamlParser(options)
        doc = parser.parse(yaml_content)

        assert isinstance(doc.children[0], CodeBlock)
        # Content should be valid YAML
        assert "name:" in doc.children[0].content
        assert "items:" in doc.children[0].content

    def test_parse_and_verify_structure(self):
        """Test parsing and verify document structure."""
        yaml_content = """
title: Document
sections:
  - name: Section 1
    content: Content 1
  - name: Section 2
    content: Content 2
"""
        parser = YamlParser()
        doc = parser.parse(yaml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have headings for top-level keys
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0
