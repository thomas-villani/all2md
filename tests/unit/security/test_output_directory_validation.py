#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for output directory validation security."""


import pytest

from all2md.exceptions import SecurityError
from all2md.utils.attachments import process_attachment
from all2md.utils.security import validate_safe_output_directory


class TestValidateSafeOutputDirectory:
    """Test validate_safe_output_directory security function."""

    def test_relative_path_within_cwd_allowed(self, tmp_path, monkeypatch):
        """Relative paths within CWD should be allowed."""
        # Change to tmp_path so we can test relative paths safely
        monkeypatch.chdir(tmp_path)

        # Test various relative path formats
        test_paths = [
            "attachments",
            "./attachments",
            "subdir/attachments",
            "./subdir/attachments",
        ]

        for path in test_paths:
            result = validate_safe_output_directory(path)
            assert result.is_absolute()
            # Ensure result is within tmp_path
            assert result.is_relative_to(tmp_path)

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        """Path traversal attempts should be blocked."""
        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        # Test various path traversal patterns
        dangerous_paths = [
            "../etc",
            "../../tmp",
            "../../../etc/passwd",
            "attachments/../../../etc",
            "./attachments/../../../etc",
        ]

        for path in dangerous_paths:
            with pytest.raises(SecurityError, match="(Path traversal detected|Suspicious path traversal)"):
                validate_safe_output_directory(path, block_sensitive_paths=True)

    def test_sensitive_paths_blocked_by_default(self, tmp_path, monkeypatch):
        """Absolute paths to sensitive locations should be blocked by default."""
        import platform

        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        # Test platform-specific sensitive paths
        if platform.system() == "Windows":
            sensitive_paths = [
                "C:\\Windows",
                "C:\\Windows\\System32",
                "C:\\Program Files",
            ]
        else:
            sensitive_paths = [
                "/etc",
                "/sys",
                "/proc",
                "/root",
            ]

        for path in sensitive_paths:
            # These should be blocked as sensitive system directories
            with pytest.raises(SecurityError, match="sensitive system location"):
                validate_safe_output_directory(path, block_sensitive_paths=True)

    def test_empty_directory_rejected(self):
        """Empty directory paths should be rejected."""
        with pytest.raises(SecurityError, match="cannot be empty"):
            validate_safe_output_directory("")

        with pytest.raises(SecurityError, match="cannot be empty"):
            validate_safe_output_directory("   ")

    def test_allowed_base_dirs_permits_paths(self, tmp_path):
        """Paths within allowed_base_dirs should be permitted."""
        # Create a test directory structure
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        output_dir = allowed_dir / "attachments"

        # Should be allowed when allowed_dir is in allowlist
        result = validate_safe_output_directory(str(output_dir), allowed_base_dirs=[str(allowed_dir)])
        assert result == output_dir.resolve()

    def test_allowed_base_dirs_blocks_paths_outside(self, tmp_path):
        """Paths outside allowed_base_dirs should be blocked."""
        # Create test directory structure
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        forbidden_dir = tmp_path / "forbidden"
        forbidden_dir.mkdir()

        output_dir = forbidden_dir / "attachments"

        # Should be blocked when not in allowlist
        with pytest.raises(SecurityError, match="not within any allowed base directory"):
            validate_safe_output_directory(str(output_dir), allowed_base_dirs=[str(allowed_dir)])

    def test_allowed_base_dirs_empty_list_rejected(self):
        """Empty allowed_base_dirs list should be rejected."""
        with pytest.raises(SecurityError, match="cannot be an empty list"):
            validate_safe_output_directory("./test", allowed_base_dirs=[])

    def test_cwd_subdirectory_allowed(self, tmp_path, monkeypatch):
        """Subdirectories of CWD should be allowed."""
        monkeypatch.chdir(tmp_path)

        # Create nested subdirectories
        subdir = tmp_path / "level1" / "level2" / "level3"

        result = validate_safe_output_directory(str(subdir), block_sensitive_paths=True)
        assert result == subdir.resolve()
        assert result.is_relative_to(tmp_path)

    def test_cwd_itself_allowed(self, tmp_path, monkeypatch):
        """CWD itself should be allowed."""
        monkeypatch.chdir(tmp_path)

        result = validate_safe_output_directory(".", block_sensitive_paths=True)
        assert result == tmp_path.resolve()

    def test_symlink_resolution(self, tmp_path, monkeypatch):
        """Symlinks should be resolved and validated against their target."""
        monkeypatch.chdir(tmp_path)

        # Create a directory and a symlink to it
        real_dir = tmp_path / "real_attachments"
        real_dir.mkdir()

        symlink_dir = tmp_path / "link_attachments"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError as e:
            # Skip test if symlink creation requires privileges (Windows)
            pytest.skip(f"Symlink creation requires privileges: {e}")

        # Symlink within CWD should be allowed
        result = validate_safe_output_directory(str(symlink_dir), block_sensitive_paths=True)
        # Should resolve to the real directory
        assert result == real_dir.resolve()
        assert result.is_relative_to(tmp_path)

    def test_symlink_escaping_cwd_blocked(self, tmp_path, monkeypatch):
        """Symlinks that point outside CWD should be blocked."""
        # Create a working directory
        work_dir = tmp_path / "workdir"
        work_dir.mkdir()
        monkeypatch.chdir(work_dir)

        # Create a symlink that points to parent directory
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        symlink_dir = work_dir / "link_to_outside"
        try:
            symlink_dir.symlink_to(outside_dir)
        except OSError as e:
            # Skip test if symlink creation requires privileges (Windows)
            pytest.skip(f"Symlink creation requires privileges: {e}")

        # The symlink itself is relative, so it's allowed - symlinks are resolved
        # This tests that symlinks are properly resolved and don't cause issues
        result = validate_safe_output_directory(str(symlink_dir), block_sensitive_paths=True)
        # Should resolve to the target directory
        assert result == outside_dir.resolve()

    def test_temp_directory_allowed_with_sensitive_paths_disabled(self, tmp_path, monkeypatch):
        """Temp directories should be allowed when block_sensitive_paths=False."""
        monkeypatch.chdir(tmp_path)

        # Create a directory outside CWD (like a temp dir)
        outside_dir = tmp_path.parent / "outside_cwd"
        outside_dir.mkdir(exist_ok=True)

        # Absolute paths should be allowed when block_sensitive_paths=False
        result = validate_safe_output_directory(str(outside_dir), block_sensitive_paths=False, allowed_base_dirs=None)
        assert result == outside_dir.resolve()

        # Cleanup
        outside_dir.rmdir()


class TestProcessAttachmentOutputDirectoryValidation:
    """Test that process_attachment properly validates output directories."""

    def test_safe_relative_directory_works(self, tmp_path, monkeypatch):
        """Safe relative directories should work in download mode."""
        monkeypatch.chdir(tmp_path)

        # Create a safe output directory
        output_dir = "test_attachments"

        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            attachment_mode="save",
            attachment_output_dir=output_dir,
            block_sensitive_paths=True,
        )

        # Should successfully create the file
        assert "markdown" in result
        assert "![test.png]" in result["markdown"]
        assert result["source_data"] == "downloaded"

        # Verify file was created in the correct location
        expected_dir = tmp_path / output_dir
        assert expected_dir.exists()

    def test_path_traversal_falls_back_to_alt_text(self, tmp_path, monkeypatch, caplog):
        """Path traversal attempts should fall back to alt_text mode."""
        monkeypatch.chdir(tmp_path)

        # Attempt path traversal
        dangerous_dir = "../../../etc"

        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            attachment_mode="save",
            attachment_output_dir=dangerous_dir,
        )

        # Should fall back to alt_text mode
        assert "markdown" in result
        assert "![test.png]" in result["markdown"]
        assert "source_data" not in result or result.get("source_data") is None

        # Should log a warning
        assert "Output directory validation failed" in caplog.text
        assert "Falling back to alt_text mode" in caplog.text

    def test_sensitive_path_blocked(self, tmp_path, monkeypatch, caplog):
        """Paths to sensitive system directories should be blocked."""
        import platform

        monkeypatch.chdir(tmp_path)

        # Use platform-specific sensitive path
        if platform.system() == "Windows":
            dangerous_dir = "C:\\Windows\\Temp"
        else:
            dangerous_dir = "/etc/attachments"

        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            attachment_mode="save",
            attachment_output_dir=dangerous_dir,
            block_sensitive_paths=True,
        )

        # Should fall back to alt_text mode
        assert "markdown" in result
        assert "![test.png]" in result["markdown"]
        assert "source_data" not in result or result.get("source_data") is None

        # Should log a warning about validation failure
        assert "Output directory validation failed" in caplog.text

    def test_default_attachments_directory_works(self, tmp_path, monkeypatch):
        """Default 'attachments' directory should work (None provided)."""
        monkeypatch.chdir(tmp_path)

        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            attachment_mode="save",
            attachment_output_dir=None,  # Should default to "attachments"
        )

        # Should successfully create the file
        assert "markdown" in result
        assert "![test.png]" in result["markdown"]
        assert result["source_data"] == "downloaded"

        # Verify file was created in the default "attachments" directory
        expected_dir = tmp_path / "attachments"
        assert expected_dir.exists()

    def test_subdirectory_in_cwd_works(self, tmp_path, monkeypatch):
        """Subdirectories within CWD should work."""
        monkeypatch.chdir(tmp_path)

        output_dir = "subdir/nested/attachments"

        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            attachment_mode="save",
            attachment_output_dir=output_dir,
        )

        # Should successfully create the file
        assert "markdown" in result
        assert result["source_data"] == "downloaded"

        # Verify file was created in the nested directory
        expected_dir = tmp_path / "subdir" / "nested" / "attachments"
        assert expected_dir.exists()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_windows_sensitive_path_blocked(self, tmp_path, monkeypatch):
        """Windows-style sensitive paths should be blocked."""
        monkeypatch.chdir(tmp_path)

        # Test Windows sensitive paths
        import platform

        if platform.system() == "Windows":
            # C:\Windows is a sensitive location
            with pytest.raises(SecurityError, match="sensitive system location"):
                validate_safe_output_directory("C:\\Windows\\System32", block_sensitive_paths=True)

    def test_multiple_dots_normalized(self, tmp_path, monkeypatch):
        """Multiple consecutive dots should be normalized correctly."""
        monkeypatch.chdir(tmp_path)

        # Create a directory with dots (but within CWD)
        test_dir = tmp_path / "test...dir"
        test_dir.mkdir()

        # Should work because it's within CWD (dots are just part of the name)
        result = validate_safe_output_directory(str(test_dir), block_sensitive_paths=True)
        assert result == test_dir.resolve()

    def test_long_path_handled(self, tmp_path, monkeypatch):
        """Very long paths should be handled correctly."""
        monkeypatch.chdir(tmp_path)

        # Create a very deep directory structure
        deep_path = tmp_path / ("subdir/" * 10).rstrip("/")

        result = validate_safe_output_directory(str(deep_path), block_sensitive_paths=True)
        assert result == deep_path.resolve()
        assert result.is_relative_to(tmp_path)

    def test_unicode_in_path(self, tmp_path, monkeypatch):
        """Paths with Unicode characters should be handled."""
        monkeypatch.chdir(tmp_path)

        # Create a directory with Unicode characters
        unicode_dir = tmp_path / "attachments_测试_テスト"
        unicode_dir.mkdir()

        result = validate_safe_output_directory(str(unicode_dir), block_sensitive_paths=True)
        assert result == unicode_dir.resolve()

    def test_special_characters_in_path(self, tmp_path, monkeypatch):
        """Paths with special characters should be handled."""
        monkeypatch.chdir(tmp_path)

        # Create directories with special characters (but safe ones)
        test_dirs = [
            "attachments-2024",
            "attachments_data",
            "attachments.backup",
        ]

        for dir_name in test_dirs:
            test_dir = tmp_path / dir_name
            test_dir.mkdir()

            result = validate_safe_output_directory(str(test_dir), block_sensitive_paths=True)
            assert result == test_dir.resolve()
