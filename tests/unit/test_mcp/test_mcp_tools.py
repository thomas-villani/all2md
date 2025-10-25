"""Unit tests for MCP tool implementations."""

import base64

import pytest

from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import ReadDocumentAsMarkdownInput, SaveDocumentFromMarkdownInput
from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl


class TestReadDocumentAsMarkdownImpl:
    """Tests for read_document_as_markdown_impl function."""

    def test_read_from_file_path(self, tmp_path):
        """Test reading from a file path."""
        from all2md.mcp.security import prepare_allowlist_dirs

        # Create test file
        test_file = tmp_path / "test.html"
        test_file.write_text("<h1>Hello World</h1>")

        # Create config with validated allowlists
        config = MCPConfig(
            read_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
        )

        # Create input (source is auto-detected as file path)
        input_data = ReadDocumentAsMarkdownInput(source=str(test_file))

        # Execute
        result = read_document_as_markdown_impl(input_data, config)

        # Verify - result is now a list [markdown_str, ...images]
        assert isinstance(result, list)
        assert len(result) >= 1
        markdown = result[0]
        assert isinstance(markdown, str)
        assert "Hello World" in markdown

    def test_read_from_plain_text_content(self):
        """Test reading from plain text content (auto-detected)."""
        config = MCPConfig()

        # Plain HTML content (auto-detected)
        input_data = ReadDocumentAsMarkdownInput(source="<h1>Test</h1><p>Content</p>", format_hint="html")

        result = read_document_as_markdown_impl(input_data, config)

        # Verify - result is now a list [markdown_str, ...images]
        assert isinstance(result, list)
        assert len(result) >= 1
        markdown = result[0]
        assert isinstance(markdown, str)
        assert "Test" in markdown
        assert "Content" in markdown

    def test_read_from_base64_content(self):
        """Test reading from base64-encoded content (auto-detected)."""
        config = MCPConfig()

        # Create base64-encoded HTML with sufficient length (>50 bytes decoded)
        # to pass the stricter base64 detection heuristics
        html_content = b"<h1>Base64 Test</h1><p>This is a longer content to ensure it passes the minimum size threshold for base64 detection.</p>"
        base64_content = base64.b64encode(html_content).decode("ascii")

        input_data = ReadDocumentAsMarkdownInput(source=base64_content, format_hint="html")

        result = read_document_as_markdown_impl(input_data, config)

        # Verify - result is now a list [markdown_str, ...images]
        assert isinstance(result, list)
        assert len(result) >= 1
        markdown = result[0]
        assert isinstance(markdown, str)
        assert "Base64 Test" in markdown

    def test_pdf_pages_validation_rejects_malicious_input(self):
        """Test that malicious page specs are rejected (security fix)."""
        config = MCPConfig()

        # Test injection attempts
        malicious_specs = [
            "1; DROP TABLE users",
            "1-3$(echo malicious)",
            "1-3`whoami`",
            "1-3; rm -rf /",
            "../../../etc/passwd",
        ]

        # Use valid base64 content (doesn't need to be valid PDF for this test)
        dummy_content = base64.b64encode(b"dummy PDF content").decode("ascii")

        for malicious_spec in malicious_specs:
            input_data = ReadDocumentAsMarkdownInput(source=dummy_content, format_hint="pdf", pdf_pages=malicious_spec)

            with pytest.raises(ValueError, match="Invalid page range format"):
                read_document_as_markdown_impl(input_data, config)

    def test_pdf_pages_option(self, tmp_path):
        """Test PDF page specification option."""
        from all2md.mcp.security import prepare_allowlist_dirs

        # This would require a real PDF file, so we'll mock it
        config = MCPConfig(read_allowlist=prepare_allowlist_dirs([str(tmp_path)]))

        # Create a dummy PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\ntest content")

        input_data = ReadDocumentAsMarkdownInput(source=str(test_file), format_hint="pdf", pdf_pages="1-3")

        # This will fail without actual PDF parsing, but tests the parameter passing
        with pytest.raises(All2MdError):
            read_document_as_markdown_impl(input_data, config)

    def test_server_level_flavor(self):
        """Test that server-level flavor is used."""
        config = MCPConfig(flavor="commonmark")

        input_data = ReadDocumentAsMarkdownInput(source="# Test\n\nContent", format_hint="markdown")

        result = read_document_as_markdown_impl(input_data, config)

        # Verify - result is now a list [markdown_str, ...images]
        assert isinstance(result, list)
        assert len(result) >= 1
        markdown = result[0]
        assert isinstance(markdown, str)

    def test_invalid_format_hint_rejected(self):
        """Test that invalid format_hint values are rejected (security fix)."""
        config = MCPConfig()

        # Test with invalid format_hint
        input_data = ReadDocumentAsMarkdownInput(
            source="<h1>Test</h1>",
            format_hint="invalid_format_xyz",  # type: ignore[arg-type]
        )

        with pytest.raises(ValueError, match="Invalid format_hint"):
            read_document_as_markdown_impl(input_data, config)

    def test_valid_format_hint_accepted(self):
        """Test that valid format_hint values are accepted."""
        config = MCPConfig()

        # Test with valid format_hint
        input_data = ReadDocumentAsMarkdownInput(source="<h1>Test</h1>", format_hint="html")

        result = read_document_as_markdown_impl(input_data, config)

        # Verify - result is now a list [markdown_str, ...images]
        assert isinstance(result, list)
        assert len(result) >= 1
        markdown = result[0]
        assert isinstance(markdown, str)
        assert "Test" in markdown


class TestSaveDocumentFromMarkdownImpl:
    """Tests for save_document_from_markdown_impl function."""

    def test_save_to_html(self, tmp_path):
        """Test saving markdown to HTML file."""
        from all2md.mcp.security import prepare_allowlist_dirs

        output_file = tmp_path / "output.html"

        config = MCPConfig(write_allowlist=prepare_allowlist_dirs([str(tmp_path)]))

        input_data = SaveDocumentFromMarkdownInput(
            format="html", source="# Test Output\n\nSome content", filename=str(output_file)
        )

        result = save_document_from_markdown_impl(input_data, config)

        assert result.output_path == str(output_file)
        assert output_file.exists()
        content = output_file.read_text()
        assert "Test Output" in content

    def test_save_to_pdf(self, tmp_path):
        """Test saving markdown to PDF file."""
        from all2md.mcp.security import prepare_allowlist_dirs

        output_file = tmp_path / "output.pdf"

        config = MCPConfig(write_allowlist=prepare_allowlist_dirs([str(tmp_path)]))

        input_data = SaveDocumentFromMarkdownInput(
            format="pdf", source="# Test PDF\n\nContent", filename=str(output_file)
        )

        result = save_document_from_markdown_impl(input_data, config)

        assert result.output_path == str(output_file)
        assert output_file.exists()

    def test_server_level_flavor_used(self, tmp_path):
        """Test that server-level flavor is used."""
        from all2md.mcp.security import prepare_allowlist_dirs

        output_file = tmp_path / "output.html"

        config = MCPConfig(write_allowlist=prepare_allowlist_dirs([str(tmp_path)]), flavor="commonmark")

        input_data = SaveDocumentFromMarkdownInput(format="html", source="# Test\n\nContent", filename=str(output_file))

        result = save_document_from_markdown_impl(input_data, config)

        assert result.output_path == str(output_file)
        assert output_file.exists()


class TestToolsErrorHandling:
    """Tests for error handling in tool implementations."""

    def test_read_catches_all2md_errors(self):
        """Test that conversion errors are properly caught and re-raised."""
        config = MCPConfig()

        # Intentionally malformed input to trigger error
        input_data = ReadDocumentAsMarkdownInput(
            source="not-a-valid-document",
            format_hint="pdf",  # Can't parse random text as PDF
        )

        with pytest.raises(All2MdError):
            read_document_as_markdown_impl(input_data, config)

    def test_save_catches_all2md_errors(self, tmp_path):
        """Test that rendering errors are properly caught and re-raised."""
        from all2md.mcp.security import prepare_allowlist_dirs

        config = MCPConfig(write_allowlist=prepare_allowlist_dirs([str(tmp_path)]))

        output_file = tmp_path / "output.invalid"

        # Invalid format for rendering
        input_data = SaveDocumentFromMarkdownInput(
            format="invalid_format",
            source="# Test",
            filename=str(output_file),  # type: ignore[arg-type]
        )

        with pytest.raises(All2MdError):
            save_document_from_markdown_impl(input_data, config)


class TestBase64DetectionHeuristics:
    """Tests for base64 detection heuristics (security fix for Issue #3)."""

    def test_plain_text_not_misidentified_as_base64(self):
        """Test that plain text is not misidentified as base64 (security fix)."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Plain text that only contains base64 characters (like a password)
        # Should NOT be detected as base64
        plain_texts = [
            "AAAAAABBBBBBCCCCCCDDDDDD",  # Only A-D chars
            "HelloWorld",  # Short text
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",  # Alphabet
        ]

        for text in plain_texts:
            source, detection_type = _detect_source_type(text, config)
            # Should be detected as plain_text, not base64
            assert detection_type == "plain_text", f"Text '{text}' was incorrectly detected as {detection_type}"

    def test_valid_base64_detected_correctly(self):
        """Test that valid base64 is still detected correctly."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Create valid base64 with sufficient length and diversity
        # Base64 encode a meaningful amount of data (>50 bytes decoded)
        original_data = b"This is test data " * 10  # Will be >50 bytes
        base64_str = base64.b64encode(original_data).decode("ascii")

        source, detection_type = _detect_source_type(base64_str, config)

        # Should be detected as base64
        assert detection_type == "base64"
        assert isinstance(source, bytes)
        assert source == original_data

    def test_short_base64_rejected(self):
        """Test that short base64 is rejected (likely not a file)."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Base64 that decodes to <50 bytes (minimum threshold)
        short_data = b"short"  # Only 5 bytes
        base64_str = base64.b64encode(short_data).decode("ascii")

        source, detection_type = _detect_source_type(base64_str, config)

        # Should NOT be detected as base64 (too short)
        assert detection_type == "plain_text"

    def test_low_entropy_base64_rejected(self):
        """Test that low entropy base64 is rejected (e.g., AAAABBBB...)."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Create base64 with low character diversity (repeated chars)
        # Even if it's long enough, it should be rejected for low entropy
        low_entropy = "A" * 200  # Long but only one unique char

        source, detection_type = _detect_source_type(low_entropy, config)

        # Should NOT be detected as base64 (insufficient diversity)
        assert detection_type == "plain_text"

    def test_malformed_base64_rejected(self):
        """Test that malformed base64 is rejected."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Base64 with invalid length (not multiple of 4)
        malformed = "SGVsbG8gV29ybGQ"  # Missing padding, length not multiple of 4

        source, detection_type = _detect_source_type(malformed, config)

        # Should NOT be detected as base64 (malformed)
        assert detection_type == "plain_text"

    def test_data_uri_still_works(self):
        """Test that data URI detection still works (not affected by base64 changes)."""
        from all2md.mcp.tools import _detect_source_type

        config = MCPConfig()

        # Data URI with base64
        html_data = b"<h1>Test</h1>"
        base64_data = base64.b64encode(html_data).decode("ascii")
        data_uri = f"data:text/html;base64,{base64_data}"

        source, detection_type = _detect_source_type(data_uri, config)

        # Should be detected as data_uri
        assert detection_type == "data_uri"
        assert isinstance(source, bytes)
        assert source == html_data
