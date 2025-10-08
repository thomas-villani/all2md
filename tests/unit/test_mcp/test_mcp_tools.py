"""Unit tests for MCP tool implementations."""

import base64

import pytest

from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import ConvertToMarkdownInput, RenderFromMarkdownInput
from all2md.mcp.tools import convert_to_markdown_impl, render_from_markdown_impl


class TestConvertToMarkdownImpl:
    """Tests for convert_to_markdown_impl function."""

    def test_convert_from_file_path(self, tmp_path):
        """Test converting from a file path."""
        from all2md.mcp.security import prepare_allowlist_dirs

        # Create test file
        test_file = tmp_path / "test.html"
        test_file.write_text("<h1>Hello World</h1>")

        # Create config with validated allowlists
        config = MCPConfig(
            read_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)])
        )

        # Create input
        input_data = ConvertToMarkdownInput(
            source_path=str(test_file),
            source_format="html"
        )

        # Execute
        result = convert_to_markdown_impl(input_data, config)

        # Verify
        assert result.markdown is not None
        assert "Hello World" in result.markdown
        assert isinstance(result.attachments, list)
        assert isinstance(result.warnings, list)

    def test_convert_from_plain_text_content(self):
        """Test converting from plain text content."""
        config = MCPConfig()

        input_data = ConvertToMarkdownInput(
            source_content="<h1>Test</h1><p>Content</p>",
            content_encoding="plain",
            source_format="html"
        )

        result = convert_to_markdown_impl(input_data, config)

        assert result.markdown is not None
        assert "Test" in result.markdown
        assert "Content" in result.markdown

    def test_convert_from_base64_content(self):
        """Test converting from base64-encoded content."""
        config = MCPConfig()

        # Create base64-encoded HTML
        html_content = b"<h1>Base64 Test</h1>"
        base64_content = base64.b64encode(html_content).decode('ascii')

        input_data = ConvertToMarkdownInput(
            source_content=base64_content,
            content_encoding="base64",
            source_format="html"
        )

        result = convert_to_markdown_impl(input_data, config)

        assert result.markdown is not None
        assert "Base64 Test" in result.markdown

    def test_mutually_exclusive_sources_error(self):
        """Test that providing both source_path and source_content raises error."""
        config = MCPConfig()

        input_data = ConvertToMarkdownInput(
            source_path="/some/path.html",
            source_content="<h1>Test</h1>"
        )

        with pytest.raises(ValueError, match="Cannot specify both"):
            convert_to_markdown_impl(input_data, config)

    def test_no_source_provided_error(self):
        """Test that providing neither source raises error."""
        config = MCPConfig()

        input_data = ConvertToMarkdownInput()

        with pytest.raises(ValueError, match="Must specify either"):
            convert_to_markdown_impl(input_data, config)

    def test_invalid_base64_encoding(self):
        """Test that invalid base64 content raises error."""
        config = MCPConfig()

        input_data = ConvertToMarkdownInput(
            source_content="not-valid-base64!!!",
            content_encoding="base64",
            source_format="html"
        )

        with pytest.raises(ValueError, match="Invalid base64 encoding"):
            convert_to_markdown_impl(input_data, config)

    def test_pdf_pages_option(self, tmp_path):
        """Test PDF page specification option."""
        # This would require a real PDF file, so we'll mock it
        config = MCPConfig(
            read_allowlist=[str(tmp_path)]
        )

        # Create a dummy PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4\ntest content")

        input_data = ConvertToMarkdownInput(
            source_path=str(test_file),
            source_format="pdf",
            pdf_pages="1-3"
        )

        # This will fail without actual PDF parsing, but tests the parameter passing
        with pytest.raises(All2MdError):
            convert_to_markdown_impl(input_data, config)

    def test_markdown_flavor_option(self):
        """Test markdown flavor option."""
        config = MCPConfig()

        input_data = ConvertToMarkdownInput(
            source_content="# Test\n\nContent",
            source_format="markdown",
            flavor="commonmark"
        )

        result = convert_to_markdown_impl(input_data, config)

        assert result.markdown is not None


class TestRenderFromMarkdownImpl:
    """Tests for render_from_markdown_impl function."""

    def test_render_from_markdown_string(self):
        """Test rendering from markdown string."""
        config = MCPConfig()

        input_data = RenderFromMarkdownInput(
            markdown="# Test\n\nSome content",
            target_format="html"
        )

        result = render_from_markdown_impl(input_data, config)

        assert result.content is not None
        assert "Test" in result.content
        assert result.output_path is None

    def test_render_from_markdown_file(self, tmp_path):
        """Test rendering from markdown file."""
        from all2md.mcp.security import prepare_allowlist_dirs

        # Create test markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nWorld")

        config = MCPConfig(
            read_allowlist=prepare_allowlist_dirs([str(tmp_path)])
        )

        input_data = RenderFromMarkdownInput(
            markdown_path=str(md_file),
            target_format="html"
        )

        result = render_from_markdown_impl(input_data, config)

        assert result.content is not None
        assert "Hello" in result.content

    def test_render_to_output_file(self, tmp_path):
        """Test rendering to output file."""
        from all2md.mcp.security import prepare_allowlist_dirs

        output_file = tmp_path / "output.html"

        config = MCPConfig(
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)])
        )

        input_data = RenderFromMarkdownInput(
            markdown="# Test Output",
            target_format="html",
            output_path=str(output_file)
        )

        result = render_from_markdown_impl(input_data, config)

        assert result.output_path == str(output_file)
        assert result.content is None
        assert output_file.exists()

    def test_mutually_exclusive_markdown_sources(self):
        """Test that providing both markdown and markdown_path raises error."""
        config = MCPConfig()

        input_data = RenderFromMarkdownInput(
            markdown="# Test",
            markdown_path="/some/path.md",
            target_format="html"
        )

        with pytest.raises(ValueError, match="Cannot specify both"):
            render_from_markdown_impl(input_data, config)

    def test_no_markdown_source_provided(self):
        """Test that providing neither markdown source raises error."""
        config = MCPConfig()

        input_data = RenderFromMarkdownInput(
            target_format="html"
        )

        with pytest.raises(ValueError, match="Must specify either"):
            render_from_markdown_impl(input_data, config)

    def test_binary_format_returns_base64(self):
        """Test that binary formats return base64-encoded content when no output_path."""
        config = MCPConfig()

        input_data = RenderFromMarkdownInput(
            markdown="# Test PDF",
            target_format="pdf"
        )

        result = render_from_markdown_impl(input_data, config)

        # Content should be base64-encoded for binary formats
        assert result.content is not None
        # Should be base64 (will contain warning about base64 encoding)
        assert len(result.warnings) > 0
        assert "base64" in result.warnings[0].lower()


class TestToolsErrorHandling:
    """Tests for error handling in tool implementations."""

    def test_convert_catches_all2md_errors(self):
        """Test that conversion errors are properly caught and re-raised."""
        config = MCPConfig()

        # Intentionally malformed input to trigger error
        input_data = ConvertToMarkdownInput(
            source_content="not-a-valid-document",
            source_format="pdf"  # Can't parse random text as PDF
        )

        with pytest.raises(All2MdError):
            convert_to_markdown_impl(input_data, config)

    def test_render_catches_all2md_errors(self):
        """Test that rendering errors are properly caught and re-raised."""
        config = MCPConfig()

        # Invalid markdown for rendering
        input_data = RenderFromMarkdownInput(
            markdown="# Test",
            target_format="invalid_format"  # type: ignore[arg-type]
        )

        with pytest.raises(All2MdError):
            render_from_markdown_impl(input_data, config)
