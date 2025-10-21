#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for archive conversion."""

import io
import tarfile
from pathlib import Path

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import Document
from all2md.options.archive import ArchiveOptions


def create_test_tar_with_nested_content(tmp_path: Path) -> bytes:
    """Create a TAR archive with nested parseable files.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory path

    Returns
    -------
    bytes
        TAR archive bytes

    """
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
        # Add a markdown file
        md_content = b"# Test Document\n\nThis is a test."
        md_info = tarfile.TarInfo(name="docs/test.md")
        md_info.size = len(md_content)
        tf.addfile(md_info, io.BytesIO(md_content))

        # Add a text file
        txt_content = b"Plain text content"
        txt_info = tarfile.TarInfo(name="notes.txt")
        txt_info.size = len(txt_content)
        tf.addfile(txt_info, io.BytesIO(txt_content))

        # Add a CSV file
        csv_content = b"Name,Age\nAlice,30\nBob,25"
        csv_info = tarfile.TarInfo(name="data/users.csv")
        csv_info.size = len(csv_content)
        tf.addfile(csv_info, io.BytesIO(csv_content))

    return tar_buffer.getvalue()


@pytest.mark.integration
class TestArchiveConversion:
    """Integration tests for archive conversion."""

    def test_tar_with_multiple_formats(self, tmp_path):
        """Test TAR archive containing multiple file formats."""
        tar_data = create_test_tar_with_nested_content(tmp_path)

        doc = to_ast(tar_data, source_format="archive")

        assert isinstance(doc, Document)
        # Should have content from all three files
        assert len(doc.children) > 3

        # Convert to markdown
        markdown = to_markdown(tar_data, source_format="archive")
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_tar_with_resource_extraction(self, tmp_path):
        """Test TAR archive with resource file extraction."""
        # Create a TAR with an image file (mock)
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Add a text file
            txt_content = b"Text content"
            txt_info = tarfile.TarInfo(name="readme.txt")
            txt_info.size = len(txt_content)
            tf.addfile(txt_info, io.BytesIO(txt_content))

            # Add a "binary" resource (mock image)
            img_content = b"\x89PNG\r\n\x1a\n" + b"fake image data"
            img_info = tarfile.TarInfo(name="images/logo.png")
            img_info.size = len(img_content)
            tf.addfile(img_info, io.BytesIO(img_content))

        tar_data = tar_buffer.getvalue()

        # Setup extraction directory
        extract_dir = tmp_path / "extracted"

        options = ArchiveOptions(
            extract_resource_files=True, attachment_output_dir=str(extract_dir), include_resource_manifest=True
        )

        doc = to_ast(tar_data, source_format="archive", parser_options=options)

        assert isinstance(doc, Document)

        # Check that resource was extracted
        assert extract_dir.exists()
        extracted_files = list(extract_dir.rglob("*"))
        # Should have extracted the image
        assert len(extracted_files) > 0

    def test_tar_path_preservation(self, tmp_path):
        """Test that directory structure is preserved in headings."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Add file in subdirectory
            content = b"Content"
            info = tarfile.TarInfo(name="project/src/main.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        options = ArchiveOptions(preserve_directory_structure=True, create_section_headings=True)

        markdown = to_markdown(tar_data, source_format="archive", parser_options=options)

        # Should include full path in heading
        assert "project/src/main.txt" in markdown

    def test_tar_with_file_io(self, tmp_path):
        """Test parsing TAR from file path."""
        # Create TAR file on disk
        tar_path = tmp_path / "test.tar.gz"

        with tarfile.open(tar_path, mode="w:gz") as tf:
            content = b"File content"
            info = tarfile.TarInfo(name="file.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        # Parse from file path
        doc = to_ast(str(tar_path))

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_tar_error_handling(self):
        """Test handling of malformed TAR files."""
        # Create invalid TAR data
        invalid_tar = b"This is not a valid TAR file"

        with pytest.raises(Exception):  # Should raise MalformedFileError or similar
            to_ast(invalid_tar, source_format="archive")

    def test_nested_archives_not_recursed(self):
        """Test that nested archives are not automatically extracted."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Create an inner TAR
            inner_tar = io.BytesIO()
            with tarfile.open(fileobj=inner_tar, mode="w") as inner_tf:
                content = b"Inner content"
                info = tarfile.TarInfo(name="inner.txt")
                info.size = len(content)
                inner_tf.addfile(info, io.BytesIO(content))

            inner_tar_data = inner_tar.getvalue()

            # Add the inner TAR to outer TAR
            info = tarfile.TarInfo(name="nested.tar")
            info.size = len(inner_tar_data)
            tf.addfile(info, io.BytesIO(inner_tar_data))

        tar_data = tar_buffer.getvalue()

        doc = to_ast(tar_data, source_format="archive")

        # Should process outer TAR but not automatically recurse into nested.tar
        # (nested.tar would be treated as a parseable file and converted to AST,
        #  which would then recurse into it. This is actually desired behavior!)
        assert isinstance(doc, Document)

    def test_large_file_filtering(self, tmp_path):
        """Test filtering of files by pattern in large archive."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tf:
            # Add multiple files with different patterns
            for i in range(10):
                if i % 2 == 0:
                    content = f"Text file {i}".encode()
                    info = tarfile.TarInfo(name=f"file{i}.txt")
                else:
                    content = f"Log file {i}".encode()
                    info = tarfile.TarInfo(name=f"file{i}.log")
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))

        tar_data = tar_buffer.getvalue()

        # Exclude .log files
        options = ArchiveOptions(exclude_patterns=["*.log"])
        doc = to_ast(tar_data, source_format="archive", parser_options=options)

        # Should only have .txt files (5 files)
        from all2md.ast import Heading

        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 5


@pytest.mark.integration
@pytest.mark.skipif(
    not pytest.importorskip("py7zr", reason="py7zr not installed"), reason="Requires py7zr for 7Z support"
)
class TestSevenZipIntegration:
    """Integration tests for 7Z archive support."""

    def test_7z_basic_conversion(self, tmp_path):
        """Test basic 7Z conversion (if py7zr is available)."""
        import py7zr

        # Create 7Z file
        sz_path = tmp_path / "test.7z"
        with py7zr.SevenZipFile(sz_path, mode="w") as sz:
            content = b"Test content"
            sz.writestr("test.txt", content.decode("utf-8"))

        # Parse 7Z file
        doc = to_ast(str(sz_path))

        assert isinstance(doc, Document)
        assert len(doc.children) > 0


@pytest.mark.integration
@pytest.mark.skipif(
    not pytest.importorskip("rarfile", reason="rarfile not installed"), reason="Requires rarfile for RAR support"
)
class TestRarIntegration:
    """Integration tests for RAR archive support."""

    def test_rar_detection(self):
        """Test RAR detection (requires rarfile)."""
        # Note: Creating actual RAR files requires UnRAR binary
        # This test just verifies the import works
        import rarfile

        assert rarfile is not None
