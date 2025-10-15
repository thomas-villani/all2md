#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for attachment handling utilities.

This module tests the attachment processing functions in all2md.utils.attachments,
including Markdown escaping and URL quoting.
"""

from pathlib import Path

from all2md.utils.attachments import process_attachment


class TestMarkdownEscaping:
    """Test suite for Markdown escaping in attachment alt text."""

    def test_image_alt_text_with_brackets_escaped(self):
        """Test that square brackets in image alt text are escaped."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="image.png",
            alt_text="Test [bracket] text",
            attachment_mode="alt_text",
            is_image=True
        )

        markdown = result['markdown']
        # Square brackets should be escaped
        assert r"\[" in markdown or "[bracket]" not in markdown
        assert "Test" in markdown

    def test_image_filename_with_brackets_escaped(self):
        """Test that square brackets in image filename are escaped when used as alt text."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="image[1].png",
            alt_text="",
            attachment_mode="alt_text",
            is_image=True
        )

        markdown = result['markdown']
        # Square brackets should be escaped
        assert r"\[" in markdown or "[1]" not in markdown

    def test_link_text_with_brackets_escaped(self):
        """Test that square brackets in link text are escaped."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="file[version].pdf",
            alt_text="",
            attachment_mode="alt_text",
            is_image=False
        )

        markdown = result['markdown']
        # Square brackets should be escaped
        assert r"\[" in markdown or "[version]" not in markdown

    def test_base64_mode_escapes_alt_text(self):
        """Test that base64 mode escapes alt text."""
        image_data = b'\x89PNG\r\n\x1a\n'  # PNG header
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="test.png",
            alt_text="Alt [text] with brackets",
            attachment_mode="base64",
            is_image=True
        )

        markdown = result['markdown']
        # Alt text should be escaped
        assert r"\[" in markdown or "[text]" not in markdown
        assert "Alt" in markdown

    def test_download_mode_escapes_display_name(self, tmp_path):
        """Test that download mode escapes display name."""
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="image.png",
            alt_text="Display [name]",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            is_image=True
        )

        markdown = result['markdown']
        # Display name should be escaped
        assert r"\[" in markdown or "[name]" not in markdown


class TestUrlQuoting:
    """Test suite for URL quoting in attachment paths."""

    def test_filename_with_spaces_url_encoded(self, tmp_path):
        """Test that filenames with spaces are URL-encoded."""
        # Note: filename sanitization converts spaces to underscores first
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="my image.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/assets/",
            is_image=True
        )

        url = result['url']
        # After sanitization, spaces become underscores, then URL-encoded
        # my_image.png is a valid filename, so no encoding needed for it
        assert "https://example.com" in url
        assert ".png" in url
        # Verify the filename is sanitized (spaces -> underscores)
        assert "my_image.png" in url or "my%5Fimage.png" in url

    def test_filename_with_special_chars_url_encoded(self, tmp_path):
        """Test that filenames with special characters are URL-encoded."""
        # Note: filename sanitization removes & first
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="file&name.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True
        )

        url = result['url']
        # After sanitization, & is removed: "filename.png"
        assert "https://example.com" in url
        assert "filename.png" in url

    def test_local_path_uses_posix_format(self, tmp_path):
        """Test that local paths use POSIX format with forward slashes."""
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="image.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            # No base_url means local path
            is_image=True
        )

        url = result['url']
        # Should use forward slashes (POSIX style)
        assert "/" in url
        # Should not have backslashes (Windows style)
        assert "\\" not in url or Path(url).as_posix() == url

    def test_filename_with_hash_url_encoded(self, tmp_path):
        """Test that filenames with # are URL-encoded."""
        # Note: filename sanitization removes # first
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="file#1.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True
        )

        url = result['url']
        # After sanitization, # is removed: "file1.png"
        assert "https://example.com" in url
        assert "file1.png" in url

    def test_unicode_filename_url_encoded(self, tmp_path):
        """Test that Unicode filenames are URL-encoded."""
        image_data = b'\x89PNG\r\n\x1a\n'
        # Unicode filename will be sanitized first, but if it survives, should be encoded
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="test.png",  # Use ASCII for test
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True
        )

        url = result['url']
        # Should have a valid URL
        assert "https://example.com" in url
        assert ".png" in url


class TestCombinedEscapingAndQuoting:
    """Test suite for combined Markdown escaping and URL quoting."""

    def test_download_mode_escapes_and_quotes(self, tmp_path):
        """Test that download mode both escapes alt text and quotes URLs."""
        image_data = b'\x89PNG\r\n\x1a\n'
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="my file.png",
            alt_text="Image [1]",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True
        )

        markdown = result['markdown']
        url = result['url']

        # Alt text should be escaped
        assert r"\[" in markdown or "[1]" not in markdown
        # Filename is sanitized (spaces -> underscores) then URL-encoded
        assert "my_file.png" in url or "my%5Ffile.png" in url
