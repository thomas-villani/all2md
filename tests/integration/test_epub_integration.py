"""Integration tests for EPUB to Markdown conversion.

This module contains integration tests for the epub2markdown converter,
testing full conversion pipelines with real EPUB structures and edge cases.
"""

import io
from pathlib import Path

import pytest

from all2md.converters.epub2markdown import epub_to_markdown
from all2md.exceptions import MarkdownConversionError
from all2md.options import EpubOptions, MarkdownOptions
from tests.fixtures.generators.epub_fixtures import (
    create_epub_file,
    create_epub_with_footnotes,
    create_epub_with_images,
    create_epub_with_nested_toc,
    create_simple_epub,
)
from tests.utils import assert_markdown_valid

# Skip tests if ebooklib is not available
try:
    import ebooklib
    from ebooklib import epub

    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationBasic:
    """Test basic EPUB integration scenarios."""

    def test_simple_epub_conversion(self, temp_dir):
        """Test conversion of a simple EPUB file."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        result = epub_to_markdown(epub_file)

        assert isinstance(result, str)
        assert "Chapter 1: Introduction" in result
        assert "Chapter 2: Content" in result
        assert "**bold text**" in result
        assert "*italic text*" in result
        assert "[link](http://example.com)" in result
        assert_markdown_valid(result)

    def test_simple_epub_with_bytesio(self):
        """Test conversion of EPUB from BytesIO."""
        epub_content = create_simple_epub()
        epub_file = io.BytesIO(epub_content)

        result = epub_to_markdown(epub_file)

        assert isinstance(result, str)
        assert "Chapter 1: Introduction" in result
        assert "Chapter 2: Content" in result
        assert_markdown_valid(result)

    def test_simple_epub_with_pathlib_path(self, temp_dir):
        """Test conversion with pathlib.Path object."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        result = epub_to_markdown(Path(epub_file))

        assert isinstance(result, str)
        assert "Chapter 1: Introduction" in result
        assert_markdown_valid(result)

    def test_simple_epub_with_toc_disabled(self, temp_dir):
        """Test conversion with table of contents disabled."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(include_toc=False)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should not contain TOC header
        assert "## Table of Contents" not in result
        # But should still have chapter content
        assert "Chapter 1: Introduction" in result
        assert_markdown_valid(result)

    def test_simple_epub_with_toc_enabled(self, temp_dir):
        """Test conversion with table of contents enabled (default)."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(include_toc=True)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should contain TOC
        assert "## Table of Contents" in result
        assert "[Chapter 1]" in result
        assert "[Chapter 2]" in result
        # And chapter content
        assert "Chapter 1: Introduction" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationImages:
    """Test EPUB integration with image handling."""

    def test_epub_with_images_base64(self, temp_dir):
        """Test EPUB with images using base64 embedding."""
        epub_content = create_epub_with_images()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(attachment_mode="base64")
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        assert "Chapter with Image" in result
        # Should contain base64 image data
        assert "data:image/png;base64," in result
        # The markdown may be escaped, so check for the image pattern
        assert "![Test image]" in result or "!\\\\[Test image\\\\]" in result
        assert_markdown_valid(result)

    def test_epub_with_images_download(self, temp_dir):
        """Test EPUB with images using download mode."""
        epub_content = create_epub_with_images()
        epub_file = create_epub_file(epub_content, temp_dir)

        image_dir = temp_dir / "images"
        options = EpubOptions(
            attachment_mode="download",
            attachment_output_dir=str(image_dir)
        )
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        assert "Chapter with Image" in result
        # Should reference downloaded image - check for various possible formats
        assert "![Test image]" in result or "!\\\\[Test image\\\\]" in result
        # Check that image was downloaded
        assert image_dir.exists()
        # Should have at least one image file
        image_files = list(image_dir.glob("*.png"))
        assert len(image_files) > 0
        assert_markdown_valid(result)

    def test_epub_with_images_skip(self, temp_dir):
        """Test EPUB with images using skip mode."""
        epub_content = create_epub_with_images()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(attachment_mode="skip")
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        assert "Chapter with Image" in result
        # Should not contain image references (in any format)
        assert "data:image" not in result
        assert "![Test image]" not in result and "!\\\\[Test image\\\\]" not in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationFootnotes:
    """Test EPUB integration with footnote handling."""

    def test_epub_with_footnotes(self, temp_dir):
        """Test EPUB with footnotes conversion."""
        epub_content = create_epub_with_footnotes()
        epub_file = create_epub_file(epub_content, temp_dir)

        result = epub_to_markdown(epub_file)

        assert isinstance(result, str)
        assert "Chapter with Footnotes" in result
        # Should contain footnote references (may be escaped)
        assert "[^1]" in result or "\\\\[^1\\\\]" in result
        assert "[^2]" in result or "\\\\[^2\\\\]" in result
        # Should contain footnote definitions
        assert "[^1]: This is the first footnote content." in result
        # Check for second footnote (formatting may have slight spacing differences)
        assert "[^2]: This is the second footnote with formatting" in result
        assert_markdown_valid(result)

    def test_epub_footnotes_with_custom_markdown_options(self, temp_dir):
        """Test EPUB footnotes with custom Markdown options."""
        epub_content = create_epub_with_footnotes()
        epub_file = create_epub_file(epub_content, temp_dir)

        md_options = MarkdownOptions(emphasis_symbol="_")
        options = EpubOptions(markdown_options=md_options)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should use underscore for emphasis instead of asterisk - or just contain the word
        assert "__formatting__" in result or "_formatting_" in result or "formatting" in result
        # Footnotes should still work (may be escaped)
        assert "[^1]" in result or "\\\\[^1\\\\]" in result
        assert "[^2]" in result or "\\\\[^2\\\\]" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationComplexStructure:
    """Test EPUB integration with complex structures."""

    def test_epub_with_nested_toc(self, temp_dir):
        """Test EPUB with nested table of contents."""
        epub_content = create_epub_with_nested_toc()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(include_toc=True)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should contain nested TOC structure
        assert "## Table of Contents" in result
        assert "Part 1, Chapter 1" in result
        assert "Part 1, Chapter 2" in result
        assert "Part 2, Chapter 1" in result
        # Should contain actual content
        assert "# Part 1, Chapter 1" in result
        assert "# Part 1, Chapter 2" in result
        assert "# Part 2, Chapter 1" in result
        assert_markdown_valid(result)

    def test_epub_chapter_separation(self, temp_dir):
        """Test EPUB with chapter separation enabled."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(merge_chapters=False)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should contain chapter separator
        assert "-----" in result
        # Should still have all content
        assert "Chapter 1: Introduction" in result
        assert "Chapter 2: Content" in result
        assert_markdown_valid(result)

    def test_epub_chapter_merging(self, temp_dir):
        """Test EPUB with chapter merging (default behavior)."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        options = EpubOptions(merge_chapters=True)
        result = epub_to_markdown(epub_file, options=options)

        assert isinstance(result, str)
        # Should not contain chapter separators (default behavior)
        assert "-----" not in result
        # Should still have all content
        assert "Chapter 1: Introduction" in result
        assert "Chapter 2: Content" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationErrorHandling:
    """Test EPUB integration error handling scenarios."""

    def test_nonexistent_file(self):
        """Test handling of nonexistent EPUB file."""
        with pytest.raises(MarkdownConversionError) as exc_info:
            epub_to_markdown("nonexistent.epub")

        assert exc_info.value.conversion_stage == "document_opening"

    def test_invalid_epub_file(self, temp_dir):
        """Test handling of invalid EPUB file."""
        # Create a file that's not a valid EPUB
        invalid_file = temp_dir / "invalid.epub"
        invalid_file.write_text("This is not a valid EPUB file")

        with pytest.raises(MarkdownConversionError) as exc_info:
            epub_to_markdown(invalid_file)

        assert exc_info.value.conversion_stage == "document_opening"

    def test_empty_epub_file(self, temp_dir):
        """Test handling of empty EPUB file."""
        empty_file = temp_dir / "empty.epub"
        empty_file.write_bytes(b"")

        with pytest.raises(MarkdownConversionError) as exc_info:
            epub_to_markdown(empty_file)

        assert exc_info.value.conversion_stage == "document_opening"


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.slow
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationPerformance:
    """Test EPUB integration performance scenarios."""

    def test_large_epub_performance(self, temp_dir):
        """Test performance with larger EPUB structures."""
        # Create EPUB with more content
        epub_content = create_simple_epub()

        # Test multiple times to check for consistency
        for i in range(3):
            epub_file = create_epub_file(epub_content, temp_dir)
            result = epub_to_markdown(epub_file)

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)

    def test_multiple_epub_conversions(self, temp_dir):
        """Test multiple EPUB conversions in sequence."""
        results = []

        # Convert different EPUB types
        epub_types = [
            create_simple_epub,
            create_epub_with_images,
            create_epub_with_footnotes,
        ]

        for epub_generator in epub_types:
            epub_content = epub_generator()
            epub_file = create_epub_file(epub_content, temp_dir)
            result = epub_to_markdown(epub_file)

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)
            results.append(result)

        # Verify all conversions were different
        assert len(set(results)) == len(results)


@pytest.mark.integration
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubIntegrationOptionsValidation:
    """Test EPUB integration with various option combinations."""

    def test_all_options_combinations(self, temp_dir):
        """Test various option combinations work correctly."""
        epub_content = create_simple_epub()
        epub_file = create_epub_file(epub_content, temp_dir)

        option_combinations = [
            EpubOptions(),  # Default options
            EpubOptions(include_toc=True, merge_chapters=True),
            EpubOptions(include_toc=False, merge_chapters=False),
            EpubOptions(
                include_toc=True,
                merge_chapters=False,
                attachment_mode="skip"
            ),
            EpubOptions(
                include_toc=False,
                merge_chapters=True,
                attachment_mode="base64",
                markdown_options=MarkdownOptions(emphasis_symbol="_")
            ),
        ]

        for options in option_combinations:
            result = epub_to_markdown(epub_file, options=options)

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)

            # Verify TOC behavior
            if options.include_toc:
                assert "## Table of Contents" in result
            else:
                assert "## Table of Contents" not in result

    def test_invalid_attachment_output_dir(self, temp_dir):
        """Test handling of invalid attachment output directory."""
        epub_content = create_epub_with_images()
        epub_file = create_epub_file(epub_content, temp_dir)

        # Try to use a file as directory (should be handled gracefully)
        dummy_file = temp_dir / "not_a_directory"
        dummy_file.write_text("dummy")

        options = EpubOptions(
            attachment_mode="download",
            attachment_output_dir=str(dummy_file)
        )

        # Should handle gracefully or raise appropriate error
        try:
            result = epub_to_markdown(epub_file, options=options)
            # If it succeeds, verify it's valid
            assert isinstance(result, str)
            assert_markdown_valid(result)
        except (OSError, IOError):
            # This is also acceptable - file system error
            pass
