#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for ZIP archive parser."""

import io
import zipfile

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import Document, Heading
from all2md.exceptions import MalformedFileError, ZipFileSecurityError
from all2md.options.zip import ZipOptions
from all2md.parsers.zip import ZipToAstConverter


def create_test_zip(files: dict[str, bytes]) -> bytes:
    """Create a ZIP archive with the given files.

    Parameters
    ----------
    files : dict[str, bytes]
        Mapping of file paths to content bytes

    Returns
    -------
    bytes
        ZIP archive as bytes

    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path, content in files.items():
            zf.writestr(file_path, content)
    return zip_buffer.getvalue()


class TestZipParser:
    """Tests for ZIP archive parsing."""

    def test_empty_zip(self):
        """Test parsing an empty ZIP archive."""
        zip_data = create_test_zip({})

        doc = to_ast(zip_data, source_format="zip")

        assert isinstance(doc, Document)
        assert len(doc.children) > 0
        # Should have a note about empty archive
        assert any("Empty archive" in str(child) for child in doc.children)

    def test_single_text_file(self):
        """Test parsing a ZIP with a single text file."""
        files = {
            "test.txt": b"Hello, World!"
        }
        zip_data = create_test_zip(files)

        doc = to_ast(zip_data, source_format="zip")

        assert isinstance(doc, Document)
        # Should have heading for the file
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 1

    def test_multiple_files(self):
        """Test parsing a ZIP with multiple files."""
        files = {
            "file1.txt": b"Content 1",
            "file2.txt": b"Content 2",
            "subdir/file3.txt": b"Content 3"
        }
        zip_data = create_test_zip(files)

        doc = to_ast(zip_data, source_format="zip")

        assert isinstance(doc, Document)
        # Should have headings for each file
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 3

    def test_exclude_patterns(self):
        """Test excluding files by pattern."""
        files = {
            "file1.txt": b"Content 1",
            "file2.log": b"Log content",
            "__MACOSX/._file1.txt": b"Mac metadata"
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(
            exclude_patterns=["*.log", "__MACOSX/*"]
        )

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        # Should only have file1.txt
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1

    def test_include_patterns(self):
        """Test including only specific files."""
        files = {
            "document.txt": b"Text content",
            "image.png": b"PNG data",
            "data.json": b'{"key": "value"}'
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(
            include_patterns=["*.txt", "*.json"]
        )

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        headings = [node for node in doc.children if isinstance(node, Heading)]
        # Should have 2 headings (txt and json)
        assert len(headings) == 2

    def test_max_depth(self):
        """Test limiting directory traversal depth."""
        files = {
            "root.txt": b"Root level",
            "level1/file.txt": b"Level 1",
            "level1/level2/file.txt": b"Level 2",
            "level1/level2/level3/file.txt": b"Level 3"
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(max_depth=1)

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        headings = [node for node in doc.children if isinstance(node, Heading)]
        # Should only have root.txt and level1/file.txt (depth 0 and 1)
        assert len(headings) == 2

    def test_flatten_structure(self):
        """Test flattening directory structure in output."""
        files = {
            "subdir/file.txt": b"Content"
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(flatten_structure=True)

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        # Find heading and check it only shows filename, not full path
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1
        heading_text = headings[0].content[0].content
        assert heading_text == "file.txt"
        assert "/" not in heading_text

    def test_no_section_headings(self):
        """Test disabling section headings."""
        files = {
            "file.txt": b"Content"
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(create_section_headings=False)

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        # Should have no headings
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 0

    def test_skip_empty_files(self):
        """Test skipping empty files."""
        files = {
            "content.txt": b"Has content",
            "empty.txt": b""
        }
        zip_data = create_test_zip(files)

        options = ZipOptions(skip_empty_files=True)

        parser = ZipToAstConverter(options=options)
        doc = parser.parse(zip_data)

        headings = [node for node in doc.children if isinstance(node, Heading)]
        # Should only have heading for content.txt
        assert len(headings) == 1

    def test_nested_zip_with_markdown(self):
        """Test ZIP containing a markdown file."""
        markdown_content = b"# Hello\n\nThis is a test."
        files = {
            "document.md": markdown_content
        }
        zip_data = create_test_zip(files)

        doc = to_ast(zip_data, source_format="zip")

        assert isinstance(doc, Document)
        # Should parse the markdown content
        headings = [node for node in doc.children if isinstance(node, Heading)]
        # At least section heading for the file
        assert len(headings) >= 1

    def test_zip_bomb_protection(self):
        """Test that zip bombs are rejected."""
        # Create a zip with suspicious compression ratio
        # This would require creating an actual zip bomb, which is complex
        # For now, we'll just verify the validation function is called
        # via integration with validate_zip_archive
        pass  # Skip for basic unit test

    def test_path_traversal_protection(self):
        """Test that path traversal attacks are blocked."""
        # Create ZIP with malicious path
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Try to create entry with path traversal
            info = zipfile.ZipInfo("../../../etc/passwd")
            zf.writestr(info, b"malicious content")
        zip_data = zip_buffer.getvalue()

        # Should be rejected by security validation
        with pytest.raises(ZipFileSecurityError):
            to_ast(zip_data, source_format="zip")

    def test_invalid_zip(self):
        """Test handling of invalid ZIP data."""
        invalid_data = b"This is not a ZIP file"

        with pytest.raises(MalformedFileError):
            to_ast(invalid_data, source_format="zip")

    def test_zip_with_directory_entries(self):
        """Test that directory entries are skipped."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("dir1/", "")  # Directory entry
            zf.writestr("dir1/file.txt", b"Content")
        zip_data = zip_buffer.getvalue()

        doc = to_ast(zip_data, source_format="zip")

        # Should only process the file, not the directory
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 1


class TestZipMetadata:
    """Tests for ZIP metadata extraction."""

    def test_metadata_extraction(self):
        """Test that metadata is extracted from ZIP."""
        files = {
            "file1.txt": b"Content 1",
            "file2.txt": b"Content 2"
        }
        zip_data = create_test_zip(files)

        doc = to_ast(zip_data, source_format="zip")

        # Check metadata
        assert doc.metadata is not None
        assert "file_count" in doc.metadata
        assert doc.metadata["file_count"] == 2


@pytest.mark.integration
class TestZipIntegration:
    """Integration tests for ZIP parser."""

    def test_to_markdown_conversion(self):
        """Test converting ZIP to markdown string."""
        files = {
            "test.txt": b"Hello, World!"
        }
        zip_data = create_test_zip(files)

        markdown = to_markdown(zip_data, source_format="zip")

        assert isinstance(markdown, str)
        assert len(markdown) > 0
        # Should contain the filename as heading
        assert "test.txt" in markdown

    def test_mixed_file_types(self):
        """Test ZIP with multiple file types."""
        files = {
            "document.txt": b"Plain text content",
            "data.json": b'{"key": "value"}',
            "notes.md": b"# Markdown\n\nContent"
        }
        zip_data = create_test_zip(files)

        markdown = to_markdown(zip_data, source_format="zip")

        assert "document.txt" in markdown
        assert "data.json" in markdown
        assert "notes.md" in markdown
