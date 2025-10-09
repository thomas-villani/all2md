"""Integration tests for MCP server."""

import tempfile
from pathlib import Path

import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import ConvertToMarkdownInput, RenderFromMarkdownInput
from all2md.mcp.tools import convert_to_markdown_impl, render_from_markdown_impl


class TestMCPEndToEndWorkflow:
    """Test complete workflows through MCP server."""

    def test_html_to_markdown_workflow(self, tmp_path):
        """Test converting HTML to Markdown and back."""
        # Setup
        html_file = tmp_path / "input.html"
        html_content = """
        <html>
            <body>
                <h1>Test Document</h1>
                <p>This is a <strong>test</strong> paragraph.</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
            </body>
        </html>
        """
        html_file.write_text(html_content)

        config = MCPConfig(
            read_allowlist=[str(tmp_path)],
            write_allowlist=[str(tmp_path)],
            attachment_mode="skip"
        )

        # Convert HTML to Markdown
        convert_input = ConvertToMarkdownInput(
            source_path=str(html_file),
            source_format="html"
        )

        result = convert_to_markdown_impl(convert_input, config)

        assert "Test Document" in result[0] if isinstance(result, list) else result.markdown
        assert "test" in result[0] if isinstance(result, list) else result.markdown
        assert "Item 1" in result[0] if isinstance(result, list) else result.markdown

    def test_markdown_to_html_workflow(self, tmp_path):
        """Test converting Markdown to HTML."""
        config = MCPConfig(
            write_allowlist=[str(tmp_path)]
        )

        markdown_content = """
# My Document

This is a **test** document with:

- List item 1
- List item 2

## Section 2

More content here.
        """

        output_file = tmp_path / "output.html"

        render_input = RenderFromMarkdownInput(
            markdown=markdown_content,
            target_format="html",
            output_path=str(output_file)
        )

        result = render_from_markdown_impl(render_input, config)

        assert result.output_path == str(output_file)
        assert output_file.exists()

        html_output = output_file.read_text()
        assert "My Document" in html_output
        assert "test" in html_output

    def test_temp_workspace_workflow(self):
        """Test workflow using temporary workspace."""
        # Create temporary workspace
        with tempfile.TemporaryDirectory(prefix="all2md-mcp-test-") as temp_dir:
            config = MCPConfig(
                read_allowlist=[temp_dir],
                write_allowlist=[temp_dir],
                attachment_mode="skip"
            )

            # Create test HTML file
            html_file = Path(temp_dir) / "test.html"
            html_file.write_text("<h1>Temp Test</h1><p>Content</p>")

            # Convert to markdown
            convert_input = ConvertToMarkdownInput(
                source_path=str(html_file),
                source_format="html"
            )

            result = convert_to_markdown_impl(convert_input, config)

            assert "Temp Test" in result[0] if isinstance(result, list) else result.markdown

            # Render back to HTML
            output_file = Path(temp_dir) / "output.html"
            render_input = RenderFromMarkdownInput(
                markdown=result[0] if isinstance(result, list) else result.markdown,
                target_format="html",
                output_path=str(output_file)
            )

            render_result = render_from_markdown_impl(render_input, config)

            # Normalize paths for comparison (Windows can use 8.3 format vs full names)
            assert Path(render_result.output_path).resolve() == output_file.resolve()
            assert output_file.exists()

    def test_inline_content_workflow(self):
        """Test workflow with inline content (no files)."""
        config = MCPConfig(attachment_mode="skip")

        # Convert HTML string to Markdown
        html_content = "<h1>Inline Test</h1><p>Some <em>content</em> here.</p>"

        convert_input = ConvertToMarkdownInput(
            source_content=html_content,
            content_encoding="plain",
            source_format="html"
        )

        result = convert_to_markdown_impl(convert_input, config)

        assert "Inline Test" in result[0] if isinstance(result, list) else result.markdown
        assert "content" in result[0] if isinstance(result, list) else result.markdown

        # Render Markdown to HTML (returned as string)
        render_input = RenderFromMarkdownInput(
            markdown=result[0] if isinstance(result, list) else result.markdown,
            target_format="html"
        )

        render_result = render_from_markdown_impl(render_input, config)

        assert render_result.content is not None
        assert "Inline Test" in render_result.content

    def test_security_prevents_path_traversal(self, tmp_path):
        """Test that security prevents accessing files outside allowlist."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        # Create file in forbidden directory
        forbidden_file = forbidden_dir / "secret.html"
        forbidden_file.write_text("<h1>Secret</h1>")

        config = MCPConfig(
            read_allowlist=[str(allowed_dir)]
        )

        # Try to access file outside allowlist
        convert_input = ConvertToMarkdownInput(
            source_path=str(forbidden_file),
            source_format="html"
        )

        from all2md.mcp.security import MCPSecurityError
        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            convert_to_markdown_impl(convert_input, config)

    def test_different_markdown_flavors(self):
        """Test conversion with different markdown flavors."""
        config = MCPConfig()

        markdown_content = "# Test\n\nContent with **bold** and *italic*."

        # Test GFM flavor
        gfm_input = RenderFromMarkdownInput(
            markdown=markdown_content,
            target_format="html",
            flavor="gfm"
        )
        gfm_result = render_from_markdown_impl(gfm_input, config)
        assert gfm_result.content is not None

        # Test CommonMark flavor
        cm_input = RenderFromMarkdownInput(
            markdown=markdown_content,
            target_format="html",
            flavor="commonmark"
        )
        cm_result = render_from_markdown_impl(cm_input, config)
        assert cm_result.content is not None
