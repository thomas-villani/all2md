"""Golden tests for DOCX to Markdown conversion.

These tests use syrupy for snapshot testing to ensure DOCX conversion
output remains consistent across code changes.
"""

from io import BytesIO

import pytest
from fixtures.generators.docx_fixtures import (
    create_docx_with_formatting,
    create_docx_with_lists,
    create_docx_with_tables,
    save_docx_to_bytes,
)

from all2md import to_markdown
from all2md.options import DocxOptions


@pytest.mark.golden
@pytest.mark.docx
@pytest.mark.unit
class TestDOCXGolden:
    """Golden/snapshot tests for DOCX converter."""

    def test_basic_docx_conversion(self, snapshot):
        """Test basic DOCX conversion matches snapshot."""
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        result = to_markdown(BytesIO(docx_bytes), source_format='docx')
        assert result == snapshot

    def test_docx_with_formatting(self, snapshot):
        """Test DOCX with formatting matches snapshot."""
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        result = to_markdown(BytesIO(docx_bytes), source_format='docx')
        assert result == snapshot

    def test_docx_with_lists(self, snapshot):
        """Test DOCX with lists matches snapshot."""
        doc = create_docx_with_lists()
        docx_bytes = save_docx_to_bytes(doc)

        result = to_markdown(BytesIO(docx_bytes), source_format='docx')
        assert result == snapshot

    def test_docx_with_table(self, snapshot):
        """Test DOCX with table matches snapshot."""
        doc = create_docx_with_tables()
        docx_bytes = save_docx_to_bytes(doc)

        result = to_markdown(BytesIO(docx_bytes), source_format='docx')
        assert result == snapshot

    def test_docx_with_attachment_mode_skip(self, snapshot):
        """Test DOCX with images skipped matches snapshot."""
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        options = DocxOptions(attachment_mode='skip')
        result = to_markdown(BytesIO(docx_bytes), source_format='docx', parser_options=options)
        assert result == snapshot

    def test_docx_with_attachment_mode_alt_text(self, snapshot):
        """Test DOCX with images as alt-text matches snapshot."""
        doc = create_docx_with_formatting()
        docx_bytes = save_docx_to_bytes(doc)

        options = DocxOptions(attachment_mode='alt_text')
        result = to_markdown(BytesIO(docx_bytes), source_format='docx', parser_options=options)
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.docx
@pytest.mark.integration
class TestDOCXGoldenFromFiles:
    """Golden tests for DOCX converter using fixture files."""

    def test_basic_docx_file(self, snapshot):
        """Test basic DOCX file matches snapshot."""
        fixture_path = 'tests/fixtures/documents/basic.docx'

        try:
            with open(fixture_path, 'rb') as f:
                result = to_markdown(f, source_format='docx')
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")

    def test_footnotes_endnotes_docx_file(self, snapshot):
        """Test DOCX with footnotes and endnotes matches snapshot."""
        fixture_path = 'tests/fixtures/documents/footnotes-endnotes-comments.docx'

        try:
            with open(fixture_path, 'rb') as f:
                result = to_markdown(f, source_format='docx')
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")
