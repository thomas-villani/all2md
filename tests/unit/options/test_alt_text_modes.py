"""Unit tests for alt_text_mode functionality in attachment processing.

This module tests the new AltTextMode enum and its implementation in the
process_attachment function, verifying that different modes produce
the expected markdown output.
"""

import pytest

from all2md.utils.attachments import process_attachment


class TestAltTextModes:
    """Test different alt_text_mode configurations."""

    def test_default_mode_images(self):
        """Test default mode for images produces standard markdown."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="alt_text",
            alt_text_mode="default",
            is_image=True
        )
        assert result["markdown"] == "![Test Image]"
        assert result["footnote_label"] is None
        assert result["url"] == ""

    def test_default_mode_files(self):
        """Test default mode for files produces standard markdown."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="document.pdf",
            alt_text="Test Document",
            attachment_mode="alt_text",
            alt_text_mode="default",
            is_image=False
        )
        assert result["markdown"] == "[document.pdf]"
        assert result["footnote_label"] is None

    def test_plain_filename_mode_images(self):
        """Test plain_filename mode for images still uses markdown syntax."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="alt_text",
            alt_text_mode="plain_filename",
            is_image=True
        )
        assert result["markdown"] == "![Test Image]"

    def test_plain_filename_mode_files(self):
        """Test plain_filename mode for files produces plain text."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="document.pdf",
            alt_text="Test Document",
            attachment_mode="alt_text",
            alt_text_mode="plain_filename",
            is_image=False
        )
        assert result["markdown"] == "document.pdf"

    def test_strict_markdown_mode_images(self):
        """Test strict_markdown mode for images includes empty link."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="alt_text",
            alt_text_mode="strict_markdown",
            is_image=True
        )
        assert result["markdown"] == "![Test Image](#)"
        assert result["url"] == "#"

    def test_strict_markdown_mode_files(self):
        """Test strict_markdown mode for files includes empty link."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="document.pdf",
            alt_text="Test Document",
            attachment_mode="alt_text",
            alt_text_mode="strict_markdown",
            is_image=False
        )
        assert result["markdown"] == "[document.pdf](#)"
        assert result["url"] == "#"

    def test_footnote_mode_images(self):
        """Test footnote mode for images uses footnote reference with sanitized label (no extension)."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="alt_text",
            alt_text_mode="footnote",
            is_image=True
        )
        # Footnote labels are sanitized and extension is removed for cleaner references
        # Note: Space between image and footnote reference for valid Markdown syntax
        assert result["markdown"] == "![Test Image] [^test]"
        assert result["footnote_label"] == "test"
        assert result["footnote_content"] == "Test Image"
        assert result["url"] == ""

    def test_footnote_mode_files(self):
        """Test footnote mode for files uses footnote reference with sanitized label (no extension)."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="document.pdf",
            alt_text="Test Document",
            attachment_mode="alt_text",
            alt_text_mode="footnote",
            is_image=False
        )
        # Footnote labels are sanitized and extension is removed for cleaner references
        # Note: Space between link and footnote reference for valid Markdown syntax
        assert result["markdown"] == "[document.pdf] [^document]"
        assert result["footnote_label"] == "document"
        assert result["footnote_content"] == "document.pdf"

    def test_alt_text_fallback_uses_filename(self):
        """Test that empty alt_text falls back to filename."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="",
            attachment_mode="alt_text",
            alt_text_mode="default",
            is_image=True
        )
        assert result["markdown"] == "![test.png]"

    def test_alt_text_mode_with_download_mode(self):
        """Test that alt_text_mode doesn't affect download mode."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            result = process_attachment(
                attachment_data=b"fake image data",
                attachment_name="test.png",
                alt_text="Test Image",
                attachment_mode="download",
                attachment_output_dir=temp_dir,
                alt_text_mode="strict_markdown",
                is_image=True
            )
            # Download mode should ignore alt_text_mode
            assert result["markdown"].startswith("![Test Image](")
            assert "test.png" in result["markdown"]
            assert result["url"]  # Should have a URL

    def test_alt_text_mode_with_base64_mode(self):
        """Test that alt_text_mode doesn't affect base64 mode."""
        result = process_attachment(
            attachment_data=b"fake image data",
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="base64",
            alt_text_mode="footnote",
            is_image=True
        )
        # Base64 mode should ignore alt_text_mode
        assert result["markdown"].startswith("![Test Image](data:")
        assert result["url"].startswith("data:")

    def test_alt_text_mode_with_skip_mode(self):
        """Test that alt_text_mode doesn't affect skip mode."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="skip",
            alt_text_mode="footnote",
            is_image=True
        )
        # Skip mode should return empty string regardless of alt_text_mode
        assert result["markdown"] == ""

    def test_fallback_respects_alt_text_mode(self):
        """Test that fallback behavior respects alt_text_mode."""
        # Test with unsupported mode to trigger fallback
        result = process_attachment(
            attachment_data=None,
            attachment_name="test.png",
            alt_text="Test Image",
            attachment_mode="unsupported_mode",  # This will trigger fallback
            alt_text_mode="strict_markdown",
            is_image=True
        )
        assert result["markdown"] == "![Test Image](#)"

    def test_all_alt_text_modes_enum_values(self):
        """Test that all AltTextMode enum values are handled."""
        modes = ["default", "plain_filename", "strict_markdown", "footnote"]

        for mode in modes:
            # Test with image
            result_img = process_attachment(
                attachment_data=None,
                attachment_name="test.png",
                alt_text="Test",
                attachment_mode="alt_text",
                alt_text_mode=mode,
                is_image=True
            )
            assert isinstance(result_img, dict)
            assert "markdown" in result_img
            assert len(result_img["markdown"]) > 0

            # Test with file
            result_file = process_attachment(
                attachment_data=None,
                attachment_name="test.pdf",
                alt_text="Test",
                attachment_mode="alt_text",
                alt_text_mode=mode,
                is_image=False
            )
            assert isinstance(result_file, dict)
            assert "markdown" in result_file
            assert len(result_file["markdown"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])
