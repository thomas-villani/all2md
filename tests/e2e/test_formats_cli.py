"""End-to-end tests for all2md CLI list-formats command.

This module tests the format listing feature as a subprocess, simulating
real-world usage patterns for querying supported file formats.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestFormatsCLI:
    """End-to-end tests for CLI list-formats command."""

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

    def test_list_formats_basic(self):
        """Test basic list-formats command."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        # Should list common formats
        common_formats = ["pdf", "docx", "html", "markdown", "epub"]
        found_formats = sum(1 for fmt in common_formats if fmt in output.lower())
        assert found_formats >= 3, f"Expected at least 3 common formats, found {found_formats}"

    def test_formats_alias(self):
        """Test that 'formats' is an alias for 'list-formats'."""
        result = self._run_cli(["formats"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        # Should produce same output as list-formats
        common_formats = ["pdf", "html", "markdown"]
        found_formats = sum(1 for fmt in common_formats if fmt in output.lower())
        assert found_formats >= 2

    def test_list_formats_includes_parsers(self):
        """Test that format listing includes parser information."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout

        # Should mention parsers or input formats
        assert len(output) > 200, "Output seems too short to contain format list"

        # Common parsers that should be listed
        parsers = ["PDF", "DOCX", "HTML", "LaTeX", "RTF", "EPUB"]
        found_parsers = sum(1 for parser in parsers if parser in output)
        assert found_parsers >= 3, "Should list multiple parser formats"

    def test_list_formats_includes_renderers(self):
        """Test that format listing includes renderer information."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout

        # Common renderers that should be listed
        renderers = ["Markdown", "HTML", "PDF", "DOCX", "LaTeX"]
        found_renderers = sum(1 for renderer in renderers if renderer in output)
        assert found_renderers >= 2, "Should list multiple renderer formats"

    def test_list_formats_shows_extensions(self):
        """Test that format listing shows file extensions."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout

        # Should show file extensions
        extensions = [".pdf", ".docx", ".html", ".md", ".epub", ".txt"]
        found_extensions = sum(1 for ext in extensions if ext in output.lower())
        assert found_extensions >= 3, "Should show file extensions"

    def test_list_formats_to_file(self):
        """Test list-formats output can be redirected to file."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Write output to file manually (list-formats outputs to stdout)
        output_file = self.temp_dir / "formats.txt"
        output_file.write_text(result.stdout, encoding="utf-8")

        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 100
        assert "pdf" in content.lower() or "html" in content.lower()

    def test_list_formats_help(self):
        """Test list-formats help message."""
        result = self._run_cli(["list-formats", "--help"])

        assert result.returncode == 0
        assert "format" in result.stdout.lower()
        # Should explain what the command does
        assert "list" in result.stdout.lower() or "show" in result.stdout.lower()

    def test_list_formats_in_main_help(self):
        """Test that list-formats is documented in main help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "list-formats" in result.stdout.lower() or "formats" in result.stdout.lower()

    def test_list_formats_structured_output(self):
        """Test that format listing has structured output."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout

        # Should have some structure (headers, sections, or formatting)
        lines = output.split("\n")
        assert len(lines) >= 10, "Should have multiple lines of output"

        # Should have some organization (not just a flat list)
        # Could be headers, separators, or grouped formats
        has_structure = any(
            line.strip().startswith(("#", "=", "-", "*")) or line.isupper() or ":" in line
            for line in lines[:10]  # Check first 10 lines for structure
        )
        assert has_structure or len(lines) >= 20, "Should have structured or extensive output"

    def test_list_formats_includes_special_formats(self):
        """Test that listing includes special or less common formats."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout.lower()

        # Check for some less common but supported formats
        special_formats = ["epub", "latex", "rtf", "org", "rst"]
        found_special = sum(1 for fmt in special_formats if fmt in output)
        assert found_special >= 2, "Should list special formats too"

    def test_list_formats_includes_plaintext(self):
        """Test that listing includes plaintext/code formats."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout.lower()

        # Should mention text or source code formats
        plaintext_indicators = ["text", "txt", "source", "code", "plain"]
        found_text = sum(1 for indicator in plaintext_indicators if indicator in output)
        assert found_text >= 1, "Should mention text/code formats"

    def test_list_formats_includes_archive_formats(self):
        """Test that listing includes archive formats."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        output = result.stdout.lower()

        # Should mention archive formats
        archive_formats = ["zip", "epub", "docx"]  # docx and epub are zip-based
        found_archives = sum(1 for fmt in archive_formats if fmt in output)
        assert found_archives >= 1, "Should list archive-based formats"

    def test_list_formats_consistent_output(self):
        """Test that format listing produces consistent output."""
        result1 = self._run_cli(["list-formats"])
        result2 = self._run_cli(["list-formats"])

        assert result1.returncode == 0
        assert result2.returncode == 0

        # Both outputs should be identical
        assert result1.stdout == result2.stdout, "Format listing should be deterministic"

    def test_list_formats_no_errors(self):
        """Test that format listing produces no errors."""
        result = self._run_cli(["list-formats"])

        assert result.returncode == 0
        # May have warnings (like pkg_resources deprecation), but no actual errors
        stderr_lower = result.stderr.lower()
        assert "error" not in stderr_lower or "user" in stderr_lower  # UserWarning is ok

    def test_formats_and_list_formats_equivalent(self):
        """Test that 'formats' and 'list-formats' produce identical output."""
        result_list = self._run_cli(["list-formats"])
        result_alias = self._run_cli(["formats"])

        assert result_list.returncode == 0
        assert result_alias.returncode == 0

        # Both should produce same output
        assert result_list.stdout == result_alias.stdout, "Alias should produce identical output"
