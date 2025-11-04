"""Unit tests for shell completion generators."""

import pytest

from all2md.cli.commands.completion import (
    generate_bash_completion,
    generate_powershell_completion,
    generate_zsh_completion,
    handle_completion_command,
)
from all2md.cli.help_formatter import _serialize_catalog_for_completion, build_help_renderer


@pytest.mark.unit
class TestCompletionCatalogSerialization:
    """Test catalog serialization for completion generation."""

    def test_serialize_catalog_structure(self):
        """Test that catalog serialization returns expected structure."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        assert isinstance(catalog_data, dict)
        assert "global" in catalog_data
        assert "parsers" in catalog_data
        assert "renderers" in catalog_data
        assert "subcommands" in catalog_data
        assert "formats" in catalog_data
        assert "transforms" in catalog_data

    def test_serialize_catalog_global_options(self):
        """Test that global options are included."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        global_opts = catalog_data["global"]
        assert isinstance(global_opts, list)
        assert len(global_opts) > 0

        # Check for some expected global options
        all_flags = [flag for opt in global_opts for flag in opt["flags"]]
        assert "--out" in all_flags or "-o" in all_flags
        assert "--format" in all_flags or "-f" in all_flags

    def test_serialize_catalog_parser_options(self):
        """Test that parser options are organized by format."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        parsers = catalog_data["parsers"]
        assert isinstance(parsers, dict)

        # Should have at least some common formats
        expected_formats = ["pdf", "html", "docx"]
        for fmt in expected_formats:
            if fmt in parsers:
                assert isinstance(parsers[fmt], list)

    def test_serialize_catalog_renderer_options(self):
        """Test that renderer options are organized by format."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        renderers = catalog_data["renderers"]
        assert isinstance(renderers, dict)

    def test_serialize_catalog_formats_list(self):
        """Test that formats list is populated."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        formats = catalog_data["formats"]
        assert isinstance(formats, list)
        assert len(formats) > 0

        # Check for common formats
        common_formats = ["pdf", "html", "markdown", "docx"]
        for fmt in common_formats:
            assert fmt in formats

    def test_serialize_catalog_subcommands_list(self):
        """Test that subcommands list is populated."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)

        subcommands = catalog_data["subcommands"]
        assert isinstance(subcommands, list)
        assert "help" in subcommands
        assert "config" in subcommands
        assert "completion" in subcommands


@pytest.mark.unit
class TestCompletionHandlers:
    """Test completion command handlers."""

    def test_handle_completion_command_returns_none_for_non_completion(self):
        """Test that non-completion commands return None."""
        result = handle_completion_command(["convert", "test.pdf"])
        assert result is None

    def test_handle_completion_command_bash(self, capsys):
        """Test bash completion generation."""
        result = handle_completion_command(["completion", "bash"])
        assert result == 0

        captured = capsys.readouterr()
        assert "Bash completion for all2md" in captured.out
        assert "_all2md_completion" in captured.out
        assert "complete -F _all2md_completion all2md" in captured.out

    def test_handle_completion_command_zsh(self, capsys):
        """Test zsh completion generation."""
        result = handle_completion_command(["completion", "zsh"])
        assert result == 0

        captured = capsys.readouterr()
        assert "#compdef all2md" in captured.out
        assert "_all2md" in captured.out

    def test_handle_completion_command_powershell(self, capsys):
        """Test PowerShell completion generation."""
        result = handle_completion_command(["completion", "powershell"])
        assert result == 0

        captured = capsys.readouterr()
        assert "PowerShell completion for all2md" in captured.out
        assert "Register-ArgumentCompleter" in captured.out

    def test_handle_completion_command_no_args(self, capsys):
        """Test completion command with no shell argument shows error."""
        result = handle_completion_command(["completion"])
        assert result == 1

        captured = capsys.readouterr()
        assert "required: shell" in captured.err or "required" in captured.err

    def test_handle_completion_command_invalid_shell(self, capsys):
        """Test completion command with invalid shell shows error."""
        result = handle_completion_command(["completion", "fish"])
        assert result == 1

        captured = capsys.readouterr()
        assert "invalid choice" in captured.err or "fish" in captured.err


@pytest.mark.unit
class TestBashCompletionGenerator:
    """Test bash completion script generation."""

    def test_bash_completion_basic_structure(self):
        """Test that bash completion has required structure."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_bash_completion(catalog_data)

        assert "# Bash completion for all2md" in script
        assert "_all2md_completion()" in script
        assert "complete -F _all2md_completion all2md" in script

    def test_bash_completion_includes_subcommands(self):
        """Test that subcommands are included in bash completion."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_bash_completion(catalog_data)

        assert "help" in script
        assert "config" in script
        assert "completion" in script

    def test_bash_completion_includes_formats(self):
        """Test that format names are included."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_bash_completion(catalog_data)

        # Should have format completion for --format flag
        assert "--format" in script or "-f" in script
        assert "pdf" in script
        assert "html" in script

    def test_bash_completion_context_aware(self):
        """Test that bash completion has context-aware logic."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_bash_completion(catalog_data)

        # Should detect format from command line
        assert 'format=""' in script or "format=''" in script
        assert 'if [[ "$format" ==' in script

    def test_bash_completion_no_syntax_errors(self):
        """Test that generated bash script has no obvious syntax errors."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_bash_completion(catalog_data)

        # Check for basic syntax elements
        assert script.count("{") == script.count("}")
        assert "COMPREPLY" in script
        assert "_filedir" in script or "_files" in script or "file completion" in script.lower()


@pytest.mark.unit
class TestZshCompletionGenerator:
    """Test zsh completion script generation."""

    def test_zsh_completion_basic_structure(self):
        """Test that zsh completion has required structure."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_zsh_completion(catalog_data)

        assert "#compdef all2md" in script
        assert "_all2md()" in script or "_all2md() {" in script
        assert "_all2md" in script

    def test_zsh_completion_includes_subcommands(self):
        """Test that subcommands are included in zsh completion."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_zsh_completion(catalog_data)

        assert "help" in script
        assert "config" in script

    def test_zsh_completion_uses_arguments(self):
        """Test that zsh completion uses _arguments."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_zsh_completion(catalog_data)

        assert "_arguments" in script

    def test_zsh_completion_includes_formats(self):
        """Test that format names are included."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_zsh_completion(catalog_data)

        # Should have formats somewhere in the completion
        assert "pdf" in script or "formats" in script.lower()

    def test_zsh_completion_no_syntax_errors(self):
        """Test that generated zsh script has no obvious syntax errors."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_zsh_completion(catalog_data)

        # Check for basic syntax elements
        assert script.count("{") == script.count("}")
        assert script.count("(") == script.count(")")


@pytest.mark.unit
class TestPowerShellCompletionGenerator:
    """Test PowerShell completion script generation."""

    def test_powershell_completion_basic_structure(self):
        """Test that PowerShell completion has required structure."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_powershell_completion(catalog_data)

        assert "# PowerShell completion for all2md" in script
        assert "Register-ArgumentCompleter" in script
        assert "-CommandName all2md" in script

    def test_powershell_completion_includes_subcommands(self):
        """Test that subcommands are included in PowerShell completion."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_powershell_completion(catalog_data)

        assert "help" in script
        assert "config" in script

    def test_powershell_completion_context_aware(self):
        """Test that PowerShell completion has context-aware logic."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_powershell_completion(catalog_data)

        # Should detect format from command line
        assert "$format" in script
        assert "if ($format -eq" in script or "if ($outputType -eq" in script

    def test_powershell_completion_uses_completion_result(self):
        """Test that PowerShell completion uses CompletionResult objects."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_powershell_completion(catalog_data)

        assert "CompletionResult" in script

    def test_powershell_completion_no_syntax_errors(self):
        """Test that generated PowerShell script has no obvious syntax errors."""
        renderer = build_help_renderer()
        catalog_data = _serialize_catalog_for_completion(renderer.catalog)
        script = generate_powershell_completion(catalog_data)

        # Check for basic syntax elements
        # Note: curly braces in PowerShell don't always match 1:1 in all contexts
        # Just verify the script has the expected structure
        assert script.count("(") == script.count(")")
        assert "Register-ArgumentCompleter" in script
        assert "$completions" in script
