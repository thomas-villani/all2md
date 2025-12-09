"""Unit tests for all2md CLI serve command handlers.

This module tests the serve command handler directly,
providing coverage for argument parsing, setup, and helper functions.
"""

from unittest.mock import patch

import pytest

from all2md.cli.commands.server import (
    _format_file_size,
    _get_content_type_for_format,
    _scan_directory_for_documents,
    handle_serve_command,
)


@pytest.mark.unit
class TestServerHelpers:
    """Test helper functions for serve command."""

    def test_get_content_type_html(self):
        """Test getting content type for HTML."""
        content_type = _get_content_type_for_format("html")
        assert content_type == "text/html; charset=utf-8"

    def test_get_content_type_markdown(self):
        """Test getting content type for Markdown."""
        content_type = _get_content_type_for_format("markdown")
        assert content_type == "text/markdown; charset=utf-8"

    def test_get_content_type_json(self):
        """Test getting content type for JSON."""
        content_type = _get_content_type_for_format("json")
        assert content_type == "application/json"

    def test_get_content_type_pdf(self):
        """Test getting content type for PDF."""
        content_type = _get_content_type_for_format("pdf")
        assert content_type == "application/pdf"

    def test_get_content_type_unknown(self):
        """Test getting content type for unknown format."""
        content_type = _get_content_type_for_format("xyz_unknown")
        assert content_type == "application/octet-stream"

    def test_format_file_size_bytes(self):
        """Test formatting file size in bytes."""
        assert _format_file_size(500) == "500.0 B"

    def test_format_file_size_kilobytes(self):
        """Test formatting file size in KB."""
        assert _format_file_size(1024) == "1.0 KB"
        assert _format_file_size(2048) == "2.0 KB"

    def test_format_file_size_megabytes(self):
        """Test formatting file size in MB."""
        assert _format_file_size(1024 * 1024) == "1.0 MB"
        assert _format_file_size(5 * 1024 * 1024) == "5.0 MB"

    def test_format_file_size_gigabytes(self):
        """Test formatting file size in GB."""
        assert _format_file_size(1024 * 1024 * 1024) == "1.0 GB"


@pytest.mark.unit
class TestScanDirectoryForDocuments:
    """Test directory scanning functionality."""

    def test_scan_directory_empty(self, tmp_path):
        """Test scanning empty directory."""
        files = _scan_directory_for_documents(tmp_path, recursive=False)
        assert len(files) == 0

    @patch("all2md.cli.commands.server.registry")
    def test_scan_directory_with_files(self, mock_registry, tmp_path):
        """Test scanning directory with supported files."""
        # Create test files
        (tmp_path / "test.md").write_text("# Test")
        (tmp_path / "doc.pdf").write_text("fake pdf")
        (tmp_path / "unsupported.xyz").write_text("data")

        # Mock registry to accept .md and .pdf but not .xyz
        def mock_detect(path):
            path_str = str(path)
            if path_str.endswith(".md"):
                return "markdown"
            elif path_str.endswith(".pdf"):
                return "pdf"
            else:
                raise ValueError("Unsupported")

        mock_registry.detect_format = mock_detect

        files = _scan_directory_for_documents(tmp_path, recursive=False)

        # Should find 2 supported files
        assert len(files) == 2
        file_names = [f.name for f in files]
        assert "test.md" in file_names
        assert "doc.pdf" in file_names
        assert "unsupported.xyz" not in file_names

    @patch("all2md.cli.commands.server.registry")
    def test_scan_directory_recursive(self, mock_registry, tmp_path):
        """Test recursive directory scanning."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.md").write_text("# Root")
        (subdir / "nested.md").write_text("# Nested")

        mock_registry.detect_format = lambda x: "markdown"

        files = _scan_directory_for_documents(tmp_path, recursive=True)

        assert len(files) == 2
        file_names = [f.name for f in files]
        assert "root.md" in file_names
        assert "nested.md" in file_names

    @patch("all2md.cli.commands.server.registry")
    def test_scan_directory_non_recursive(self, mock_registry, tmp_path):
        """Test non-recursive scanning skips subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.md").write_text("# Root")
        (subdir / "nested.md").write_text("# Nested")

        mock_registry.detect_format = lambda x: "markdown"

        files = _scan_directory_for_documents(tmp_path, recursive=False)

        assert len(files) == 1
        assert files[0].name == "root.md"


@pytest.mark.unit
class TestHandleServeCommand:
    """Test handle_serve_command function."""

    def test_serve_help(self, capsys):
        """Test serve --help returns successfully."""
        exit_code = handle_serve_command(["--help"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "Usage:" in captured.out

    def test_serve_nonexistent_input(self, capsys):
        """Test serving nonexistent file/directory."""
        exit_code = handle_serve_command(["nonexistent_path_xyz"])
        assert exit_code != 0
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "Error" in captured.err

    def test_serve_empty_directory(self, tmp_path, capsys):
        """Test serving empty directory fails."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Patch registry to reject all files
        with patch("all2md.cli.commands.server.registry.detect_format", side_effect=ValueError("Unsupported")):
            exit_code = handle_serve_command([str(empty_dir)])

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "No supported document files found" in captured.err or "Error" in captured.err

    def test_serve_invalid_theme(self, tmp_path, capsys):
        """Test serving with invalid theme."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        exit_code = handle_serve_command([str(test_file), "--theme", "nonexistent_theme_xyz"])

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "Error" in captured.err
