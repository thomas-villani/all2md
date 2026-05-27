"""Unit tests for all2md CLI configuration management.

This module tests the configuration system including file discovery, loading,
presets, and priority handling.
"""

import json
import tempfile
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


from all2md.cli.commands.config import handle_config_generate_command, handle_config_show_command
from all2md.cli.config import (
    _load_pyproject_all2md_section,
    discover_config_file,
    find_config_in_parents,
    get_config_search_paths,
    load_config_file,
    load_config_with_priority,
    merge_configs,
)
from all2md.cli.presets import (
    apply_preset,
    get_preset_config,
    get_preset_description,
    get_preset_names,
    list_presets,
)


@pytest.mark.unit
@pytest.mark.cli
class TestConfigDiscovery:
    """Test configuration file discovery functionality."""

    def test_discover_config_in_cwd(self):
        """Test discovering config file in current working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config file in temp directory
            config_file = temp_path / ".all2md.toml"
            config_file.write_text("[pdf]\ndetect_columns = true")

            # Mock cwd to return temp directory
            with patch("pathlib.Path.cwd", return_value=temp_path):
                discovered = discover_config_file()

                assert discovered is not None
                assert discovered.resolve() == config_file.resolve()
                assert discovered.exists()

    def test_discover_config_in_home(self):
        """Test discovering config file in home directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config file in temp directory (simulating home)
            config_file = temp_path / ".all2md.json"
            config_file.write_text('{"pdf": {"detect_columns": true}}')

            # Mock both cwd (empty) and home (has config)
            with patch("pathlib.Path.cwd", return_value=Path(tempfile.mkdtemp())):
                with patch("pathlib.Path.home", return_value=temp_path):
                    discovered = discover_config_file()

                    assert discovered is not None
                    assert discovered == config_file

    def test_discover_config_prefers_toml_over_json(self):
        """Test that TOML files are preferred over JSON when both exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create both config files
            toml_file = temp_path / ".all2md.toml"
            json_file = temp_path / ".all2md.json"
            toml_file.write_text("[pdf]\ndetect_columns = true")
            json_file.write_text('{"pdf": {"detect_columns": false}}')

            with patch("pathlib.Path.cwd", return_value=temp_path):
                discovered = discover_config_file()

                # Should prefer TOML
                assert discovered.resolve() == toml_file.resolve()

    def test_discover_config_prefers_cwd_over_home(self):
        """Test that current directory config takes precedence over home."""
        with tempfile.TemporaryDirectory() as cwd_dir:
            with tempfile.TemporaryDirectory() as home_dir:
                cwd_path = Path(cwd_dir)
                home_path = Path(home_dir)

                # Create config in both locations
                cwd_config = cwd_path / ".all2md.toml"
                home_config = home_path / ".all2md.toml"
                cwd_config.write_text("[pdf]\ndetect_columns = true")
                home_config.write_text("[pdf]\ndetect_columns = false")

                with patch("pathlib.Path.cwd", return_value=cwd_path):
                    with patch("pathlib.Path.home", return_value=home_path):
                        discovered = discover_config_file()

                        # Should use cwd config
                        assert discovered.resolve() == cwd_config.resolve()

    def test_discover_config_returns_none_when_not_found(self):
        """Test that None is returned when no config file exists."""
        with tempfile.TemporaryDirectory() as cwd_dir:
            with tempfile.TemporaryDirectory() as home_dir:
                cwd_path = Path(cwd_dir)
                home_path = Path(home_dir)

                with patch("pathlib.Path.cwd", return_value=cwd_path):
                    with patch("pathlib.Path.home", return_value=home_path):
                        discovered = discover_config_file()

                        assert discovered is None

    def test_get_config_search_paths(self):
        """Test getting list of config search paths."""
        paths = get_config_search_paths()

        assert len(paths) == 9  # 5 in cwd + 4 in home

        # Should contain dedicated configs and pyproject.toml
        path_names = [p.name for p in paths]
        assert ".all2md.toml" in path_names
        assert ".all2md.yaml" in path_names
        assert ".all2md.yml" in path_names
        assert ".all2md.json" in path_names
        assert "pyproject.toml" in path_names


@pytest.mark.unit
@pytest.mark.cli
@pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
class TestPyprojectTomlSupport:
    """Test pyproject.toml configuration support."""

    def test_load_pyproject_with_tool_section(self):
        """Test loading pyproject.toml with [tool.all2md] section."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            pyproject_file = temp_path / "pyproject.toml"
            config_data = {
                "project": {"name": "test-project"},
                "tool": {
                    "all2md": {
                        "attachment_mode": "download",
                        "pdf": {"detect_columns": True},
                    }
                },
            }

            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            loaded = _load_pyproject_all2md_section(pyproject_file)

            assert loaded["attachment_mode"] == "download"
            assert loaded["pdf"]["detect_columns"] is True

    def test_load_pyproject_without_tool_section(self):
        """Test loading pyproject.toml without [tool.all2md] section."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"project": {"name": "test-project"}}

            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            loaded = _load_pyproject_all2md_section(pyproject_file)

            assert loaded == {}

    def test_load_config_file_pyproject(self):
        """Test load_config_file with pyproject.toml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            pyproject_file = temp_path / "pyproject.toml"
            config_data = {
                "tool": {
                    "all2md": {
                        "attachment_mode": "base64",
                    }
                }
            }

            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            loaded = load_config_file(pyproject_file)

            assert loaded["attachment_mode"] == "base64"

    def test_find_config_in_cwd(self):
        """Test finding pyproject.toml in current working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"tool": {"all2md": {"test": "value"}}}

            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            found = find_config_in_parents(start_dir=temp_path)

            assert found.resolve() == pyproject_file.resolve()

    def test_find_config_in_parent_directory(self):
        """Test finding pyproject.toml in parent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config in parent directory
            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"tool": {"all2md": {"test": "value"}}}

            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            # Create subdirectory and search from there
            subdir = temp_path / "src" / "mypackage"
            subdir.mkdir(parents=True)

            found = find_config_in_parents(start_dir=subdir)

            assert found.resolve() == pyproject_file.resolve()

    def test_dedicated_config_takes_precedence_over_pyproject(self):
        """Test that .all2md.toml takes precedence over pyproject.toml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create both files in same directory
            dedicated_config = temp_path / ".all2md.toml"
            with open(dedicated_config, "wb") as f:
                tomli_w.dump({"attachment_mode": "download"}, f)

            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"tool": {"all2md": {"attachment_mode": "skip"}}}
            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            found = find_config_in_parents(start_dir=temp_path)

            # Should find dedicated config, not pyproject.toml
            assert found.resolve() == dedicated_config.resolve()

    def test_search_stops_at_first_match(self):
        """Test that search stops at first config file found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config in parent
            parent_config = temp_path / "pyproject.toml"
            config_data = {"tool": {"all2md": {"test": "parent"}}}
            with open(parent_config, "wb") as f:
                tomli_w.dump(config_data, f)

            # Create config in subdirectory
            subdir = temp_path / "src"
            subdir.mkdir()
            subdir_config = subdir / "pyproject.toml"
            config_data = {"tool": {"all2md": {"test": "subdir"}}}
            with open(subdir_config, "wb") as f:
                tomli_w.dump(config_data, f)

            found = find_config_in_parents(start_dir=subdir)

            # Should find subdir config, not parent
            assert found.resolve() == subdir_config.resolve()

    def test_discover_config_finds_pyproject_in_parents(self):
        """Test discover_config_file finds pyproject.toml in parent dirs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create pyproject.toml in temp directory
            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"tool": {"all2md": {"test": "value"}}}
            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            # Create subdirectory
            subdir = temp_path / "src"
            subdir.mkdir()

            # Mock cwd to return subdirectory
            with patch("pathlib.Path.cwd", return_value=subdir):
                discovered = discover_config_file()

                assert discovered.resolve() == pyproject_file.resolve()

    def test_pyproject_without_all2md_section_is_skipped(self):
        """Test that pyproject.toml without [tool.all2md] is not used."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create pyproject.toml WITHOUT [tool.all2md] section
            pyproject_file = temp_path / "pyproject.toml"
            config_data = {"project": {"name": "test"}, "tool": {"other": {}}}
            with open(pyproject_file, "wb") as f:
                tomli_w.dump(config_data, f)

            found = find_config_in_parents(start_dir=temp_path)

            # Should not find config (no [tool.all2md] section)
            assert found is None

    def test_invalid_pyproject_is_skipped(self):
        """Test that invalid pyproject.toml is skipped during search."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid pyproject.toml
            pyproject_file = temp_path / "pyproject.toml"
            pyproject_file.write_text("invalid toml [[[")

            # Should not crash, just return None
            found = find_config_in_parents(start_dir=temp_path)
            assert found is None


@pytest.mark.unit
@pytest.mark.cli
@pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
class TestConfigLoading:
    """Test configuration file loading functionality."""

    def test_load_toml_config(self):
        """Test loading configuration from TOML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.toml"
            config_data = {
                "attachment_mode": "download",
                "pdf": {"detect_columns": True, "pages": [1, 2, 3]},
            }

            with open(config_file, "wb") as f:
                tomli_w.dump(config_data, f)

            loaded = load_config_file(config_file)

            assert loaded["attachment_mode"] == "download"
            assert loaded["pdf"]["detect_columns"] is True
            assert loaded["pdf"]["pages"] == [1, 2, 3]

    def test_load_json_config(self):
        """Test loading configuration from JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.json"
            config_data = {
                "attachment_mode": "skip",
                "pdf": {"detect_columns": False},
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            loaded = load_config_file(config_file)

            assert loaded["attachment_mode"] == "skip"
        assert loaded["pdf"]["detect_columns"] is False

    def test_load_config_auto_detects_format(self):
        """Test that config loader auto-detects file format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test TOML detection
            toml_file = temp_path / "test.toml"
            with open(toml_file, "wb") as f:
                tomli_w.dump({"test": "value"}, f)

            loaded = load_config_file(toml_file)
            assert loaded["test"] == "value"

            # Test JSON detection
            json_file = temp_path / "test.json"
            with open(json_file, "w") as f:
                json.dump({"test": "other"}, f)

            loaded = load_config_file(json_file)
            assert loaded["test"] == "other"


@pytest.mark.unit
@pytest.mark.cli
class TestConfigGenerateDefaults:
    """Validate default config generation."""

    def test_generate_config_json_defaults(self, capsys):
        exit_code = handle_config_generate_command(["--format", "json"])
        assert exit_code == 0

        output = capsys.readouterr().out
        data = json.loads(output)

        # Check for format sections
        assert "pdf" in data and "detect_columns" in data["pdf"]
        assert "archive" in data
        # Attachment mode is per-format now
        if "attachment_mode" in data.get("archive", {}):
            assert data["archive"]["attachment_mode"] in {"alt_text", "skip", "download", "base64"}

    def test_generate_config_toml_defaults(self, capsys):
        exit_code = handle_config_generate_command(["--format", "toml"])
        assert exit_code == 0

        output = capsys.readouterr().out
        data = tomllib.loads(output)

        # Check for format sections
        assert "pdf" in data and "detect_columns" in data["pdf"]
        assert "archive" in data
        # Attachment mode is per-format now
        if "attachment_mode" in data.get("archive", {}):
            assert data["archive"]["attachment_mode"] in {"alt_text", "skip", "download", "base64"}

    def test_generate_config_yaml_defaults(self, capsys):
        exit_code = handle_config_generate_command(["--format", "yaml"])
        assert exit_code == 0

        output = capsys.readouterr().out
        data = yaml.safe_load(output)

        # Check for format sections
        assert "pdf" in data and "detect_columns" in data["pdf"]
        assert "archive" in data
        # Attachment mode is per-format now
        if "attachment_mode" in data.get("archive", {}):
            assert data["archive"]["attachment_mode"] in {"alt_text", "skip", "download", "base64"}

    def test_load_config_invalid_file_raises_error(self):
        """Test that loading non-existent file raises error."""
        import argparse

        with pytest.raises(argparse.ArgumentTypeError) as exc_info:
            load_config_file("/nonexistent/config.toml")

        assert "does not exist" in str(exc_info.value)

    def test_load_yaml_config(self):
        """Test loading configuration from YAML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.yaml"
            config_data = {
                "attachment_mode": "base64",
                "pdf": {"detect_columns": True},
            }

            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            loaded = load_config_file(config_file)

            assert loaded["attachment_mode"] == "base64"
            assert loaded["pdf"]["detect_columns"] is True

    def test_load_config_invalid_toml_raises_error(self):
        """Test that invalid TOML syntax raises error."""
        import argparse

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.toml"
            config_file.write_text("invalid toml [[[")

            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                load_config_file(config_file)

            assert "Invalid TOML" in str(exc_info.value)

    def test_load_config_invalid_json_raises_error(self):
        """Test that invalid JSON syntax raises error."""
        import argparse

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.json"
            config_file.write_text('{"invalid": json}')

            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                load_config_file(config_file)

            assert "Invalid JSON" in str(exc_info.value)

    def test_load_config_invalid_yaml_raises_error(self):
        """Test that invalid YAML syntax raises error."""
        import argparse

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "config.yaml"
            config_file.write_text("invalid: yaml: [[[")

            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                load_config_file(config_file)

            assert "Invalid YAML" in str(exc_info.value)

    def test_load_config_non_dict_raises_error(self):
        """Test that non-dict config raises error."""
        import argparse

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # JSON array at root
            config_file = temp_path / "config.json"
            config_file.write_text("[1, 2, 3]")

            with pytest.raises(argparse.ArgumentTypeError) as exc_info:
                load_config_file(config_file)

            assert "must contain an object" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.cli
class TestConfigMerging:
    """Test configuration merging functionality."""

    def test_merge_configs_simple(self):
        """Test simple config merging."""
        base = {"attachment_mode": "skip", "rich": False}
        override = {"rich": True}

        merged = merge_configs(base, override)

        assert merged["attachment_mode"] == "skip"
        assert merged["rich"] is True

    def test_merge_configs_nested(self):
        """Test merging nested dictionaries."""
        base = {
            "pdf": {"detect_columns": True, "pages": [1, 2]},
            "html": {"extract_title": False},
        }
        override = {
            "pdf": {"pages": [3, 4, 5]},
            "markdown": {"emphasis_symbol": "_"},
        }

        merged = merge_configs(base, override)

        # PDF settings should be merged
        assert merged["pdf"]["detect_columns"] is True  # From base
        assert merged["pdf"]["pages"] == [3, 4, 5]  # Overridden

        # HTML settings preserved
        assert merged["html"]["extract_title"] is False

        # New markdown settings added
        assert merged["markdown"]["emphasis_symbol"] == "_"

    def test_merge_configs_deep_nesting(self):
        """Test merging with deep nesting."""
        base = {
            "html": {
                "network": {
                    "allow_remote_fetch": False,
                    "timeout": 10,
                }
            }
        }
        override = {
            "html": {
                "network": {
                    "allow_remote_fetch": True,
                }
            }
        }

        merged = merge_configs(base, override)

        assert merged["html"]["network"]["allow_remote_fetch"] is True
        assert merged["html"]["network"]["timeout"] == 10  # Preserved

    def test_merge_configs_override_replaces_non_dicts(self):
        """Test that non-dict values are replaced entirely."""
        base = {"pages": [1, 2, 3]}
        override = {"pages": [4, 5]}

        merged = merge_configs(base, override)

        # List should be replaced, not merged
        assert merged["pages"] == [4, 5]

    def test_merge_configs_empty_base(self):
        """Test merging with empty base."""
        base = {}
        override = {"test": "value"}

        merged = merge_configs(base, override)

        assert merged["test"] == "value"

    def test_merge_configs_empty_override(self):
        """Test merging with empty override."""
        base = {"test": "value"}
        override = {}

        merged = merge_configs(base, override)

        assert merged["test"] == "value"


@pytest.mark.unit
@pytest.mark.cli
@pytest.mark.skipif(tomli_w is None, reason="tomli_w is required for these tests")
class TestConfigPriority:
    """Test configuration priority and loading logic."""

    def test_load_config_with_priority_explicit_path(self):
        """Test that explicit path has highest priority."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "explicit.toml"
            with open(config_file, "wb") as f:
                tomli_w.dump({"test": "explicit"}, f)

            loaded = load_config_with_priority(explicit_path=str(config_file))

            assert loaded["test"] == "explicit"

    def test_load_config_with_priority_env_var_path(self):
        """Test that env var path is used when explicit path not provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / "env.toml"
            with open(config_file, "wb") as f:
                tomli_w.dump({"test": "env"}, f)

            loaded = load_config_with_priority(env_var_path=str(config_file))

            assert loaded["test"] == "env"

    def test_load_config_with_priority_auto_discovery(self):
        """Test that auto-discovery is used when no explicit path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config_file = temp_path / ".all2md.toml"
            with open(config_file, "wb") as f:
                tomli_w.dump({"test": "auto"}, f)

            with patch("pathlib.Path.cwd", return_value=temp_path):
                loaded = load_config_with_priority()
                print(loaded)
                assert loaded["test"] == "auto"


@pytest.mark.unit
@pytest.mark.cli
class TestConfigCommands:
    """Tests for config-related CLI commands."""

    def test_config_generate_writes_json(self, tmp_path):
        """Generating configuration to a file should succeed."""
        output_path = tmp_path / "generated.json"

        exit_code = handle_config_generate_command(
            [
                "--format",
                "json",
                "--out",
                str(output_path),
            ]
        )

        assert exit_code == 0
        assert output_path.exists()

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "pdf" in data
        assert "archive" in data

    def test_config_generate_stdout_toml(self, capsys):
        """Default invocation should emit TOML to stdout."""
        exit_code = handle_config_generate_command([])
        assert exit_code == 0

        captured = capsys.readouterr()
        data = tomllib.loads(captured.out)
        assert "pdf" in data
        assert "archive" in data

    def test_config_show_json_no_source(self, capsys, monkeypatch):
        """Config show should honor --format json and --no-source."""
        monkeypatch.delenv("ALL2MD_CONFIG", raising=False)

        with (
            patch("all2md.cli.commands.config.load_config_with_priority", return_value={"pdf": {"pages": [1]}}),
            patch("all2md.cli.commands.config.get_config_search_paths", return_value=[]),
        ):
            exit_code = handle_config_show_command(["--format", "json", "--no-source"])

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Configuration Sources" not in captured.out
        assert '"pdf"' in captured.out

    def test_load_config_with_priority_returns_empty_when_not_found(self):
        """Test that empty dict is returned when no config found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("pathlib.Path.cwd", return_value=temp_path):
                with patch("pathlib.Path.home", return_value=temp_path):
                    loaded = load_config_with_priority()

                    assert loaded == {}

    def test_load_config_with_priority_explicit_overrides_env(self):
        """Test that explicit path overrides env var path."""
        require_tomli_w()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            explicit_file = temp_path / "explicit.toml"
            env_file = temp_path / "env.toml"

            with open(explicit_file, "wb") as f:
                tomli_w.dump({"test": "explicit"}, f)
            with open(env_file, "wb") as f:
                tomli_w.dump({"test": "env"}, f)

            loaded = load_config_with_priority(explicit_path=str(explicit_file), env_var_path=str(env_file))

            assert loaded["test"] == "explicit"


@pytest.mark.unit
@pytest.mark.cli
class TestPresets:
    """Test preset configuration functionality."""

    def test_get_preset_names(self):
        """Test getting list of preset names."""
        names = get_preset_names()

        assert isinstance(names, list)
        assert len(names) > 0
        assert "fast" in names
        assert "quality" in names
        assert "minimal" in names

    def test_get_preset_config(self):
        """Test getting preset configuration."""
        config = get_preset_config("fast")

        assert isinstance(config, dict)
        assert "attachment_mode" in config
        assert config["attachment_mode"] == "skip"

    def test_get_preset_config_invalid_name_raises_error(self):
        """Test that invalid preset name raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_preset_config("nonexistent")

        assert "Unknown preset" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_get_preset_description(self):
        """Test getting preset description."""
        desc = get_preset_description("fast")

        assert isinstance(desc, str)
        assert len(desc) > 0
        assert "fast" in desc.lower() or "speed" in desc.lower()

    def test_get_preset_description_invalid_name_raises_error(self):
        """Test that invalid preset name raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_preset_description("nonexistent")

        assert "Unknown preset" in str(exc_info.value)

    def test_list_presets(self):
        """Test listing all presets with descriptions."""
        presets = list_presets()

        assert isinstance(presets, list)
        assert len(presets) > 0

        # Each entry should be (name, description) tuple
        for name, desc in presets:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(name) > 0
            assert len(desc) > 0

    def test_apply_preset_basic(self):
        """Test applying preset to base config."""
        base = {}
        result = apply_preset("fast", base)

        assert "attachment_mode" in result
        assert result["attachment_mode"] == "skip"

    def test_apply_preset_base_overrides_preset(self):
        """Test that base config overrides preset values."""
        base = {"attachment_mode": "download"}
        result = apply_preset("fast", base)

        # Base value should override preset
        assert result["attachment_mode"] == "download"

    def test_apply_preset_nested_override(self):
        """Test nested config overrides with presets."""
        base = {"pdf": {"pages": [1, 2]}}
        result = apply_preset("quality", base)

        # Should have both preset PDF settings and base override
        assert "pdf" in result
        assert result["pdf"]["pages"] == [1, 2]  # From base
        # Should also have preset PDF settings
        if "detect_columns" in result["pdf"]:
            assert isinstance(result["pdf"]["detect_columns"], bool)

    def test_preset_fast_skips_images(self):
        """Test that fast preset disables image extraction."""
        config = get_preset_config("fast")

        assert config["attachment_mode"] == "skip"
        if "pdf" in config:
            # Fast preset should optimize for speed
            assert config["pdf"].get("skip_image_extraction", False) is True

    def test_preset_quality_maximizes_fidelity(self):
        """Test that quality preset enables all features."""
        config = get_preset_config("quality")

        assert config["attachment_mode"] == "save"
        if "pdf" in config:
            # Quality preset should enable advanced features
            assert config["pdf"].get("detect_columns", False) is True

    def test_preset_minimal_text_only(self):
        """Test that minimal preset produces text-only output."""
        config = get_preset_config("minimal")

        assert config["attachment_mode"] == "skip"

    def test_preset_archival_embeds_resources(self):
        """Test that archival preset uses base64 embedding."""
        config = get_preset_config("archival")

        assert config["attachment_mode"] == "base64"


@pytest.mark.unit
@pytest.mark.cli
class TestConfigIntegration:
    """Test integration of config system with CLI."""

    def test_config_flag_parsing(self):
        """Test --config flag parsing."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.config is None

        # Test with config path
        args = parser.parse_args(["test.pdf", "--config", "my-config.toml"])
        assert args.config == "my-config.toml"

    def test_preset_flag_parsing(self):
        """Test --preset flag parsing."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        # Test default (None)
        args = parser.parse_args(["test.pdf"])
        assert args.preset is None

        # Test with preset name
        args = parser.parse_args(["test.pdf", "--preset", "fast"])
        assert args.preset == "fast"

    def test_preset_choices_validation(self):
        """Test that preset flag validates choices."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        # Valid presets should work
        for preset in get_preset_names():
            args = parser.parse_args(["test.pdf", "--preset", preset])
            assert args.preset == preset

        # Invalid preset should fail
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--preset", "invalid"])

    def test_config_and_preset_can_be_combined(self):
        """Test that --config and --preset can be used together."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        args = parser.parse_args(["test.pdf", "--config", "custom.toml", "--preset", "quality"])

        assert args.config == "custom.toml"
        assert args.preset == "quality"


@pytest.mark.unit
@pytest.mark.cli
class TestApplyConfigToParser:
    """Test apply_config_to_parser, the subcommand (view/serve/diff) config bridge."""

    def _diff_parser(self):
        from all2md.cli.commands.diff import _create_diff_parser

        return _create_diff_parser()

    def _write(self, tmp_path: Path, body: str) -> str:
        cfg = tmp_path / ".all2md.toml"
        cfg.write_text(body, encoding="utf-8")
        return str(cfg)

    def test_section_values_applied_as_defaults(self, tmp_path):
        """A [diff] section supplies defaults when no CLI flags are given."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[diff]\ngranularity = "word"\ncontext = 7\nshow_context = false\n')
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=cfg)

        assert applied == {"granularity": "word", "context": 7, "show_context": False}
        parsed = parser.parse_args(["a.md", "b.md"])
        assert parsed.granularity == "word"
        assert parsed.context == 7
        assert parsed.show_context is False

    def test_cli_overrides_config(self, tmp_path):
        """Explicit CLI flags win over config-provided defaults."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[diff]\ngranularity = "word"\ncontext = 7\n')
        parser = self._diff_parser()
        apply_config_to_parser(parser, "diff", explicit_path=cfg)

        parsed = parser.parse_args(["a.md", "b.md", "--granularity", "block", "--context", "2"])
        assert parsed.granularity == "block"
        assert parsed.context == 2

    def test_no_config_skips_loading(self, tmp_path):
        """no_config=True ignores the file and keeps hard-coded defaults."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[diff]\ngranularity = "word"\n')
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=cfg, no_config=True)

        assert applied == {}
        assert parser.parse_args(["a.md", "b.md"]).granularity == "block"

    def test_unknown_keys_ignored_with_warning(self, tmp_path, caplog):
        """Keys that don't match an argument dest are skipped (and logged)."""
        import logging

        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[diff]\ngranularity = "word"\nbogus_key = "x"\n')
        parser = self._diff_parser()
        with caplog.at_level(logging.WARNING, logger="all2md.cli.config"):
            applied = apply_config_to_parser(parser, "diff", explicit_path=cfg)

        assert "bogus_key" not in applied
        assert applied == {"granularity": "word"}
        assert "bogus_key" in caplog.text

    def test_hyphenated_keys_normalized(self, tmp_path):
        """Config keys may use hyphens; they map to the snake_case dest."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, "[diff]\nignore-whitespace = true\n")
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=cfg)

        assert applied == {"ignore_whitespace": True}
        assert parser.parse_args(["a.md", "b.md"]).ignore_whitespace is True

    def test_only_named_section_is_read(self, tmp_path):
        """Top-level keys and other sections never leak into the parser."""
        from all2md.cli.config import apply_config_to_parser

        # Top-level 'format' is the converter's input-format key; it must not
        # become diff's --format default.
        cfg = self._write(tmp_path, 'format = "pdf"\n[view]\nno_wait = true\n')
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=cfg)

        assert applied == {}
        assert parser.parse_args(["a.md", "b.md"]).format == "unified"

    def test_positionals_are_not_configurable(self, tmp_path):
        """Positional args (e.g. diff's 'original') cannot be set from config."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[diff]\noriginal = "sneaky.md"\n')
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=cfg)

        assert "original" not in applied

    def test_view_no_wait_and_serve_port(self, tmp_path):
        """The documented examples: [view] no_wait and [serve] port resolve correctly."""
        import argparse

        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, "[view]\nno_wait = true\n[serve]\nport = 9123\n")

        view_parser = argparse.ArgumentParser()
        view_parser.add_argument("input")
        view_parser.add_argument("--no-wait", action="store_true")
        apply_config_to_parser(view_parser, "view", explicit_path=cfg)
        assert view_parser.parse_args(["x.md"]).no_wait is True

        serve_parser = argparse.ArgumentParser()
        serve_parser.add_argument("input")
        serve_parser.add_argument("--port", type=int, default=8000)
        apply_config_to_parser(serve_parser, "serve", explicit_path=cfg)
        assert serve_parser.parse_args(["x.md"]).port == 9123

    def test_missing_section_is_a_noop(self, tmp_path):
        """A config without the requested section changes nothing."""
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, "[pdf]\ndetect_columns = true\n")
        parser = self._diff_parser()
        assert apply_config_to_parser(parser, "diff", explicit_path=cfg) == {}

    def test_invalid_config_warns_and_returns_empty(self, tmp_path, capsys):
        """A malformed config file is reported but does not crash the subcommand."""
        from all2md.cli.config import apply_config_to_parser

        cfg = tmp_path / ".all2md.toml"
        cfg.write_text("this is not valid toml = = =\n", encoding="utf-8")
        parser = self._diff_parser()
        applied = apply_config_to_parser(parser, "diff", explicit_path=str(cfg))

        assert applied == {}
        assert "could not load configuration" in capsys.readouterr().err

    def test_edit_section(self, tmp_path):
        """The [edit] section configures the edit command, CLI still overrides."""
        from all2md.cli.commands.edit import _create_edit_parser
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, "[edit]\nport = 7777\nno_browser = true\n")
        parser = _create_edit_parser()
        apply_config_to_parser(parser, "edit", explicit_path=cfg)

        assert parser.parse_args(["doc.md"]).port == 7777
        assert parser.parse_args(["doc.md"]).no_browser is True
        assert parser.parse_args(["doc.md", "--port", "8001"]).port == 8001

    def test_generate_site_section(self, tmp_path):
        """The [generate-site] section (hyphenated) configures generate-site."""
        from all2md.cli.commands.generate_site import _create_generate_site_parser
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[generate-site]\nscaffold = true\ncontent_subdir = "docs"\n')
        parser = _create_generate_site_parser()
        applied = apply_config_to_parser(parser, "generate-site", explicit_path=cfg)

        assert applied == {"scaffold": True, "content_subdir": "docs"}
        parsed = parser.parse_args(["a.md", "--output-dir", "site", "--generator", "hugo"])
        assert parsed.scaffold is True
        assert parsed.content_subdir == "docs"

    def test_config_can_satisfy_required_option(self, tmp_path):
        """A config value for a required option drops argparse's CLI requirement."""
        from all2md.cli.commands.arxiv import _create_arxiv_parser
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[arxiv]\noutput = "paper.tar.gz"\ndocument_class = "report"\n')
        parser = _create_arxiv_parser()
        apply_config_to_parser(parser, "arxiv", explicit_path=cfg)

        # --output is required=True, but the config value satisfies it.
        parsed = parser.parse_args(["paper.tex"])
        assert parsed.output == "paper.tar.gz"
        assert parsed.document_class == "report"
        # CLI still overrides the config-provided value.
        assert parser.parse_args(["paper.tex", "-o", "other.tar.gz"]).output == "other.tar.gz"

    def test_required_option_still_enforced_without_config(self, tmp_path):
        """When neither config nor CLI supply a required option, it still errors."""
        from all2md.cli.commands.arxiv import _create_arxiv_parser
        from all2md.cli.config import apply_config_to_parser

        cfg = self._write(tmp_path, '[arxiv]\ndocument_class = "report"\n')
        parser = _create_arxiv_parser()
        apply_config_to_parser(parser, "arxiv", explicit_path=cfg)

        with pytest.raises(SystemExit):
            parser.parse_args(["paper.tex"])  # --output not provided anywhere


@pytest.mark.unit
@pytest.mark.cli
class TestConfigGenerateSubcommandSections:
    """config generate emits a template section for each config-aware subcommand."""

    def test_all_subcommand_sections_present(self):
        from all2md.cli.commands.config import _build_default_config_data
        from all2md.cli.config import SUBCOMMAND_CONFIG_SECTIONS

        config = _build_default_config_data()
        for section in SUBCOMMAND_CONFIG_SECTIONS:
            assert section in config, f"missing [{section}] section"

    def test_serve_port_and_view_no_wait_defaults(self):
        from all2md.cli.commands.config import _build_default_config_data

        config = _build_default_config_data()
        assert config["serve"]["port"] == 8000
        assert config["view"]["no_wait"] is False

    def test_required_and_cli_only_keys_omitted(self):
        """Required options (None default) and --config/--no-config are not templated."""
        from all2md.cli.commands.config import _build_default_config_data

        config = _build_default_config_data()
        # arxiv --output is required (no default) and must not appear.
        assert "output" not in config["arxiv"]
        # The CLI-only config controls are never emitted.
        for section in ("view", "serve", "arxiv"):
            assert "config" not in config[section]
            assert "no_config" not in config[section]
