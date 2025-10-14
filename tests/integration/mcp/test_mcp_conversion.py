"""Integration tests for MCP server."""

import tempfile
from pathlib import Path

import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import ReadDocumentAsMarkdownInput, SaveDocumentFromMarkdownInput
from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl


class TestMCPEndToEndWorkflow:
    """Test complete workflows through MCP server."""

    def test_html_to_markdown_workflow(self, tmp_path):
        """Test converting HTML to Markdown and back."""
        from all2md.mcp.security import prepare_allowlist_dirs

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
            read_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            include_images=False  # Use alt_text mode
        )

        # Convert HTML to Markdown (source auto-detected as file path)
        convert_input = ReadDocumentAsMarkdownInput(
            source=str(html_file)
        )

        result = read_document_as_markdown_impl(convert_input, config)

        # Result is a list [markdown_str, ...images]
        assert isinstance(result, list)
        markdown = result[0]
        assert "Test Document" in markdown
        assert "test" in markdown
        assert "Item 1" in markdown

    def test_markdown_to_html_workflow(self, tmp_path):
        """Test converting Markdown to HTML."""
        from all2md.mcp.security import prepare_allowlist_dirs

        config = MCPConfig(
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)])
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

        # Simplified API: source + format + filename (all required)
        save_input = SaveDocumentFromMarkdownInput(
            format="html",
            source=markdown_content,
            filename=str(output_file)
        )

        result = save_document_from_markdown_impl(save_input, config)

        assert result.output_path == str(output_file)
        assert output_file.exists()

        html_output = output_file.read_text()
        assert "My Document" in html_output
        assert "test" in html_output

    def test_temp_workspace_workflow(self):
        """Test workflow using temporary workspace."""
        from all2md.mcp.security import prepare_allowlist_dirs

        # Create temporary workspace
        with tempfile.TemporaryDirectory(prefix="all2md-mcp-test-") as temp_dir:
            config = MCPConfig(
                read_allowlist=prepare_allowlist_dirs([temp_dir]),
                write_allowlist=prepare_allowlist_dirs([temp_dir]),
                include_images=False
            )

            # Create test HTML file
            html_file = Path(temp_dir) / "test.html"
            html_file.write_text("<h1>Temp Test</h1><p>Content</p>")

            # Convert to markdown (source auto-detected as file path)
            convert_input = ReadDocumentAsMarkdownInput(
                source=str(html_file)
            )

            result = read_document_as_markdown_impl(convert_input, config)

            # Result is a list [markdown_str, ...images]
            assert isinstance(result, list)
            markdown = result[0]
            assert "Temp Test" in markdown

            # Save back to HTML
            output_file = Path(temp_dir) / "output.html"
            save_input = SaveDocumentFromMarkdownInput(
                format="html",
                source=markdown,
                filename=str(output_file)
            )

            save_result = save_document_from_markdown_impl(save_input, config)

            # Normalize paths for comparison (Windows can use 8.3 format vs full names)
            assert Path(save_result.output_path).resolve() == output_file.resolve()
            assert output_file.exists()

    def test_inline_content_workflow(self, tmp_path):
        """Test workflow with inline content (no files)."""
        from all2md.mcp.security import prepare_allowlist_dirs

        config = MCPConfig(
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            include_images=False
        )

        # Convert HTML string to Markdown (auto-detected as plain text)
        html_content = "<h1>Inline Test</h1><p>Some <em>content</em> here.</p>"

        convert_input = ReadDocumentAsMarkdownInput(
            source=html_content,
            format_hint="html"
        )

        result = read_document_as_markdown_impl(convert_input, config)

        # Result is a list [markdown_str, ...images]
        assert isinstance(result, list)
        markdown = result[0]
        assert "Inline Test" in markdown
        assert "content" in markdown

        # Save Markdown to HTML file (always writes to disk)
        output_file = tmp_path / "output.html"
        save_input = SaveDocumentFromMarkdownInput(
            format="html",
            source=markdown,
            filename=str(output_file)
        )

        save_result = save_document_from_markdown_impl(save_input, config)

        assert save_result.output_path == str(output_file)
        assert output_file.exists()
        html_output = output_file.read_text()
        assert "Inline Test" in html_output

    def test_security_prevents_path_traversal(self, tmp_path):
        """Test that security prevents accessing files outside allowlist."""
        from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs

        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()

        # Create file in forbidden directory
        forbidden_file = forbidden_dir / "secret.html"
        forbidden_file.write_text("<h1>Secret</h1>")

        config = MCPConfig(
            read_allowlist=prepare_allowlist_dirs([str(allowed_dir)])
        )

        # Try to access file outside allowlist (source is auto-detected as file path)
        convert_input = ReadDocumentAsMarkdownInput(
            source=str(forbidden_file)
        )

        with pytest.raises(MCPSecurityError, match="not in allowlist"):
            read_document_as_markdown_impl(convert_input, config)

    def test_different_markdown_flavors(self, tmp_path):
        """Test conversion with different markdown flavors (server-level)."""
        from all2md.mcp.security import prepare_allowlist_dirs

        markdown_content = "# Test\n\nContent with **bold** and *italic*."

        # Test GFM flavor (server-level config)
        gfm_config = MCPConfig(
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            flavor="gfm"
        )
        output_file_gfm = tmp_path / "output_gfm.html"
        gfm_input = SaveDocumentFromMarkdownInput(
            format="html",
            source=markdown_content,
            filename=str(output_file_gfm)
        )
        gfm_result = save_document_from_markdown_impl(gfm_input, gfm_config)
        assert gfm_result.output_path == str(output_file_gfm)
        assert output_file_gfm.exists()

        # Test CommonMark flavor (server-level config)
        cm_config = MCPConfig(
            write_allowlist=prepare_allowlist_dirs([str(tmp_path)]),
            flavor="commonmark"
        )
        output_file_cm = tmp_path / "output_cm.html"
        cm_input = SaveDocumentFromMarkdownInput(
            format="html",
            source=markdown_content,
            filename=str(output_file_cm)
        )
        cm_result = save_document_from_markdown_impl(cm_input, cm_config)
        assert cm_result.output_path == str(output_file_cm)
        assert output_file_cm.exists()
