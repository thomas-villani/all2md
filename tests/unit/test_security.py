#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for security functionality in all2md."""

import tempfile
from pathlib import Path

import pytest

from all2md.utils.attachments import (
    ensure_unique_attachment_path,
    process_attachment,
    sanitize_attachment_filename,
)
from all2md.utils.security import validate_local_file_access


class TestValidateLocalFileAccess:
    """Test validate_local_file_access security function."""

    def test_non_file_url_always_allowed(self):
        """Non-file:// URLs should always be allowed."""
        assert validate_local_file_access("http://example.com/image.png") is True
        assert validate_local_file_access("https://example.com/image.png") is True
        assert validate_local_file_access("data:image/png;base64,abc") is True
        assert validate_local_file_access("cid:123") is True

    def test_master_switch_false_blocks_all_local_files(self):
        """When allow_local_files=False, no local files should be allowed."""
        # Test various file:// URL formats
        test_urls = [
            "file:///etc/passwd",
            "file:///home/user/document.pdf",
            "file://./image.png",  # Current directory
            "file://../image.png",  # Parent directory
            "file://image.png",  # Relative path
        ]

        for url in test_urls:
            assert validate_local_file_access(
                url,
                allow_local_files=False,
                allow_cwd_files=True  # Should be ignored when master switch is False
            ) is False

    def test_master_switch_false_ignores_allowlist(self):
        """When allow_local_files=False, allowlist should be ignored."""
        assert validate_local_file_access(
            "file:///allowed/path/image.png",
            allow_local_files=False,
            local_file_allowlist=["/allowed/path"],
            allow_cwd_files=True
        ) is False

    def test_master_switch_false_with_denylist_still_blocks(self):
        """When allow_local_files=False, denylist check should still block but master switch takes precedence."""
        # File not in denylist but still blocked by master switch
        assert validate_local_file_access(
            "file:///not/denied/image.png",
            allow_local_files=False,
            local_file_denylist=["/denied/path"],
            allow_cwd_files=True
        ) is False

    def test_denylist_blocks_access_even_when_allowed(self):
        """Denylist should block access even when allow_local_files=True."""
        denied_path = str(Path.cwd() / "denied")

        assert validate_local_file_access(
            f"file://{denied_path}/image.png",
            allow_local_files=True,
            local_file_denylist=[denied_path],
            allow_cwd_files=True
        ) is False

    def test_cwd_access_requires_master_switch(self):
        """CWD access should only work when allow_local_files=True."""
        cwd_path = Path.cwd()
        test_file_url = f"file://{cwd_path}/image.png"

        # Should be blocked when master switch is False
        assert validate_local_file_access(
            test_file_url,
            allow_local_files=False,
            allow_cwd_files=True
        ) is False

        # Should be allowed when master switch is True and allow_cwd_files=True
        assert validate_local_file_access(
            test_file_url,
            allow_local_files=True,
            allow_cwd_files=True
        ) is True

        # Should be allowed when master switch is True but allow_cwd_files=False
        # (falls through to default allow when no allowlist provided)
        assert validate_local_file_access(
            test_file_url,
            allow_local_files=True,
            allow_cwd_files=False
        ) is True

        # Should be blocked when master switch is True, allow_cwd_files=False, and empty allowlist
        assert validate_local_file_access(
            test_file_url,
            allow_local_files=True,
            allow_cwd_files=False,
            local_file_allowlist=[]
        ) is False

    def test_relative_cwd_paths(self):
        """Test relative path handling for CWD files."""
        test_cases = [
            "file://./image.png",
            "file://../image.png",
            "file://image.png",
        ]

        for url in test_cases:
            # Blocked when master switch is False
            assert validate_local_file_access(
                url,
                allow_local_files=False,
                allow_cwd_files=True
            ) is False

            # Allowed when both switches are True
            assert validate_local_file_access(
                url,
                allow_local_files=True,
                allow_cwd_files=True
            ) is True

    def test_allowlist_functionality(self):
        """Test allowlist functionality when master switch is enabled."""
        allowed_dir = "/allowed/directory"
        not_allowed_dir = "/not/allowed"

        # File in allowed directory should be permitted
        assert validate_local_file_access(
            f"file://{allowed_dir}/image.png",
            allow_local_files=True,
            local_file_allowlist=[allowed_dir],
            allow_cwd_files=False
        ) is True

        # File not in allowed directory should be blocked
        assert validate_local_file_access(
            f"file://{not_allowed_dir}/image.png",
            allow_local_files=True,
            local_file_allowlist=[allowed_dir],
            allow_cwd_files=False
        ) is False

    def test_no_allowlist_allows_all_when_master_enabled(self):
        """When no allowlist is provided and master switch is True, all should be allowed."""
        assert validate_local_file_access(
            "file:///any/path/image.png",
            allow_local_files=True,
            local_file_allowlist=None,
            allow_cwd_files=False
        ) is True

    def test_denylist_precedence_over_allowlist(self):
        """Denylist should take precedence over allowlist."""
        path = "/test/directory"

        assert validate_local_file_access(
            f"file://{path}/image.png",
            allow_local_files=True,
            local_file_allowlist=[path],
            local_file_denylist=[path],
            allow_cwd_files=False
        ) is False

    def test_denylist_precedence_over_cwd(self):
        """Denylist should take precedence over CWD access."""
        cwd_path = str(Path.cwd())

        assert validate_local_file_access(
            f"file://{cwd_path}/image.png",
            allow_local_files=True,
            local_file_denylist=[cwd_path],
            allow_cwd_files=True
        ) is False

    def test_empty_lists_handling(self):
        """Test behavior with empty allowlist/denylist."""
        # Empty denylist should not block anything
        assert validate_local_file_access(
            "file:///etc/passwd",
            allow_local_files=True,
            local_file_denylist=[],
            allow_cwd_files=False
        ) is True

        # Empty allowlist should block everything (when allowlist is provided)
        assert validate_local_file_access(
            "file:///etc/passwd",
            allow_local_files=True,
            local_file_allowlist=[],
            allow_cwd_files=False
        ) is False

    def test_path_traversal_handling(self):
        """Test that path resolution handles traversal attempts correctly."""
        # This should be resolved to actual paths and compared properly
        cwd = Path.cwd()
        parent_dir = cwd.parent

        # Test with path traversal in URL
        assert validate_local_file_access(
            f"file://{cwd}/../image.png",
            allow_local_files=True,
            local_file_denylist=[str(parent_dir)],
            allow_cwd_files=True
        ) is False

    def test_complex_security_scenario(self):
        """Test a complex scenario with multiple security constraints."""
        cwd = Path.cwd()
        allowed_dir = "/safe/directory"
        denied_dir = str(cwd / "unsafe")

        # File in CWD but not in denied area - should be allowed
        assert validate_local_file_access(
            f"file://{cwd}/safe_image.png",
            allow_local_files=True,
            local_file_allowlist=[allowed_dir],
            local_file_denylist=[denied_dir],
            allow_cwd_files=True
        ) is True

        # File in denied area under CWD - should be blocked
        assert validate_local_file_access(
            f"file://{denied_dir}/bad_image.png",
            allow_local_files=True,
            local_file_allowlist=[allowed_dir],
            local_file_denylist=[denied_dir],
            allow_cwd_files=True
        ) is False

        # File in allowed directory - should be allowed
        assert validate_local_file_access(
            f"file://{allowed_dir}/good_image.png",
            allow_local_files=True,
            local_file_allowlist=[allowed_dir],
            local_file_denylist=[denied_dir],
            allow_cwd_files=True
        ) is True

    def test_default_parameter_behavior(self):
        """Test that default parameters work as expected."""
        # Default should have allow_local_files=False, allow_cwd_files=True
        # But our fix should make master switch take precedence
        assert validate_local_file_access("file://./image.png") is False

        # When explicitly allowing local files, CWD should work with default allow_cwd_files=True
        assert validate_local_file_access(
            "file://./image.png",
            allow_local_files=True
        ) is True


class TestFilenameSanitization:
    """Test filename sanitization security features."""

    def test_basic_sanitization(self):
        """Test basic character filtering and normalization."""
        assert sanitize_attachment_filename("test.png") == "test.png"
        assert sanitize_attachment_filename("Test.PNG") == "test.png"
        assert sanitize_attachment_filename("file with spaces.txt") == "file_with_spaces.txt"

    def test_unicode_normalization(self):
        """Test Unicode normalization prevents visual confusables."""
        # Test combining characters
        result = sanitize_attachment_filename("test\u0301.png")  # test with combining accent
        assert result == "test.png"

        # Test compatibility characters
        result = sanitize_attachment_filename("ﬁle.txt")  # ligature fi -> fi
        assert result == "file.txt"

    def test_malicious_patterns(self):
        """Test detection and sanitization of malicious filename patterns."""
        # Directory traversal
        assert sanitize_attachment_filename("../../../etc/passwd") == "passwd"
        assert sanitize_attachment_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"

        # Absolute paths
        assert sanitize_attachment_filename("/etc/passwd") == "passwd"
        assert sanitize_attachment_filename("C:\\Windows\\system32\\cmd.exe") == "cmd.exe"

        # Control characters
        assert sanitize_attachment_filename("file\x00name.txt") == "filename.txt"
        assert sanitize_attachment_filename("file\x1fname.txt") == "file_name.txt"

    def test_dangerous_characters(self):
        """Test removal of dangerous filesystem characters."""
        assert sanitize_attachment_filename("file<>|name?.txt") == "filename.txt"
        assert sanitize_attachment_filename('file"name*.txt') == "filename.txt"
        assert sanitize_attachment_filename("file:name.txt") == "filename.txt"

    def test_windows_reserved_names(self):
        """Test handling of Windows reserved filenames."""
        assert sanitize_attachment_filename("con.txt") == "file_con.txt"
        assert sanitize_attachment_filename("PRN.txt") == "file_prn.txt"
        assert sanitize_attachment_filename("aux") == "file_aux"
        assert sanitize_attachment_filename("com1.exe") == "file_com1.exe"
        assert sanitize_attachment_filename("lpt9.dat") == "file_lpt9.dat"

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Empty/whitespace only
        assert sanitize_attachment_filename("") == "attachment"
        assert sanitize_attachment_filename("   ") == "attachment"
        assert sanitize_attachment_filename("\t\n") == "attachment"

        # Only dots
        assert sanitize_attachment_filename("...") == "attachment"
        assert sanitize_attachment_filename(".") == "attachment"

        # Only underscores (after sanitization)
        assert sanitize_attachment_filename("___") == "attachment"

    def test_length_limits(self):
        """Test filename length truncation."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_attachment_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")

        # Test without extension
        long_name = "a" * 300
        result = sanitize_attachment_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_preserve_extensions(self):
        """Test that file extensions are preserved when possible."""
        assert sanitize_attachment_filename("test.PNG") == "test.png"
        assert sanitize_attachment_filename("file.tar.gz") == "file.tar.gz"
        assert sanitize_attachment_filename("document.pdf") == "document.pdf"

    def test_multiple_dots_and_spaces(self):
        """Test handling of multiple consecutive dots and spaces."""
        assert sanitize_attachment_filename("file...with....dots.txt") == "file.with.dots.txt"
        assert sanitize_attachment_filename("file   with   spaces.txt") == "file_with_spaces.txt"


class TestPathCollisionHandling:
    """Test path collision detection and resolution."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_collision(self):
        """Test when no collision exists."""
        test_path = self.temp_dir / "test.txt"
        result = ensure_unique_attachment_path(test_path)
        assert result == test_path

    def test_single_collision(self):
        """Test collision resolution with single existing file."""
        # Create existing file
        existing_file = self.temp_dir / "test.txt"
        existing_file.touch()

        # Test collision resolution
        test_path = self.temp_dir / "test.txt"
        result = ensure_unique_attachment_path(test_path)
        assert result == self.temp_dir / "test-1.txt"

    def test_multiple_collisions(self):
        """Test collision resolution with multiple existing files."""
        # Create multiple existing files
        (self.temp_dir / "test.txt").touch()
        (self.temp_dir / "test-1.txt").touch()
        (self.temp_dir / "test-2.txt").touch()

        # Test collision resolution
        test_path = self.temp_dir / "test.txt"
        result = ensure_unique_attachment_path(test_path)
        assert result == self.temp_dir / "test-3.txt"

    def test_collision_with_no_extension(self):
        """Test collision resolution for files without extensions."""
        # Create existing file
        existing_file = self.temp_dir / "testfile"
        existing_file.touch()

        # Test collision resolution
        test_path = self.temp_dir / "testfile"
        result = ensure_unique_attachment_path(test_path)
        assert result == self.temp_dir / "testfile-1"

    def test_max_attempts_exceeded(self):
        """Test error when max attempts is exceeded."""
        # Create the base file
        base_path = self.temp_dir / "test.txt"
        base_path.touch()

        # Test with very low max_attempts
        with pytest.raises(RuntimeError, match="Unable to find unique path"):
            ensure_unique_attachment_path(base_path, max_attempts=0)


class TestAttachmentProcessingSecurity:
    """Test security aspects of attachment processing."""

    def setup_method(self):
        """Set up temporary directory for tests."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_download_mode_sanitization(self):
        """Test that download mode properly sanitizes filenames."""
        malicious_name = "../../../etc/passwd"
        test_data = b"test data"

        result = process_attachment(
            attachment_data=test_data,
            attachment_name=malicious_name,
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        # Should create a safe filename
        assert "passwd" in result["markdown"]
        assert "../" not in result["markdown"]

        # Check that the file was actually created safely
        created_files = list(self.temp_dir.glob("*"))
        assert len(created_files) == 1
        assert created_files[0].name == "passwd"

    def test_download_mode_collision_handling(self):
        """Test that download mode handles filename collisions."""
        # Create initial file
        test_data1 = b"test data 1"
        result1 = process_attachment(
            attachment_data=test_data1,
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        # Create second file with same name
        test_data2 = b"test data 2"
        result2 = process_attachment(
            attachment_data=test_data2,
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        # Should have different filenames
        assert result1 != result2
        assert "test.txt" in result1["markdown"]
        assert "test-1.txt" in result2["markdown"]

        # Both files should exist
        created_files = list(self.temp_dir.glob("*"))
        assert len(created_files) == 2

    def test_download_mode_unicode_handling(self):
        """Test Unicode filename handling in download mode."""
        # Use properly constructed Unicode: e + combining acute accent = é, then normalize to é
        unicode_name = "te\u0301st.png"  # test with combining accent on 'e'
        test_data = b"fake image data"

        result = process_attachment(
            attachment_data=test_data,
            attachment_name=unicode_name,
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=True
        )

        # Should normalize the Unicode and convert to lowercase
        # e + combining accent becomes é
        assert "tést.png" in result["markdown"]

        # Check the actual file created
        created_files = list(self.temp_dir.glob("*"))
        assert len(created_files) == 1
        assert created_files[0].name == "tést.png"

    def test_download_mode_error_fallback(self):
        """Test fallback behavior when file writing fails."""
        # Create a file where we want a directory, causing directory creation to fail
        block_file = self.temp_dir / "block_dir"
        block_file.write_text("blocking file")

        # Try to create a directory with the same name as the file
        invalid_dir = str(block_file)

        result = process_attachment(
            attachment_data=b"test data",
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=invalid_dir,
            is_image=False
        )

        # Should fall back to alt-text mode
        assert result["markdown"] == "[test.txt]"

    def test_windows_reserved_names_in_download(self):
        """Test handling of Windows reserved names in download mode."""
        result = process_attachment(
            attachment_data=b"test data",
            attachment_name="con.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        # Should rename the file to avoid Windows reserved name
        assert "file_con.txt" in result["markdown"]

        # Check the actual file created
        created_files = list(self.temp_dir.glob("*"))
        assert len(created_files) == 1
        assert created_files[0].name == "file_con.txt"

    def test_case_normalization_prevents_collisions(self):
        """Test that case normalization prevents unexpected collisions."""
        # On case-insensitive filesystems, these should be treated as the same
        test_data = b"test data"

        result1 = process_attachment(
            attachment_data=test_data,
            attachment_name="TEST.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        result2 = process_attachment(
            attachment_data=test_data,
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False
        )

        # Both should normalize to lowercase, so second should get suffix
        assert "test.txt" in result1["markdown"]
        assert "test-1.txt" in result2["markdown"]
