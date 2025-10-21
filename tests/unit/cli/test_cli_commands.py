"""Unit tests for CLI command functions."""

import argparse
from pathlib import Path

import pytest

from all2md.cli.commands import parse_batch_list


@pytest.mark.unit
class TestParseBatchList:
    """Test parse_batch_list() function."""

    def test_parse_batch_list_basic(self, tmp_path: Path):
        """Test basic batch list parsing."""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create batch list
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text(f"{file1}\n{file2}\n")

        # Parse batch list
        result = parse_batch_list(batch_list)

        assert len(result) == 2
        assert str(file1) in result
        assert str(file2) in result

    def test_parse_batch_list_comments(self, tmp_path: Path):
        """Test that comments are ignored."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Create batch list with comments
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text(f"# This is a comment\n{test_file}\n# Another comment\n")

        result = parse_batch_list(batch_list)

        assert len(result) == 1
        assert str(test_file) in result

    def test_parse_batch_list_empty_lines(self, tmp_path: Path):
        """Test that empty lines are ignored."""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create batch list with empty lines
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text(f"{file1}\n\n\n{file2}\n\n")

        result = parse_batch_list(batch_list)

        assert len(result) == 2

    def test_parse_batch_list_relative_paths(self, tmp_path: Path):
        """Test that relative paths are resolved relative to list file directory."""
        # Create subdirectory and files
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        file1 = tmp_path / "root_file.txt"
        file2 = subdir / "sub_file.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create batch list in subdir with relative path to parent
        batch_list = subdir / "batch.txt"
        batch_list.write_text("../root_file.txt\nsub_file.txt\n")

        result = parse_batch_list(batch_list)

        assert len(result) == 2
        # Paths should be absolute
        assert Path(result[0]).is_absolute()
        assert Path(result[1]).is_absolute()

    def test_parse_batch_list_nonexistent_file_error(self, tmp_path: Path):
        """Test error when batch list file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(argparse.ArgumentTypeError, match="does not exist"):
            parse_batch_list(nonexistent)

    def test_parse_batch_list_file_not_found_in_list(self, tmp_path: Path):
        """Test error when file listed in batch file doesn't exist."""
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text("nonexistent_file.pdf\n")

        with pytest.raises(argparse.ArgumentTypeError, match="File not found in batch list"):
            parse_batch_list(batch_list)

    def test_parse_batch_list_empty_list_error(self, tmp_path: Path):
        """Test error when batch list is empty or has no valid entries."""
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text("# Only comments\n\n# More comments\n")

        with pytest.raises(argparse.ArgumentTypeError, match="empty or contains no valid entries"):
            parse_batch_list(batch_list)

    def test_parse_batch_list_from_stdin(self, monkeypatch, tmp_path: Path):
        """Test reading batch list from stdin."""
        import sys
        from io import StringIO

        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Mock stdin
        stdin_content = f"{file1}\n{file2}\n"
        monkeypatch.setattr(sys, "stdin", StringIO(stdin_content))

        # Test with "-" to read from stdin
        result = parse_batch_list("-")

        assert len(result) == 2
        assert str(file1) in result
        assert str(file2) in result

    def test_parse_batch_list_mixed_absolute_relative(self, tmp_path: Path):
        """Test batch list with mix of absolute and relative paths."""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        # Create batch list with mix of absolute and relative paths
        batch_list = tmp_path / "batch.txt"
        batch_list.write_text(f"{file1}\nfile2.txt\n")

        result = parse_batch_list(batch_list)

        assert len(result) == 2
        # Both should be absolute after processing
        assert Path(result[0]).is_absolute()
        assert Path(result[1]).is_absolute()
