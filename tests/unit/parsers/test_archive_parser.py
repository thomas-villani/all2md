#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for archive (TAR/7Z/RAR) parser."""

import io
import tarfile

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import Document, Heading
from all2md.options.archive import ArchiveOptions
from all2md.parsers.archive import ArchiveToAstConverter


def create_test_tar(files: dict[str, bytes]) -> bytes:
    """Create a TAR archive with the given files.

    Parameters
    ----------
    files : dict[str, bytes]
        Mapping of file paths to content bytes

    Returns
    -------
    bytes
        TAR archive as bytes

    """
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
        for file_path, content in files.items():
            tarinfo = tarfile.TarInfo(name=file_path)
            tarinfo.size = len(content)
            tf.addfile(tarinfo, io.BytesIO(content))
    return tar_buffer.getvalue()


def create_test_tar_gz(files: dict[str, bytes]) -> bytes:
    """Create a gzipped TAR archive with the given files.

    Parameters
    ----------
    files : dict[str, bytes]
        Mapping of file paths to content bytes

    Returns
    -------
    bytes
        TAR.GZ archive as bytes

    """
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
        for file_path, content in files.items():
            tarinfo = tarfile.TarInfo(name=file_path)
            tarinfo.size = len(content)
            tf.addfile(tarinfo, io.BytesIO(content))
    return tar_buffer.getvalue()


class TestArchiveParser:
    """Tests for archive parsing."""

    def test_empty_tar(self):
        """Test parsing an empty TAR archive."""
        tar_data = create_test_tar({})

        doc = to_ast(tar_data, source_format="archive")

        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        # Should have a note about empty archive
        assert any("Empty archive" in str(child) for child in doc.children)

    def test_single_text_file_tar(self):
        """Test parsing a TAR with a single text file."""
        files = {"test.txt": b"Hello, World!"}
        tar_data = create_test_tar(files)

        doc = to_ast(tar_data, source_format="archive")

        assert isinstance(doc, Document)
        # Should have heading for the file
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 1

    def test_multiple_files_tar(self):
        """Test parsing a TAR with multiple files."""
        files = {"file1.txt": b"Content 1", "file2.txt": b"Content 2", "subdir/file3.txt": b"Content 3"}
        tar_data = create_test_tar(files)

        doc = to_ast(tar_data, source_format="archive")

        assert isinstance(doc, Document)
        # Should have headings for each file
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 3

    def test_tar_gz(self):
        """Test parsing a gzipped TAR archive."""
        files = {"file1.txt": b"Content 1", "file2.txt": b"Content 2"}
        tar_gz_data = create_test_tar_gz(files)

        doc = to_ast(tar_gz_data, source_format="archive")

        assert isinstance(doc, Document)
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 2

    def test_exclude_patterns(self):
        """Test excluding files by pattern."""
        files = {"file1.txt": b"Content 1", "file2.log": b"Log content", "__MACOSX/._file1.txt": b"Mac metadata"}
        tar_data = create_test_tar(files)

        options = ArchiveOptions(exclude_patterns=["*.log", "__MACOSX/*"])

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Should only have file1.txt
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1

    def test_include_patterns(self):
        """Test including only specific patterns."""
        files = {"file1.txt": b"Content 1", "file2.md": b"Markdown", "file3.log": b"Log"}
        tar_data = create_test_tar(files)

        options = ArchiveOptions(include_patterns=["*.txt", "*.md"])

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Should have file1.txt and file2.md
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 2

    def test_max_depth(self):
        """Test limiting directory depth."""
        files = {
            "file1.txt": b"Depth 0",
            "dir1/file2.txt": b"Depth 1",
            "dir1/dir2/file3.txt": b"Depth 2",
        }
        tar_data = create_test_tar(files)

        options = ArchiveOptions(max_depth=1)

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Should only have file1.txt and dir1/file2.txt
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 2

    def test_flatten_structure(self):
        """Test flattening directory structure."""
        files = {"dir1/file1.txt": b"Content"}
        tar_data = create_test_tar(files)

        options = ArchiveOptions(flatten_structure=True, create_section_headings=True)

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Check that heading uses filename only, not full path
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1
        heading_text = str(headings[0])
        assert "file1.txt" in heading_text
        assert "dir1" not in heading_text

    def test_no_section_headings(self):
        """Test disabling section headings."""
        files = {"file1.txt": b"Content 1"}
        tar_data = create_test_tar(files)

        options = ArchiveOptions(create_section_headings=False)

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Should not have section headings
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 0

    def test_skip_empty_files(self):
        """Test skipping empty files."""
        files = {"file1.txt": b"Content", "empty.txt": b""}
        tar_data = create_test_tar(files)

        options = ArchiveOptions(skip_empty_files=True)

        parser = ArchiveToAstConverter(options=options)
        doc = parser.parse(tar_data)

        # Should only have file1.txt
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1

    def test_archive_type_detection_tar(self):
        """Test archive type detection for plain TAR."""
        parser = ArchiveToAstConverter()
        tar_data = create_test_tar({"file.txt": b"content"})

        # Create a BytesIO with name attribute
        file_obj = io.BytesIO(tar_data)
        file_obj.name = "test.tar"

        archive_type = parser._detect_archive_type(file_obj)
        assert archive_type == "tar"

    def test_archive_type_detection_tar_gz(self):
        """Test archive type detection for TAR.GZ."""
        parser = ArchiveToAstConverter()
        tar_gz_data = create_test_tar_gz({"file.txt": b"content"})

        # Create a BytesIO with name attribute
        file_obj = io.BytesIO(tar_gz_data)
        file_obj.name = "test.tar.gz"

        archive_type = parser._detect_archive_type(file_obj)
        assert archive_type == "tar.gz"

    def test_archive_type_detection_tgz(self):
        """Test archive type detection for .tgz extension."""
        parser = ArchiveToAstConverter()
        tar_gz_data = create_test_tar_gz({"file.txt": b"content"})

        file_obj = io.BytesIO(tar_gz_data)
        file_obj.name = "test.tgz"

        archive_type = parser._detect_archive_type(file_obj)
        assert archive_type == "tar.gz"

    def test_archive_type_detection_magic_bytes_gzip(self):
        """Test archive type detection via GZIP magic bytes."""
        parser = ArchiveToAstConverter()
        tar_gz_data = create_test_tar_gz({"file.txt": b"content"})

        # Detect by magic bytes (no filename)
        archive_type = parser._detect_archive_type(tar_gz_data)
        assert archive_type == "tar.gz"

    def test_metadata_extraction(self):
        """Test metadata extraction from archive."""
        files = {"file1.txt": b"Content 1", "file2.txt": b"Content 2"}
        tar_data = create_test_tar(files)

        parser = ArchiveToAstConverter()
        doc = parser.parse(tar_data)

        # Check metadata
        assert doc.metadata is not None
        assert "file_count" in doc.metadata
        assert doc.metadata["file_count"] == 2

    def test_to_markdown_integration(self):
        """Test integration with to_markdown function."""
        files = {"test.txt": b"Hello, World!"}
        tar_data = create_test_tar(files)

        markdown = to_markdown(tar_data, source_format="archive")

        assert isinstance(markdown, str)
        assert "test.txt" in markdown or "Hello, World!" in markdown


@pytest.mark.skipif(
    not pytest.importorskip("py7zr", reason="py7zr not installed"), reason="Requires py7zr for 7Z support"
)
class TestSevenZipSupport:
    """Tests for 7Z archive support."""

    def test_7z_detection(self):
        """Test 7Z archive type detection."""
        parser = ArchiveToAstConverter()

        # Create a mock file object with .7z extension
        file_obj = io.BytesIO(b"7z\xbc\xaf\x27\x1csome7zdata")
        file_obj.name = "test.7z"

        archive_type = parser._detect_archive_type(file_obj)
        assert archive_type == "7z"


@pytest.mark.skipif(
    not pytest.importorskip("rarfile", reason="rarfile not installed"), reason="Requires rarfile for RAR support"
)
class TestRarSupport:
    """Tests for RAR archive support."""

    def test_rar_detection(self):
        """Test RAR archive type detection."""
        parser = ArchiveToAstConverter()

        # Create a mock file object with .rar extension
        file_obj = io.BytesIO(b"Rar!\x1a\x07\x00somerardata")
        file_obj.name = "test.rar"

        archive_type = parser._detect_archive_type(file_obj)
        assert archive_type == "rar"
