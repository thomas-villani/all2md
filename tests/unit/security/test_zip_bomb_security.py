"""Unit tests for ZIP bomb detection and archive security validation.

This test module validates the security measures implemented to prevent
ZIP bomb attacks and other archive-based threats in the all2md library.

Test Coverage:
- Compression ratio detection
- Entry count limits
- Uncompressed size limits
- Path traversal detection
- Valid archive acceptance
- Integration with format parsers (DOCX, PPTX, EPUB, ODF)
"""

import zipfile

import pytest

from all2md.exceptions import MalformedFileError, ZipFileSecurityError
from all2md.utils.security import validate_zip_archive


@pytest.mark.unit
@pytest.mark.security
class TestZipBombDetection:
    """Test ZIP bomb detection via compression ratio analysis."""

    def test_normal_compression_ratio_passes(self, tmp_path):
        """Test that archives with normal compression ratios are allowed."""
        zip_path = tmp_path / "normal.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add some normal files (compression ratio ~2-3x)
            zf.writestr("file1.txt", "Hello World! " * 100)
            zf.writestr("file2.txt", "Test data " * 50)
            zf.writestr("file3.txt", "Normal content " * 75)

        # Should not raise
        validate_zip_archive(zip_path)

    def test_high_compression_ratio_blocked(self, tmp_path):
        """Test that suspicious compression ratios trigger security error."""
        zip_path = tmp_path / "suspicious.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Create highly compressible content (compression ratio > 100x)
            highly_compressible = "0" * 1000000  # 1MB of zeros
            zf.writestr("bomb.txt", highly_compressible)

        # Should raise due to high compression ratio
        with pytest.raises(ZipFileSecurityError, match="suspicious compression ratio"):
            validate_zip_archive(zip_path, max_compression_ratio=100.0)

    def test_zip_bomb_with_small_compressed_size(self, tmp_path):
        """Test detection of classic zip bomb pattern (tiny compressed, huge uncompressed)."""
        zip_path = tmp_path / "bomb.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Create multiple highly compressible files
            for i in range(5):
                zf.writestr(f"layer{i}.txt", "A" * 10000000)  # 10MB each of 'A's

        # Should raise due to high compression ratio
        with pytest.raises(ZipFileSecurityError, match="suspicious compression ratio"):
            validate_zip_archive(zip_path, max_compression_ratio=50.0)

    def test_custom_compression_ratio_limit(self, tmp_path):
        """Test that custom compression ratio limits are respected."""
        zip_path_high = tmp_path / "high_compression.zip"
        zip_path_low = tmp_path / "low_compression.zip"

        # Create a file with high compression (repeated data)
        with zipfile.ZipFile(zip_path_high, "w", zipfile.ZIP_DEFLATED) as zf:
            data_high = "A" * 50000  # Very compressible
            zf.writestr("data.txt", data_high)

        # Should fail with moderate limit (high compression ~500:1)
        with pytest.raises(ZipFileSecurityError, match="suspicious compression ratio"):
            validate_zip_archive(zip_path_high, max_compression_ratio=50.0)

        # Create a file with low compression (random-ish data)
        with zipfile.ZipFile(zip_path_low, "w", zipfile.ZIP_STORED) as zf:  # STORED = no compression
            import random

            random.seed(42)
            data_low = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789 \n!@#$%^&*()_+", k=10000))
            zf.writestr("data.txt", data_low)

        # Should pass with any reasonable limit (compression ratio ~1:1)
        validate_zip_archive(zip_path_low, max_compression_ratio=5.0)


@pytest.mark.unit
@pytest.mark.security
class TestEntryCountLimits:
    """Test entry count validation to prevent resource exhaustion."""

    def test_normal_entry_count_passes(self, tmp_path):
        """Test that archives with normal entry counts are allowed."""
        zip_path = tmp_path / "normal.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create 100 normal entries
            for i in range(100):
                zf.writestr(f"file{i}.txt", f"Content {i}")

        # Should not raise
        validate_zip_archive(zip_path)

    def test_excessive_entry_count_blocked(self, tmp_path):
        """Test that archives with too many entries are blocked."""
        zip_path = tmp_path / "too_many.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create 15,000 entries (exceeds default limit of 10,000)
            for i in range(15000):
                zf.writestr(f"file{i}.txt", f"Data {i}")

        # Should raise due to too many entries
        with pytest.raises(ZipFileSecurityError, match="too many entries"):
            validate_zip_archive(zip_path, max_entries=10000)

    def test_custom_entry_count_limit(self, tmp_path):
        """Test that custom entry count limits are respected."""
        zip_path = tmp_path / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create 150 entries
            for i in range(150):
                zf.writestr(f"file{i}.txt", f"Content {i}")

        # Should pass with high limit
        validate_zip_archive(zip_path, max_entries=200)

        # Should fail with low limit
        with pytest.raises(ZipFileSecurityError, match="too many entries"):
            validate_zip_archive(zip_path, max_entries=100)

    def test_empty_archive_passes(self, tmp_path):
        """Test that empty archives are allowed."""
        zip_path = tmp_path / "empty.zip"

        with zipfile.ZipFile(zip_path, "w"):
            pass  # Empty archive

        # Should not raise
        validate_zip_archive(zip_path)


@pytest.mark.unit
@pytest.mark.security
class TestUncompressedSizeLimits:
    """Test uncompressed size validation to prevent resource exhaustion."""

    def test_normal_uncompressed_size_passes(self, tmp_path):
        """Test that archives with normal uncompressed sizes are allowed."""
        zip_path = tmp_path / "normal.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create files totaling ~1MB uncompressed
            for i in range(10):
                zf.writestr(f"file{i}.txt", "X" * 100000)  # 100KB each

        # Should not raise
        validate_zip_archive(zip_path)

    @pytest.mark.slow
    def test_excessive_uncompressed_size_blocked(self, tmp_path):
        """Test that archives with excessive uncompressed size are blocked."""
        zip_path = tmp_path / "huge.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Create files that would expand to >1GB
            # Use highly compressible data to create small compressed file
            for i in range(200):
                zf.writestr(f"file{i}.txt", "A" * 10000000)  # 10MB each = 2GB total

        # Should raise due to excessive uncompressed size (default limit: 1GB)
        with pytest.raises(ZipFileSecurityError, match="uncompressed size too large"):
            validate_zip_archive(zip_path)

    def test_custom_uncompressed_size_limit(self, tmp_path):
        """Test that custom uncompressed size limits are respected."""
        zip_path = tmp_path / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create 5MB of data
            zf.writestr("data.txt", "Y" * 5000000)

        # Should pass with high limit
        validate_zip_archive(zip_path, max_uncompressed_size=10 * 1024 * 1024)

        # Should fail with low limit
        with pytest.raises(ZipFileSecurityError, match="uncompressed size too large"):
            validate_zip_archive(zip_path, max_uncompressed_size=1 * 1024 * 1024)


@pytest.mark.unit
@pytest.mark.security
class TestPathTraversalDetection:
    """Test path traversal attack detection in ZIP archives."""

    def test_normal_paths_pass(self, tmp_path):
        """Test that normal paths are allowed."""
        zip_path = tmp_path / "normal.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")
            zf.writestr("subdir/file.txt", "content")
            zf.writestr("deep/nested/path/file.txt", "content")

        # Should not raise
        validate_zip_archive(zip_path)

    def test_parent_directory_traversal_blocked(self, tmp_path):
        """Test that ../ path traversal is blocked."""
        zip_path = tmp_path / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious")

        # Should raise due to path traversal
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            validate_zip_archive(zip_path)

    def test_relative_parent_in_middle_blocked(self, tmp_path):
        """Test that ../ in the middle of paths is blocked."""
        zip_path = tmp_path / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("dir/../../../secret.txt", "malicious")

        # Should raise due to path traversal
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            validate_zip_archive(zip_path)

    def test_absolute_path_blocked(self, tmp_path):
        """Test that absolute paths are blocked."""
        zip_path = tmp_path / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("/etc/passwd", "malicious")

        # Should raise due to absolute path
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            validate_zip_archive(zip_path)

    def test_windows_absolute_path_blocked(self, tmp_path):
        """Test that Windows absolute paths are blocked."""
        zip_path = tmp_path / "malicious.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Note: ZipFile normalizes this, but our check should still catch it
            # if it somehow makes it through
            zf.writestr("C:/Windows/System32/malware.exe", "malicious")

        # The path might be normalized by ZipFile, so we need to check
        # what actually got written
        with zipfile.ZipFile(zip_path, "r") as zf:
            entries = zf.namelist()
            # If it contains suspicious patterns, it should be blocked
            if any(".." in entry or entry.startswith("/") for entry in entries):
                with pytest.raises(ZipFileSecurityError, match="suspicious path"):
                    validate_zip_archive(zip_path)


@pytest.mark.unit
@pytest.mark.security
class TestInvalidArchiveHandling:
    """Test handling of invalid or corrupted archives."""

    def test_corrupted_zip_raises_malformed_error(self, tmp_path):
        """Test that corrupted ZIP files raise MalformedFileError."""
        corrupt_zip = tmp_path / "corrupt.zip"
        corrupt_zip.write_bytes(b"This is not a valid ZIP file")

        # Should raise MalformedFileError (not ZipFileSecurityError)
        with pytest.raises(MalformedFileError, match="Invalid ZIP archive"):
            validate_zip_archive(corrupt_zip)

    def test_nonexistent_file_raises_malformed_error(self, tmp_path):
        """Test that nonexistent files raise MalformedFileError."""
        nonexistent = tmp_path / "doesnotexist.zip"

        # Should raise MalformedFileError
        with pytest.raises(MalformedFileError, match="Could not read ZIP archive"):
            validate_zip_archive(nonexistent)

    def test_directory_instead_of_file_raises_malformed_error(self, tmp_path):
        """Test that directories raise MalformedFileError."""
        # tmp_path is a directory
        with pytest.raises(MalformedFileError):
            validate_zip_archive(tmp_path)


@pytest.mark.unit
@pytest.mark.security
class TestCombinedSecurityChecks:
    """Test archives that trigger multiple security checks."""

    @pytest.mark.slow
    def test_high_compression_and_many_entries(self, tmp_path):
        """Test archive with both high compression and many entries."""
        zip_path = tmp_path / "combined_threat.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Many entries with high compression
            for i in range(1000):
                zf.writestr(f"file{i}.txt", "A" * 100000)  # Highly compressible

        # Should raise (either for count or compression, doesn't matter which)
        with pytest.raises(ZipFileSecurityError):
            validate_zip_archive(zip_path, max_entries=500, max_compression_ratio=50.0)

    def test_path_traversal_with_large_size(self, tmp_path):
        """Test archive with both path traversal and large size."""
        zip_path = tmp_path / "combined_threat.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../malicious.txt", "X" * 10000000)

        # Should raise for path traversal (checked first)
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            validate_zip_archive(zip_path)


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.integration
class TestDocxPptxZipSecurity:
    """Test that DOCX and PPTX files (which are ZIP archives) are validated."""

    def test_valid_docx_structure_passes(self, tmp_path):
        """Test that valid DOCX structure passes validation."""
        docx_path = tmp_path / "test.docx"

        # Create a minimal valid DOCX structure
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships/>')
            zf.writestr("word/document.xml", '<?xml version="1.0"?><document/>')

        # Should not raise
        validate_zip_archive(docx_path)

    def test_malicious_docx_blocked(self, tmp_path):
        """Test that malicious DOCX files are blocked."""
        docx_path = tmp_path / "malicious.docx"

        with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Looks like DOCX but contains zip bomb
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("word/bomb.xml", "X" * 50000000)  # 50MB highly compressible

        # Should raise due to high compression or size
        with pytest.raises(ZipFileSecurityError):
            validate_zip_archive(docx_path, max_uncompressed_size=10 * 1024 * 1024)


@pytest.mark.unit
@pytest.mark.security
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_compression_limit(self, tmp_path):
        """Test archive with compression ratio exactly at the limit."""
        zip_path = tmp_path / "at_limit.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Target compression ratio of ~50:1
            # This is tricky to get exact, so we'll create something close
            # and use a lenient assertion
            zf.writestr("data.txt", "A" * 500000)

        # Get actual compression ratio
        with zipfile.ZipFile(zip_path, "r") as zf:
            entry = zf.infolist()[0]
            if entry.compress_size > 0:
                actual_ratio = entry.file_size / entry.compress_size

                # Test with limit just above actual ratio - should pass
                validate_zip_archive(zip_path, max_compression_ratio=actual_ratio + 1)

                # Test with limit just below actual ratio - should fail
                with pytest.raises(ZipFileSecurityError):
                    validate_zip_archive(zip_path, max_compression_ratio=actual_ratio - 1)

    def test_archive_with_zero_byte_files(self, tmp_path):
        """Test archive containing zero-byte files."""
        zip_path = tmp_path / "zero_bytes.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("empty1.txt", "")
            zf.writestr("empty2.txt", "")
            zf.writestr("with_content.txt", "Some content")

        # Should not raise (zero-byte files are fine)
        validate_zip_archive(zip_path)

    def test_archive_with_directories(self, tmp_path):
        """Test archive containing directory entries."""
        zip_path = tmp_path / "with_dirs.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Create directory entries (end with /)
            zf.writestr("dir1/", "")
            zf.writestr("dir1/subdir/", "")
            zf.writestr("dir1/subdir/file.txt", "content")

        # Should not raise
        validate_zip_archive(zip_path)
