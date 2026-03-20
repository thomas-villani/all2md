#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/cli/test_cli_arxiv.py
"""Unit tests for the ArXiv CLI command.

Tests cover:
- Argument parsing
- Error handling for missing files
- Successful package generation
"""

import pytest


@pytest.mark.unit
class TestCliArxiv:
    """Tests for the arxiv CLI command."""

    def test_missing_input_file(self, tmp_path):
        """Should return error for nonexistent input file."""
        from all2md.cli.commands.arxiv import handle_arxiv_command

        result = handle_arxiv_command(["nonexistent.pdf", "-o", str(tmp_path / "out.tar.gz")])
        assert result == 4  # EXIT_FILE_ERROR

    def test_missing_bib_file(self, tmp_path):
        """Should return error for nonexistent bib file."""
        from all2md.cli.commands.arxiv import handle_arxiv_command

        # Create a valid input file
        input_file = tmp_path / "input.md"
        input_file.write_text("# Hello\n\nWorld")

        result = handle_arxiv_command(
            [
                str(input_file),
                "-o",
                str(tmp_path / "out.tar.gz"),
                "--bib",
                "nonexistent.bib",
            ]
        )
        assert result == 4  # EXIT_FILE_ERROR

    def test_successful_generation(self, tmp_path):
        """Should generate archive from a markdown file."""
        from all2md.cli.commands.arxiv import handle_arxiv_command

        input_file = tmp_path / "input.md"
        input_file.write_text("# Test Document\n\nSome content here.")

        output = tmp_path / "submission.tar.gz"
        result = handle_arxiv_command([str(input_file), "-o", str(output)])

        assert result == 0
        assert output.exists()

    def test_directory_output_format(self, tmp_path):
        """Should generate directory output when requested."""
        from all2md.cli.commands.arxiv import handle_arxiv_command

        input_file = tmp_path / "input.md"
        input_file.write_text("# Test\n\nContent")

        output = tmp_path / "submission_dir"
        result = handle_arxiv_command(
            [
                str(input_file),
                "-o",
                str(output),
                "--output-format",
                "directory",
            ]
        )

        assert result == 0
        assert (output / "main.tex").exists()

    def test_dispatch_routes_arxiv(self):
        """dispatch_command should route 'arxiv' to the handler."""
        from all2md.cli.commands import dispatch_command

        # With no valid file, should return an error code (not None)
        result = dispatch_command(["arxiv", "nonexistent.pdf", "-o", "out.tar.gz"])
        assert result is not None
