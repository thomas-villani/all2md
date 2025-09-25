"""End-to-end tests for the complete all2md conversion pipeline.

These tests verify the entire conversion process from file input to markdown output,
testing the integration of all components including format detection, parsing,
and conversion across different document types.
"""

import tempfile
from pathlib import Path
from io import BytesIO

import pytest

from all2md import to_markdown, DocumentFormat
from all2md.options import DocxOptions, HtmlOptions, PdfOptions, PptxOptions, MarkdownOptions
from tests.fixtures.generators.docx_fixtures import (
    create_docx_with_formatting,
    save_docx_to_bytes
)
from tests.fixtures.generators.html_fixtures import create_html_with_tables
from tests.fixtures.generators.pptx_fixtures import (
    create_pptx_with_basic_slides,
    save_pptx_to_bytes
)
from tests.fixtures.generators.pdf_test_fixtures import create_pdf_with_figures
from tests.utils import assert_markdown_valid


@pytest.mark.e2e
class TestFullConversionPipeline:
    """End-to-end tests for complete document conversion workflows."""

    def test_docx_to_markdown_full_pipeline(self, temp_dir):
        """Test complete DOCX to Markdown conversion pipeline."""
        # Create a DOCX document with various formatting
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        # Test conversion with different options
        options = DocxOptions(
            extract_images=True,
            table_style='grid'
        )
        markdown_options = MarkdownOptions(
            heading_style='atx',
            bullet_style='-'
        )

        # Convert to markdown
        result = to_markdown(
            docx_bytes,
            file_extension='.docx',
            docx_options=options,
            markdown_options=markdown_options
        )

        assert_markdown_valid(result.text)

        # Should contain expected content
        assert "Formatting Test Document" in result.text
        assert "**bold text**" in result.text.lower()
        assert "*italic text*" in result.text.lower()

        # Should detect format correctly
        assert result.format == DocumentFormat.DOCX

    def test_html_to_markdown_full_pipeline(self, temp_dir):
        """Test complete HTML to Markdown conversion pipeline."""
        # Create HTML content with tables
        html_content = create_html_with_tables()

        # Convert with options
        options = HtmlOptions(
            convert_tables=True,
            preserve_whitespace=False,
            skip_tags=['script', 'style']
        )
        markdown_options = MarkdownOptions(
            heading_style='atx'
        )

        result = to_markdown(
            html_content.encode('utf-8'),
            file_extension='.html',
            html_options=options,
            markdown_options=markdown_options
        )

        assert_markdown_valid(result.text)

        # Should contain table content
        assert "Table Test Document" in result.text
        assert "|" in result.text  # Should have table formatting
        assert "Alice Johnson" in result.text

        # Should detect format correctly
        assert result.format == DocumentFormat.HTML

    def test_pptx_to_markdown_full_pipeline(self, temp_dir):
        """Test complete PPTX to Markdown conversion pipeline."""
        # Create a PPTX presentation
        prs = create_pptx_with_basic_slides()
        pptx_bytes = save_pptx_to_bytes(prs)

        # Convert with options
        options = PptxOptions(
            extract_images=False,
            include_slide_numbers=True
        )
        markdown_options = MarkdownOptions(
            heading_style='atx'
        )

        result = to_markdown(
            pptx_bytes,
            file_extension='.pptx',
            pptx_options=options,
            markdown_options=markdown_options
        )

        assert_markdown_valid(result.text)

        # Should contain presentation content
        assert "Test Presentation" in result.text
        assert "Main Content Slide" in result.text
        assert "First bullet point" in result.text

        # Should detect format correctly
        assert result.format == DocumentFormat.PPTX

    def test_pdf_to_markdown_full_pipeline(self, temp_dir):
        """Test complete PDF to Markdown conversion pipeline."""
        # Create a PDF with figures
        doc = create_pdf_with_figures()

        try:
            # Save to bytes
            pdf_bytes = BytesIO()
            doc.save(pdf_bytes)
            pdf_bytes.seek(0)

            # Convert with options
            options = PdfOptions(
                extract_images=True,
                extract_tables=True
            )
            markdown_options = MarkdownOptions(
                heading_style='atx'
            )

            result = to_markdown(
                pdf_bytes.read(),
                file_extension='.pdf',
                pdf_options=options,
                markdown_options=markdown_options
            )

            assert_markdown_valid(result.text)

            # Should contain PDF content
            assert "Test Document with Figures" in result.text
            assert "figure" in result.text.lower()

            # Should detect format correctly
            assert result.format == DocumentFormat.PDF

        finally:
            doc.close()

    def test_automatic_format_detection_pipeline(self, temp_dir):
        """Test automatic format detection in the conversion pipeline."""
        # Test with different file types without explicit extension

        # DOCX test
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        result_docx = to_markdown(docx_bytes)  # No explicit extension
        assert result_docx.format == DocumentFormat.DOCX
        assert_markdown_valid(result_docx.text)

        # HTML test
        html_content = create_html_with_tables()
        html_bytes = html_content.encode('utf-8')

        result_html = to_markdown(html_bytes)  # No explicit extension
        assert result_html.format == DocumentFormat.HTML
        assert_markdown_valid(result_html.text)

    def test_error_handling_in_full_pipeline(self, temp_dir):
        """Test error handling throughout the conversion pipeline."""
        # Test with invalid content
        invalid_content = b"This is not a valid document"

        # Should handle gracefully
        with pytest.raises(Exception):  # Specific exception depends on implementation
            to_markdown(invalid_content, file_extension='.docx')

        # Test with unsupported format
        with pytest.raises(ValueError):
            to_markdown(b"content", file_extension='.unsupported')

    def test_large_document_pipeline_performance(self, temp_dir):
        """Test pipeline performance with larger documents."""
        # Create a larger document for performance testing
        import docx

        doc = docx.Document()
        doc.add_heading("Large Document Test", level=1)

        # Add many paragraphs
        for i in range(100):
            p = doc.add_paragraph(f"This is paragraph {i+1} with some content.")
            if i % 10 == 0:
                p.runs[0].bold = True

        # Add a large table
        table = doc.add_table(rows=20, cols=5)
        for i, row in enumerate(table.rows):
            for j, cell in enumerate(row.cells):
                cell.text = f"Row {i+1}, Col {j+1}"

        docx_bytes = save_docx_to_bytes(doc)

        # Convert (should complete without timeout)
        result = to_markdown(docx_bytes, file_extension='.docx')

        assert_markdown_valid(result.text)
        assert "Large Document Test" in result.text
        assert "paragraph 50" in result.text
        assert "Row 10, Col 3" in result.text

    def test_options_propagation_through_pipeline(self, temp_dir):
        """Test that conversion options are properly propagated through the pipeline."""
        # Create HTML with various elements
        html = '''
        <html>
        <head><title>Options Test</title></head>
        <body>
            <h1>Main Title</h1>
            <p>Regular paragraph.</p>
            <table>
                <tr><th>Header</th></tr>
                <tr><td>Data</td></tr>
            </table>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
        </body>
        </html>
        '''

        # Test with table conversion disabled
        options_no_tables = HtmlOptions(
            convert_tables=False,
            skip_tags=['script', 'style']
        )

        result_no_tables = to_markdown(
            html.encode('utf-8'),
            file_extension='.html',
            html_options=options_no_tables
        )

        # Should not contain table formatting
        assert "|" not in result_no_tables.text
        assert "Header" in result_no_tables.text  # Content should still be there

        # Test with table conversion enabled
        options_with_tables = HtmlOptions(
            convert_tables=True,
            skip_tags=['script', 'style']
        )

        result_with_tables = to_markdown(
            html.encode('utf-8'),
            file_extension='.html',
            html_options=options_with_tables
        )

        # Should contain table formatting
        assert "|" in result_with_tables.text
        assert "Header" in result_with_tables.text

    def test_mixed_content_document_pipeline(self, temp_dir):
        """Test conversion of documents with mixed content types."""
        # Create a complex DOCX with tables, images, and various formatting
        import docx
        from docx.shared import Inches

        doc = docx.Document()

        # Title and introduction
        doc.add_heading("Complex Document", level=1)
        doc.add_paragraph("This document contains various content types.")

        # Table
        table = doc.add_table(rows=3, cols=3)
        table.style = 'Table Grid'

        # Add table content
        for i, row in enumerate(table.rows):
            for j, cell in enumerate(row.cells):
                if i == 0:
                    cell.text = f"Header {j+1}"
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = True
                else:
                    cell.text = f"Data {i}-{j+1}"

        # More content
        doc.add_heading("Section 2", level=2)
        doc.add_paragraph("Content after the table.")

        # Lists
        doc.add_paragraph("Features:", style='List Bullet')
        doc.add_paragraph("Feature 1", style='List Bullet')
        doc.add_paragraph("Feature 2", style='List Bullet')

        docx_bytes = save_docx_to_bytes(doc)

        # Convert with comprehensive options
        docx_options = DocxOptions(
            extract_images=True,
            table_style='grid'
        )
        markdown_options = MarkdownOptions(
            heading_style='atx',
            bullet_style='-'
        )

        result = to_markdown(
            docx_bytes,
            file_extension='.docx',
            docx_options=docx_options,
            markdown_options=markdown_options
        )

        assert_markdown_valid(result.text)

        # Should contain all content types
        assert "# Complex Document" in result.text
        assert "## Section 2" in result.text
        assert "Header 1" in result.text
        assert "Data 1-1" in result.text
        assert "- Feature 1" in result.text
        assert "various content types" in result.text

    @pytest.mark.slow
    def test_batch_conversion_pipeline(self, temp_dir):
        """Test conversion of multiple documents in sequence."""
        # Create multiple test documents
        documents = []

        # DOCX
        docx_doc = create_docx_with_formatting()
        documents.append((save_docx_to_bytes(docx_doc), '.docx', DocumentFormat.DOCX))

        # HTML
        html_content = create_html_with_tables()
        documents.append((html_content.encode('utf-8'), '.html', DocumentFormat.HTML))

        # PPTX
        pptx_prs = create_pptx_with_basic_slides()
        documents.append((save_pptx_to_bytes(pptx_prs), '.pptx', DocumentFormat.PPTX))

        # Convert all documents
        results = []
        for content, extension, expected_format in documents:
            result = to_markdown(content, file_extension=extension)
            results.append(result)

            # Verify each conversion
            assert result.format == expected_format
            assert_markdown_valid(result.text)
            assert len(result.text) > 0

        # Verify different content in each result
        assert "Formatting Test Document" in results[0].text  # DOCX
        assert "Table Test Document" in results[1].text       # HTML
        assert "Test Presentation" in results[2].text         # PPTX

        # All should be valid markdown
        for result in results:
            assert_markdown_valid(result.text)