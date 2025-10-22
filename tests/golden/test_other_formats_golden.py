"""Golden tests for other format converters (PPTX, Markdown, etc.).

These tests use syrupy for snapshot testing to ensure conversion
output remains consistent across code changes.
"""

from io import BytesIO

import pytest
from fixtures.generators.markdown_fixtures import (
    create_markdown_with_code_and_lists,
    create_markdown_with_tables,
    markdown_bytes_io,
)
from fixtures.generators.pptx_fixtures import create_pptx_with_basic_slides, save_pptx_to_bytes

from all2md import PptxOptions, to_markdown


@pytest.mark.golden
@pytest.mark.pptx
@pytest.mark.unit
class TestPPTXGolden:
    """Golden/snapshot tests for PPTX converter."""

    def test_basic_pptx_conversion(self, snapshot):
        """Test basic PPTX conversion matches snapshot."""
        prs = create_pptx_with_basic_slides()
        pptx_bytes = save_pptx_to_bytes(prs)

        result = to_markdown(BytesIO(pptx_bytes), source_format="pptx")
        assert result == snapshot

    def test_pptx_with_slide_numbers(self, snapshot):
        """Test PPTX with slide numbers matches snapshot."""
        prs = create_pptx_with_basic_slides()
        pptx_bytes = save_pptx_to_bytes(prs)

        options = PptxOptions(include_slide_numbers=True)
        result = to_markdown(BytesIO(pptx_bytes), source_format="pptx", parser_options=options)
        assert result == snapshot

    def test_pptx_attachment_mode_skip(self, snapshot):
        """Test PPTX with images skipped matches snapshot."""
        prs = create_pptx_with_basic_slides()
        pptx_bytes = save_pptx_to_bytes(prs)

        options = PptxOptions(attachment_mode="skip")
        result = to_markdown(BytesIO(pptx_bytes), source_format="pptx", parser_options=options)
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestMarkdownRoundtripGolden:
    """Golden/snapshot tests for Markdown parser (round-trip)."""

    def test_markdown_roundtrip_basic(self, snapshot):
        """Test basic markdown round-trip matches snapshot."""
        markdown_stream = markdown_bytes_io(create_markdown_with_code_and_lists())

        result = to_markdown(markdown_stream, source_format="markdown")
        assert result == snapshot

    def test_markdown_roundtrip_with_table(self, snapshot):
        """Test markdown with table round-trip matches snapshot."""
        markdown_stream = markdown_bytes_io(create_markdown_with_tables())

        result = to_markdown(markdown_stream, source_format="markdown")
        assert result == snapshot


@pytest.mark.golden
@pytest.mark.integration
class TestFileFormatGoldenFromFiles:
    """Golden tests for various formats using fixture files."""

    def test_basic_html_file(self, snapshot):
        """Test basic HTML file matches snapshot."""
        fixture_path = "tests/fixtures/documents/basic.html"

        try:
            with open(fixture_path, "rb") as f:
                result = to_markdown(f, source_format="html")
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")

    def test_basic_pptx_file(self, snapshot):
        """Test basic PPTX file matches snapshot."""
        fixture_path = "tests/fixtures/documents/basic.pptx"

        try:
            with open(fixture_path, "rb") as f:
                result = to_markdown(f, source_format="pptx")
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")

    def test_basic_odt_file(self, snapshot):
        """Test basic ODT file matches snapshot."""
        fixture_path = "tests/fixtures/documents/basic.odt"

        try:
            with open(fixture_path, "rb") as f:
                result = to_markdown(f, source_format="odt")
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")

    def test_basic_xlsx_file(self, snapshot):
        """Test basic XLSX file matches snapshot."""
        fixture_path = "tests/fixtures/documents/basic.xlsx"

        try:
            with open(fixture_path, "rb") as f:
                result = to_markdown(f, source_format="xlsx")
            assert result == snapshot
        except FileNotFoundError:
            pytest.skip(f"Fixture file not found: {fixture_path}")
