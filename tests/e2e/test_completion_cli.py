"""End-to-end tests for all2md CLI completion command.

This module tests the shell completion generation feature as a subprocess,
simulating real-world usage patterns for bash, zsh, and PowerShell completion.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestCompletionCLI:
    """End-to-end tests for CLI completion command."""

    def setup_method(self):
        """Set up test environment.

        Creates a temporary directory for test files and locates the CLI module.
        """
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

    def teardown_method(self):
        """Clean up test environment.

        Removes temporary files and directories created during tests.
        """
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def test_completion_bash(self):
        """Test bash completion script generation."""
        result = self._run_cli(["completion", "bash"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should output a bash completion script
        output = result.stdout
        assert len(output) > 100, "Completion script seems too short"

        # Bash completion scripts typically contain these patterns
        bash_patterns = [
            "bash",
            "complete",
            "_all2md",  # Typical completion function name
        ]

        # At least one bash pattern should be present
        has_bash_pattern = any(pattern in output.lower() for pattern in bash_patterns)
        assert has_bash_pattern, "Output doesn't look like a bash completion script"

    def test_completion_zsh(self):
        """Test zsh completion script generation."""
        result = self._run_cli(["completion", "zsh"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should output a zsh completion script
        output = result.stdout
        assert len(output) > 100, "Completion script seems too short"

        # Zsh completion scripts typically contain these patterns
        zsh_patterns = [
            "zsh",
            "#compdef",
            "_arguments",
            "compadd",
        ]

        # At least one zsh pattern should be present
        has_zsh_pattern = any(pattern in output.lower() for pattern in zsh_patterns)
        assert has_zsh_pattern, "Output doesn't look like a zsh completion script"

    def test_completion_powershell(self):
        """Test PowerShell completion script generation."""
        result = self._run_cli(["completion", "powershell"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should output a PowerShell completion script
        output = result.stdout
        assert len(output) > 100, "Completion script seems too short"

        # PowerShell completion scripts typically contain these patterns
        ps_patterns = [
            "powershell",
            "Register-ArgumentCompleter",
            "param",
            "$",
        ]

        # At least one PowerShell pattern should be present
        has_ps_pattern = any(pattern in output for pattern in ps_patterns)
        assert has_ps_pattern, "Output doesn't look like a PowerShell completion script"

    def test_completion_bash_to_file(self):
        """Test bash completion script generation can be redirected to file."""
        result = self._run_cli(["completion", "bash"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Write output to file manually (completion command outputs to stdout)
        output_file = self.temp_dir / "all2md-completion.bash"
        output_file.write_text(result.stdout, encoding="utf-8")

        # Verify file content
        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 100
        assert "bash" in content.lower() or "complete" in content.lower()

    def test_completion_zsh_to_file(self):
        """Test zsh completion script generation can be redirected to file."""
        result = self._run_cli(["completion", "zsh"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Write output to file manually (completion command outputs to stdout)
        output_file = self.temp_dir / "_all2md"
        output_file.write_text(result.stdout, encoding="utf-8")

        # Verify file content
        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 100

    def test_completion_powershell_to_file(self):
        """Test PowerShell completion script generation can be redirected to file."""
        result = self._run_cli(["completion", "powershell"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Write output to file manually (completion command outputs to stdout)
        output_file = self.temp_dir / "all2md-completion.ps1"
        output_file.write_text(result.stdout, encoding="utf-8")

        # Verify file content
        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 100

    def test_completion_no_shell_error(self):
        """Test error when no shell type is specified."""
        result = self._run_cli(["completion"])

        # Should fail with missing argument error
        assert result.returncode != 0
        # Should have error message about missing shell type
        assert "shell" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_completion_invalid_shell_error(self):
        """Test error handling for invalid shell type."""
        result = self._run_cli(["completion", "invalid_shell"])

        # Should fail with invalid choice error
        assert result.returncode != 0, "Should fail with invalid shell"
        assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower()

    def test_completion_help(self):
        """Test completion command help."""
        result = self._run_cli(["completion", "--help"])

        # Help should succeed (exit code 0 or 1 depending on implementation)
        assert result.returncode in [0, 1], f"Unexpected return code: {result.returncode}"

        # Should document the shell options (in stdout or stderr)
        output = result.stdout + result.stderr
        assert "bash" in output.lower()
        assert "zsh" in output.lower()
        assert "powershell" in output.lower()

        # Should explain what the command does
        assert "completion" in output.lower()

    def test_completion_in_main_help(self):
        """Test that completion command is documented in main help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "completion" in result.stdout.lower()

    def test_completion_bash_output_structure(self):
        """Test that bash completion output has proper structure."""
        result = self._run_cli(["completion", "bash"])

        assert result.returncode == 0
        output = result.stdout

        # Should be a valid bash script (starts with shebang or comment)
        lines = output.split("\n")
        first_line = lines[0] if lines else ""
        # First line is typically shebang or comment
        assert first_line.startswith("#") or first_line.startswith("_") or "function" in first_line.lower()

    def test_completion_zsh_output_structure(self):
        """Test that zsh completion output has proper structure."""
        result = self._run_cli(["completion", "zsh"])

        assert result.returncode == 0
        output = result.stdout

        # Should be a valid zsh completion script
        lines = output.split("\n")
        # Should have compdef or function definition
        has_compdef = any("#compdef" in line for line in lines)
        has_function = any("function" in line.lower() or "_" in line for line in lines)
        assert has_compdef or has_function, "Missing compdef or function definition"

    def test_completion_powershell_output_structure(self):
        """Test that PowerShell completion output has proper structure."""
        result = self._run_cli(["completion", "powershell"])

        assert result.returncode == 0
        output = result.stdout

        # Should be a valid PowerShell script
        lines = output.split("\n")
        # Should have Register-ArgumentCompleter or function definition
        has_register = any("Register-ArgumentCompleter" in line for line in lines)
        has_function = any("function" in line or "param" in line for line in lines)
        assert has_register or has_function, "Missing Register-ArgumentCompleter or function"

    def test_completion_bash_includes_commands(self):
        """Test that bash completion includes main commands."""
        result = self._run_cli(["completion", "bash"])

        assert result.returncode == 0
        output = result.stdout

        # Should include some main commands or subcommands
        commands = ["view", "serve", "search", "diff", "config", "help"]

        # At least some commands should be mentioned
        commands_found = sum(1 for cmd in commands if cmd in output)
        assert commands_found >= 2, f"Expected at least 2 commands in completion, found {commands_found}"

    def test_completion_script_idempotent(self):
        """Test that running completion twice produces same output."""
        result1 = self._run_cli(["completion", "bash"])
        result2 = self._run_cli(["completion", "bash"])

        assert result1.returncode == 0
        assert result2.returncode == 0

        # Both outputs should be identical
        assert result1.stdout == result2.stdout, "Completion script should be deterministic"

    def test_completion_all_shells(self):
        """Test that all supported shells can generate completion scripts."""
        shells = ["bash", "zsh", "powershell"]

        for shell in shells:
            result = self._run_cli(["completion", shell])
            assert result.returncode == 0, f"Failed to generate {shell} completion"
            assert len(result.stdout) > 50, f"{shell} completion seems too short"
