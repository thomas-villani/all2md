"""Unit tests for HTML table parsing and conversion.

These tests focus on the core table parsing logic in HTML-to-Markdown conversion.
They use fixture-based testing instead of inline HTML for better maintainability.
"""

import pytest

from all2md import to_markdown as html_to_markdown
from fixtures.generators.html_fixtures import create_html_with_tables
from utils import assert_markdown_valid


@pytest.mark.unit
class TestHtmlTableParsing:
    """Unit tests for HTML table structure parsing."""

    def test_basic_table_structure_parsing(self):
        """Test parsing of basic table with thead, tbody structure."""
        html_content = create_html_with_tables()
        markdown = html_to_markdown(html_content, source_format="html")

        assert_markdown_valid(markdown)
        # Should contain table headers
        assert "| Name | Age | City |" in markdown
        # Should contain table data
        assert "| Alice Johnson | 25 | New York |" in markdown

    def test_table_with_caption_parsing(self):
        """Test table caption detection and conversion."""
        html = """
        <table>
            <caption>Test Table Caption</caption>
            <tr>
                <th>Header 1</th>
                <th>Header 2</th>
            </tr>
            <tr>
                <td>Data 1</td>
                <td>Data 2</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)
        assert "Test Table Caption" in markdown

    def test_table_header_detection(self):
        """Test proper detection of table headers vs data cells."""
        html = """
        <table>
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Price</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Widget</td>
                    <td>$10</td>
                </tr>
            </tbody>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should have header separator (various formats possible)
        assert "|:" in markdown or "|--" in markdown or "|---" in markdown
        assert "| Product | Price |" in markdown
        assert "| Widget | $10 |" in markdown

    def test_table_without_headers(self):
        """Test table parsing when no explicit headers are present."""
        html = """
        <table>
            <tr>
                <td>Data 1</td>
                <td>Data 2</td>
            </tr>
            <tr>
                <td>Data 3</td>
                <td>Data 4</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should still create table structure
        assert "| Data 1 | Data 2 |" in markdown
        assert "| Data 3 | Data 4 |" in markdown

    def test_empty_table_cells(self):
        """Test handling of empty table cells."""
        html = """
        <table>
            <tr>
                <th>A</th>
                <th>B</th>
                <th>C</th>
            </tr>
            <tr>
                <td>Value</td>
                <td></td>
                <td>Another Value</td>
            </tr>
            <tr>
                <td></td>
                <td>Middle</td>
                <td></td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle empty cells gracefully
        assert "| Value |  | Another Value |" in markdown
        assert "|  | Middle |  |" in markdown

    def test_table_cell_whitespace_normalization(self):
        """Test normalization of whitespace in table cells."""
        html = """
        <table>
            <tr>
                <th>  Header with spaces  </th>
                <th>Normal</th>
            </tr>
            <tr>
                <td>
                    Multi-line
                    content
                </td>
                <td>   Padded   </td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Whitespace should be normalized
        assert "Header with spaces" in markdown
        assert "Multi-line" in markdown and "content" in markdown
        assert "Padded" in markdown


@pytest.mark.unit
class TestHtmlTableFormatting:
    """Unit tests for table cell formatting and content handling."""

    def test_formatted_text_in_table_cells(self):
        """Test preservation of text formatting within table cells."""
        html = """
        <table>
            <tr>
                <th><strong>Bold Header</strong></th>
                <th><em>Italic Header</em></th>
            </tr>
            <tr>
                <td>Text with <strong>bold</strong> word</td>
                <td>Text with <em>italic</em> word</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should preserve formatting in cells
        assert "**Bold Header**" in markdown
        assert "*Italic Header*" in markdown
        assert "**bold**" in markdown
        assert "*italic*" in markdown

    def test_links_in_table_cells(self):
        """Test handling of links within table cells."""
        html = """
        <table>
            <tr>
                <th>Site</th>
                <th>URL</th>
            </tr>
            <tr>
                <td><a href="https://example.com">Example</a></td>
                <td>https://example.com</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should convert links properly in table cells
        assert "[Example](https://example.com)" in markdown

    def test_code_in_table_cells(self):
        """Test handling of code elements within table cells."""
        html = """
        <table>
            <tr>
                <th>Function</th>
                <th>Usage</th>
            </tr>
            <tr>
                <td><code>print()</code></td>
                <td>Use <code>print("hello")</code> for output</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should preserve code formatting in cells
        assert "`print()`" in markdown
        assert '`print("hello")`' in markdown


@pytest.mark.unit
class TestHtmlTableEdgeCases:
    """Unit tests for edge cases in HTML table parsing."""

    def test_malformed_table_structure(self):
        """Test handling of malformed table HTML."""
        html = """
        <table>
            <tr>
                <th>Header 1</th>
                <th>Header 2
            </tr>
            <tr>
                <td>Data 1</td>
                <td>Data 2</td>
                <td>Extra cell</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")

        # Should not crash and should produce some output
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_deeply_nested_table_content(self):
        """Test table cells with deeply nested HTML content."""
        html = """
        <table>
            <tr>
                <th>Nested Content</th>
            </tr>
            <tr>
                <td>
                    <div>
                        <p>Paragraph with <span><strong>nested bold</strong></span></p>
                        <ul>
                            <li>List item</li>
                        </ul>
                    </div>
                </td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle nested content appropriately
        assert "**nested bold**" in markdown
        assert "List item" in markdown

    def test_table_with_special_characters(self):
        """Test table cells containing special characters."""
        html = """
        <table>
            <tr>
                <th>Special Chars</th>
                <th>Values</th>
            </tr>
            <tr>
                <td>&amp; &lt; &gt;</td>
                <td>Pipe | character</td>
            </tr>
            <tr>
                <td>Unicode: ñ, é, ü</td>
                <td>Math: ≥ ≤ ≠</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle entities and special chars
        assert "& < >" in markdown
        assert "Unicode: ñ, é, ü" in markdown

    def test_table_with_multiline_cell_content(self):
        """Test handling of multiline content in table cells."""
        html = """
        <table>
            <tr>
                <th>Description</th>
            </tr>
            <tr>
                <td>Line 1<br>Line 2<br>Line 3</td>
            </tr>
        </table>
        """
        markdown = html_to_markdown(html, source_format="html")
        assert_markdown_valid(markdown)

        # Should handle line breaks appropriately
        assert "Line 1" in markdown
        assert "Line 2" in markdown
        assert "Line 3" in markdown
