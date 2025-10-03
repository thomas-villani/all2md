"""Advanced tests for HTML table handling edge cases."""

import pytest

from all2md import HtmlOptions
from all2md import to_markdown as html_to_markdown
from tests.utils import assert_markdown_valid


@pytest.mark.integration
class TestHtmlTablesAdvanced:
    """Test complex table scenarios in HTML documents."""

    def test_table_with_thead_tbody_tfoot(self):
        """Test tables with proper thead, tbody, and tfoot sections."""
        html = '''
        <table>
            <caption>Quarterly Sales Data</caption>
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Q1</th>
                    <th>Q2</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Widget A</td>
                    <td>100</td>
                    <td>150</td>
                    <td>250</td>
                </tr>
                <tr>
                    <td>Widget B</td>
                    <td>75</td>
                    <td>125</td>
                    <td>200</td>
                </tr>
            </tbody>
            <tfoot>
                <tr>
                    <td><strong>Total</strong></td>
                    <td>175</td>
                    <td>275</td>
                    <td><strong>450</strong></td>
                </tr>
            </tfoot>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should include caption
        assert "*Quarterly Sales Data*" in markdown

        # Should maintain table structure
        assert "| Product | Q1 | Q2 | Total |" in markdown
        assert "| Widget A | 100 | 150 | 250 |" in markdown
        assert "| Widget B | 75 | 125 | 200 |" in markdown

        # Should include footer content
        assert "**Total**" in markdown
        assert "450" in markdown

    def test_table_with_rowspan_colspan(self):
        """Test tables with rowspan and colspan attributes."""
        html = '''
        <table border="1">
            <tr>
                <th rowspan="2">Category</th>
                <th colspan="2">Values</th>
                <th rowspan="2">Notes</th>
            </tr>
            <tr>
                <th>Min</th>
                <th>Max</th>
            </tr>
            <tr>
                <td rowspan="2">Group A</td>
                <td>1</td>
                <td>10</td>
                <td>Range data</td>
            </tr>
            <tr>
                <td colspan="2">Average: 5.5</td>
                <td>Calculated</td>
            </tr>
            <tr>
                <td>Group B</td>
                <td>5</td>
                <td>15</td>
                <td>More data</td>
            </tr>
        </table>
        '''
        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle spanning cells reasonably
        assert "Category" in markdown
        assert "Values" in markdown
        assert "Min" in markdown
        assert "Max" in markdown
        assert "Group A" in markdown
        assert "Group B" in markdown
        assert "Average: 5.5" in markdown

    def test_table_alignment_detection(self):
        """Test automatic detection of table column alignment."""
        html = '''
        <table>
            <tr>
                <th align="left">Left Column</th>
                <th align="center">Center Column</th>
                <th align="right">Right Column</th>
                <th style="text-align: justify">Justify Column</th>
            </tr>
            <tr>
                <td style="text-align: left">Left text</td>
                <td style="text-align: center">Center text</td>
                <td style="text-align: right">Right text</td>
                <td>Justify text</td>
            </tr>
            <tr>
                <td align="left">More left</td>
                <td align="center">More center</td>
                <td align="right">More right</td>
                <td>More justify</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html", parser_options=HtmlOptions(detect_table_alignment=True))
        assert_markdown_valid(markdown)

        # Should detect and apply alignment
        assert "|:---|" in markdown or "| --- |" in markdown  # Left alignment
        assert "|:---:|" in markdown  # Center alignment
        assert "|---:|" in markdown  # Right alignment

        # Should contain content
        assert "Left Column" in markdown
        assert "Center Column" in markdown
        assert "Right Column" in markdown
        assert "Left text" in markdown

    def test_nested_content_in_table_cells(self):
        """Test table cells containing complex nested content."""
        html = '''
        <table>
            <tr>
                <th>Simple</th>
                <th>Formatted</th>
                <th>Complex</th>
            </tr>
            <tr>
                <td>Plain text</td>
                <td><strong>Bold</strong> and <em>italic</em></td>
                <td>
                    <ul>
                        <li>List item 1</li>
                        <li>List item 2</li>
                    </ul>
                </td>
            </tr>
            <tr>
                <td><code>inline code</code></td>
                <td>
                    <a href="http://example.com">Link text</a>
                </td>
                <td>
                    <p>Multiple paragraphs</p>
                    <p>In single cell</p>
                </td>
            </tr>
            <tr>
                <td colspan="3">
                    <blockquote>
                        <p>Quote spanning entire row</p>
                    </blockquote>
                </td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should preserve formatting in cells
        assert "**Bold**" in markdown
        assert "*italic*" in markdown
        assert "`inline code`" in markdown
        assert "[Link text]" in markdown

        # Complex content might be simplified or preserved
        assert "List item 1" in markdown
        assert "Multiple paragraphs" in markdown
        assert "Quote spanning" in markdown

    def test_table_with_no_headers(self):
        """Test tables without explicit header rows."""
        html = '''
        <table>
            <tr>
                <td>Data A1</td>
                <td>Data B1</td>
                <td>Data C1</td>
            </tr>
            <tr>
                <td>Data A2</td>
                <td>Data B2</td>
                <td>Data C2</td>
            </tr>
            <tr>
                <td>Data A3</td>
                <td>Data B3</td>
                <td>Data C3</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should still generate valid table (first row becomes header)
        assert "| Data A1 | Data B1 | Data C1 |" in markdown
        assert "| Data A2 | Data B2 | Data C2 |" in markdown
        # Check for separator row (with or without spaces)
        assert "|---|---|---|" in markdown or "| --- | --- | --- |" in markdown or "|:---:|:---:|:---:|" in markdown

    def test_empty_and_sparse_tables(self):
        """Test tables with empty cells and sparse data."""
        html = '''
        <table>
            <tr>
                <th>Column 1</th>
                <th></th>
                <th>Column 3</th>
            </tr>
            <tr>
                <td>Data</td>
                <td></td>
                <td></td>
            </tr>
            <tr>
                <td></td>
                <td>   </td>
                <td>More data</td>
            </tr>
            <tr>
                <td colspan="3"></td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle empty cells gracefully
        assert "Column 1" in markdown
        assert "Column 3" in markdown
        assert "Data" in markdown
        assert "More data" in markdown

        # Check table structure is maintained
        lines = markdown.split('\n')
        table_lines = [line for line in lines if '|' in line and line.strip()]
        assert len(table_lines) >= 3  # At least header, separator, and data rows

    def test_table_with_multiple_header_rows(self):
        """Test tables with multiple header rows."""
        html = '''
        <table>
            <thead>
                <tr>
                    <th colspan="2">Group 1</th>
                    <th colspan="2">Group 2</th>
                </tr>
                <tr>
                    <th>Sub A</th>
                    <th>Sub B</th>
                    <th>Sub C</th>
                    <th>Sub D</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Data 1</td>
                    <td>Data 2</td>
                    <td>Data 3</td>
                    <td>Data 4</td>
                </tr>
                <tr>
                    <td>More 1</td>
                    <td>More 2</td>
                    <td>More 3</td>
                    <td>More 4</td>
                </tr>
            </tbody>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle multiple header rows
        assert "Group 1" in markdown
        assert "Group 2" in markdown
        assert "Sub A" in markdown
        assert "Sub B" in markdown
        assert "Data 1" in markdown
        assert "More 1" in markdown

    def test_table_with_mixed_cell_types(self):
        """Test tables mixing th and td elements."""
        html = '''
        <table>
            <tr>
                <th>Header 1</th>
                <th>Header 2</th>
                <th>Header 3</th>
            </tr>
            <tr>
                <th>Row Header</th>
                <td>Data 1</td>
                <td>Data 2</td>
            </tr>
            <tr>
                <td>Normal</td>
                <th>Mid Header</th>
                <td>Data 3</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle mixed th/td elements
        assert "Header 1" in markdown
        assert "Row Header" in markdown
        assert "Mid Header" in markdown
        assert "Data 1" in markdown
        assert "Data 3" in markdown

    def test_table_with_css_styling_classes(self):
        """Test tables with CSS classes and styling."""
        html = '''
        <table class="styled-table">
            <tr class="header-row">
                <th class="name-col">Name</th>
                <th class="number-col">Number</th>
                <th class="status-col">Status</th>
            </tr>
            <tr class="data-row even">
                <td class="name-col">Item A</td>
                <td class="number-col">123</td>
                <td class="status-col active">Active</td>
            </tr>
            <tr class="data-row odd">
                <td class="name-col">Item B</td>
                <td class="number-col">456</td>
                <td class="status-col inactive">Inactive</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should ignore CSS classes but preserve content
        assert "| Name | Number | Status |" in markdown
        assert "| Item A | 123 | Active |" in markdown
        assert "| Item B | 456 | Inactive |" in markdown

    def test_malformed_table_structures(self):
        """Test handling of malformed or inconsistent table structures."""
        html = '''
        <table>
            <tr>
                <th>Col 1</th>
                <th>Col 2</th>
                <th>Col 3</th>
            </tr>
            <tr>
                <td>Data 1</td>
                <td>Data 2</td>
                <!-- Missing third cell -->
            </tr>
            <tr>
                <td>Extra 1</td>
                <td>Extra 2</td>
                <td>Extra 3</td>
                <td>Extra 4</td>
                <!-- Extra cell -->
            </tr>
            <tr>
                <td>Just one cell</td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle malformed structure gracefully
        assert "Col 1" in markdown
        assert "Data 1" in markdown
        assert "Extra 1" in markdown
        assert "Just one cell" in markdown

    def test_table_with_block_level_content(self):
        """Test table cells containing block-level elements."""
        html = '''
        <table>
            <tr>
                <th>Content Type</th>
                <th>Example</th>
            </tr>
            <tr>
                <td>Paragraph</td>
                <td>
                    <p>This is a paragraph in a table cell.</p>
                    <p>Multiple paragraphs are possible.</p>
                </td>
            </tr>
            <tr>
                <td>Code Block</td>
                <td>
                    <pre><code>function example() {
    return "code in table";
}</code></pre>
                </td>
            </tr>
            <tr>
                <td>Nested Table</td>
                <td>
                    <table>
                        <tr><td>Nested</td><td>Table</td></tr>
                        <tr><td>Row 2</td><td>Data</td></tr>
                    </table>
                </td>
            </tr>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should handle block content in cells
        assert "Content Type" in markdown
        assert "paragraph in a table" in markdown
        assert "Multiple paragraphs" in markdown
        assert "function example" in markdown
        assert "Nested" in markdown
        assert "Table" in markdown

    def test_table_accessibility_features(self):
        """Test tables with accessibility features."""
        html = '''
        <table summary="Sales data for Q1-Q2">
            <caption>Quarterly Sales by Product</caption>
            <thead>
                <tr>
                    <th scope="col" id="product">Product</th>
                    <th scope="col" id="q1">Q1 Sales</th>
                    <th scope="col" id="q2">Q2 Sales</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <th scope="row" headers="product">Widget</th>
                    <td headers="product q1">100</td>
                    <td headers="product q2">150</td>
                </tr>
                <tr>
                    <th scope="row" headers="product">Gadget</th>
                    <td headers="product q1">75</td>
                    <td headers="product q2">125</td>
                </tr>
            </tbody>
        </table>
        '''

        markdown = html_to_markdown(html, format="html")
        assert_markdown_valid(markdown)

        # Should preserve content while ignoring accessibility attributes
        assert "*Quarterly Sales by Product*" in markdown
        assert "| Product | Q1 Sales | Q2 Sales |" in markdown
        assert "| Widget | 100 | 150 |" in markdown
        assert "| Gadget | 75 | 125 |" in markdown
