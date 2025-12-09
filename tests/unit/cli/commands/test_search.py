"""Unit tests for all2md CLI search command handlers.

This module tests the search and grep command handlers directly,
providing coverage for argument parsing and helper functions.
"""

import argparse

import pytest

from all2md.cli.commands.search import (
    _format_plain_snippet,
    _parse_line_number_if_present,
    _parse_search_mode,
    handle_grep_command,
    handle_search_command,
)
from all2md.options.search import SearchOptions


@pytest.mark.unit
class TestSearchCommandHelpers:
    """Test helper functions for search command."""

    def test_parse_line_number_present(self):
        """Test parsing line number from grep output."""
        line_num, content = _parse_line_number_if_present("42: some text here", True)
        assert line_num == "42"
        assert content == "some text here"

    def test_parse_line_number_absent(self):
        """Test parsing when no line number present."""
        line_num, content = _parse_line_number_if_present("just text", True)
        assert line_num is None
        assert content == "just text"

    def test_parse_line_number_disabled(self):
        """Test parsing when line numbers disabled."""
        line_num, content = _parse_line_number_if_present("42: text", False)
        assert line_num is None
        assert content == "42: text"

    def test_format_plain_snippet_basic(self):
        """Test formatting plain text snippet."""
        lines = _format_plain_snippet("Short text", width=100, indent="  ")
        assert len(lines) == 1
        assert lines[0] == "  Short text"

    def test_format_plain_snippet_multiline(self):
        """Test formatting multiline snippet."""
        text = "Line 1\nLine 2\nLine 3"
        lines = _format_plain_snippet(text, width=100, indent="    ")
        assert len(lines) == 3
        assert all(line.startswith("    ") for line in lines)

    def test_parse_search_mode_grep(self):
        """Test parsing grep mode."""
        from all2md.search.service import SearchMode

        options = SearchOptions()
        mode = _parse_search_mode("grep", options)
        assert mode == SearchMode.GREP

    def test_parse_search_mode_keyword(self):
        """Test parsing keyword mode."""
        from all2md.search.service import SearchMode

        options = SearchOptions()
        mode = _parse_search_mode("keyword", options)
        assert mode == SearchMode.KEYWORD

    def test_parse_search_mode_invalid(self):
        """Test parsing invalid mode raises error."""
        options = SearchOptions()
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_search_mode("invalid_mode", options)


@pytest.mark.unit
class TestHandleSearchCommand:
    """Test handle_search_command function."""

    def test_search_help(self, capsys):
        """Test search --help returns successfully."""
        exit_code = handle_search_command(["--help"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_search_missing_query(self):
        """Test search without query fails."""
        exit_code = handle_search_command([])
        # Returns non-zero or raises SystemExit
        if exit_code is not None:
            assert exit_code != 0

    def test_search_persist_without_index_dir(self, capsys):
        """Test --persist requires --index-dir."""
        try:
            exit_code = handle_search_command(["query", "file.md", "--persist"])
            assert exit_code != 0
        except SystemExit as e:
            assert e.code != 0
        captured = capsys.readouterr()
        assert "--persist requires --index-dir" in captured.err

    def test_search_negative_context(self, capsys):
        """Test negative context values are rejected."""
        with pytest.raises(SystemExit):
            handle_search_command(["query", "file.md", "--grep", "-A", "-1"])


@pytest.mark.unit
class TestHandleGrepCommand:
    """Test handle_grep_command function."""

    def test_grep_help(self, capsys):
        """Test grep --help returns successfully."""
        with pytest.raises(SystemExit) as exc_info:
            handle_grep_command(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_grep_missing_inputs(self):
        """Test grep without inputs fails."""
        with pytest.raises(SystemExit):
            handle_grep_command([])
