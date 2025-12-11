"""Unit tests for all2md CLI serve command handlers.

This module tests the serve command handler directly,
providing coverage for argument parsing, setup, and helper functions.
"""

from unittest.mock import patch

import pytest

from all2md.cli.commands.server import (
    _format_file_size,
    _generate_directory_index,
    _generate_upload_form,
    _get_content_type_for_format,
    _parse_multipart_form_data,
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

    def test_format_file_size_terabytes(self):
        """Test formatting file size in TB."""
        assert _format_file_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_format_file_size_zero(self):
        """Test formatting zero bytes."""
        assert _format_file_size(0) == "0.0 B"

    def test_get_content_type_md(self):
        """Test getting content type for md alias."""
        content_type = _get_content_type_for_format("md")
        assert content_type == "text/markdown; charset=utf-8"

    def test_get_content_type_plaintext(self):
        """Test getting content type for plaintext."""
        content_type = _get_content_type_for_format("plaintext")
        assert content_type == "text/plain; charset=utf-8"

    def test_get_content_type_txt(self):
        """Test getting content type for txt."""
        content_type = _get_content_type_for_format("txt")
        assert content_type == "text/plain; charset=utf-8"

    def test_get_content_type_yaml(self):
        """Test getting content type for yaml."""
        content_type = _get_content_type_for_format("yaml")
        assert content_type == "application/x-yaml"

    def test_get_content_type_yml(self):
        """Test getting content type for yml alias."""
        content_type = _get_content_type_for_format("yml")
        assert content_type == "application/x-yaml"

    def test_get_content_type_toml(self):
        """Test getting content type for toml."""
        content_type = _get_content_type_for_format("toml")
        assert content_type == "application/toml"

    def test_get_content_type_xml(self):
        """Test getting content type for xml."""
        content_type = _get_content_type_for_format("xml")
        assert content_type == "application/xml"

    def test_get_content_type_csv(self):
        """Test getting content type for csv."""
        content_type = _get_content_type_for_format("csv")
        assert content_type == "text/csv; charset=utf-8"

    def test_get_content_type_docx(self):
        """Test getting content type for docx."""
        content_type = _get_content_type_for_format("docx")
        assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_get_content_type_odt(self):
        """Test getting content type for odt."""
        content_type = _get_content_type_for_format("odt")
        assert content_type == "application/vnd.oasis.opendocument.text"

    def test_get_content_type_rtf(self):
        """Test getting content type for rtf."""
        content_type = _get_content_type_for_format("rtf")
        assert content_type == "application/rtf"

    def test_get_content_type_epub(self):
        """Test getting content type for epub."""
        content_type = _get_content_type_for_format("epub")
        assert content_type == "application/epub+zip"

    def test_get_content_type_latex(self):
        """Test getting content type for latex."""
        content_type = _get_content_type_for_format("latex")
        assert content_type == "application/x-latex"

    def test_get_content_type_tex(self):
        """Test getting content type for tex alias."""
        content_type = _get_content_type_for_format("tex")
        assert content_type == "application/x-latex"

    def test_get_content_type_rst(self):
        """Test getting content type for rst."""
        content_type = _get_content_type_for_format("rst")
        assert content_type == "text/x-rst; charset=utf-8"

    def test_get_content_type_asciidoc(self):
        """Test getting content type for asciidoc."""
        content_type = _get_content_type_for_format("asciidoc")
        assert content_type == "text/asciidoc; charset=utf-8"

    def test_get_content_type_org(self):
        """Test getting content type for org."""
        content_type = _get_content_type_for_format("org")
        assert content_type == "text/org; charset=utf-8"

    def test_get_content_type_case_insensitive(self):
        """Test getting content type is case insensitive."""
        assert _get_content_type_for_format("HTML") == "text/html; charset=utf-8"
        assert _get_content_type_for_format("Json") == "application/json"


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

    def test_serve_missing_args(self):
        """Test serve without required input argument."""
        exit_code = handle_serve_command([])
        assert exit_code != 0

    def test_serve_custom_port(self, capsys):
        """Test serve --port argument parsing."""
        exit_code = handle_serve_command(["--help"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "--port" in captured.out

    def test_serve_custom_host(self, capsys):
        """Test serve --host argument parsing."""
        exit_code = handle_serve_command(["--help"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "--host" in captured.out


@pytest.mark.unit
class TestParseMultipartFormData:
    """Test multipart form data parsing functionality."""

    def test_parse_simple_text_field(self):
        """Test parsing a simple text field."""
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"------{boundary}\r\n"
            f'Content-Disposition: form-data; name="format"\r\n'
            f"\r\n"
            f"html\r\n"
            f"------{boundary}--"
        ).encode("utf-8")

        content_type = f"multipart/form-data; boundary=----{boundary}"
        result = _parse_multipart_form_data(body, content_type)

        assert "format" in result
        assert result["format"] == "html"

    def test_parse_file_field(self):
        """Test parsing a file upload field."""
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        file_content = b"Hello, this is file content"
        body = (
            (
                f"------{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
                f"Content-Type: text/plain\r\n"
                f"\r\n"
            ).encode("utf-8")
            + file_content
            + f"\r\n------{boundary}--".encode("utf-8")
        )

        content_type = f"multipart/form-data; boundary=----{boundary}"
        result = _parse_multipart_form_data(body, content_type)

        # File uploads use the filename as the key
        assert "test.txt" in result or "file" in result
        # Check the content is present
        file_value = result.get("test.txt") or result.get("file")
        if isinstance(file_value, dict):
            assert file_value["data"] == file_content
        else:
            assert file_value == file_content.decode("utf-8")

    def test_parse_multiple_fields(self):
        """Test parsing multiple fields."""
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"------{boundary}\r\n"
            f'Content-Disposition: form-data; name="format"\r\n'
            f"\r\n"
            f"markdown\r\n"
            f"------{boundary}\r\n"
            f'Content-Disposition: form-data; name="option"\r\n'
            f"\r\n"
            f"value\r\n"
            f"------{boundary}--"
        ).encode("utf-8")

        content_type = f"multipart/form-data; boundary=----{boundary}"
        result = _parse_multipart_form_data(body, content_type)

        assert result["format"] == "markdown"
        assert result["option"] == "value"

    def test_parse_no_boundary_raises_error(self):
        """Test parsing without boundary raises ValueError."""
        body = b"some content"
        content_type = "multipart/form-data"

        with pytest.raises(ValueError, match="No boundary found"):
            _parse_multipart_form_data(body, content_type)

    def test_parse_boundary_with_quotes(self):
        """Test parsing boundary with quotes."""
        boundary = "testboundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="field"\r\n'
            f"\r\n"
            f"value\r\n"
            f"--{boundary}--"
        ).encode("utf-8")

        content_type = f'multipart/form-data; boundary="{boundary}"'
        result = _parse_multipart_form_data(body, content_type)

        assert result["field"] == "value"

    def test_parse_empty_parts(self):
        """Test parsing with empty parts is handled."""
        boundary = "testboundary"
        body = f"--{boundary}--".encode("utf-8")

        content_type = f"multipart/form-data; boundary={boundary}"
        result = _parse_multipart_form_data(body, content_type)

        assert result == {}

    def test_parse_newline_variations(self):
        """Test parsing with different newline styles."""
        boundary = "testboundary"
        # Using just \n instead of \r\n
        body = (
            f"--{boundary}\n" f'Content-Disposition: form-data; name="field"\n' f"\n" f"value\n" f"--{boundary}--"
        ).encode("utf-8")

        content_type = f"multipart/form-data; boundary={boundary}"
        result = _parse_multipart_form_data(body, content_type)

        assert result["field"] == "value"


@pytest.mark.unit
class TestGenerateUploadForm:
    """Test upload form generation functionality."""

    def test_generate_upload_form_basic(self, tmp_path):
        """Test basic upload form generation."""
        # Create a minimal theme template
        theme_path = tmp_path / "theme.html"
        theme_path.write_text(
            "<!DOCTYPE html><html><head><title>{TITLE}</title></head>" "<body>{CONTENT}</body></html>"
        )

        with patch("all2md.cli.commands.server.registry") as mock_registry:
            mock_registry.list_formats.return_value = ["html", "markdown", "pdf"]

            html = _generate_upload_form(theme_path)

        assert "{TITLE}" not in html  # Template should be replaced
        assert "{CONTENT}" not in html
        assert "Document Converter" in html
        assert "<form" in html
        assert 'type="file"' in html
        assert "<select" in html

    def test_generate_upload_form_includes_formats(self, tmp_path):
        """Test that upload form includes format options."""
        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        with patch("all2md.cli.commands.server.registry") as mock_registry:
            mock_registry.list_formats.return_value = ["html", "markdown", "pdf", "docx"]

            html = _generate_upload_form(theme_path)

        # Should include format options
        assert 'value="html"' in html
        assert 'value="markdown"' in html
        assert 'value="pdf"' in html
        assert 'value="docx"' in html

    def test_generate_upload_form_excludes_auto(self, tmp_path):
        """Test that upload form excludes 'auto' format."""
        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        with patch("all2md.cli.commands.server.registry") as mock_registry:
            mock_registry.list_formats.return_value = ["auto", "html", "markdown"]

            html = _generate_upload_form(theme_path)

        assert 'value="auto"' not in html
        assert 'value="html"' in html


@pytest.mark.unit
class TestGenerateDirectoryIndex:
    """Test directory index generation functionality."""

    def test_generate_directory_index_basic(self, tmp_path):
        """Test basic directory index generation."""
        # Create test files
        file1 = tmp_path / "doc1.pdf"
        file2 = tmp_path / "doc2.md"
        file1.write_text("pdf content")
        file2.write_text("# Markdown")

        # Create theme template
        theme_path = tmp_path / "theme.html"
        theme_path.write_text(
            "<!DOCTYPE html><html><head><title>{TITLE}</title></head>" "<body>{CONTENT}</body></html>"
        )

        html = _generate_directory_index(
            [file1, file2],
            "TestDir",
            theme_path,
            tmp_path,
            enable_upload=False,
        )

        assert "TestDir" in html
        assert "doc1.pdf" in html
        assert "doc2.md" in html
        assert "2 document(s)" in html

    def test_generate_directory_index_with_upload_link(self, tmp_path):
        """Test directory index with upload link enabled."""
        file1 = tmp_path / "test.md"
        file1.write_text("content")

        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        html = _generate_directory_index(
            [file1],
            "TestDir",
            theme_path,
            tmp_path,
            enable_upload=True,
        )

        assert "/upload" in html
        assert "Upload" in html

    def test_generate_directory_index_no_upload_link(self, tmp_path):
        """Test directory index without upload link."""
        file1 = tmp_path / "test.md"
        file1.write_text("content")

        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        html = _generate_directory_index(
            [file1],
            "TestDir",
            theme_path,
            tmp_path,
            enable_upload=False,
        )

        assert "/upload" not in html

    def test_generate_directory_index_nested_files(self, tmp_path):
        """Test directory index with nested directory structure."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        file1 = tmp_path / "root.md"
        file2 = subdir / "nested.pdf"
        file1.write_text("root content")
        file2.write_text("nested content")

        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        html = _generate_directory_index(
            [file1, file2],
            "TestDir",
            theme_path,
            tmp_path,
            enable_upload=False,
        )

        assert "root.md" in html
        assert "nested.pdf" in html
        assert "subdir" in html  # Directory name should appear

    def test_generate_directory_index_shows_file_size(self, tmp_path):
        """Test that directory index shows file sizes."""
        file1 = tmp_path / "small.txt"
        file1.write_text("x" * 100)  # 100 bytes

        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        html = _generate_directory_index(
            [file1],
            "TestDir",
            theme_path,
            tmp_path,
            enable_upload=False,
        )

        # Should contain file size
        assert "B" in html  # Size in bytes

    def test_generate_directory_index_empty_files(self, tmp_path):
        """Test directory index with empty file list."""
        theme_path = tmp_path / "theme.html"
        theme_path.write_text("{TITLE} {CONTENT}")

        html = _generate_directory_index(
            [],
            "EmptyDir",
            theme_path,
            tmp_path,
            enable_upload=False,
        )

        assert "EmptyDir" in html
        assert "0 document(s)" in html
