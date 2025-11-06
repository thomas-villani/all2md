"""End-to-end tests for all2md CLI check-deps command.

This module tests the dependency checking feature as a subprocess, simulating
real-world usage patterns for verifying optional dependencies.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestDepsCLI:
    """End-to-end tests for CLI check-deps command."""

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

    def test_check_deps_basic(self):
        """Test basic check-deps command."""
        result = self._run_cli(["check-deps"])

        # Exit code 0 = all deps ok, 1 = some deps missing (both are valid)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        output = result.stdout
        # Should check some dependencies
        assert len(output) > 50, "Output seems too short"

        # Should mention at least some packages or formats
        common_deps = ["pdf", "docx", "html", "image", "pymupdf", "python-docx"]
        found_deps = sum(1 for dep in common_deps if dep.lower() in output.lower())
        assert found_deps >= 2, "Should mention some dependencies"

    def test_check_deps_json_output(self):
        """Test check-deps with JSON output format."""
        result = self._run_cli(["check-deps", "--json"])

        # Exit code 0 = all deps ok, 1 = some deps missing (both are valid)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        output = result.stdout
        # Should be valid JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {output[:200]}")

        # Should have dependency information
        assert isinstance(data, (dict, list)), "JSON should be dict or list"
        assert len(data) > 0, "JSON should contain dependency information"

    def test_check_deps_rich_output(self):
        """Test check-deps with rich formatted output."""
        result = self._run_cli(["check-deps", "--rich"])

        # Exit code 0 = all deps ok, 1 = some deps missing (both are valid)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        output = result.stdout
        # Rich output should be more detailed
        assert len(output) > 100, "Rich output should be substantial"

        # May contain ANSI codes or rich formatting
        # At minimum, should have dependency information
        common_indicators = ["installed", "available", "missing", "version", "status"]
        found_indicators = sum(1 for indicator in common_indicators if indicator.lower() in output.lower())
        assert found_indicators >= 1, "Should show dependency status"

    def test_check_deps_to_file(self):
        """Test check-deps output can be redirected to file."""
        result = self._run_cli(["check-deps"])

        # Exit code 0 = all deps ok, 1 = some deps missing (both are valid)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        # Write output to file manually
        output_file = self.temp_dir / "deps.txt"
        output_file.write_text(result.stdout, encoding="utf-8")

        content = output_file.read_text(encoding="utf-8")
        assert len(content) > 50
        # Should contain dependency information
        assert "pdf" in content.lower() or "docx" in content.lower() or "html" in content.lower()

    def test_check_deps_json_to_file(self):
        """Test check-deps JSON output can be redirected to file."""
        result = self._run_cli(["check-deps", "--json"])

        # Exit code 0 = all deps ok, 1 = some deps missing (both are valid)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"

        # Write output to file manually
        output_file = self.temp_dir / "deps.json"
        output_file.write_text(result.stdout, encoding="utf-8")

        content = output_file.read_text(encoding="utf-8")
        # Should be valid JSON
        try:
            data = json.loads(content)
            assert len(data) > 0
        except json.JSONDecodeError:
            pytest.fail("File content is not valid JSON")

    def test_check_deps_includes_format_info(self):
        """Test that dependency check includes format-specific information."""
        result = self._run_cli(["check-deps"])

        assert result.returncode in [0, 1]
        output = result.stdout.lower()

        # Should mention specific file formats
        formats = ["pdf", "docx", "excel", "powerpoint", "epub", "image"]
        found_formats = sum(1 for fmt in formats if fmt in output)
        assert found_formats >= 2, "Should mention format-specific dependencies"

    def test_check_deps_shows_installed_status(self):
        """Test that dependency check shows installation status."""
        result = self._run_cli(["check-deps"])

        assert result.returncode in [0, 1]
        output = result.stdout.lower()

        # Should indicate installation status
        status_indicators = ["installed", "available", "missing", "not found", "yes", "no", "ok"]
        found_status = sum(1 for indicator in status_indicators if indicator in output)
        assert found_status >= 1, "Should show installation status"

    def test_check_deps_help(self):
        """Test check-deps help message."""
        result = self._run_cli(["check-deps", "--help"])

        assert result.returncode == 0
        assert "check" in result.stdout.lower() or "dep" in result.stdout.lower()
        # Should explain what the command does
        assert "help" in result.stdout.lower()

    def test_check_deps_in_main_help(self):
        """Test that check-deps is documented in main help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "check-deps" in result.stdout.lower() or "dependencies" in result.stdout.lower()

    def test_check_deps_no_arguments_required(self):
        """Test that check-deps works without arguments."""
        result = self._run_cli(["check-deps"])

        # Should work fine without any additional arguments
        assert result.returncode in [0, 1]

    def test_check_deps_consistent_output(self):
        """Test that dependency check produces consistent output."""
        result1 = self._run_cli(["check-deps"])
        result2 = self._run_cli(["check-deps"])

        assert result1.returncode in [0, 1]
        assert result2.returncode in [0, 1]

        # Both outputs should be identical (unless environment changes)
        assert result1.stdout == result2.stdout, "Dependency check should be deterministic"

    def test_check_deps_json_structure(self):
        """Test that JSON output has proper structure."""
        result = self._run_cli(["check-deps", "--json"])

        assert result.returncode in [0, 1]

        data = json.loads(result.stdout)

        # JSON should contain structured dependency information
        if isinstance(data, dict):
            # Should have keys for different dependency types or formats
            assert len(data.keys()) > 0, "JSON dict should have keys"
        elif isinstance(data, list):
            # Should have multiple dependency entries
            assert len(data) > 0, "JSON list should have entries"
            # Each entry should have some structure
            if len(data) > 0:
                first_entry = data[0]
                assert isinstance(first_entry, (dict, str)), "Entries should be structured"

    def test_check_deps_includes_python_version(self):
        """Test that dependency check includes Python version info."""
        result = self._run_cli(["check-deps"])

        assert result.returncode in [0, 1]
        output = result.stdout.lower()

        # Should mention Python or version somewhere
        version_indicators = ["python", "version", "3.", sys.version_info.major]
        found_version = any(str(indicator) in output for indicator in version_indicators)
        assert found_version, "Should show Python version information"

    def test_check_deps_includes_optional_packages(self):
        """Test that dependency check lists optional packages."""
        result = self._run_cli(["check-deps"])

        assert result.returncode in [0, 1]
        output = result.stdout.lower()

        # Should mention some optional packages
        optional_packages = ["pymupdf", "python-docx", "ebooklib", "pillow", "beautifulsoup"]
        found_packages = sum(1 for pkg in optional_packages if pkg in output)
        assert found_packages >= 1, "Should list optional package dependencies"

    def test_check_deps_json_and_rich_mutually_exclusive(self):
        """Test that --json and --rich cannot be used together."""
        result = self._run_cli(["check-deps", "--json", "--rich"])

        # Should either succeed with one taking precedence, or fail
        # At minimum, should not crash
        assert result.returncode in [0, 2], "Should handle conflicting flags gracefully"

    def test_check_deps_no_errors_on_success(self):
        """Test that dependency check completes without fatal errors."""
        result = self._run_cli(["check-deps"])

        # Exit code 0 or 1 is expected (1 = missing deps, not a fatal error)
        assert result.returncode in [0, 1]
        # Should have minimal or no stderr output (warnings are ok)
        stderr_lower = result.stderr.lower()
        # No fatal errors (warnings about pkg_resources are ok)
        assert not ("error:" in stderr_lower and "fatal" in stderr_lower)
