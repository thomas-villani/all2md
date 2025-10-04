"""Golden tests for PDF to Markdown conversion.

These tests use syrupy for snapshot testing to ensure PDF conversion
output remains consistent across code changes.
"""

from io import BytesIO

import pytest

from all2md import to_markdown
from all2md.options import PdfOptions
from tests.fixtures.generators.pdf_test_fixtures import (
    create_pdf_with_formatting,
    create_pdf_with_figures,
    create_pdf_with_tables,
)


@pytest.mark.golden
@pytest.mark.pdf
@pytest.mark.unit
class TestPDFGolden:
    """Golden/snapshot tests for PDF converter."""

    def test_basic_pdf_conversion(self, snapshot):
        """Test basic PDF conversion matches snapshot."""
        pdf_doc = create_pdf_with_formatting()
        pdf_bytes = pdf_doc.tobytes()

        result = to_markdown(BytesIO(pdf_bytes), format='pdf')
        assert result == snapshot

    def test_pdf_with_tables(self, snapshot):
        """Test PDF with tables matches snapshot."""
        pdf_doc = create_pdf_with_tables()
        pdf_bytes = pdf_doc.tobytes()

        result = to_markdown(BytesIO(pdf_bytes), format='pdf')
        assert result == snapshot

    def test_pdf_with_figures(self, snapshot):
        """Test PDF with figures matches snapshot."""
        pdf_doc = create_pdf_with_figures()
        pdf_bytes = pdf_doc.tobytes()

        options = PdfOptions(attachment_mode='alt_text')
        result = to_markdown(BytesIO(pdf_bytes), format='pdf', parser_options=options)
        assert result == snapshot

    def test_pdf_attachment_mode_skip(self, snapshot):
        """Test PDF with images skipped matches snapshot."""
        pdf_doc = create_pdf_with_figures()
        pdf_bytes = pdf_doc.tobytes()

        options = PdfOptions(attachment_mode='skip')
        result = to_markdown(BytesIO(pdf_bytes), format='pdf', parser_options=options)
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.pdf
@pytest.mark.integration
class TestPDFGoldenFromFiles:
    """Golden tests for PDF converter using fixture files."""

    def test_basic_pdf_file(self, snapshot):
        """Test basic PDF file matches snapshot."""
        fixture_path = 'tests/fixtures/documents/basic.pdf'

        try:
            with open(fixture_path, 'rb') as f:
                result = to_markdown(f, format='pdf')
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")
