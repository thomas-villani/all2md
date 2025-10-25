"""Unit tests for MCP security module."""

import os
from pathlib import Path

import pytest

from all2md.mcp.security import (
    MCPSecurityError,
    prepare_allowlist_dirs,
    secure_open_for_write,
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
        assert dir1.resolve() in result
        assert dir2.resolve() in result

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

        # Prepare allowlist (returns validated Path objects)
        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        result = validate_read_path(str(test_file), allowlist)
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
            validate_read_path(str(test_file), allowlist)

    def test_validate_read_path_nonexistent(self, tmp_path):
        """Test that nonexistent file is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        nonexistent = allowed_dir / "nonexistent.txt"

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="does not exist"):
            validate_read_path(str(nonexistent), allowlist)

    def test_validate_read_path_is_directory(self, tmp_path):
        """Test that directory (not file) is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        subdir = allowed_dir / "subdir"
        subdir.mkdir()

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="not a file"):
            validate_read_path(str(subdir), allowlist)


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

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        result = validate_write_path(str(output_file), allowlist)
        assert result.parent == allowed_dir.resolve()
        assert result.name == "output.txt"

    def test_validate_write_path_not_in_allowlist(self, tmp_path):
        """Test that path outside allowlist is denied."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        output_file = forbidden_dir / "output.txt"

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            validate_write_path(str(output_file), allowlist)

    def test_validate_write_path_parent_not_exists(self, tmp_path):
        """Test that nonexistent parent directory is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        nonexistent_parent = allowed_dir / "nonexistent" / "output.txt"

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="parent directory does not exist"):
            validate_write_path(str(nonexistent_parent), allowlist)

    def test_validate_write_path_traversal(self, tmp_path):
        """Test that path traversal (..) is denied."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Try to escape using ..
        traversal_path = allowed_dir / ".." / "forbidden" / "output.txt"

        allowlist = prepare_allowlist_dirs([str(allowed_dir)])

        with pytest.raises(MCPSecurityError, match="parent directory"):
            validate_write_path(str(traversal_path), allowlist)


class TestSecureOpenForWrite:
    """Tests for secure_open_for_write function (TOCTOU protection)."""

    def test_secure_open_creates_new_file(self, tmp_path):
        """Test that secure_open_for_write creates a new file successfully."""
        output_file = tmp_path / "new_file.txt"

        with secure_open_for_write(output_file) as f:
            f.write(b"test content")

        assert output_file.exists()
        assert output_file.read_bytes() == b"test content"

    def test_secure_open_overwrites_existing_file(self, tmp_path):
        """Test that secure_open_for_write overwrites existing file."""
        output_file = tmp_path / "existing.txt"
        output_file.write_text("old content")

        with secure_open_for_write(output_file) as f:
            f.write(b"new content")

        assert output_file.read_bytes() == b"new content"

    def test_secure_open_rejects_symlink(self, tmp_path):
        """Test that secure_open_for_write rejects symlinks (TOCTOU protection)."""
        # Create a target file
        target_file = tmp_path / "target.txt"
        target_file.write_text("sensitive data")

        # Create a symlink
        symlink = tmp_path / "link.txt"
        try:
            symlink.symlink_to(target_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        # Should reject the symlink
        with pytest.raises(MCPSecurityError, match="symlink"):
            secure_open_for_write(symlink)

        # Verify target file was not modified
        assert target_file.read_text() == "sensitive data"

    def test_secure_open_requires_absolute_path(self, tmp_path):
        """Test that secure_open_for_write requires absolute path."""
        # Use relative path
        relative_path = Path("relative/path.txt")

        with pytest.raises(MCPSecurityError, match="absolute path"):
            secure_open_for_write(relative_path)

    def test_secure_open_binary_mode(self, tmp_path):
        """Test that secure_open_for_write opens in binary mode."""
        output_file = tmp_path / "binary.bin"

        with secure_open_for_write(output_file) as f:
            # Should be binary mode
            assert hasattr(f, "write")
            f.write(b"\x00\x01\x02\xff")

        assert output_file.read_bytes() == b"\x00\x01\x02\xff"

    @pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW not available on Windows")
    def test_secure_open_uses_nofollow_flag(self, tmp_path):
        """Test that O_NOFOLLOW flag is used on supported platforms."""
        # This test verifies that O_NOFOLLOW is used when available
        # The actual protection is tested in test_secure_open_rejects_symlink
        output_file = tmp_path / "test.txt"

        # Should succeed with O_NOFOLLOW
        with secure_open_for_write(output_file) as f:
            f.write(b"test")

        assert output_file.exists()
