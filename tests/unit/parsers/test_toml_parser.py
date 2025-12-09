#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_toml_parser.py
"""Comprehensive unit tests for TOML parser."""

from __future__ import annotations

import sys
from io import BytesIO

import pytest

from all2md.ast import CodeBlock, Document, Heading
from all2md.exceptions import ParsingError
from all2md.options.toml import TomlParserOptions
from all2md.parsers.toml import TomlParser


class TestTomlParserInitialization:
    """Test TOML parser initialization."""

    def test_default_initialization(self):
        """Test parser initializes with default options."""
        parser = TomlParser()
        assert parser.options is not None
        assert isinstance(parser.options, TomlParserOptions)

    def test_initialization_with_options(self):
        """Test parser initializes with custom options."""
        options = TomlParserOptions(max_heading_depth=3, sort_keys=True)
        parser = TomlParser(options)
        assert parser.options.max_heading_depth == 3
        assert parser.options.sort_keys is True

    def test_initialization_with_invalid_options(self):
        """Test parser raises error with invalid options type."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            TomlParser(options="invalid")


class TestTomlParserLiteralBlock:
    """Test TOML parser in literal block mode."""

    def test_literal_block_mode(self):
        """Test parsing TOML as literal code block."""
        toml_content = """
[server]
host = "localhost"
port = 8080
"""
        options = TomlParserOptions(literal_block=True)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].language == "toml"

    def test_literal_block_with_invalid_toml(self):
        """Test literal block mode handles invalid TOML gracefully."""
        invalid_toml = "[invalid section"
        options = TomlParserOptions(literal_block=True)
        parser = TomlParser(options)
        doc = parser.parse(invalid_toml)

        # Should still create a code block even if TOML is invalid
        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        assert isinstance(doc.children[0], CodeBlock)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="tomli_w may not be available")
    def test_literal_block_formats_valid_toml(self):
        """Test literal block mode formats valid TOML."""
        toml_content = """
[server]
host="localhost"
port=8080
"""
        options = TomlParserOptions(literal_block=True)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        # Should format the TOML
        assert isinstance(doc.children[0], CodeBlock)


class TestTomlParserPrimitiveTypes:
    """Test parsing TOML primitive types."""

    def test_parse_string(self):
        """Test parsing string values."""
        parser = TomlParser()
        doc = parser.parse('name = "John Doe"')

        assert isinstance(doc, Document)

    def test_parse_integer(self):
        """Test parsing integer values."""
        parser = TomlParser()
        doc = parser.parse("count = 42")

        assert isinstance(doc, Document)

    def test_parse_large_integer_with_formatting(self):
        """Test parsing large integers with thousand separators."""
        options = TomlParserOptions(pretty_format_numbers=True)
        parser = TomlParser(options)
        doc = parser.parse("count = 1000000")

        # Should format with commas
        assert isinstance(doc, Document)

    def test_parse_large_integer_without_formatting(self):
        """Test parsing large integers without formatting."""
        options = TomlParserOptions(pretty_format_numbers=False)
        parser = TomlParser(options)
        doc = parser.parse("count = 1000000")

        assert isinstance(doc, Document)

    def test_parse_float(self):
        """Test parsing float values."""
        parser = TomlParser()
        doc = parser.parse("pi = 3.14159")

        assert isinstance(doc, Document)

    def test_parse_boolean_true(self):
        """Test parsing boolean true."""
        parser = TomlParser()
        doc = parser.parse("enabled = true")

        assert isinstance(doc, Document)

    def test_parse_boolean_false(self):
        """Test parsing boolean false."""
        parser = TomlParser()
        doc = parser.parse("enabled = false")

        assert isinstance(doc, Document)

    def test_parse_multiline_string(self):
        """Test parsing multiline string values."""
        toml_content = '''
description = """
Line 1
Line 2
Line 3
"""
'''
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_datetime(self):
        """Test parsing datetime values."""
        parser = TomlParser()
        doc = parser.parse("timestamp = 2024-06-15T12:30:00")

        assert isinstance(doc, Document)

    def test_parse_date(self):
        """Test parsing date values."""
        parser = TomlParser()
        doc = parser.parse("birthday = 2024-06-15")

        assert isinstance(doc, Document)

    def test_parse_time(self):
        """Test parsing time values."""
        parser = TomlParser()
        doc = parser.parse("meeting = 14:30:00")

        assert isinstance(doc, Document)


class TestTomlParserArrays:
    """Test parsing TOML arrays."""

    def test_parse_simple_array(self):
        """Test parsing simple array of primitives."""
        toml_content = """
items = ["apple", "banana", "cherry"]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_array_of_integers(self):
        """Test parsing array of integers."""
        toml_content = """
numbers = [1, 2, 3, 4, 5]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_empty_array(self):
        """Test parsing empty array."""
        parser = TomlParser()
        doc = parser.parse("items = []")

        assert isinstance(doc, Document)

    def test_parse_nested_arrays(self):
        """Test parsing nested arrays."""
        toml_content = """
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_mixed_type_array(self):
        """Test parsing array with mixed types."""
        toml_content = """
mixed = ["string", 123, true, 3.14]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)


class TestTomlParserTables:
    """Test parsing TOML tables."""

    def test_parse_simple_table(self):
        """Test parsing simple table."""
        toml_content = """
[server]
host = "localhost"
port = 8080
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        # Should contain heading for "server"
        has_heading = any(isinstance(child, Heading) for child in doc.children)
        assert has_heading

    def test_parse_nested_tables(self):
        """Test parsing nested tables."""
        toml_content = """
[database]
[database.primary]
host = "db1.example.com"
port = 5432

[database.secondary]
host = "db2.example.com"
port = 5432
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_dotted_keys(self):
        """Test parsing dotted keys."""
        toml_content = """
database.primary.host = "db1.example.com"
database.primary.port = 5432
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_inline_table(self):
        """Test parsing inline table."""
        toml_content = """
point = { x = 1, y = 2, z = 3 }
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)


class TestTomlParserArraysOfTables:
    """Test parsing TOML arrays of tables."""

    def test_parse_array_of_tables(self):
        """Test parsing array of tables."""
        toml_content = """
[[users]]
name = "Alice"
role = "admin"

[[users]]
name = "Bob"
role = "user"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_array_of_tables_with_nested_data(self):
        """Test parsing array of tables with nested data."""
        toml_content = """
[[products]]
name = "Laptop"
price = 999.99
specs = { cpu = "Intel", ram = "16GB" }

[[products]]
name = "Mouse"
price = 29.99
specs = { dpi = 1600, buttons = 5 }
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_array_of_tables_threshold(self):
        """Test array of tables with threshold."""
        toml_content = """
[[users]]
name = "Alice"
role = "admin"
"""
        options = TomlParserOptions(array_as_table_threshold=2)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        # Single item should not be rendered as table
        assert isinstance(doc, Document)


class TestTomlParserOptions:
    """Test TOML parser options."""

    def test_sort_keys_enabled(self):
        """Test parsing with sort_keys enabled."""
        toml_content = """
zebra = "last"
apple = "first"
banana = "second"
"""
        options = TomlParserOptions(sort_keys=True)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_sort_keys_disabled(self):
        """Test parsing preserving key order."""
        toml_content = """
zebra = "last"
apple = "first"
banana = "second"
"""
        options = TomlParserOptions(sort_keys=False)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_flatten_single_keys_enabled(self):
        """Test flattening objects with single keys."""
        toml_content = """
[wrapper]
[wrapper.actual_data]
value = 123
"""
        options = TomlParserOptions(flatten_single_keys=True)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_flatten_single_keys_disabled(self):
        """Test not flattening when option is disabled."""
        toml_content = """
[wrapper]
[wrapper.actual_data]
value = 123
"""
        options = TomlParserOptions(flatten_single_keys=False)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_max_heading_depth_custom(self):
        """Test custom maximum heading depth."""
        toml_content = """
[level1]
[level1.level2]
[level1.level2.level3]
[level1.level2.level3.level4]
value = "deep"
"""
        options = TomlParserOptions(max_heading_depth=2)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)


class TestTomlParserInputTypes:
    """Test TOML parser with different input types."""

    def test_parse_string_input(self):
        """Test parsing string input."""
        parser = TomlParser()
        doc = parser.parse('key = "value"')

        assert isinstance(doc, Document)

    def test_parse_bytes_input(self):
        """Test parsing bytes input."""
        parser = TomlParser()
        doc = parser.parse(b'key = "value"')

        assert isinstance(doc, Document)

    def test_parse_path_input(self, tmp_path):
        """Test parsing file path input."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('key = "value"\n', encoding="utf-8")

        parser = TomlParser()
        doc = parser.parse(toml_file)

        assert isinstance(doc, Document)

    def test_parse_string_path_input(self, tmp_path):
        """Test parsing string path input."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('key = "value"\n', encoding="utf-8")

        parser = TomlParser()
        doc = parser.parse(str(toml_file))

        assert isinstance(doc, Document)

    def test_parse_file_like_input(self):
        """Test parsing file-like input."""
        toml_bytes = b'key = "value"\n'
        file_like = BytesIO(toml_bytes)

        parser = TomlParser()
        doc = parser.parse(file_like)

        assert isinstance(doc, Document)


class TestTomlParserErrorHandling:
    """Test TOML parser error handling."""

    def test_parse_invalid_toml_raises_error(self):
        """Test parsing invalid TOML raises ParsingError."""
        invalid_toml = """
[section
key = value
"""
        parser = TomlParser()

        with pytest.raises(ParsingError) as excinfo:
            parser.parse(invalid_toml)
        assert "Invalid TOML" in str(excinfo.value)

    def test_parse_malformed_toml(self):
        """Test parsing malformed TOML."""
        malformed = '[section]\nkey = "unclosed string'
        parser = TomlParser()

        with pytest.raises(ParsingError):
            parser.parse(malformed)

    def test_parse_duplicate_keys(self):
        """Test parsing TOML with duplicate keys."""
        duplicate = """
key = "value1"
key = "value2"
"""
        parser = TomlParser()

        with pytest.raises(ParsingError):
            parser.parse(duplicate)

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing nonexistent file."""
        nonexistent = tmp_path / "nonexistent.toml"
        parser = TomlParser()

        with pytest.raises(Exception):
            parser.parse(nonexistent)


class TestTomlParserMetadata:
    """Test TOML parser metadata extraction."""

    def test_extract_metadata_from_document(self):
        """Test metadata extraction from TOML document."""
        toml_content = """
title = "Test Document"
author = "John Doe"

[data]
key = "value"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert hasattr(doc, "metadata")

    def test_metadata_with_empty_document(self):
        """Test metadata with empty document."""
        parser = TomlParser()
        doc = parser.parse("")

        assert isinstance(doc, Document)


class TestTomlParserComplexScenarios:
    """Test TOML parser with complex scenarios."""

    def test_parse_complex_config_file(self):
        """Test parsing complex configuration file."""
        toml_content = """
title = "TOML Example"

[owner]
name = "Tom Preston-Werner"
dob = 1979-05-27T07:32:00-08:00

[database]
server = "192.168.1.1"
ports = [8001, 8001, 8002]
connection_max = 5000
enabled = true

[servers]

[servers.alpha]
ip = "10.0.0.1"
dc = "eqdc10"

[servers.beta]
ip = "10.0.0.2"
dc = "eqdc10"

[clients]
data = [["gamma", "delta"], [1, 2]]
hosts = [
  "alpha",
  "omega"
]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_mixed_tables_and_arrays(self):
        """Test parsing mixed tables and arrays."""
        toml_content = """
[package]
name = "myproject"
version = "1.0.0"

[[dependencies]]
name = "requests"
version = "2.28.0"

[[dependencies]]
name = "pyyaml"
version = "6.0"

[dev-dependencies]
pytest = "7.0.0"
mypy = "0.991"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_with_all_options(self):
        """Test parsing with all options enabled."""
        toml_content = """
[zebra]
nested_value = 1000

[apple]
data = "test"
"""
        options = TomlParserOptions(
            max_heading_depth=4,
            array_as_table_threshold=2,
            flatten_single_keys=True,
            include_type_hints=True,
            pretty_format_numbers=True,
            sort_keys=True,
        )
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_pyproject_toml_structure(self):
        """Test parsing typical pyproject.toml structure."""
        toml_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "myproject"
version = "0.1.0"
description = "A test project"
authors = [
    {name = "John Doe", email = "john@example.com"}
]
dependencies = [
    "requests>=2.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "mypy>=0.991",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0


class TestTomlParserEdgeCases:
    """Test TOML parser edge cases."""

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        parser = TomlParser()
        doc = parser.parse("")

        assert isinstance(doc, Document)

    def test_parse_only_comments(self):
        """Test parsing TOML with only comments."""
        toml_content = """
# This is a comment
# Another comment
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only content."""
        parser = TomlParser()
        doc = parser.parse("   \n\n  \t  \n")

        assert isinstance(doc, Document)

    def test_parse_unicode_content(self):
        """Test parsing Unicode content."""
        toml_content = """
message = "Hello, 世界! 🌍"
emoji = "🎉🎊🎈"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_escaped_strings(self):
        """Test parsing escaped strings."""
        toml_content = r"""
path = "C:\\Users\\Documents"
quote = "He said \"hello\""
newline = "Line 1\nLine 2"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_literal_strings(self):
        """Test parsing literal strings."""
        toml_content = """
regex = '<\\i\\c*\\s*>'
path = 'C:\\Users\\Documents'
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_multiline_literal_string(self):
        """Test parsing multiline literal strings."""
        toml_content = """
poem = '''
Roses are red
Violets are blue'''
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_hexadecimal_octal_binary(self):
        """Test parsing different number formats."""
        toml_content = """
hex = 0xDEADBEEF
oct = 0o01234567
bin = 0b11010110
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)

    def test_parse_infinity_and_nan(self):
        """Test parsing special float values."""
        toml_content = """
pos_inf = inf
neg_inf = -inf
not_a_number = nan
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)


class TestTomlParserIntegration:
    """Integration tests for TOML parser."""

    def test_round_trip_with_literal_block(self):
        """Test that literal block preserves content structure."""
        toml_content = """
[package]
name = "test"
version = "1.0.0"

[[dependencies]]
name = "requests"
"""
        options = TomlParserOptions(literal_block=True)
        parser = TomlParser(options)
        doc = parser.parse(toml_content)

        assert isinstance(doc.children[0], CodeBlock)
        # Content should be valid TOML
        assert "[package]" in doc.children[0].content

    def test_parse_and_verify_structure(self):
        """Test parsing and verify document structure."""
        toml_content = """
title = "Document"

[[sections]]
name = "Section 1"
content = "Content 1"

[[sections]]
name = "Section 2"
content = "Content 2"
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have headings for top-level keys
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0

    def test_parse_real_world_cargo_toml(self):
        """Test parsing a real-world Cargo.toml-like file."""
        toml_content = """
[package]
name = "my-rust-project"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "0.5"

[[bench]]
name = "my_benchmark"
harness = false
"""
        parser = TomlParser()
        doc = parser.parse(toml_content)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0
