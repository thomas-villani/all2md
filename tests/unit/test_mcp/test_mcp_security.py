"""Unit tests for MCP security module."""

import tempfile
from pathlib import Path

import pytest

from all2md.mcp.security import (
    MCPSecurityError,
    prepare_allowlist_dirs,
    validate_read_path,
    validate_write_path,
)


class TestPrepareAllowlistDirs:
    """Tests for prepare_allowlist_dirs function."""

    def test_prepare_allowlist_none(self):
        """Test that None allowlist returns None."""
        result = prepare_allowlist_dirs(None)
        assert result is None

    def test_prepare_allowlist_valid_dirs(self, tmp_path):
        """Test preparing allowlist with valid directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        result = prepare_allowlist_dirs([str(dir1), str(dir2)])

        assert result is not None
        assert len(result) == 2
        assert str(dir1.resolve()) in result
        assert str(dir2.resolve()) in result

    def test_prepare_allowlist_nonexistent_dir(self, tmp_path):
        """Test that nonexistent directory raises error."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(MCPSecurityError, match="Invalid allowlist path"):
            prepare_allowlist_dirs([str(nonexistent)])

    def test_prepare_allowlist_file_not_dir(self, tmp_path):
        """Test that file path (not directory) raises error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(MCPSecurityError, match="not a directory"):
            prepare_allowlist_dirs([str(file_path)])


class TestValidateReadPath:
    """Tests for validate_read_path function."""

    def test_validate_read_path_no_allowlist(self, tmp_path):
        """Test that no allowlist allows all paths."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = validate_read_path(str(test_file), None)
        assert result == test_file.resolve()

    def test_validate_read_path_in_allowlist(self, tmp_path):
        """Test that path in allowlist is allowed."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        test_file = allowed_dir / "test.txt"
        test_file.write_text("test")

        # Prepare allowlist (returns validated string paths)
        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        result = validate_read_path(
            str(test_file),
            allowlist
        )
        assert result == test_file.resolve()

    def test_validate_read_path_not_in_allowlist(self, tmp_path):
        """Test that path outside allowlist is denied."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        test_file = forbidden_dir / "test.txt"
        test_file.write_text("test")

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            validate_read_path(
                str(test_file),
                allowlist
            )

    def test_validate_read_path_nonexistent(self, tmp_path):
        """Test that nonexistent file is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        nonexistent = allowed_dir / "nonexistent.txt"

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="does not exist"):
            validate_read_path(
                str(nonexistent),
                allowlist
            )

    def test_validate_read_path_is_directory(self, tmp_path):
        """Test that directory (not file) is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        subdir = allowed_dir / "subdir"
        subdir.mkdir()

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="not a file"):
            validate_read_path(
                str(subdir),
                allowlist
            )


class TestValidateWritePath:
    """Tests for validate_write_path function."""

    def test_validate_write_path_no_allowlist(self, tmp_path):
        """Test that no allowlist allows all paths."""
        test_file = tmp_path / "output.txt"

        result = validate_write_path(str(test_file), None)
        # Should return absolute path (file doesn't need to exist yet)
        assert result.parent == tmp_path.resolve()
        assert result.name == "output.txt"

    def test_validate_write_path_in_allowlist(self, tmp_path):
        """Test that path in allowlist is allowed."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        output_file = allowed_dir / "output.txt"

        result = validate_write_path(
            str(output_file),
            [str(allowed_dir)]
        )
        assert result.parent == allowed_dir.resolve()
        assert result.name == "output.txt"

    def test_validate_write_path_not_in_allowlist(self, tmp_path):
        """Test that path outside allowlist is denied."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        output_file = forbidden_dir / "output.txt"

        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            validate_write_path(
                str(output_file),
                [str(allowed_dir)]
            )

    def test_validate_write_path_parent_not_exists(self, tmp_path):
        """Test that nonexistent parent directory is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        nonexistent_parent = allowed_dir / "nonexistent" / "output.txt"

        with pytest.raises(MCPSecurityError, match="parent directory does not exist"):
            validate_write_path(
                str(nonexistent_parent),
                [str(allowed_dir)]
            )

    def test_validate_write_path_traversal(self, tmp_path):
        """Test that path traversal (..) is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Try to escape using ..
        traversal_path = allowed_dir / ".." / "forbidden" / "output.txt"

        with pytest.raises(MCPSecurityError, match="parent directory"):
            validate_write_path(
                str(traversal_path),
                [str(allowed_dir)]
            )
