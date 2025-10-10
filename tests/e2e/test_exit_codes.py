"""End-to-end tests for CLI exit codes.

This module tests that the CLI returns appropriate exit codes for different
error conditions, allowing scripts and automation to properly handle failures.
"""

import subprocess

import pytest


@pytest.mark.e2e
@pytest.mark.slow
class TestExitCodes:
    """Test suite for CLI exit codes."""

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI with the given arguments.

        Parameters
        ----------
        args : list[str]
            Command-line arguments to pass to all2md

        Returns
        -------
        subprocess.CompletedProcess
            The result of the CLI execution

        """
        import sys
        cmd = [sys.executable, "-m", "all2md"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        return result

    def test_exit_code_success(self, tmp_path):
        """Test exit code 0 for successful conversion."""
        # Create a simple HTML file
        html_file = tmp_path / "test.html"
        html_file.write_text("<h1>Test</h1>")

        result = self._run_cli([str(html_file)])

        assert result.returncode == 0
        assert "Test" in result.stdout

    def test_exit_code_input_error_nonexistent_file(self, tmp_path):
        """Test exit code 4 (FILE_ERROR) for nonexistent file."""
        nonexistent = tmp_path / "does_not_exist.pdf"

        result = self._run_cli([str(nonexistent)])

        assert result.returncode == 4
        assert "Error" in result.stderr

    def test_exit_code_input_error_no_input(self):
        """Test exit code 3 (VALIDATION_ERROR) when no input provided."""
        result = self._run_cli([])

        assert result.returncode == 3
        assert "Input file is required" in result.stderr

    def test_exit_code_input_error_invalid_json_options(self, tmp_path):
        """Test exit code 3 (VALIDATION_ERROR) for invalid options JSON."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<h1>Test</h1>")

        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{ invalid json }")

        result = self._run_cli([
            str(html_file),
            "--options-json", str(invalid_json)
        ])

        assert result.returncode == 3
        assert "Error" in result.stderr

    def test_exit_code_input_error_malformed_file(self, tmp_path):
        """Test exit code 4 (FILE_ERROR) for malformed input file."""
        # Create invalid JSON for ipynb
        invalid_ipynb = tmp_path / "invalid.ipynb"
        invalid_ipynb.write_text("{ invalid json }")

        result = self._run_cli([str(invalid_ipynb)])

        assert result.returncode == 4
        assert "Error" in result.stderr

    def test_exit_code_input_error_invalid_format(self, tmp_path):
        """Test exit code 3 (VALIDATION_ERROR) for invalid format specification."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<h1>Test</h1>")

        # Test with list-formats command - invalid format name
        result = self._run_cli(["list-formats", "invalid_format_xyz"])

        assert result.returncode == 3
        assert "Error" in result.stderr

    def test_exit_code_dependency_error_missing_rich(self, tmp_path):
        """Test exit code 2 (DEPENDENCY_ERROR) when Rich is required but missing.

        Note: This test will pass if Rich is installed, so we skip it in that case.
        """
        try:
            import importlib.util
            if importlib.util.find_spec("rich") is not None:
                pytest.skip("Rich is installed, cannot test missing dependency")
        except Exception:
            pass

        html_file = tmp_path / "test.html"
        html_file.write_text("<h1>Test</h1>")

        result = self._run_cli([str(html_file), "--rich"])

        assert result.returncode == 2
        assert "Rich library not installed" in result.stderr

    def test_exit_code_conversion_error(self, tmp_path):
        """Test exit code for conversion failures.

        This tests that conversion errors return appropriate exit codes based on failure type.
        """
        # Create a file with valid structure but problematic content
        # that might cause conversion issues
        test_file = tmp_path / "test.docx"
        # Write some bytes that look like a docx but aren't valid
        test_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        result = self._run_cli([str(test_file)])

        # Should be file error (4) or parsing error (6) depending on where it fails
        assert result.returncode in [4, 6]
        assert "Error" in result.stderr

    def test_exit_code_multiple_files_highest_error(self, tmp_path):
        """Test that with multiple files, highest exit code is returned.

        Note: Nonexistent files are filtered during collection with a warning,
        so they don't cause failure if at least one valid file exists.
        """
        # Create one valid file and one nonexistent file
        valid_file = tmp_path / "valid.html"
        valid_file.write_text("<h1>Valid</h1>")

        nonexistent = tmp_path / "nonexistent.html"

        output_dir = tmp_path / "output"
        result = self._run_cli([
            str(valid_file),
            str(nonexistent),
            "--output-dir", str(output_dir)
        ])

        # Nonexistent files are filtered with warning, but processing succeeds
        assert result.returncode == 0
        assert "WARNING: Path does not exist" in result.stderr
        assert "valid.html" in result.stdout

    def test_exit_code_skip_errors_with_conversion_failure(self, tmp_path):
        """Test that --skip-errors returns highest exit code when files fail conversion.

        Note: We need to test with actual conversion failures, not just missing files,
        since missing files are filtered during collection.
        """
        valid_file = tmp_path / "valid.html"
        valid_file.write_text("<h1>Valid</h1>")

        # Create a malformed ipynb that will fail during conversion
        invalid_file = tmp_path / "invalid.ipynb"
        invalid_file.write_text("{ invalid json }")

        output_dir = tmp_path / "output"
        result = self._run_cli([
            str(valid_file),
            str(invalid_file),
            "--output-dir", str(output_dir),
            "--skip-errors"
        ])

        # Should return 4 (file error from malformed file)
        assert result.returncode == 4
        # But should have processed the valid file
        assert "valid.html" in result.stdout or "valid.md" in result.stdout

    def test_exit_code_detect_only_missing_dependency(self, tmp_path):
        """Test exit code 2 for detect-only when converter unavailable.

        Note: This is hard to test reliably since it depends on what's installed.
        """
        # This test would need a file format with unavailable dependencies
        # For now, we'll just verify the command doesn't crash
        html_file = tmp_path / "test.html"
        html_file.write_text("<h1>Test</h1>")

        result = self._run_cli([str(html_file), "--detect-only"])

        # Should succeed since HTML converter is always available
        assert result.returncode == 0

    def test_exit_code_stdin_no_data(self):
        """Test exit code when reading from stdin with no data."""
        # Simulate empty stdin
        import sys
        cmd = [sys.executable, "-m", "all2md", "-"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=""
        )

        # Should return error (likely 1 for general error)
        assert result.returncode != 0
        assert "Error" in result.stderr


@pytest.mark.e2e
class TestExitCodeConstants:
    """Test that exit code constants are properly defined and used."""

    def test_constants_defined(self):
        """Test that exit code constants are defined in constants.py."""
        from all2md.constants import (
            EXIT_DEPENDENCY_ERROR,
            EXIT_ERROR,
            EXIT_FILE_ERROR,
            EXIT_FORMAT_ERROR,
            EXIT_PARSING_ERROR,
            EXIT_PASSWORD_ERROR,
            EXIT_RENDERING_ERROR,
            EXIT_SECURITY_ERROR,
            EXIT_SUCCESS,
            EXIT_VALIDATION_ERROR,
        )

        assert EXIT_SUCCESS == 0
        assert EXIT_ERROR == 1
        assert EXIT_DEPENDENCY_ERROR == 2
        assert EXIT_VALIDATION_ERROR == 3
        assert EXIT_FILE_ERROR == 4
        assert EXIT_FORMAT_ERROR == 5
        assert EXIT_PARSING_ERROR == 6
        assert EXIT_RENDERING_ERROR == 7
        assert EXIT_SECURITY_ERROR == 8
        assert EXIT_PASSWORD_ERROR == 9

    def test_get_exit_code_for_exception_malformed_error(self):
        """Test mapping MalformedFileError to exit code 4."""
        from all2md.constants import EXIT_FILE_ERROR, get_exit_code_for_exception
        from all2md.exceptions import MalformedFileError

        exc = MalformedFileError("Test malformed file error")
        assert get_exit_code_for_exception(exc) == EXIT_FILE_ERROR

    def test_get_exit_code_for_exception_dependency_error(self):
        """Test mapping DependencyError to exit code 2."""
        from all2md.constants import EXIT_DEPENDENCY_ERROR, get_exit_code_for_exception
        from all2md.exceptions import DependencyError

        exc = DependencyError("test", [("pkg", ">=1.0")])
        assert get_exit_code_for_exception(exc) == EXIT_DEPENDENCY_ERROR

    def test_get_exit_code_for_exception_import_error(self):
        """Test mapping ImportError to exit code 2."""
        from all2md.constants import EXIT_DEPENDENCY_ERROR, get_exit_code_for_exception

        exc = ImportError("Test import error")
        assert get_exit_code_for_exception(exc) == EXIT_DEPENDENCY_ERROR

    def test_get_exit_code_for_exception_parsing_error(self):
        """Test mapping ParsingError to exit code 6."""
        from all2md.constants import EXIT_PARSING_ERROR, get_exit_code_for_exception
        from all2md.exceptions import ParsingError

        exc = ParsingError("Test parsing error")
        assert get_exit_code_for_exception(exc) == EXIT_PARSING_ERROR

    def test_get_exit_code_for_exception_generic(self):
        """Test mapping generic exceptions to exit code 1."""
        from all2md.constants import EXIT_ERROR, get_exit_code_for_exception

        exc = ValueError("Test generic error")
        assert get_exit_code_for_exception(exc) == EXIT_ERROR
