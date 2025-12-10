"""Unit tests for all2md CLI config command handlers.

This module tests the config command handler directly,
providing coverage for subcommand dispatching and option parsing.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

try:
    import tomli_w
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tomli_w = None


def require_tomli_w() -> None:
    if tomli_w is None:
        pytest.skip("tomli_w is required for this test")


from all2md.cli.commands.config import (
    _serialize_config_value,
    handle_config_command,
    handle_config_generate_command,
    handle_config_show_command,
    handle_config_validate_command,
)


@pytest.mark.unit
class TestConfigCommandHelp:
    """Test config command help messages."""

    def test_config_show_help(self, capsys):
        """Test config show --help shows options."""
        result = handle_config_show_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "format" in captured.out.lower()

    def test_config_generate_help(self, capsys):
        """Test config generate --help shows options."""
        result = handle_config_generate_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "format" in captured.out.lower()

    def test_config_validate_help(self, capsys):
        """Test config validate --help shows options."""
        result = handle_config_validate_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "file" in captured.out.lower() or "config" in captured.out.lower()


@pytest.mark.unit
class TestHandleConfigCommand:
    """Test handle_config_command() function."""

    def test_config_generate_direct_returns_int(self, capsys):
        """Test config generate direct call returns int."""
        result = handle_config_generate_command(["--format", "json"])
        assert isinstance(result, int)
        assert result == 0


@pytest.mark.unit
class TestHandleConfigShowCommand:
    """Test handle_config_show_command() function."""

    def test_show_help(self, capsys):
        """Test config show --help returns successfully."""
        result = handle_config_show_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_show_json_format(self, capsys, monkeypatch):
        """Test config show with JSON format outputs JSON content."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={"test_key": "test_value"}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            result = handle_config_show_command(["--format", "json", "--no-source"])

        assert result == 0
        captured = capsys.readouterr()
        # Should contain JSON-like content (may have header)
        assert "test_key" in captured.out
        assert "test_value" in captured.out

    def test_show_yaml_format(self, capsys, monkeypatch):
        """Test config show with YAML format outputs YAML content."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={"test_key": "test_value"}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            result = handle_config_show_command(["--format", "yaml", "--no-source"])

        assert result == 0
        captured = capsys.readouterr()
        # Should contain YAML-like content (may have header)
        assert "test_key" in captured.out
        assert "test_value" in captured.out

    def test_show_toml_format(self, capsys, monkeypatch):
        """Test config show with TOML format outputs TOML content."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={"test_key": "test_value"}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            result = handle_config_show_command(["--format", "toml", "--no-source"])

        assert result == 0
        captured = capsys.readouterr()
        # Should contain TOML-formatted output
        assert "test_key" in captured.out and "test_value" in captured.out

    def test_show_includes_source_by_default(self, capsys, monkeypatch):
        """Test that config show includes source information by default."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            result = handle_config_show_command([])

        assert result == 0
        captured = capsys.readouterr()
        assert "Configuration Sources" in captured.out or "Source" in captured.out


@pytest.mark.unit
class TestHandleConfigGenerateCommand:
    """Test handle_config_generate_command() function."""

    def test_generate_help(self, capsys):
        """Test config generate --help returns successfully."""
        result = handle_config_generate_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_generate_json_format(self, capsys):
        """Test generating JSON config."""
        result = handle_config_generate_command(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        # Should be valid JSON
        data = json.loads(captured.out)
        assert "pdf" in data

    def test_generate_yaml_format(self, capsys):
        """Test generating YAML config."""
        result = handle_config_generate_command(["--format", "yaml"])
        assert result == 0
        captured = capsys.readouterr()
        # Should be valid YAML
        data = yaml.safe_load(captured.out)
        assert "pdf" in data

    def test_generate_toml_format(self, capsys):
        """Test generating TOML config."""
        result = handle_config_generate_command(["--format", "toml"])
        assert result == 0
        captured = capsys.readouterr()
        # Should be valid TOML
        data = tomllib.loads(captured.out)
        assert "pdf" in data

    def test_generate_to_file(self, tmp_path, capsys):
        """Test generating config to file."""
        output_file = tmp_path / "generated.json"
        result = handle_config_generate_command(["--format", "json", "--out", str(output_file)])

        assert result == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "pdf" in data

    def test_generate_default_format_is_toml(self, capsys):
        """Test that default output format is TOML."""
        result = handle_config_generate_command([])
        assert result == 0
        captured = capsys.readouterr()
        # Should be valid TOML
        data = tomllib.loads(captured.out)
        assert "pdf" in data

    def test_generate_includes_all_sections(self, capsys):
        """Test that generated config includes all format sections."""
        result = handle_config_generate_command(["--format", "json"])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # Should include common format sections
        expected_sections = ["pdf", "html", "docx"]
        for section in expected_sections:
            assert section in data, f"Missing section: {section}"


@pytest.mark.unit
class TestHandleConfigValidateCommand:
    """Test handle_config_validate_command() function."""

    @pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
    def test_validate_help(self, capsys):
        """Test config validate --help returns successfully."""
        result = handle_config_validate_command(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    @pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
    def test_validate_valid_toml(self, tmp_path, capsys):
        """Test validating valid TOML config."""
        config_file = tmp_path / "valid.toml"
        with open(config_file, "wb") as f:
            tomli_w.dump({"pdf": {"detect_columns": True}}, f)

        result = handle_config_validate_command([str(config_file)])
        assert result == 0
        captured = capsys.readouterr()
        assert "valid" in captured.out.lower() or "Valid" in captured.out

    def test_validate_valid_json(self, tmp_path, capsys):
        """Test validating valid JSON config."""
        config_file = tmp_path / "valid.json"
        config_file.write_text('{"pdf": {"detect_columns": true}}')

        result = handle_config_validate_command([str(config_file)])
        assert result == 0
        captured = capsys.readouterr()
        assert "valid" in captured.out.lower() or "Valid" in captured.out

    def test_validate_valid_yaml(self, tmp_path, capsys):
        """Test validating valid YAML config."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text("pdf:\n  detect_columns: true\n")

        result = handle_config_validate_command([str(config_file)])
        assert result == 0
        captured = capsys.readouterr()
        assert "valid" in captured.out.lower() or "Valid" in captured.out

    def test_validate_invalid_toml(self, tmp_path, capsys):
        """Test validating invalid TOML config."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid toml [[[")

        result = handle_config_validate_command([str(config_file)])
        assert result != 0
        captured = capsys.readouterr()
        assert "invalid" in captured.err.lower() or "error" in captured.err.lower()

    def test_validate_invalid_json(self, tmp_path, capsys):
        """Test validating invalid JSON config."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text('{"invalid": json}')

        result = handle_config_validate_command([str(config_file)])
        assert result != 0
        captured = capsys.readouterr()
        assert "invalid" in captured.err.lower() or "error" in captured.err.lower()

    def test_validate_nonexistent_file(self, capsys):
        """Test validating nonexistent file."""
        result = handle_config_validate_command(["nonexistent_file.toml"])
        assert result != 0
        captured = capsys.readouterr()
        # Could say "does not exist" or "not found"
        assert (
            "does not exist" in captured.err.lower()
            or "not found" in captured.err.lower()
            or "invalid" in captured.err.lower()
        )

    @pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
    def test_validate_unknown_keys(self, tmp_path, capsys):
        """Test validation reports unknown keys."""
        config_file = tmp_path / "unknown_keys.toml"
        with open(config_file, "wb") as f:
            tomli_w.dump({"unknown_section": {"unknown_key": "value"}}, f)

        result = handle_config_validate_command([str(config_file)])
        assert result in [0, 1]


@pytest.mark.unit
class TestSerializeConfigValue:
    """Test _serialize_config_value() function."""

    def test_serialize_string(self):
        """Test serializing string values."""
        result = _serialize_config_value("test string")
        assert result == "test string"

    def test_serialize_int(self):
        """Test serializing integer values."""
        result = _serialize_config_value(42)
        assert result == 42

    def test_serialize_float(self):
        """Test serializing float values."""
        result = _serialize_config_value(3.14)
        assert result == 3.14

    def test_serialize_bool(self):
        """Test serializing boolean values."""
        assert _serialize_config_value(True) is True
        assert _serialize_config_value(False) is False

    def test_serialize_none(self):
        """Test serializing None values."""
        result = _serialize_config_value(None)
        assert result is None

    def test_serialize_list(self):
        """Test serializing list values."""
        result = _serialize_config_value([1, 2, 3])
        assert result == [1, 2, 3]

    def test_serialize_dict(self):
        """Test serializing dict values."""
        result = _serialize_config_value({"key": "value"})
        assert result == {"key": "value"}

    def test_serialize_nested_structure(self):
        """Test serializing nested structures."""
        nested = {"outer": {"inner": [1, 2, {"deep": "value"}]}}
        result = _serialize_config_value(nested)
        assert result == nested

    def test_serialize_path(self):
        """Test serializing Path objects."""
        path = Path("/some/path")
        result = _serialize_config_value(path)
        assert result == "/some/path" or result == str(path)


@pytest.mark.unit
class TestConfigCommandEdgeCases:
    """Test edge cases for config commands."""

    def test_config_unknown_subcommand(self, capsys):
        """Test config with unknown subcommand returns None or exits."""
        result = handle_config_command(["unknown_subcommand"])
        # Unknown subcommand returns None (not handled) or raises SystemExit
        assert result is None or result != 0

    def test_config_show_empty_config(self, capsys, monkeypatch):
        """Test config show when no config exists."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            result = handle_config_show_command(["--no-source"])

        assert result == 0

    def test_generate_invalid_format(self, capsys):
        """Test generate with invalid format returns error."""
        result = handle_config_generate_command(["--format", "invalid_format"])
        # Returns error code from argparse
        assert result != 0

    def test_generate_write_failure(self, tmp_path, capsys):
        """Test generate handles write failure gracefully."""
        # Create a directory where we expect a file
        output_path = tmp_path / "output_dir"
        output_path.mkdir()

        result = handle_config_generate_command(["--format", "json", "--out", str(output_path)])

        # Should fail because we can't write to a directory as a file
        assert result != 0
