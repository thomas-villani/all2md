"""Unit tests for the diff CLI command."""

import argparse
from pathlib import Path

import pytest

from all2md.cli.commands.diff import (
    _create_diff_parser,
    _validate_context_lines,
    handle_diff_command,
)


@pytest.mark.unit
class TestValidateContextLines:
    """Test _validate_context_lines() helper function."""

    def test_valid_positive_integer(self):
        """Test valid positive integer."""
        assert _validate_context_lines("3") == 3
        assert _validate_context_lines("0") == 0
        assert _validate_context_lines("10") == 10

    def test_invalid_negative_integer(self):
        """Test rejection of negative integer."""
        with pytest.raises(argparse.ArgumentTypeError, match="non-negative"):
            _validate_context_lines("-1")

    def test_invalid_non_integer(self):
        """Test rejection of non-integer value."""
        with pytest.raises(argparse.ArgumentTypeError, match="must be an integer"):
            _validate_context_lines("abc")

    def test_invalid_float(self):
        """Test rejection of float value."""
        with pytest.raises(argparse.ArgumentTypeError, match="must be an integer"):
            _validate_context_lines("3.5")


@pytest.mark.unit
class TestCreateDiffParser:
    """Test _create_diff_parser() function."""

    def test_parser_creation(self):
        """Test parser is created correctly."""
        parser = _create_diff_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "all2md diff"

    def test_parser_required_args(self):
        """Test parser requires source files."""
        parser = _create_diff_parser()
        # Should fail without source files
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_format_options(self):
        """Test parser accepts format options."""
        parser = _create_diff_parser()
        args = parser.parse_args(["file1.txt", "file2.txt", "--format", "html"])
        assert args.format == "html"
        assert args.source1 == "file1.txt"
        assert args.source2 == "file2.txt"

    def test_parser_default_values(self):
        """Test parser default values."""
        parser = _create_diff_parser()
        args = parser.parse_args(["file1.txt", "file2.txt"])
        assert args.format == "unified"
        assert args.context == 3
        assert args.granularity == "block"
        assert args.color == "auto"
        assert args.ignore_whitespace is False
        assert args.show_context is True

    def test_parser_all_options(self):
        """Test parser with all options."""
        parser = _create_diff_parser()
        args = parser.parse_args(
            [
                "file1.txt",
                "file2.txt",
                "--format",
                "json",
                "--output",
                "diff.json",
                "--color",
                "never",
                "--ignore-whitespace",
                "--context",
                "5",
                "--granularity",
                "word",
                "--no-context",
            ]
        )
        assert args.format == "json"
        assert args.output == "diff.json"
        assert args.color == "never"
        assert args.ignore_whitespace is True
        assert args.context == 5
        assert args.granularity == "word"
        assert args.show_context is False


@pytest.mark.unit
class TestHandleDiffCommand:
    """Test handle_diff_command() function."""

    def test_missing_source1(self, tmp_path: Path):
        """Test error when source1 doesn't exist."""
        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

        result = handle_diff_command(["nonexistent.txt", str(file2)])
        assert result != 0  # Should return error

    def test_missing_source2(self, tmp_path: Path):
        """Test error when source2 doesn't exist."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")

        result = handle_diff_command([str(file1), "nonexistent.txt"])
        assert result != 0  # Should return error

    def test_identical_files(self, tmp_path: Path):
        """Test diffing identical files returns 0."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("identical content\n")
        file2.write_text("identical content\n")

        result = handle_diff_command([str(file1), str(file2)])
        assert result == 0

    def test_different_files_unified(self, tmp_path: Path, capsys):
        """Test diffing different files with unified format."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nmodified\nline3\n")

        result = handle_diff_command([str(file1), str(file2), "--color", "never"])
        assert result == 0

    def test_different_files_html_output(self, tmp_path: Path):
        """Test diffing with HTML output to file."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        output = tmp_path / "diff.html"

        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nmodified\nline3\n")

        result = handle_diff_command([str(file1), str(file2), "--format", "html", "--output", str(output)])
        assert result == 0
        assert output.exists()
        content = output.read_text()
        assert "<!DOCTYPE html>" in content or "<html" in content.lower()

    def test_different_files_json_output(self, tmp_path: Path):
        """Test diffing with JSON output to file."""
        import json

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        output = tmp_path / "diff.json"

        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nmodified\nline3\n")

        result = handle_diff_command([str(file1), str(file2), "--format", "json", "--output", str(output)])
        assert result == 0
        assert output.exists()
        # Should be valid JSON
        data = json.loads(output.read_text())
        assert isinstance(data, dict)

    def test_ignore_whitespace(self, tmp_path: Path):
        """Test ignore whitespace option."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line1\nline2\n")
        file2.write_text("line1  \nline2\n")  # Extra whitespace

        result = handle_diff_command([str(file1), str(file2), "--ignore-whitespace"])
        assert result == 0

    def test_context_lines(self, tmp_path: Path):
        """Test custom context lines."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nmodified\nline3\n")

        result = handle_diff_command([str(file1), str(file2), "--context", "5"])
        assert result == 0

    def test_granularity_sentence(self, tmp_path: Path):
        """Test sentence granularity."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("First sentence. Second sentence.")
        file2.write_text("First sentence. Modified sentence.")

        result = handle_diff_command([str(file1), str(file2), "--granularity", "sentence"])
        assert result == 0

    def test_granularity_word(self, tmp_path: Path):
        """Test word granularity."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("hello world")
        file2.write_text("hello there")

        result = handle_diff_command([str(file1), str(file2), "--granularity", "word"])
        assert result == 0

    def test_help_returns_zero(self):
        """Test --help returns exit code 0."""
        result = handle_diff_command(["--help"])
        assert result == 0

    def test_no_changes_with_output_file(self, tmp_path: Path):
        """Test no changes still writes output file in requested format."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        output = tmp_path / "diff.html"

        file1.write_text("identical\n")
        file2.write_text("identical\n")

        result = handle_diff_command([str(file1), str(file2), "--format", "html", "--output", str(output)])
        assert result == 0
        assert output.exists()
