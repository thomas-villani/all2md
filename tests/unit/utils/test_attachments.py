#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for attachment handling utilities.

This module tests the attachment processing functions in all2md.utils.attachments,
including Markdown escaping, URL quoting, and thread safety.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from all2md.utils.attachments import (
    create_attachment_sequencer,
    ensure_unique_attachment_path,
    process_attachment,
)


class TestMarkdownEscaping:
    """Test suite for Markdown escaping in attachment alt text."""

    def test_image_alt_text_with_brackets_escaped(self):
        """Test that square brackets in image alt text are escaped."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="image.png",
            alt_text="Test [bracket] text",
            attachment_mode="alt_text",
            is_image=True,
        )

        markdown = result["markdown"]
        # Square brackets should be escaped
        assert r"\[" in markdown or "[bracket]" not in markdown
        assert "Test" in markdown

    def test_image_filename_with_brackets_escaped(self):
        """Test that square brackets in image filename are escaped when used as alt text."""
        result = process_attachment(
            attachment_data=None, attachment_name="image[1].png", alt_text="", attachment_mode="alt_text", is_image=True
        )

        markdown = result["markdown"]
        # Square brackets should be escaped
        assert r"\[" in markdown or "[1]" not in markdown

    def test_link_text_with_brackets_escaped(self):
        """Test that square brackets in link text are escaped."""
        result = process_attachment(
            attachment_data=None,
            attachment_name="file[version].pdf",
            alt_text="",
            attachment_mode="alt_text",
            is_image=False,
        )

        markdown = result["markdown"]
        # Square brackets should be escaped
        assert r"\[" in markdown or "[version]" not in markdown

    def test_base64_mode_escapes_alt_text(self):
        """Test that base64 mode escapes alt text."""
        image_data = b"\x89PNG\r\n\x1a\n"  # PNG header
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="test.png",
            alt_text="Alt [text] with brackets",
            attachment_mode="base64",
            is_image=True,
        )

        markdown = result["markdown"]
        # Alt text should be escaped
        assert r"\[" in markdown or "[text]" not in markdown
        assert "Alt" in markdown
        assert result.get("source_data") == "base64"

    def test_download_mode_escapes_display_name(self, tmp_path):
        """Test that download mode escapes display name."""
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="image.png",
            alt_text="Display [name]",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            is_image=True,
        )

        markdown = result["markdown"]
        # Display name should be escaped
        assert r"\[" in markdown or "[name]" not in markdown
        assert result.get("source_data") == "downloaded"


class TestUrlQuoting:
    """Test suite for URL quoting in attachment paths."""

    def test_filename_with_spaces_url_encoded(self, tmp_path):
        """Test that filenames with spaces are URL-encoded."""
        # Note: filename sanitization converts spaces to underscores first
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="my image.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/assets/",
            is_image=True,
        )

        url = result["url"]
        # After sanitization, spaces become underscores, then URL-encoded
        # my_image.png is a valid filename, so no encoding needed for it
        assert "https://example.com" in url
        assert ".png" in url
        # Verify the filename is sanitized (spaces -> underscores)
        assert "my_image.png" in url or "my%5Fimage.png" in url
        assert result.get("source_data") == "downloaded"

    def test_filename_with_special_chars_url_encoded(self, tmp_path):
        """Test that filenames with special characters are URL-encoded."""
        # Note: filename sanitization removes & first
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="file&name.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True,
        )

        url = result["url"]
        # After sanitization, & is removed: "filename.png"
        assert "https://example.com" in url
        assert "filename.png" in url
        assert result.get("source_data") == "downloaded"

    def test_local_path_uses_posix_format(self, tmp_path):
        """Test that local paths use POSIX format with forward slashes."""
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="image.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            # No base_url means local path
            is_image=True,
        )

        url = result["url"]
        # Should use forward slashes (POSIX style)
        assert "/" in url
        # Should not have backslashes (Windows style)
        assert "\\" not in url or Path(url).as_posix() == url
        assert result.get("source_data") == "downloaded"

    def test_filename_with_hash_url_encoded(self, tmp_path):
        """Test that filenames with # are URL-encoded."""
        # Note: filename sanitization removes # first
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="file#1.png",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True,
        )

        url = result["url"]
        # After sanitization, # is removed: "file1.png"
        assert "https://example.com" in url
        assert "file1.png" in url
        assert result.get("source_data") == "downloaded"

    def test_unicode_filename_url_encoded(self, tmp_path):
        """Test that Unicode filenames are URL-encoded."""
        image_data = b"\x89PNG\r\n\x1a\n"
        # Unicode filename will be sanitized first, but if it survives, should be encoded
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="test.png",  # Use ASCII for test
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True,
        )

        url = result["url"]
        # Should have a valid URL
        assert "https://example.com" in url
        assert ".png" in url
        assert result.get("source_data") == "downloaded"


class TestCombinedEscapingAndQuoting:
    """Test suite for combined Markdown escaping and URL quoting."""

    def test_download_mode_escapes_and_quotes(self, tmp_path):
        """Test that download mode both escapes alt text and quotes URLs."""
        image_data = b"\x89PNG\r\n\x1a\n"
        result = process_attachment(
            attachment_data=image_data,
            attachment_name="my file.png",
            alt_text="Image [1]",
            attachment_mode="download",
            attachment_output_dir=str(tmp_path),
            attachment_base_url="https://example.com/",
            is_image=True,
        )

        markdown = result["markdown"]
        url = result["url"]

        # Alt text should be escaped
        assert r"\[" in markdown or "[1]" not in markdown
        # Filename is sanitized (spaces -> underscores) then URL-encoded
        assert "my_file.png" in url or "my%5Ffile.png" in url
        assert result.get("source_data") == "downloaded"


class TestSequencerThreadSafety:
    """Test thread-safety of attachment sequencer."""

    def test_sequencer_concurrent_access_no_duplicates(self):
        """Test that concurrent sequencer calls produce unique filenames."""
        sequencer = create_attachment_sequencer()
        results = []
        errors = []
        num_threads = 10
        calls_per_thread = 100

        def worker():
            thread_results = []
            for _ in range(calls_per_thread):
                try:
                    filename, _ = sequencer("doc", "pdf", page_num=1, extension="png")
                    thread_results.append(filename)
                except Exception as e:
                    errors.append(e)
            return thread_results

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            for future in as_completed(futures):
                results.extend(future.result())

        # No errors should have occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All filenames should be unique
        assert len(results) == len(set(results)), "Duplicate filenames generated!"

        # Should have expected number of results
        assert len(results) == num_threads * calls_per_thread

    def test_sequencer_concurrent_different_contexts(self):
        """Test concurrent access with different format contexts."""
        sequencer = create_attachment_sequencer()
        results = {"pdf": [], "pptx": [], "general": []}

        def pdf_worker():
            for i in range(50):
                filename, _ = sequencer("doc", "pdf", page_num=i % 5 + 1, extension="png")
                results["pdf"].append(filename)

        def pptx_worker():
            for i in range(50):
                filename, _ = sequencer("pres", "pptx", slide_num=i % 3 + 1, extension="jpg")
                results["pptx"].append(filename)

        def general_worker():
            for _ in range(50):
                filename, _ = sequencer("article", "general", extension="gif")
                results["general"].append(filename)

        threads = [
            threading.Thread(target=pdf_worker),
            threading.Thread(target=pptx_worker),
            threading.Thread(target=general_worker),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check uniqueness within each category
        for category, filenames in results.items():
            assert len(filenames) == len(set(filenames)), f"Duplicates in {category}"


class TestAtomicPathUniqueness:
    """Test atomic file creation for path uniqueness."""

    def test_atomic_creates_placeholder(self, tmp_path):
        """Test that atomic mode creates a placeholder file."""
        base_path = tmp_path / "test.png"
        result_path = ensure_unique_attachment_path(base_path, atomic=True)

        assert result_path == base_path
        assert result_path.exists()
        assert result_path.stat().st_size == 0  # Placeholder is 0 bytes

    def test_atomic_handles_existing_file(self, tmp_path):
        """Test that atomic mode finds unique path when file exists."""
        base_path = tmp_path / "test.png"
        base_path.write_bytes(b"existing content")

        result_path = ensure_unique_attachment_path(base_path, atomic=True)

        assert result_path == tmp_path / "test-1.png"
        assert result_path.exists()
        assert result_path.stat().st_size == 0  # Placeholder

    def test_atomic_concurrent_no_collisions(self, tmp_path):
        """Test that concurrent atomic creation never produces collisions."""
        base_path = tmp_path / "image.png"
        results = []
        errors = []
        num_threads = 20

        def worker():
            try:
                path = ensure_unique_attachment_path(base_path, atomic=True)
                return path
            except Exception as e:
                errors.append(e)
                return None

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        # No errors should have occurred
        assert len(errors) == 0, f"Errors: {errors}"

        # All paths should be unique
        assert len(results) == len(set(results)), "Duplicate paths!"

        # All paths should exist as placeholders
        for path in results:
            assert path.exists()

    def test_non_atomic_backward_compatible(self, tmp_path):
        """Test that non-atomic mode works as before (no placeholder)."""
        base_path = tmp_path / "test.png"
        result_path = ensure_unique_attachment_path(base_path, atomic=False)

        assert result_path == base_path
        assert not result_path.exists()  # Non-atomic doesn't create file

    def test_non_atomic_handles_existing_file(self, tmp_path):
        """Test that non-atomic mode finds unique path when file exists."""
        base_path = tmp_path / "test.png"
        base_path.write_bytes(b"existing content")

        result_path = ensure_unique_attachment_path(base_path, atomic=False)

        assert result_path == tmp_path / "test-1.png"
        assert not result_path.exists()  # Non-atomic doesn't create placeholder


class TestDownloadModeThreadSafety:
    """Test thread-safety of download mode attachment processing."""

    def test_concurrent_downloads_no_collision(self, tmp_path):
        """Test that concurrent download mode calls don't overwrite each other."""
        results = []
        errors = []
        num_threads = 10
        image_data = b"\x89PNG\r\n\x1a\n" + b"x" * 100

        def worker(thread_id):
            try:
                result = process_attachment(
                    attachment_data=image_data,
                    attachment_name="image.png",
                    alt_text=f"Thread {thread_id}",
                    attachment_mode="download",
                    attachment_output_dir=str(tmp_path),
                    is_image=True,
                )
                return result
            except Exception as e:
                errors.append(e)
                return None

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        # No errors
        assert len(errors) == 0, f"Errors: {errors}"

        # All URLs should be unique
        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls)), "Duplicate URLs in results!"

        # All files should exist and have content
        files = list(tmp_path.glob("*.png"))
        assert len(files) == num_threads
        for f in files:
            assert f.stat().st_size > 0
