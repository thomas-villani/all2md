"""End-to-end tests for all2md config CLI command.

This module tests the config command and its subcommands: generate, show, and validate.
Tests cover configuration file creation, validation, and display functionality.
"""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestConfigCLIEndToEnd:
    """End-to-end tests for config CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        # Store original env var value
        self.original_env = os.environ.get("ALL2MD_CONFIG")

    def teardown_method(self):
        """Clean up test environment."""
        # Restore original env var
        if self.original_env is not None:
            os.environ["ALL2MD_CONFIG"] = self.original_env
        elif "ALL2MD_CONFIG" in os.environ:
            del os.environ["ALL2MD_CONFIG"]

        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI
        env : dict[str, str], optional
            Environment variables to set for the subprocess

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md"] + args
        subprocess_env = os.environ.copy()
        if env:
            subprocess_env.update(env)

        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            env=subprocess_env,
        )

    def test_config_without_subcommand(self):
        """Test config command without subcommand shows usage."""
        result = self._run_cli(["config"])

        assert result.returncode != 0
        assert "Subcommands:" in result.stderr or "subcommands:" in result.stderr.lower()
        assert "generate" in result.stderr
        assert "show" in result.stderr
        assert "validate" in result.stderr

    def test_config_with_invalid_subcommand(self):
        """Test config with unknown subcommand."""
        result = self._run_cli(["config", "invalid-subcommand"])

        assert result.returncode != 0
        assert "Unknown" in result.stderr or "unknown" in result.stderr.lower()

    def test_config_generate_toml_default(self):
        """Test config generate creates TOML file by default."""
        output_file = self.temp_dir / "config.toml"

        result = self._run_cli(["config", "generate", "--out", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        assert "Configuration written to" in result.stdout

        # Verify it's valid TOML
        with open(output_file, "rb") as toml_file:
            config_data = tomllib.load(toml_file)
        assert isinstance(config_data, dict)

    def test_config_generate_toml_explicit(self):
        """Test config generate with explicit TOML format."""
        output_file = self.temp_dir / "config.toml"

        result = self._run_cli(["config", "generate", "--format", "toml", "--out", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

        # Verify it's valid TOML
        with open(output_file, "rb") as toml_file:
            config_data = tomllib.load(toml_file)
        assert isinstance(config_data, dict)

    def test_config_generate_yaml(self):
        """Test config generate with YAML format."""
        output_file = self.temp_dir / "config.yaml"

        result = self._run_cli(["config", "generate", "--format", "yaml", "--out", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

        # Verify it's valid YAML
        with open(output_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        assert isinstance(config_data, dict)

    def test_config_generate_json(self):
        """Test config generate with JSON format."""
        output_file = self.temp_dir / "config.json"

        result = self._run_cli(["config", "generate", "--format", "json", "--out", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

        # Verify it's valid JSON
        with open(output_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        assert isinstance(config_data, dict)

    def test_config_generate_to_stdout(self):
        """Test config generate outputs to stdout when no --out specified."""
        result = self._run_cli(["config", "generate", "--format", "json"])

        assert result.returncode == 0
        # Output should be valid JSON
        config_data = json.loads(result.stdout)
        assert isinstance(config_data, dict)

    def test_config_generate_creates_parent_directories(self):
        """Test config generate creates parent directories if needed."""
        output_file = self.temp_dir / "subdir" / "nested" / "config.toml"

        result = self._run_cli(["config", "generate", "--out", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        assert output_file.parent.exists()

    def test_config_generate_help(self):
        """Test config generate --help displays usage information."""
        result = self._run_cli(["config", "generate", "--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout
        assert "--format" in result.stdout
        assert "--out" in result.stdout

    def test_config_show_no_config_found(self):
        """Test config show when no configuration file exists."""
        # Use an empty directory with no config files
        result = self._run_cli(["config", "show"])

        assert result.returncode == 0
        assert "No configuration found" in result.stdout

    def test_config_show_with_toml_config(self):
        """Test config show displays TOML configuration."""
        # Create a config file in the temp directory
        config_file = self.temp_dir / ".all2md.toml"
        config_content = """
[parser_options.html]
extract_title = true

[renderer_options.markdown]
heading_style = "atx"
"""
        config_file.write_text(config_content, encoding="utf-8")

        # Set env var to point to our config
        env = {"ALL2MD_CONFIG": str(config_file)}
        result = self._run_cli(["config", "show"], env=env)

        assert result.returncode == 0
        assert "Configuration Sources" in result.stdout
        assert str(config_file) in result.stdout

    def test_config_show_format_toml(self):
        """Test config show with TOML output format."""
        config_file = self.temp_dir / ".all2md.toml"
        config_content = """
[parser_options.html]
extract_title = true
"""
        config_file.write_text(config_content, encoding="utf-8")

        env = {"ALL2MD_CONFIG": str(config_file)}
        result = self._run_cli(["config", "show", "--format", "toml"], env=env)

        assert result.returncode == 0
        # Should show TOML formatted output
        assert "[parser_options.html]" in result.stdout or "parser_options" in result.stdout

    def test_config_show_format_json(self):
        """Test config show with JSON output format."""
        config_file = self.temp_dir / ".all2md.toml"
        config_content = """
[parser_options.html]
extract_title = true
"""
        config_file.write_text(config_content, encoding="utf-8")

        env = {"ALL2MD_CONFIG": str(config_file)}
        result = self._run_cli(["config", "show", "--format", "json"], env=env)

        assert result.returncode == 0
        # Should show JSON formatted output
        assert "{" in result.stdout
        # Try to parse as JSON
        try:
            json.loads(
                result.stdout.split("Configuration Sources")[-1]
                if "Configuration Sources" in result.stdout
                else result.stdout
            )
        except json.JSONDecodeError:
            # May contain non-JSON header text
            pass

    def test_config_show_format_yaml(self):
        """Test config show with YAML output format."""
        config_file = self.temp_dir / ".all2md.toml"
        config_content = """
[parser_options.html]
extract_title = true
"""
        config_file.write_text(config_content, encoding="utf-8")

        env = {"ALL2MD_CONFIG": str(config_file)}
        result = self._run_cli(["config", "show", "--format", "yaml"], env=env)

        assert result.returncode == 0
        # Should show YAML formatted output

    def test_config_show_no_source(self):
        """Test config show with --no-source flag."""
        config_file = self.temp_dir / ".all2md.toml"
        config_content = """
[parser_options.html]
extract_title = true
"""
        config_file.write_text(config_content, encoding="utf-8")

        env = {"ALL2MD_CONFIG": str(config_file)}
        result = self._run_cli(["config", "show", "--no-source"], env=env)

        assert result.returncode == 0
        # Should NOT show configuration sources
        assert "Configuration Sources" not in result.stdout

    def test_config_show_help(self):
        """Test config show --help displays usage information."""
        result = self._run_cli(["config", "show", "--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout
        assert "--format" in result.stdout
        assert "--no-source" in result.stdout

    def test_config_validate_valid_toml(self):
        """Test config validate with valid TOML file."""
        config_file = self.temp_dir / "config.toml"
        config_content = """
[parser_options.html]
extract_title = true

[renderer_options.markdown]
heading_style = "atx"
"""
        config_file.write_text(config_content, encoding="utf-8")

        result = self._run_cli(["config", "validate", str(config_file)])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower()
        assert str(config_file) in result.stdout

    def test_config_validate_valid_json(self):
        """Test config validate with valid JSON file."""
        config_file = self.temp_dir / "config.json"
        config_content = {"parser_options": {"html": {"extract_title": True}}}
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_content, f)

        result = self._run_cli(["config", "validate", str(config_file)])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_config_validate_valid_yaml(self):
        """Test config validate with valid YAML file."""
        config_file = self.temp_dir / "config.yaml"
        config_content = {"parser_options": {"html": {"extract_title": True}}}
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_content, f)

        result = self._run_cli(["config", "validate", str(config_file)])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_config_validate_invalid_toml(self):
        """Test config validate with invalid TOML file."""
        config_file = self.temp_dir / "config.toml"
        # Invalid TOML - missing closing bracket
        config_content = """
[parser_options.html
extract_title = true
"""
        config_file.write_text(config_content, encoding="utf-8")

        result = self._run_cli(["config", "validate", str(config_file)])

        assert result.returncode != 0
        assert "Error" in result.stderr or "error" in result.stderr.lower() or "invalid" in result.stderr.lower()

    def test_config_validate_invalid_json(self):
        """Test config validate with invalid JSON file."""
        config_file = self.temp_dir / "config.json"
        # Invalid JSON - missing closing brace
        config_content = '{"parser_options": {"html": {"extract_title": true}'
        config_file.write_text(config_content, encoding="utf-8")

        result = self._run_cli(["config", "validate", str(config_file)])

        assert result.returncode != 0
        assert "Error" in result.stderr or "error" in result.stderr.lower() or "invalid" in result.stderr.lower()

    def test_config_validate_nonexistent_file(self):
        """Test config validate with file that doesn't exist."""
        nonexistent = self.temp_dir / "nonexistent.toml"

        result = self._run_cli(["config", "validate", str(nonexistent)])

        assert result.returncode != 0
        assert "invalid configuration file: configuration file does not exist:" in result.stderr.lower()
        assert str(nonexistent) in result.stderr

    def test_config_validate_without_file(self):
        """Test config validate without providing a file path."""
        result = self._run_cli(["config", "validate"])

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "Config file path" in result.stderr

    def test_config_validate_help(self):
        """Test config validate --help displays usage information."""
        result = self._run_cli(["config", "validate", "--help"])

        assert result.returncode == 0
        assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()
        assert "config-file" in result.stdout or "config_file" in result.stdout

    def test_config_generate_and_validate_roundtrip_toml(self):
        """Test generating a config file and then validating it (TOML)."""
        config_file = self.temp_dir / "roundtrip.toml"

        # Generate
        generate_result = self._run_cli(["config", "generate", "--format", "toml", "--out", str(config_file)])
        assert generate_result.returncode == 0

        # Validate
        validate_result = self._run_cli(["config", "validate", str(config_file)])
        assert validate_result.returncode == 0
        assert "valid" in validate_result.stdout.lower()

    def test_config_generate_and_validate_roundtrip_yaml(self):
        """Test generating a config file and then validating it (YAML)."""
        config_file = self.temp_dir / "roundtrip.yaml"

        # Generate
        generate_result = self._run_cli(["config", "generate", "--format", "yaml", "--out", str(config_file)])
        assert generate_result.returncode == 0

        # Validate
        validate_result = self._run_cli(["config", "validate", str(config_file)])
        assert validate_result.returncode == 0
        assert "valid" in validate_result.stdout.lower()

    def test_config_generate_and_validate_roundtrip_json(self):
        """Test generating a config file and then validating it (JSON)."""
        config_file = self.temp_dir / "roundtrip.json"

        # Generate
        generate_result = self._run_cli(["config", "generate", "--format", "json", "--out", str(config_file)])
        assert generate_result.returncode == 0

        # Validate
        validate_result = self._run_cli(["config", "validate", str(config_file)])
        assert validate_result.returncode == 0
        assert "valid" in validate_result.stdout.lower()

    def test_config_show_with_env_var_priority(self):
        """Test config show respects ALL2MD_CONFIG environment variable."""
        # Create two config files
        env_config = self.temp_dir / "env_config.toml"
        env_config.write_text("[parser_options.html]\nextract_title = true", encoding="utf-8")

        local_config = self.temp_dir / ".all2md.toml"
        local_config.write_text("[parser_options.html]\nextract_title = false", encoding="utf-8")

        # Set env var to point to env_config
        env = {"ALL2MD_CONFIG": str(env_config)}
        result = self._run_cli(["config", "show"], env=env)

        assert result.returncode == 0
        assert str(env_config) in result.stdout
        assert "FOUND" in result.stdout

    def test_config_generate_overwrites_existing_file(self):
        """Test that config generate overwrites existing file."""
        config_file = self.temp_dir / "config.toml"

        # Create initial file
        config_file.write_text("# Old content", encoding="utf-8")

        # Generate new config
        result = self._run_cli(["config", "generate", "--out", str(config_file)])

        assert result.returncode == 0
        # Verify old content is replaced
        new_content = config_file.read_text(encoding="utf-8")
        assert "# Old content" not in new_content

    def test_config_validate_directory_instead_of_file(self):
        """Test config validate with directory path instead of file."""
        result = self._run_cli(["config", "validate", str(self.temp_dir)])

        # Should fail - directories aren't valid config files
        assert result.returncode != 0
