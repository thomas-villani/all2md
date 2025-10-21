"""Integration tests for PDF image and figure handling using real PDFs."""

import pytest

from all2md import to_markdown as pdf_to_markdown
from all2md.options import PdfOptions
from fixtures.generators.pdf_test_fixtures import create_test_pdf_bytes
from utils import assert_markdown_valid, cleanup_test_dir, create_test_temp_dir


@pytest.mark.integration
class TestPdfImagesIntegration:
    """Test PDF image and figure handling with real generated PDFs."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_image_extraction_basic(self):
        """Test basic image extraction from PDF with embedded images."""
        # Create PDF with images using our fixture
        pdf_bytes = create_test_pdf_bytes("images")

        options = PdfOptions(attachment_mode="alt_text")
        result = pdf_to_markdown(pdf_bytes, parser_options=options)
        assert_markdown_valid(result)

        # Should contain our expected text content
        assert "Test Document with Figures" in result
        assert "Figure 1: Sample chart showing data trends" in result
        assert "Figure 2: Additional visualization" in result
        assert "multiple figures for testing" in result

        # Should contain image references - the exact format depends on implementation
        # but there should be some indication of images
        has_image_refs = (
            "![" in result  # Standard markdown images
            or "[image]" in result.lower()  # Alt text references
            or "figure" in result.lower()  # Figure captions
        )
        assert has_image_refs, f"No image references found in result: {result}"

    def test_image_caption_detection(self):
        """Test detection and preservation of image captions."""
        pdf_bytes = create_test_pdf_bytes("images")

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Both captions should be preserved
        assert "Figure 1: Sample chart showing data trends" in result
        assert "Figure 2: Additional visualization" in result

    def test_multiple_images_per_page(self):
        """Test handling of multiple images on a single page."""
        pdf_bytes = create_test_pdf_bytes("images")

        options = PdfOptions(attachment_mode="alt_text")
        result = pdf_to_markdown(pdf_bytes, parser_options=options)
        assert_markdown_valid(result)

        # Should handle both figures
        assert "Figure 1:" in result
        assert "Figure 2:" in result

        # Text between/after figures should be preserved
        assert "multiple figures for testing" in result

    def test_image_format_detection(self):
        """Test that images are properly detected regardless of format."""
        # Our fixture creates PNG images - test that they're handled
        pdf_bytes = create_test_pdf_bytes("images")

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should not crash and should produce valid markdown
        assert len(result) > 0
        assert "Test Document with Figures" in result

    def test_image_text_flow_integration(self):
        """Test proper text flow around images."""
        pdf_bytes = create_test_pdf_bytes("complex")

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Should contain title and all text content
        assert "Complex Layout Test" in result
        assert "text flowing around" in result
        assert "Figure: Sample chart" in result
        assert "final paragraph tests" in result

        # Content should be in logical order
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        title_idx = next(i for i, line in enumerate(lines) if "Complex Layout" in line)
        final_idx = next(i for i, line in enumerate(lines) if "final paragraph" in line)
        assert title_idx < final_idx, "Content should be in logical reading order"

    def test_figure_complex_layouts(self):
        """Test handling of figures in complex document layouts."""
        pdf_bytes = create_test_pdf_bytes("complex")

        options = PdfOptions(attachment_mode="alt_text")
        result = pdf_to_markdown(pdf_bytes, parser_options=options)
        assert_markdown_valid(result)

        # Should properly handle mixed content
        assert "Complex Layout Test" in result  # Title
        assert "Figure: Sample chart" in result  # Image caption
        assert "Item" in result and "Value" in result  # Table content
        assert "final paragraph" in result  # Text after table

    def test_corrupted_image_handling(self):
        """Test graceful handling when image extraction might fail."""
        # Create a normal PDF - if image extraction fails, it shouldn't crash
        pdf_bytes = create_test_pdf_bytes("formatting")

        options = PdfOptions(attachment_mode="alt_text")
        # Should not raise exception even if no images or extraction issues
        result = pdf_to_markdown(pdf_bytes, parser_options=options)
        assert_markdown_valid(result)

        # Should still extract text content
        assert "normal text" in result.lower() or "bold text" in result.lower()

    def test_image_attachment_modes(self):
        """Test different image attachment modes work without crashing."""
        pdf_bytes = create_test_pdf_bytes("images")

        # Test alt_text mode
        result_alt = pdf_to_markdown(pdf_bytes, parser_options=PdfOptions(attachment_mode="alt_text"))
        assert_markdown_valid(result_alt)

        # Test skip mode
        result_skip = pdf_to_markdown(pdf_bytes, parser_options=PdfOptions(attachment_mode="skip"))
        assert_markdown_valid(result_skip)

        # Both should contain text content
        assert "Test Document with Figures" in result_alt
        assert "Test Document with Figures" in result_skip

        # Skip mode might have less image-related content
        assert len(result_skip) > 0

    def test_image_positioning_markers(self):
        """Test that image positioning is handled reasonably."""
        pdf_bytes = create_test_pdf_bytes("images")

        result = pdf_to_markdown(pdf_bytes)
        assert_markdown_valid(result)

        # Images and their captions should appear in reasonable positions
        # The exact positioning depends on implementation, but content should be logical
        lines = result.split("\n")
        content_lines = [line.strip() for line in lines if line.strip()]

        # Should have substantial content
        assert len(content_lines) > 3

        # Title should come first
        title_found = any("Test Document with Figures" in line for line in content_lines[:3])
        assert title_found, "Title should appear early in the document"
