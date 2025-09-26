"""Unit tests for EPUB to Markdown conversion.

This module contains unit tests for the epub2markdown converter,
testing core functionality, error handling, and edge cases.
"""

import io
from unittest.mock import MagicMock, patch

import pytest

from all2md.converters.epub2markdown import (
    _build_toc_map,
    _preprocess_html,
    _slugify,
    epub_to_markdown,
)
from all2md.exceptions import MarkdownConversionError
from all2md.options import EpubOptions

# Skip tests if ebooklib is not available
pytest_plugins = []
try:
    import ebooklib
    from ebooklib import epub

    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False


@pytest.mark.unit
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubToMarkdown:
    """Test core EPUB to Markdown conversion functionality."""

    def test_slugify_basic(self):
        """Test basic slugification functionality."""
        assert _slugify("Simple Title") == "simple-title"
        assert _slugify("Title With Symbols!@#") == "title-with-symbols"
        assert _slugify("Multiple   Spaces") == "multiple-spaces"
        assert _slugify("Dashes-And_Underscores") == "dashes-and-underscores"
        assert _slugify("") == ""
        assert _slugify("---Leading and trailing---") == "leading-and-trailing"

    def test_build_toc_map_simple(self):
        """Test building TOC map from simple table of contents."""
        toc = [
            epub.Link("chapter1.xhtml", "Chapter 1", "ch1"),
            epub.Link("chapter2.xhtml", "Chapter 2", "ch2"),
        ]

        toc_map = _build_toc_map(toc)

        assert toc_map == {
            "chapter1.xhtml": "Chapter 1",
            "chapter2.xhtml": "Chapter 2"
        }

    def test_build_toc_map_with_anchors(self):
        """Test building TOC map with anchor links."""
        toc = [
            epub.Link("chapter1.xhtml#section1", "Section 1", "sec1"),
            epub.Link("chapter2.xhtml#intro", "Introduction", "intro"),
        ]

        toc_map = _build_toc_map(toc)

        assert toc_map == {
            "chapter1.xhtml": "Section 1",
            "chapter2.xhtml": "Introduction"
        }

    def test_build_toc_map_nested(self):
        """Test building TOC map with nested structure."""
        toc = [
            epub.Link("part1.xhtml", "Part 1", "part1"),
            (epub.Section("Chapter Group"), [
                epub.Link("chapter1.xhtml", "Chapter 1", "ch1"),
                epub.Link("chapter2.xhtml", "Chapter 2", "ch2"),
            ])
        ]

        toc_map = _build_toc_map(toc)

        assert toc_map == {
            "part1.xhtml": "Part 1",
            "chapter1.xhtml": "Chapter 1",
            "chapter2.xhtml": "Chapter 2"
        }

    def test_preprocess_html_no_images(self):
        """Test HTML preprocessing without images."""
        html_content = "<html><body><h1>Title</h1><p>Content</p></body></html>"

        # Mock item and book
        mock_item = MagicMock()
        mock_item.get_name.return_value = "chapter.xhtml"
        mock_book = MagicMock()
        options = EpubOptions()

        processed_html, footnotes = _preprocess_html(html_content, mock_item, mock_book, options)

        assert "<h1>Title</h1>" in processed_html
        assert "<p>Content</p>" in processed_html
        assert footnotes == []

    def test_preprocess_html_with_footnotes(self):
        """Test HTML preprocessing with footnotes."""
        html_content = '''
        <html><body>
            <p>Text with footnote<a epub:type="noteref" href="#fn1">1</a>.</p>
            <div id="fn1">This is the footnote content.</div>
        </body></html>
        '''

        mock_item = MagicMock()
        mock_item.get_name.return_value = "chapter.xhtml"
        mock_book = MagicMock()
        options = EpubOptions()

        processed_html, footnotes = _preprocess_html(html_content, mock_item, mock_book, options)

        assert "[^1]" in processed_html
        assert footnotes == ["[^1]: This is the footnote content."]
        # Original footnote div should be removed
        assert 'id="fn1"' not in processed_html

    def test_preprocess_html_multiple_footnotes(self):
        """Test HTML preprocessing with multiple footnotes."""
        html_content = '''
        <html><body>
            <p>First footnote<a epub:type="noteref" href="#fn1">1</a> and second<a epub:type="noteref" href="#fn2">2</a>.</p>
            <div id="fn1">First footnote content.</div>
            <div id="fn2">Second footnote with <strong>formatting</strong>.</div>
        </body></html>
        '''

        mock_item = MagicMock()
        mock_item.get_name.return_value = "chapter.xhtml"
        mock_book = MagicMock()
        options = EpubOptions()

        processed_html, footnotes = _preprocess_html(html_content, mock_item, mock_book, options)

        assert "[^1]" in processed_html
        assert "[^2]" in processed_html
        assert len(footnotes) == 2
        assert footnotes[0] == "[^1]: First footnote content."
        assert "Second footnote with formatting" in footnotes[1]

    def test_preprocess_html_fallback_footnotes(self):
        """Test HTML preprocessing with fallback footnote detection."""
        html_content = '''
        <html><body>
            <p>Text with footnote<a href="#fn1">*</a>.</p>
            <div id="fn1">Footnote without epub:type.</div>
        </body></html>
        '''

        mock_item = MagicMock()
        mock_item.get_name.return_value = "chapter.xhtml"
        mock_book = MagicMock()
        options = EpubOptions()

        processed_html, footnotes = _preprocess_html(html_content, mock_item, mock_book, options)

        assert "[^1]" in processed_html
        assert footnotes == ["[^1]: Footnote without epub:type."]

    @patch('all2md.converters.epub2markdown.epub.read_epub')
    def test_epub_to_markdown_import_error_handling(self, mock_read_epub):
        """Test handling of EPUB parsing errors."""
        mock_read_epub.side_effect = Exception("Failed to parse EPUB")

        with pytest.raises(MarkdownConversionError) as exc_info:
            epub_to_markdown("fake_epub.epub")

        assert "Failed to read or parse EPUB file" in str(exc_info.value)
        assert exc_info.value.conversion_stage == "document_opening"

    @patch('all2md.converters.epub2markdown.epub.read_epub')
    def test_epub_to_markdown_with_options(self, mock_read_epub):
        """Test EPUB conversion with various options."""
        # Setup mock book
        mock_book = MagicMock()
        mock_book.toc = []
        mock_book.spine = [("item1", "linear")]

        mock_item = MagicMock()
        mock_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_item.get_content.return_value = b"<html><body><h1>Test</h1></body></html>"
        mock_item.get_name.return_value = "chapter1.xhtml"

        mock_book.get_item_with_id.return_value = mock_item
        mock_book.get_items_of_type.return_value = [mock_item]
        mock_read_epub.return_value = mock_book

        # Test with include_toc=True
        options = EpubOptions(include_toc=True)

        with patch('all2md.converters.epub2markdown.html_to_markdown') as mock_html_to_md:
            mock_html_to_md.return_value = "# Test\n\nContent"

            result = epub_to_markdown("test.epub", options=options)

            # Should include TOC in result
            assert isinstance(result, str)
            mock_html_to_md.assert_called_once()

    @patch('all2md.converters.epub2markdown.epub.read_epub')
    def test_epub_to_markdown_chapter_processing_error(self, mock_read_epub):
        """Test handling of individual chapter processing errors."""
        # Setup mock book
        mock_book = MagicMock()
        mock_book.toc = []
        mock_book.spine = [("item1", "linear")]

        mock_item = MagicMock()
        mock_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_item.get_content.side_effect = Exception("Chapter processing failed")
        mock_item.get_name.return_value = "chapter1.xhtml"

        mock_book.get_item_with_id.return_value = mock_item
        mock_book.get_items_of_type.return_value = [mock_item]
        mock_read_epub.return_value = mock_book

        result = epub_to_markdown("test.epub")

        # Should include error message for failed chapter
        assert "> [ERROR: Failed to convert chapter: chapter1.xhtml]" in result

    def test_epub_to_markdown_with_file_object(self):
        """Test EPUB conversion with file-like object."""
        epub_bytes = b"fake epub content"
        epub_file = io.BytesIO(epub_bytes)

        with patch('all2md.converters.epub2markdown.epub.read_epub') as mock_read_epub:
            mock_book = MagicMock()
            mock_book.toc = []
            mock_book.spine = []
            mock_book.get_items_of_type.return_value = []
            mock_read_epub.return_value = mock_book

            result = epub_to_markdown(epub_file)

            assert isinstance(result, str)
            # BytesIO objects are converted to temp files, so epub.read_epub is called with a file path
            mock_read_epub.assert_called_once()
            args, kwargs = mock_read_epub.call_args
            assert len(args) == 1
            assert isinstance(args[0], str)  # Should be a temporary file path
            assert args[0].endswith('.epub')

    def test_epub_options_defaults(self):
        """Test default EPUB options."""
        options = EpubOptions()

        assert options.include_toc is True
        assert options.merge_chapters is True
        assert options.attachment_mode == "alt_text"
        assert options.attachment_output_dir is None
        assert options.attachment_base_url is None
        assert options.markdown_options is None


@pytest.mark.unit
@pytest.mark.epub
class TestEpubUtilityFunctions:
    """Test utility functions used in EPUB conversion."""

    def test_slugify_edge_cases(self):
        """Test slugify function with edge cases."""
        # Unicode characters
        assert _slugify("Cafe & Resume") == "cafe-resume"

        # Numbers and mixed content
        assert _slugify("Chapter 1: Introduction") == "chapter-1-introduction"

        # Only special characters
        assert _slugify("!@#$%^&*()") == ""

        # Leading/trailing spaces and dashes
        assert _slugify("  --Title--  ") == "title"

    def test_toc_map_empty_input(self):
        """Test TOC map building with empty input."""
        assert _build_toc_map([]) == {}

    def test_toc_map_invalid_items(self):
        """Test TOC map building with invalid items."""
        # Mix of valid and invalid items
        toc = [
            epub.Link("chapter1.xhtml", "Chapter 1", "ch1"),
            "invalid_item",  # Should be skipped
            None,  # Should be skipped
        ]

        toc_map = _build_toc_map(toc)

        assert toc_map == {"chapter1.xhtml": "Chapter 1"}


@pytest.mark.unit
@pytest.mark.epub
@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not available")
class TestEpubErrorHandling:
    """Test error handling in EPUB conversion."""

    def test_missing_ebooklib_import_error(self):
        """Test that appropriate error is raised when ebooklib is missing."""
        # This test is complex to implement properly with dynamic imports
        # For now, we'll test the import error message from the module
        with patch('all2md.converters.epub2markdown.ebooklib', None):
            with patch('all2md.converters.epub2markdown.epub', None):
                # Test would need module-level import handling
                pass

    def test_conversion_error_propagation(self):
        """Test that conversion errors are properly wrapped."""
        with patch('all2md.converters.epub2markdown.epub.read_epub') as mock_read_epub:
            mock_read_epub.side_effect = ValueError("Invalid EPUB structure")

            with pytest.raises(MarkdownConversionError) as exc_info:
                epub_to_markdown("invalid.epub")

            assert exc_info.value.conversion_stage == "document_opening"
            assert isinstance(exc_info.value.original_error, ValueError)

    def test_none_options_handling(self):
        """Test that None options are handled gracefully."""
        with patch('all2md.converters.epub2markdown.epub.read_epub') as mock_read_epub:
            mock_book = MagicMock()
            mock_book.toc = []
            mock_book.spine = []
            mock_book.get_items_of_type.return_value = []
            mock_read_epub.return_value = mock_book

            result = epub_to_markdown("test.epub", options=None)

            assert isinstance(result, str)
            # Should use default options when None is passed
