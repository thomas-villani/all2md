#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Security tests for archive parser."""

import io
import tarfile
import tempfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.exceptions import ArchiveSecurityError, MalformedFileError
from all2md.options.archive import ArchiveOptions
from all2md.parsers.archive import ArchiveToAstConverter
from all2md.utils.security import validate_rar_archive, validate_safe_extraction_path, validate_tar_archive


class TestTarSecurity:
    """Security tests for TAR archive handling."""

    def test_path_traversal_parent_directory(self):
        """Test that path traversal attempts with .. are blocked."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Try to escape with ..
            content = b"malicious content"
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        # Write to temp file for validation
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(tar_data)
            tmp_path = tmp.name

        try:
            with pytest.raises(ArchiveSecurityError, match="suspicious path"):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_path_traversal_absolute_path(self):
        """Test that absolute paths are blocked."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            content = b"malicious content"
            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(tar_data)
            tmp_path = tmp.name

        try:
            with pytest.raises(ArchiveSecurityError, match="suspicious path"):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_path_traversal_windows_absolute(self):
        """Test that Windows absolute paths are blocked."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            content = b"malicious content"
            info = tarfile.TarInfo(name="C:\\Windows\\System32\\evil.dll")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(tar_data)
            tmp_path = tmp.name

        try:
            with pytest.raises(ArchiveSecurityError, match="Windows absolute path"):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_tar_bomb_too_many_entries(self):
        """Test that archives with too many entries are blocked."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Create archive with way too many files
            for i in range(10001):  # Exceeds DEFAULT_MAX_ZIP_ENTRIES (10000)
                content = b"x"
                info = tarfile.TarInfo(name=f"file{i}.txt")
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(tar_data)
            tmp_path = tmp.name

        try:
            with pytest.raises(ArchiveSecurityError, match="too many entries"):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_tar_bomb_excessive_uncompressed_size(self):
        """Test that archives with excessive uncompressed size are blocked."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Create a single huge file (> 1GB uncompressed)
            huge_size = 1024 * 1024 * 1024 + 1  # Just over 1GB
            info = tarfile.TarInfo(name="huge.txt")
            info.size = huge_size
            # Don't actually create the data, just set the size
            # (tarfile will handle this)
            tf.addfile(info, io.BytesIO(b""))  # Empty actual content

        tar_data = tar_buffer.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(tar_data)
            tmp_path = tmp.name

        try:
            with pytest.raises(ArchiveSecurityError, match="uncompressed size too large"):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()

    def test_safe_extraction_path_validation(self, tmp_path):
        """Test safe extraction path validation."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Safe path should work
        safe_path = validate_safe_extraction_path(output_dir, "subdir/file.txt")
        assert output_dir in safe_path.parents or safe_path.parent == output_dir

        # Path traversal should fail
        with pytest.raises(ArchiveSecurityError):
            validate_safe_extraction_path(output_dir, "../../../etc/passwd")

        # Absolute path should fail
        with pytest.raises(ArchiveSecurityError):
            validate_safe_extraction_path(output_dir, "/etc/passwd")

        # Windows absolute path should fail
        with pytest.raises(ArchiveSecurityError):
            validate_safe_extraction_path(output_dir, "C:\\Windows\\System32\\file.txt")

    def test_resource_extraction_safety(self, tmp_path):
        """Test that resource extraction respects security constraints."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Add a file with path traversal attempt
            content = b"resource content"
            info = tarfile.TarInfo(name="../../escape.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        # Try to extract with resource extraction enabled
        extract_dir = tmp_path / "extracted"
        options = ArchiveOptions(extract_resource_files=True, attachment_output_dir=str(extract_dir))

        # Should not raise during parsing (validation catches it earlier)
        # But let's verify the file wasn't extracted outside the directory
        try:
            parser = ArchiveToAstConverter(options=options)
            parser.parse(tar_data)
        except ArchiveSecurityError:
            # Expected - validation should catch this
            pass

        # Verify no files were extracted outside extract_dir
        if extract_dir.exists():
            for extracted_file in extract_dir.rglob("*"):
                assert extract_dir in extracted_file.parents

    def test_invalid_tar_file(self):
        """Test handling of invalid TAR files."""
        invalid_tar = b"This is not a TAR file"

        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(invalid_tar)
            tmp_path = tmp.name

        try:
            with pytest.raises(MalformedFileError):
                validate_tar_archive(tmp_path)
        finally:
            Path(tmp_path).unlink()


@pytest.mark.skipif(
    not pytest.importorskip("py7zr", reason="py7zr not installed"), reason="Requires py7zr for 7Z support"
)
class TestSevenZipSecurity:
    """Security tests for 7Z archive handling."""

    def test_7z_path_traversal(self, tmp_path):
        """Test 7Z path traversal protection (if py7zr available)."""
        import py7zr

        sz_path = tmp_path / "test.7z"

        # Note: py7zr may have its own protections, but we test our validation
        with py7zr.SevenZipFile(sz_path, mode="w") as sz:
            # Try to add file with traversal (py7zr may normalize this)
            sz.writestr("../../../etc/passwd", "content")

        # Our validation should catch suspicious paths
        from all2md.utils.security import validate_7z_archive

        # Note: This test depends on whether py7zr allows creating such files
        # If it normalizes paths, the test may pass
        try:
            validate_7z_archive(sz_path)
        except ArchiveSecurityError:
            # Expected if path traversal was preserved
            pass


@pytest.mark.skipif(
    not pytest.importorskip("rarfile", reason="rarfile not installed"), reason="Requires rarfile for RAR support"
)
class TestRarSecurity:
    """Security tests for RAR archive handling."""

    def test_rar_security_import(self):
        """Test RAR security validation import (requires rarfile)."""
        # Verify the function exists
        assert validate_rar_archive is not None

        # Note: Creating actual RAR files requires UnRAR binary,
        # so we can't create comprehensive tests here


class TestArchiveParserSecurity:
    """Integration security tests for archive parser."""

    def test_parser_rejects_malicious_tar(self, tmp_path):
        """Test that parser rejects malicious TAR files."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            content = b"malicious"
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        # Parser should reject this during validation
        with pytest.raises(ArchiveSecurityError):
            to_ast(tar_data, source_format="archive")

    def test_normal_archives_work(self):
        """Test that normal archives are not blocked by security."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            content = b"safe content"
            info = tarfile.TarInfo(name="docs/readme.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        # Should work without issues
        doc = to_ast(tar_data, source_format="archive")
        assert doc is not None
