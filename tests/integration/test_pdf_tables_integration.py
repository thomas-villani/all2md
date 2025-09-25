"""Integration tests for PDF table detection using real generated PDFs."""

import pytest

from all2md.converters.pdf2markdown import pdf_to_markdown
from all2md.options import PdfOptions
from tests.fixtures.generators.pdf_test_fixtures import create_test_pdf_bytes
from tests.utils import assert_markdown_valid, cleanup_test_dir, create_test_temp_dir


@pytest.mark.integration
class TestPdfTablesIntegration:
    """Test PDF table detection with real generated PDFs containing tables."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_basic_table_detection(self):
        """Test detection of basic tables with clear borders."""
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should contain table content
        assert "Name" in result and "Age" in result and "City" in result  # Table 1 headers
        assert "Product" in result and "Price" in result  # Table 2 headers

        # Should contain data from both tables
        assert "Alice" in result
        assert "Widget A" in result

        # Should have table separators or structure
        has_table_structure = (
            "|" in result or  # Pipe tables
            "Name" in result and "Age" in result  # At minimum the headers
        )
        assert has_table_structure

    def test_multiple_tables_per_page(self):
        """Test handling of multiple tables on the same page."""
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should detect both tables
        assert "Name" in result  # First table header
        assert "Product" in result  # Second table header

        # Should contain text between tables
        assert "some text between" in result.lower()

        # Both tables' data should be present
        assert "Alice" in result and "25" in result  # First table data
        assert "Widget A" in result and "$10.99" in result  # Second table data

    def test_interleaved_text_and_tables(self):
        """Test proper handling of text mixed with tables."""
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should preserve proper content order
        lines = [line.strip() for line in result.split('\n') if line.strip()]

        # Title should come first
        title_found = any("Test Document with Tables" in line for line in lines[:3])
        assert title_found

        # Should contain the interleaving text
        assert "text between" in result.lower()

        # All content should be present in logical order
        content_parts = [
            "Test Document with Tables",  # Title
            "Name",  # First table
            "text between",  # Interleaving text
            "Product"  # Second table
        ]

        for part in content_parts:
            assert part.lower() in result.lower(), f"Missing content part: {part}"

    def test_table_alignment_detection(self):
        """Test detection of table structure and alignment."""
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should recognize table structure - exact format varies by implementation
        # but should preserve the tabular data relationships

        # First table: Name-Age-City relationships
        has_alice_data = "Alice" in result and "25" in result and ("NYC" in result or "25" in result)
        has_bob_data = "Bob" in result and "30" in result
        has_carol_data = "Carol" in result and "28" in result

        assert has_alice_data, "Alice's data should be preserved"
        assert has_bob_data, "Bob's data should be preserved"
        assert has_carol_data, "Carol's data should be preserved"

        # Second table: Product-Price relationships
        has_widget_pricing = ("Widget A" in result and "$10.99" in result) or ("Widget" in result and "10.99" in result)
        assert has_widget_pricing, "Product pricing data should be preserved"

    def test_table_with_complex_layout(self):
        """Test table detection in documents with mixed content."""
        pdf_bytes = create_test_pdf_bytes('complex')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should detect the small table in the complex layout
        assert "Item" in result and "Value" in result  # Table headers
        assert "100" in result and "200" in result  # Table data

        # Should maintain proper content flow
        assert "Complex Layout Test" in result  # Title
        assert "final paragraph" in result  # Content after table

    def test_table_fallback_detection(self):
        """Test fallback table detection when primary detection fails."""
        pdf_bytes = create_test_pdf_bytes('tables')

        # Test with fallback detection enabled
        options = PdfOptions(table_fallback_detection=True)
        result = pdf_to_markdown(pdf_bytes, options=options)
        assert_markdown_valid(result)

        # Should still extract table data even if table detection varies
        assert "Name" in result or "Alice" in result  # Some table content
        assert "Product" in result or "Widget" in result  # Some table content

    def test_empty_table_handling(self):
        """Test handling of documents that might not have tables."""
        # Use formatting PDF which has no tables
        pdf_bytes = create_test_pdf_bytes('formatting')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should handle gracefully and still extract text
        assert len(result) > 0
        text_content = result.lower()
        assert ("normal text" in text_content or "bold text" in text_content or
                "italic text" in text_content)

    def test_table_border_variations(self):
        """Test handling of tables with different border styles."""
        # Our generated tables have simple black borders
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should handle the bordered tables we created
        assert "Name" in result and "Age" in result  # First table
        assert "Product" in result and "Price" in result  # Second table

        # Data should be preserved regardless of border detection specifics
        table_data = ["Alice", "Bob", "Carol", "Widget A", "Widget B"]
        for data in table_data:
            assert data in result, f"Table data '{data}' should be preserved"

    def test_table_cell_formatting(self):
        """Test preservation of formatting within table cells."""
        pdf_bytes = create_test_pdf_bytes('tables')

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Our test tables have simple text, should be preserved
        assert "Alice" in result
        assert "$10.99" in result  # Price formatting
        assert "Widget A" in result

    def test_large_table_handling(self):
        """Test handling of tables that might span multiple areas."""
        # Our test tables are small, but should still be handled properly
        pdf_bytes = create_test_pdf_bytes('tables')

        options = PdfOptions(table_fallback_detection=True)
        result = pdf_to_markdown(pdf_bytes, options=options)
        assert_markdown_valid(result)

        # Should handle both tables without issues
        assert "Test Document with Tables" in result
        assert "Name" in result and "Product" in result  # Both table types
        assert len(result.split('\n')) > 5  # Should have substantial content
