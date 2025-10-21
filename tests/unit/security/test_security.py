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
            assert (
                validate_local_file_access(
                    url, allow_local_files=False, allow_cwd_files=True  # Should be ignored when master switch is False
                )
                is False
            )

    def test_master_switch_false_ignores_allowlist(self):
        """When allow_local_files=False, allowlist should be ignored."""
        assert (
            validate_local_file_access(
                "file:///allowed/path/image.png",
                allow_local_files=False,
                local_file_allowlist=["/allowed/path"],
                allow_cwd_files=True,
            )
            is False
        )

    def test_master_switch_false_with_denylist_still_blocks(self):
        """When allow_local_files=False, denylist check should still block but master switch takes precedence."""
        # File not in denylist but still blocked by master switch
        assert (
            validate_local_file_access(
                "file:///not/denied/image.png",
                allow_local_files=False,
                local_file_denylist=["/denied/path"],
                allow_cwd_files=True,
            )
            is False
        )

    def test_denylist_blocks_access_even_when_allowed(self):
        """Denylist should block access even when allow_local_files=True."""
        denied_path = str(Path.cwd() / "denied")

        assert (
            validate_local_file_access(
                f"file://{denied_path}/image.png",
                allow_local_files=True,
                local_file_denylist=[denied_path],
                allow_cwd_files=True,
            )
            is False
        )

    def test_cwd_access_requires_master_switch(self):
        """CWD access should only work when allow_local_files=True."""
        cwd_path = Path.cwd()
        test_file_url = f"file://{cwd_path}/image.png"

        # Should be blocked when master switch is False
        assert validate_local_file_access(test_file_url, allow_local_files=False, allow_cwd_files=True) is False

        # Should be allowed when master switch is True and allow_cwd_files=True
        assert validate_local_file_access(test_file_url, allow_local_files=True, allow_cwd_files=True) is True

        # Should be allowed when master switch is True but allow_cwd_files=False
        # (falls through to default allow when no allowlist provided)
        assert validate_local_file_access(test_file_url, allow_local_files=True, allow_cwd_files=False) is True

        # Should be blocked when master switch is True, allow_cwd_files=False, and empty allowlist
        assert (
            validate_local_file_access(
                test_file_url, allow_local_files=True, allow_cwd_files=False, local_file_allowlist=[]
            )
            is False
        )

    def test_relative_cwd_paths(self):
        """Test relative path handling for CWD files."""
        test_cases = [
            "file://./image.png",
            "file://../image.png",
            "file://image.png",
        ]

        for url in test_cases:
            # Blocked when master switch is False
            assert validate_local_file_access(url, allow_local_files=False, allow_cwd_files=True) is False

            # Allowed when both switches are True
            assert validate_local_file_access(url, allow_local_files=True, allow_cwd_files=True) is True

    def test_allowlist_functionality(self):
        """Test allowlist functionality when master switch is enabled."""
        allowed_dir = "/allowed/directory"
        not_allowed_dir = "/not/allowed"

        # File in allowed directory should be permitted
        assert (
            validate_local_file_access(
                f"file://{allowed_dir}/image.png",
                allow_local_files=True,
                local_file_allowlist=[allowed_dir],
                allow_cwd_files=False,
            )
            is True
        )

        # File not in allowed directory should be blocked
        assert (
            validate_local_file_access(
                f"file://{not_allowed_dir}/image.png",
                allow_local_files=True,
                local_file_allowlist=[allowed_dir],
                allow_cwd_files=False,
            )
            is False
        )

    def test_no_allowlist_allows_all_when_master_enabled(self):
        """When no allowlist is provided and master switch is True, all should be allowed."""
        assert (
            validate_local_file_access(
                "file:///any/path/image.png", allow_local_files=True, local_file_allowlist=None, allow_cwd_files=False
            )
            is True
        )

    def test_denylist_precedence_over_allowlist(self):
        """Denylist should take precedence over allowlist."""
        path = "/test/directory"

        assert (
            validate_local_file_access(
                f"file://{path}/image.png",
                allow_local_files=True,
                local_file_allowlist=[path],
                local_file_denylist=[path],
                allow_cwd_files=False,
            )
            is False
        )

    def test_denylist_precedence_over_cwd(self):
        """Denylist should take precedence over CWD access."""
        cwd_path = str(Path.cwd())

        assert (
            validate_local_file_access(
                f"file://{cwd_path}/image.png",
                allow_local_files=True,
                local_file_denylist=[cwd_path],
                allow_cwd_files=True,
            )
            is False
        )

    def test_empty_lists_handling(self):
        """Test behavior with empty allowlist/denylist."""
        # Empty denylist should not block anything
        assert (
            validate_local_file_access(
                "file:///etc/passwd", allow_local_files=True, local_file_denylist=[], allow_cwd_files=False
            )
            is True
        )

        # Empty allowlist should block everything (when allowlist is provided)
        assert (
            validate_local_file_access(
                "file:///etc/passwd", allow_local_files=True, local_file_allowlist=[], allow_cwd_files=False
            )
            is False
        )

    def test_path_traversal_handling(self):
        """Test that path resolution handles traversal attempts correctly."""
        # This should be resolved to actual paths and compared properly
        cwd = Path.cwd()
        parent_dir = cwd.parent

        # Test with path traversal in URL
        assert (
            validate_local_file_access(
                f"file://{cwd}/../image.png",
                allow_local_files=True,
                local_file_denylist=[str(parent_dir)],
                allow_cwd_files=True,
            )
            is False
        )

    def test_complex_security_scenario(self):
        """Test a complex scenario with multiple security constraints."""
        cwd = Path.cwd()
        allowed_dir = "/safe/directory"
        denied_dir = str(cwd / "unsafe")

        # File in CWD but not in denied area - should be allowed
        assert (
            validate_local_file_access(
                f"file://{cwd}/safe_image.png",
                allow_local_files=True,
                local_file_allowlist=[allowed_dir],
                local_file_denylist=[denied_dir],
                allow_cwd_files=True,
            )
            is True
        )

        # File in denied area under CWD - should be blocked
        assert (
            validate_local_file_access(
                f"file://{denied_dir}/bad_image.png",
                allow_local_files=True,
                local_file_allowlist=[allowed_dir],
                local_file_denylist=[denied_dir],
                allow_cwd_files=True,
            )
            is False
        )

        # File in allowed directory - should be allowed
        assert (
            validate_local_file_access(
                f"file://{allowed_dir}/good_image.png",
                allow_local_files=True,
                local_file_allowlist=[allowed_dir],
                local_file_denylist=[denied_dir],
                allow_cwd_files=True,
            )
            is True
        )

    def test_default_parameter_behavior(self):
        """Test that default parameters work as expected."""
        # Default should have allow_local_files=False, allow_cwd_files=True
        # But our fix should make master switch take precedence
        assert validate_local_file_access("file://./image.png") is False

        # When explicitly allowing local files, CWD should work with default allow_cwd_files=True
        assert validate_local_file_access("file://./image.png", allow_local_files=True) is True

    def test_windows_drive_letter_urls(self):
        """Test Windows drive letter file URLs like file:///C:/path."""
        # Test with master switch disabled
        assert validate_local_file_access("file:///C:/Users/test/file.txt", allow_local_files=False) is False

        # Test with master switch enabled
        assert validate_local_file_access("file:///C:/Users/test/file.txt", allow_local_files=True) is True

        # Test with allowlist
        assert (
            validate_local_file_access(
                "file:///C:/Users/test/file.txt",
                allow_local_files=True,
                local_file_allowlist=["C:/Users/test"],
                allow_cwd_files=False,
            )
            is True
        )

        # Test with denylist
        assert (
            validate_local_file_access(
                "file:///C:/Users/test/file.txt",
                allow_local_files=True,
                local_file_denylist=["C:/Users/test"],
                allow_cwd_files=False,
            )
            is False
        )

    def test_windows_unc_path_urls(self):
        """Test Windows UNC path URLs like file://server/share."""
        # Test basic UNC path
        assert validate_local_file_access("file://server/share/file.txt", allow_local_files=False) is False

        # Test with master switch enabled
        assert validate_local_file_access("file://server/share/file.txt", allow_local_files=True) is True

    def test_mixed_windows_and_unix_paths(self):
        """Test that both Windows and Unix-style paths work correctly."""
        # Unix-style path should work
        assert validate_local_file_access("file:///home/user/file.txt", allow_local_files=True) is True

        # Windows-style path should work
        assert validate_local_file_access("file:///C:/Users/file.txt", allow_local_files=True) is True


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
            is_image=False,
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
            is_image=False,
        )

        # Create second file with same name
        test_data2 = b"test data 2"
        result2 = process_attachment(
            attachment_data=test_data2,
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False,
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
            is_image=True,
        )

        # Default behavior: removes non-ASCII Unicode characters
        # e + combining accent becomes é, then é is removed -> "tst.png"
        # (To preserve Unicode, use sanitize_attachment_filename with allow_unicode=True)
        assert "tst.png" in result["markdown"]

        # Check the actual file created
        created_files = list(self.temp_dir.glob("*"))
        assert len(created_files) == 1
        assert created_files[0].name == "tst.png"

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
            is_image=False,
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
            is_image=False,
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
            is_image=False,
        )

        result2 = process_attachment(
            attachment_data=test_data,
            attachment_name="test.txt",
            attachment_mode="download",
            attachment_output_dir=str(self.temp_dir),
            is_image=False,
        )

        # Both should normalize to lowercase, so second should get suffix
        assert "test.txt" in result1["markdown"]
        assert "test-1.txt" in result2["markdown"]


class TestFilenameSanitizationEnhancements:
    """Test enhanced filename sanitization options."""

    def test_preserve_case_option(self):
        """Test preserve_case parameter preserves original case."""
        # Default behavior: lowercase
        assert sanitize_attachment_filename("Test.PNG") == "test.png"

        # With preserve_case=True: maintain case
        assert sanitize_attachment_filename("Test.PNG", preserve_case=True) == "Test.PNG"
        assert sanitize_attachment_filename("MyFile.TXT", preserve_case=True) == "MyFile.TXT"

    def test_allow_unicode_option(self):
        """Test allow_unicode parameter preserves Unicode characters."""
        # Default behavior: removes Unicode, preserves extension with "attachment" base
        assert sanitize_attachment_filename("文件.txt") == "attachment.txt"
        assert sanitize_attachment_filename("файл.pdf") == "attachment.pdf"

        # With allow_unicode=True: preserve Unicode
        assert sanitize_attachment_filename("文件.txt", allow_unicode=True) == "文件.txt"
        assert sanitize_attachment_filename("файл.pdf", allow_unicode=True) == "файл.pdf"
        assert sanitize_attachment_filename("مستند.docx", allow_unicode=True) == "مستند.docx"

    def test_preserve_case_with_unicode(self):
        """Test combining preserve_case and allow_unicode."""
        result = sanitize_attachment_filename("文件Test.TXT", preserve_case=True, allow_unicode=True)
        assert result == "文件Test.TXT"

    def test_windows_reserved_with_preserve_case(self):
        """Test Windows reserved names with case preservation."""
        # Should prefix but preserve case
        result = sanitize_attachment_filename("CON.txt", preserve_case=True)
        assert result == "file_CON.txt"

        result = sanitize_attachment_filename("Prn.log", preserve_case=True)
        assert result == "file_Prn.log"

    def test_unicode_with_special_characters(self):
        """Test Unicode filenames with special characters removed."""
        # Unicode allowed, but special chars still removed
        result = sanitize_attachment_filename("文件<test>.txt", allow_unicode=True)
        assert result == "文件test.txt"

    def test_backward_compatibility(self):
        """Test that default behavior is unchanged for backward compatibility."""
        # All these should work as before
        assert sanitize_attachment_filename("test.png") == "test.png"
        assert sanitize_attachment_filename("Test.PNG") == "test.png"
        # Unicode-only filenames now use "attachment" base with preserved extension
        assert sanitize_attachment_filename("文件.txt") == "attachment.txt"
        assert sanitize_attachment_filename("../../../etc/passwd") == "passwd"


class TestRegexValidation:
    """Test regex pattern validation to prevent ReDoS attacks."""

    def test_safe_simple_patterns(self):
        """Test that safe, simple patterns are accepted."""
        from all2md.utils.security import validate_user_regex_pattern

        # These should all pass without exception
        safe_patterns = [
            r"^/docs/",
            r"https?://example\.com",
            r"[a-zA-Z0-9]+",
            r"^test$",
            r"foo|bar",
            r"(abc)+",
            r"test{2,5}",
            r"^\d{3}-\d{3}-\d{4}$",
        ]

        for pattern in safe_patterns:
            validate_user_regex_pattern(pattern)  # Should not raise

    def test_dangerous_nested_quantifiers(self):
        """Test that patterns with nested quantifiers are rejected."""
        from all2md.exceptions import SecurityError
        from all2md.utils.security import validate_user_regex_pattern

        dangerous_patterns = [
            r"(a+)+",  # Classic nested quantifier
            r"(b*)*",  # Nested star
            r"(c+)*",  # Mixed nested quantifiers
            r"(?:d+)+",  # Non-capturing group with nested quantifiers
            r"(e*){2,}",  # Quantified group with inner quantifier
            r"(?=.*)+",  # Lookahead with quantifier
            r"(?!test)*",  # Negative lookahead with quantifier
            r"(?=.*a)",  # Lookahead containing quantifier
            r"(a|ab)*",  # Overlapping alternation with quantifier
            r"(foo|foobar)+",  # Overlapping alternation
            r"((a+)",  # Multiple nested groups with quantifier
            r".*+",  # Greedy wildcard with possessive quantifier
            r".+*",  # .+ followed by star
        ]

        for pattern in dangerous_patterns:
            with pytest.raises(SecurityError, match="dangerous nested quantifiers"):
                validate_user_regex_pattern(pattern)

    def test_pattern_length_limit(self):
        """Test that excessively long patterns are rejected."""
        from all2md.constants import MAX_REGEX_PATTERN_LENGTH
        from all2md.exceptions import SecurityError
        from all2md.utils.security import validate_user_regex_pattern

        # Pattern just under limit should pass
        safe_pattern = "a" * (MAX_REGEX_PATTERN_LENGTH - 1)
        validate_user_regex_pattern(safe_pattern)  # Should not raise

        # Pattern over limit should fail
        long_pattern = "a" * (MAX_REGEX_PATTERN_LENGTH + 1)
        with pytest.raises(SecurityError, match="exceeds maximum length"):
            validate_user_regex_pattern(long_pattern)

    def test_invalid_regex_syntax(self):
        """Test that invalid regex patterns are rejected."""
        from all2md.exceptions import SecurityError
        from all2md.utils.security import validate_user_regex_pattern

        invalid_patterns = [
            r"[",  # Unclosed bracket
            r"(?P<",  # Incomplete named group
            r"(?P<name",  # Incomplete named group
            r"(?<",  # Invalid lookbehind
            r"*",  # Nothing to repeat
        ]

        for pattern in invalid_patterns:
            with pytest.raises(SecurityError, match="Invalid regex pattern"):
                validate_user_regex_pattern(pattern)

    def test_complex_safe_patterns(self):
        """Test complex but safe patterns."""
        from all2md.utils.security import validate_user_regex_pattern

        safe_complex_patterns = [
            r"^(?:https?://)?(?:www\.)?example\.com/.*$",
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            r"(?i)^test",
            r"^/api/v[0-9]+/.*$",
        ]

        for pattern in safe_complex_patterns:
            validate_user_regex_pattern(pattern)  # Should not raise


class TestLinkRewriterTransformSecurity:
    """Test security features of LinkRewriterTransform."""

    def test_rejects_dangerous_patterns(self):
        """Test that LinkRewriterTransform rejects dangerous patterns."""
        from all2md.exceptions import SecurityError
        from all2md.transforms.builtin import LinkRewriterTransform

        with pytest.raises(SecurityError, match="dangerous nested quantifiers"):
            LinkRewriterTransform(pattern=r"(a+)+", replacement="test")

    def test_accepts_safe_patterns(self):
        """Test that LinkRewriterTransform accepts safe patterns."""
        from all2md.ast.nodes import Document, Link, Paragraph, Text
        from all2md.transforms.builtin import LinkRewriterTransform

        # Should not raise
        transform = LinkRewriterTransform(pattern=r"^/docs/", replacement="https://example.com/docs/")

        # Verify it works correctly
        doc = Document(children=[Paragraph(content=[Link(url="/docs/guide", content=[Text(content="Guide")])])])

        result = transform.transform(doc)
        link = result.children[0].content[0]
        assert link.url == "https://example.com/docs/guide"

    def test_preserves_long_urls_without_rewriting(self):
        """Test that LinkRewriterTransform preserves long URLs without rewriting."""
        from all2md.ast.nodes import Document, Link, Paragraph, Text
        from all2md.constants import MAX_URL_LENGTH
        from all2md.transforms.builtin import LinkRewriterTransform

        transform = LinkRewriterTransform(pattern=r"^/docs/", replacement="/documentation/")

        # Create a document with an excessively long URL
        long_url = "/docs/" + "a" * (MAX_URL_LENGTH + 100)
        doc = Document(children=[Paragraph(content=[Link(url=long_url, content=[Text(content="Link")])])])

        result = transform.transform(doc)
        link = result.children[0].content[0]

        # URL should be preserved unchanged (not rewritten, not truncated)
        assert link.url == long_url
        assert len(link.url) == len(long_url)


class TestRemoveBoilerplateTransformSecurity:
    """Test security features of RemoveBoilerplateTextTransform."""

    def test_rejects_dangerous_patterns(self):
        """Test that RemoveBoilerplateTextTransform rejects dangerous user patterns."""
        from all2md.exceptions import SecurityError
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        with pytest.raises(SecurityError, match="dangerous nested quantifiers"):
            RemoveBoilerplateTextTransform(patterns=[r"(a+)+"])

    def test_accepts_safe_user_patterns(self):
        """Test that RemoveBoilerplateTextTransform accepts safe user patterns."""
        from all2md.ast.nodes import Document, Paragraph, Text
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        # Should not raise
        transform = RemoveBoilerplateTextTransform(patterns=[r"^DRAFT$", r"^INTERNAL$"])

        # Verify it works correctly
        doc = Document(
            children=[
                Paragraph(content=[Text(content="DRAFT")]),
                Paragraph(content=[Text(content="Normal text")]),
            ]
        )

        result = transform.transform(doc)
        assert len(result.children) == 1
        assert result.children[0].content[0].content == "Normal text"

    def test_default_patterns_not_validated(self):
        """Test that default patterns are not subject to validation."""
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        # Should not raise even if defaults were to contain complex patterns
        transform = RemoveBoilerplateTextTransform()
        assert transform.patterns is not None
        assert len(transform.patterns) > 0

    def test_limits_text_length(self):
        """Test that RemoveBoilerplateTextTransform preserves long text for safety."""
        from all2md.ast.nodes import Document, Paragraph, Text
        from all2md.constants import MAX_TEXT_LENGTH_FOR_REGEX
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        # Test default behavior: skip_if_truncated=True preserves long text
        transform = RemoveBoilerplateTextTransform(patterns=[r"^LONG"])

        # Create a paragraph with extremely long text
        long_text = "LONG" + "x" * (MAX_TEXT_LENGTH_FOR_REGEX + 100)
        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])

        result = transform.transform(doc)

        # With skip_if_truncated=True (default), long text is preserved to avoid
        # false positives with end-anchored patterns like r"^LONG$"
        assert len(result.children) == 1

        # Test with skip_if_truncated=False: matches against truncated text
        transform_unsafe = RemoveBoilerplateTextTransform(
            patterns=[r"^LONG"], skip_if_truncated=False  # No end anchor, so safe to match truncated text
        )
        result_unsafe = transform_unsafe.transform(doc)

        # With skip_if_truncated=False, pattern matches the truncated prefix
        assert len(result_unsafe.children) == 0

    def test_multiple_safe_patterns(self):
        """Test multiple safe user patterns."""
        from all2md.ast.nodes import Document, Paragraph, Text
        from all2md.transforms.builtin import RemoveBoilerplateTextTransform

        transform = RemoveBoilerplateTextTransform(
            patterns=[
                r"^CONFIDENTIAL$",
                r"^Page \d+ of \d+$",
                r"^DRAFT$",
            ]
        )

        doc = Document(
            children=[
                Paragraph(content=[Text(content="CONFIDENTIAL")]),
                Paragraph(content=[Text(content="Page 1 of 5")]),
                Paragraph(content=[Text(content="DRAFT")]),
                Paragraph(content=[Text(content="Keep this")]),
            ]
        )

        result = transform.transform(doc)
        assert len(result.children) == 1
        assert result.children[0].content[0].content == "Keep this"
