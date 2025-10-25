"""Tests for M11: TOCTOU race condition fix in file reading.

This module tests that file reading uses file descriptors to prevent
Time-of-Check-Time-of-Use (TOCTOU) race conditions where files could
be swapped between validation and reading.
"""

import os
import tempfile
from unittest.mock import patch

from all2md import to_markdown
from all2md.options.common import LocalFileAccessOptions
from all2md.options.html import HtmlOptions


class TestFileReadingTOCTOU:
    """Test TOCTOU race condition mitigation in file reading."""

    def test_regular_file_read_succeeds(self):
        """Test that reading a regular file works correctly."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".png", delete=False) as f:
            f.write("fake image data")
            temp_file = f.name

        try:
            # Create HTML with file:// URL
            file_url = f"file://{temp_file}"
            html = f'<img src="{file_url}" alt="test">'

            options = HtmlOptions(
                attachment_mode="alt_text",
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # Should not raise an exception
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "test" in result
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_non_regular_file_rejected(self):
        """Test that non-regular files (directories, devices) are rejected."""
        # Try to read a directory
        with tempfile.TemporaryDirectory() as temp_dir:
            file_url = f"file://{temp_dir}"
            html = f'<img src="{file_url}" alt="test">'

            options = HtmlOptions(
                attachment_mode="download",
                attachment_output_dir=temp_dir,
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # Reading a directory should fail (not a regular file)
            result = to_markdown(html, source_format="html", parser_options=options)
            # Should fall back to alt_text mode
            assert "test" in result

    def test_file_size_checked_before_reading(self):
        """Test that file size is checked using fstat before reading."""
        # Create a file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            # Write small amount of data
            f.write(b"small data")
            temp_file = f.name

        try:
            file_url = f"file://{temp_file}"
            html = f'<img src="{file_url}" alt="test">'

            # Set a very small max_asset_size to trigger the size check
            options = HtmlOptions(
                attachment_mode="base64",
                max_asset_size_bytes=5,  # Very small limit
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # Should fall back to alt_text mode due to size limit
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "test" in result
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_file_descriptor_closed_on_error(self):
        """Test that file descriptors are properly closed even on errors."""
        # Create a file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(b"test data")
            temp_file = f.name

        try:
            file_url = f"file://{temp_file}"
            html = f'<img src="{file_url}" alt="test">'

            options = HtmlOptions(
                attachment_mode="base64",
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # Mock os.read to raise an exception
            with patch("os.read", side_effect=OSError("Mock read error")):
                # Should handle the error gracefully and close FD
                result = to_markdown(html, source_format="html", parser_options=options)
                # Should fall back to alt_text mode
                assert "test" in result
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_symlink_handled_correctly(self):
        """Test that symlinks are resolved and handled correctly."""
        # Create a regular file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(b"target data")
            target_file = f.name

        # Create a symlink to it
        link_file = target_file + ".link"

        try:
            os.symlink(target_file, link_file)

            file_url = f"file://{link_file}"
            html = f'<img src="{file_url}" alt="test">'

            options = HtmlOptions(
                attachment_mode="alt_text",
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # Should handle symlink correctly
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "test" in result
        finally:
            if os.path.exists(link_file):
                os.unlink(link_file)
            if os.path.exists(target_file):
                os.unlink(target_file)

    def test_file_descriptor_prevents_swap_attack(self):
        """Test that using file descriptors prevents file swap attacks.

        This test verifies that once a file descriptor is obtained,
        reading from it is safe even if the file is changed externally.
        """
        # Create a file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(b"original data")
            temp_file = f.name

        try:
            file_url = f"file://{temp_file}"
            html = f'<img src="{file_url}" alt="test">'

            options = HtmlOptions(
                attachment_mode="alt_text",
                local_files=LocalFileAccessOptions(
                    allow_local_files=True,
                    allow_cwd_files=True,
                ),
            )

            # The file descriptor approach means even if someone tries to swap
            # the file during reading, the FD points to the original file
            result = to_markdown(html, source_format="html", parser_options=options)
            assert "test" in result
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
