#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Integration tests for structured data formats (JSON, YAML, TOML, INI)."""

import json

import pytest

from all2md.parsers.ini import IniParser
from all2md.parsers.json import JsonParser
from all2md.parsers.toml import TomlParser
from all2md.parsers.yaml import YamlParser
from all2md.renderers.ini import IniRenderer
from all2md.renderers.json import JsonRenderer
from all2md.renderers.toml import TomlRenderer
from all2md.renderers.yaml import YamlRenderer


class TestRoundTripConversion:
    """Test round-trip conversion: format → AST → format."""

    def test_json_round_trip(self):
        """Test JSON → AST → JSON preserves data."""
        original = {
            "server": {"host": "localhost", "port": 8080},
            "users": [{"name": "Alice", "age": 30, "active": True}, {"name": "Bob", "age": 25, "active": False}],
        }

        # Parse
        parser = JsonParser()
        doc = parser.parse(json.dumps(original))

        # Render
        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)
        result = json.loads(result_str)

        # Verify structure
        assert "users" in result
        assert len(result["users"]) == 2
        assert result["users"][0]["name"] == "Alice"
        assert result["users"][0]["age"] == 30
        assert result["users"][0]["active"] is True

    def test_yaml_round_trip(self):
        """Test YAML → AST → YAML preserves data."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        original_yaml = """
server:
  host: localhost
  port: 8080
users:
  - name: Alice
    age: 30
    active: true
  - name: Bob
    age: 25
    active: false
        """

        # Parse
        parser = YamlParser()
        doc = parser.parse(original_yaml)

        # Render
        renderer = YamlRenderer()
        result_str = renderer.render_to_string(doc)

        # Parse result to verify
        import yaml

        result = yaml.safe_load(result_str)

        assert "users" in result
        assert len(result["users"]) == 2
        assert result["users"][0]["name"] == "Alice"

    def test_toml_round_trip(self):
        """Test TOML → AST → TOML preserves data."""
        pytest.importorskip("tomli_w", reason="tomli_w not installed")
        original_toml = """
[server]
host = "localhost"
port = 8080

[[users]]
name = "Alice"
age = 30
active = true

[[users]]
name = "Bob"
age = 25
active = false
        """

        # Parse
        parser = TomlParser()
        doc = parser.parse(original_toml)

        # Render
        renderer = TomlRenderer()
        result_str = renderer.render_to_string(doc)

        # Parse result to verify
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        result = tomllib.loads(result_str)

        assert "users" in result
        assert len(result["users"]) == 2
        assert result["users"][0]["name"] == "Alice"

    def test_ini_round_trip(self):
        """Test INI → AST → INI preserves data."""
        original_ini = """
[server]
host = localhost
port = 8080

[database]
name = mydb
timeout = 30
        """

        # Parse
        parser = IniParser()
        doc = parser.parse(original_ini)

        # Render
        renderer = IniRenderer()
        result_str = renderer.render_to_string(doc)

        # Parse result to verify
        import configparser

        result = configparser.ConfigParser()
        result.read_string(result_str)

        assert result.has_section("server")
        assert result.get("server", "host") == "localhost"
        assert result.get("server", "port") == "8080"


class TestCrossFormatConversion:
    """Test converting between different formats."""

    def test_json_to_yaml(self):
        """Test converting JSON to YAML via AST."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        json_str = '{"name": "John", "age": 30}'

        # Parse JSON
        json_parser = JsonParser()
        doc = json_parser.parse(json_str)

        # Render as YAML
        yaml_renderer = YamlRenderer()
        yaml_str = yaml_renderer.render_to_string(doc)

        # Verify YAML is valid
        import yaml

        result = yaml.safe_load(yaml_str)
        assert isinstance(result, dict)

    def test_yaml_to_json(self):
        """Test converting YAML to JSON via AST."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        yaml_str = "name: John\nage: 30"

        # Parse YAML
        yaml_parser = YamlParser()
        doc = yaml_parser.parse(yaml_str)

        # Render as JSON
        json_renderer = JsonRenderer()
        json_str = json_renderer.render_to_string(doc)

        # Verify JSON is valid
        result = json.loads(json_str)
        assert isinstance(result, dict)

    def test_toml_to_json(self):
        """Test converting TOML to JSON via AST."""
        pytest.importorskip("tomli_w", reason="tomli_w not installed")
        toml_str = '[section]\nkey = "value"'

        # Parse TOML
        toml_parser = TomlParser()
        doc = toml_parser.parse(toml_str)

        # Render as JSON
        json_renderer = JsonRenderer()
        json_str = json_renderer.render_to_string(doc)

        # Verify JSON is valid
        result = json.loads(json_str)
        assert isinstance(result, dict)

    def test_ini_to_json(self):
        """Test converting INI to JSON via AST."""
        ini_str = "[section]\nkey = value"

        # Parse INI
        ini_parser = IniParser()
        doc = ini_parser.parse(ini_str)

        # Render as JSON
        json_renderer = JsonRenderer()
        json_str = json_renderer.render_to_string(doc)

        # Verify JSON is valid
        result = json.loads(json_str)
        assert isinstance(result, dict)


class TestComplexDataStructures:
    """Test handling complex data structures across formats."""

    def test_deeply_nested_json(self):
        """Test deeply nested JSON structures."""
        nested = {"level1": {"level2": {"level3": {"level4": {"level5": {"value": "deep"}}}}}}

        parser = JsonParser()
        doc = parser.parse(json.dumps(nested))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)
        result = json.loads(result_str)

        # Should handle deep nesting
        assert isinstance(result, dict)

    def test_large_table(self):
        """Test handling large tables."""
        users = [{"id": i, "name": f"User{i}", "active": i % 2 == 0} for i in range(100)]
        data = {"users": users}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)
        result = json.loads(result_str)

        assert "users" in result
        assert len(result["users"]) == 100

    def test_mixed_array_types(self):
        """Test arrays with mixed primitive types."""
        data = {"values": [1, "two", 3.14, True, None]}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        # Should handle mixed types gracefully
        assert doc is not None

    def test_unicode_content(self):
        """Test Unicode content across formats."""
        data = {"chinese": "你好世界", "emoji": "🎉🎊", "greek": "Γεια σου κόσμε", "arabic": "مرحبا بالعالم"}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data, ensure_ascii=False))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)
        result = json.loads(result_str)

        # Unicode should be preserved
        assert isinstance(result, dict)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_structures(self):
        """Test empty objects and arrays."""
        data = {"empty_obj": {}, "empty_arr": [], "null": None}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        # Should handle empty structures
        assert doc is not None

    def test_single_value_arrays(self):
        """Test arrays with single values."""
        data = {"single": [{"key": "value"}]}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)

        # Should handle single-item arrays
        assert result_str

    def test_special_characters_in_keys(self):
        """Test special characters in object keys."""
        data = {"key-with-dash": 1, "key.with.dots": 2, "key_with_underscore": 3, "key with spaces": 4}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)

        # Should handle special characters
        assert result_str

    def test_numeric_string_keys(self):
        """Test numeric strings as keys."""
        data = {"123": "numeric key", "456": "another"}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        # Should treat as strings
        assert doc is not None

    def test_very_long_strings(self):
        """Test very long string values."""
        long_text = "x" * 10000
        data = {"long": long_text}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        # Should handle long strings
        assert doc is not None


class TestFormatSpecificFeatures:
    """Test format-specific features."""

    def test_json_null_support(self):
        """Test JSON null value support."""
        data = {"value": None}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)
        result = json.loads(result_str)

        # JSON supports null
        assert "value" in result or result == {}

    def test_yaml_date_support(self):
        """Test YAML date/time support."""
        pytest.importorskip("yaml", reason="pyyaml not installed")
        yaml_str = "date: 2025-01-15\ntime: 14:30:00"

        parser = YamlParser()
        doc = parser.parse(yaml_str)

        # Should handle dates
        assert doc is not None

    def test_toml_no_null(self):
        """Test TOML does not support null."""
        pytest.importorskip("tomli_w", reason="tomli_w not installed")
        # TOML doesn't have null values
        toml_str = '[section]\nkey = "value"'

        parser = TomlParser()
        doc = parser.parse(toml_str)

        # Should work without null
        assert doc is not None

    def test_ini_flat_structure(self):
        """Test INI flat structure (no nesting)."""
        ini_str = "[section]\nkey1 = value1\nkey2 = value2"

        parser = IniParser()
        doc = parser.parse(ini_str)

        renderer = IniRenderer()
        result_str = renderer.render_to_string(doc)

        # Should maintain flat structure
        assert "[section]" in result_str


class TestPerformance:
    """Test performance with larger datasets."""

    def test_large_document_json(self):
        """Test handling large JSON documents."""
        # Create a large structure
        data = {"items": [{"id": i, "value": f"item_{i}"} for i in range(1000)]}

        parser = JsonParser()
        doc = parser.parse(json.dumps(data))

        renderer = JsonRenderer()
        result_str = renderer.render_to_string(doc)

        # Should complete without errors
        result = json.loads(result_str)
        assert "items" in result
        assert len(result["items"]) == 1000

    def test_many_sections_ini(self):
        """Test INI with many sections."""
        # Create INI with many sections
        ini_parts = [f"[section{i}]\nkey = value{i}\n" for i in range(100)]
        ini_str = "\n".join(ini_parts)

        parser = IniParser()
        doc = parser.parse(ini_str)

        renderer = IniRenderer()
        result_str = renderer.render_to_string(doc)

        # Should handle many sections
        assert result_str
        assert "[section0]" in result_str
        assert "[section99]" in result_str
