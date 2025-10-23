#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for ZIP archive parser."""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast, to_markdown


def create_test_zip_with_markdown(content: str) -> bytes:
    """Create a ZIP archive with a markdown file.

    Parameters
    ----------
    content : str
        Markdown content

    Returns
    -------
    bytes
        ZIP archive as bytes

    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document.md", content.encode("utf-8"))
    return zip_buffer.getvalue()


def create_test_zip_with_files(files: dict[str, bytes]) -> bytes:
    """Create a ZIP archive with multiple files.

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
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path, content in files.items():
            zf.writestr(file_path, content)
    return zip_buffer.getvalue()


@pytest.mark.integration
class TestZipIntegration:
    """Integration tests for ZIP archive parsing."""

    def test_zip_with_markdown_file(self):
        """Test ZIP containing a markdown file."""
        markdown_content = "# Test Document\n\nThis is a test.\n\n## Section 1\n\nSome content here."
        zip_data = create_test_zip_with_markdown(markdown_content)

        markdown = to_markdown(zip_data, source_format="zip")

        assert isinstance(markdown, str)
        assert len(markdown) > 0
        # Should contain the markdown file name
        assert "document.md" in markdown
        # Should contain some of the markdown content
        assert "Test Document" in markdown

    def test_zip_with_python_file(self):
        """Test ZIP containing a Python file."""
        python_code = b'def hello():\n    print("Hello, World!")\n'
        files = {"script.py": python_code}
        zip_data = create_test_zip_with_files(files)

        markdown = to_markdown(zip_data, source_format="zip")

        assert isinstance(markdown, str)
        assert "script.py" in markdown
        # Python code should be in code block
        assert "```" in markdown

    def test_zip_with_json_file(self):
        """Test ZIP containing a JSON file.

        Note: JSON files have no registered parser (intentionally not treated as documents),
        so they show as "Could not parse this file" in ZIP archives.
        Use skip_empty_files=False to include them in output.
        """
        json_data = b'{"name": "test", "value": 123}'
        files = {"data.json": json_data}
        zip_data = create_test_zip_with_files(files)

        # JSON files need skip_empty_files=False to be included
        from all2md.options.zip import ZipOptions

        options = ZipOptions(skip_empty_files=False)
        markdown = to_markdown(zip_data, source_format="zip", parser_options=options)

        assert isinstance(markdown, str)
        assert "data.json" in markdown

    def test_zip_with_mixed_parseable_files(self):
        """Test ZIP with multiple parseable file types.

        Note: JSON files have no parser, so with default settings they're skipped.
        This test only checks parseable files (markdown and python).
        """
        files = {
            "readme.md": b"# README\n\nDocumentation",
            "script.py": b"print('hello')",
            "config.json": b'{"debug": true}',  # Will be skipped with default settings
        }
        zip_data = create_test_zip_with_files(files)

        markdown = to_markdown(zip_data, source_format="zip")

        # Check parseable files are included
        assert "readme.md" in markdown
        assert "script.py" in markdown

        # Check content is present
        assert "README" in markdown or "Documentation" in markdown
        assert "hello" in markdown

        # JSON file is skipped by default (skip_empty_files=True)
        # This is expected behavior for data files

    def test_zip_to_ast(self):
        """Test converting ZIP to AST."""
        markdown_content = "# Test\n\nContent"
        zip_data = create_test_zip_with_markdown(markdown_content)

        doc = to_ast(zip_data, source_format="zip")

        from all2md.ast import Document, Heading

        assert isinstance(doc, Document)
        assert doc.children is not None

        # Should have at least one heading (for the file)
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0

    def test_zip_with_nested_structure(self):
        """Test ZIP with nested directory structure."""
        files = {"docs/intro.md": b"# Introduction", "docs/guide.md": b"# Guide", "src/main.py": b"def main(): pass"}
        zip_data = create_test_zip_with_files(files)

        markdown = to_markdown(zip_data, source_format="zip")

        # Should preserve directory structure in output
        assert "docs" in markdown or "intro.md" in markdown
        assert "src" in markdown or "main.py" in markdown

    def test_zip_from_file(self):
        """Test ZIP parsing from file path."""
        files = {"test.md": b"# Test"}
        zip_data = create_test_zip_with_files(files)

        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(zip_data)
            tmp_path = tmp.name

        try:
            markdown = to_markdown(tmp_path)
            assert "test.md" in markdown
        finally:
            Path(tmp_path).unlink()

    def test_zip_with_subdirectories_and_options(self):
        """Test ZIP with subdirectories using various options."""
        files = {
            "level1/file1.md": b"# File 1",
            "level1/level2/file2.md": b"# File 2",
            "level1/level2/level3/file3.md": b"# File 3",
        }
        zip_data = create_test_zip_with_files(files)

        # Test with flattened structure
        from all2md.options.zip import ZipOptions

        options = ZipOptions(flatten_structure=True)
        markdown = to_markdown(zip_data, source_format="zip", parser_options=options)

        # Filenames should appear without full paths
        assert "file1.md" in markdown
        assert "file2.md" in markdown
        assert "file3.md" in markdown

    def test_large_zip_with_many_files(self):
        """Test ZIP with many files."""
        files = {f"file{i}.md": f"# File {i}\n\nContent {i}".encode() for i in range(10)}
        zip_data = create_test_zip_with_files(files)

        markdown = to_markdown(zip_data, source_format="zip")

        # Should process all files
        for i in range(10):
            assert f"file{i}.md" in markdown
