#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_webarchive_parser.py
"""Unit tests for Safari WebArchive to AST converter.

Tests cover:
- Basic HTML extraction from plist
- Metadata extraction (URL, MIME type, encoding)
- Subresource extraction
- Nested iframe/subframe handling
- Error handling for malformed files
- Different text encodings
"""

import tempfile
from pathlib import Path

import pytest
from fixtures.generators.webarchive_fixtures import (
    create_invalid_plist,
    create_malformed_webarchive,
    create_simple_webarchive,
    create_webarchive_file,
    create_webarchive_with_complex_html,
    create_webarchive_with_different_encoding,
    create_webarchive_with_image,
    create_webarchive_with_multiple_assets,
    create_webarchive_with_subframes,
)

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.exceptions import MalformedFileError, ParsingError
from all2md.options.webarchive import WebArchiveOptions
from all2md.parsers.webarchive import WebArchiveToAstConverter


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic WebArchive conversion."""

    def test_simple_webarchive_bytes(self) -> None:
        """Test converting a simple WebArchive from bytes."""
        webarchive_bytes = create_simple_webarchive()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should contain the heading
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0
        assert any("Test WebArchive Document" in str(h.content[0].content) for h in headings)

    def test_simple_webarchive_file(self) -> None:
        """Test converting a simple WebArchive from file path."""
        webarchive_bytes = create_simple_webarchive()

        with tempfile.TemporaryDirectory() as temp_dir:
            webarchive_file = create_webarchive_file(webarchive_bytes, Path(temp_dir))
            converter = WebArchiveToAstConverter()
            doc = converter.parse(str(webarchive_file))

            assert isinstance(doc, Document)
            assert len(doc.children) > 0

    def test_simple_webarchive_file_object(self) -> None:
        """Test converting a simple WebArchive from file-like object."""
        webarchive_bytes = create_simple_webarchive()

        with tempfile.TemporaryDirectory() as temp_dir:
            webarchive_file = create_webarchive_file(webarchive_bytes, Path(temp_dir))

            with open(webarchive_file, "rb") as f:
                converter = WebArchiveToAstConverter()
                doc = converter.parse(f)

                assert isinstance(doc, Document)
                assert len(doc.children) > 0


@pytest.mark.unit
class TestMetadataExtraction:
    """Tests for metadata extraction from WebArchive."""

    def test_metadata_url_extraction(self) -> None:
        """Test URL extraction from WebMainResource."""
        webarchive_bytes = create_simple_webarchive()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert "url" in doc.metadata
        assert "example.com" in doc.metadata["url"]

    def test_metadata_mime_type(self) -> None:
        """Test MIME type extraction."""
        webarchive_bytes = create_simple_webarchive()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert "mime_type" in doc.metadata
        assert doc.metadata["mime_type"] == "text/html"

    def test_metadata_encoding(self) -> None:
        """Test encoding extraction."""
        webarchive_bytes = create_simple_webarchive()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert "encoding" in doc.metadata
        assert doc.metadata["encoding"] == "UTF-8"

    def test_metadata_title_from_html(self) -> None:
        """Test title extraction from HTML content."""
        webarchive_bytes = create_simple_webarchive()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert doc.metadata.get("title") is not None
        assert "Test WebArchive Document" in doc.metadata["title"]

    def test_metadata_subresource_count(self) -> None:
        """Test subresource count in metadata."""
        webarchive_bytes = create_webarchive_with_image()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert "subresource_count" in doc.metadata
        assert doc.metadata["subresource_count"] == 1

    def test_metadata_subframe_count(self) -> None:
        """Test subframe count in metadata."""
        webarchive_bytes = create_webarchive_with_subframes()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert "subframe_count" in doc.metadata
        assert doc.metadata["subframe_count"] == 1


@pytest.mark.unit
class TestSubresourceExtraction:
    """Tests for embedded resource extraction."""

    def test_extract_subresources_disabled(self) -> None:
        """Test that subresources are not extracted when disabled."""
        webarchive_bytes = create_webarchive_with_image()
        options = WebArchiveOptions(extract_subresources=False)
        converter = WebArchiveToAstConverter(options)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Even with output dir set, should not extract when disabled
            options = WebArchiveOptions(extract_subresources=False, attachment_output_dir=temp_dir)
            converter = WebArchiveToAstConverter(options)
            _ = converter.parse(webarchive_bytes)

            # Check that no files were created
            extracted_files = list(Path(temp_dir).glob("*"))
            assert len(extracted_files) == 0

    def test_extract_subresources_enabled(self) -> None:
        """Test that subresources are extracted when enabled."""
        webarchive_bytes = create_webarchive_with_image()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = WebArchiveOptions(extract_subresources=True, attachment_output_dir=temp_dir)
            converter = WebArchiveToAstConverter(options)
            _ = converter.parse(webarchive_bytes)

            # Check that image was extracted
            extracted_files = list(Path(temp_dir).glob("*.png"))
            assert len(extracted_files) == 1
            assert extracted_files[0].name == "test_image.png"

    def test_extract_multiple_subresources(self) -> None:
        """Test extraction of multiple subresources."""
        webarchive_bytes = create_webarchive_with_multiple_assets()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = WebArchiveOptions(extract_subresources=True, attachment_output_dir=temp_dir)
            converter = WebArchiveToAstConverter(options)
            _ = converter.parse(webarchive_bytes)

            # Check that all resources were extracted
            extracted_files = list(Path(temp_dir).glob("*"))
            assert len(extracted_files) == 3  # 2 images + 1 CSS file

            # Check specific files
            assert (Path(temp_dir) / "image1.png").exists()
            assert (Path(temp_dir) / "image2.png").exists()
            assert (Path(temp_dir) / "styles.css").exists()


@pytest.mark.unit
class TestSubframeHandling:
    """Tests for nested iframe/subframe handling."""

    def test_handle_subframes_enabled(self) -> None:
        """Test that subframes are processed when enabled."""
        webarchive_bytes = create_webarchive_with_subframes()
        options = WebArchiveOptions(handle_subframes=True)
        converter = WebArchiveToAstConverter(options)
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)

        # Should contain heading for the nested frame
        headings = [child for child in doc.children if isinstance(child, Heading)]
        frame_headings = [h for h in headings if "Nested Frame" in str(h.content[0].content)]
        assert len(frame_headings) > 0

        # Should contain frame content
        paragraphs = [child for child in doc.children if isinstance(child, Paragraph)]
        frame_content_found = False
        for p in paragraphs:
            for content in p.content:
                if isinstance(content, Text) and "inside the nested frame" in content.content:
                    frame_content_found = True
                    break
        assert frame_content_found

    def test_handle_subframes_disabled(self) -> None:
        """Test that subframes are skipped when disabled."""
        webarchive_bytes = create_webarchive_with_subframes()
        options = WebArchiveOptions(handle_subframes=False)
        converter = WebArchiveToAstConverter(options)
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)

        # Should NOT contain heading for the nested frame
        headings = [child for child in doc.children if isinstance(child, Heading)]
        frame_headings = [h for h in headings if "Nested Frame" in str(h.content[0].content)]
        assert len(frame_headings) == 0

        # Should NOT contain frame-specific content
        paragraphs = [child for child in doc.children if isinstance(child, Paragraph)]
        for p in paragraphs:
            for content in p.content:
                if isinstance(content, Text):
                    assert "inside the nested frame" not in content.content


@pytest.mark.unit
class TestComplexHTML:
    """Tests for complex HTML structures."""

    def test_complex_html_conversion(self) -> None:
        """Test conversion of WebArchive with complex HTML."""
        webarchive_bytes = create_webarchive_with_complex_html()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should contain main heading
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert any("Complex WebArchive Document" in str(h.content[0].content) for h in headings)


@pytest.mark.unit
class TestEncodingHandling:
    """Tests for different text encodings."""

    def test_non_utf8_encoding(self) -> None:
        """Test handling of non-UTF-8 encoded content."""
        webarchive_bytes = create_webarchive_with_different_encoding()
        converter = WebArchiveToAstConverter()
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling."""

    def test_malformed_webarchive_missing_main_resource(self) -> None:
        """Test error handling for WebArchive without WebMainResource."""
        webarchive_bytes = create_malformed_webarchive()
        converter = WebArchiveToAstConverter()

        with pytest.raises(ParsingError) as exc_info:
            converter.parse(webarchive_bytes)

        assert "WebMainResource" in str(exc_info.value)

    def test_invalid_plist_format(self) -> None:
        """Test error handling for invalid plist format."""
        invalid_bytes = create_invalid_plist()
        converter = WebArchiveToAstConverter()

        with pytest.raises((MalformedFileError, ParsingError)):
            converter.parse(invalid_bytes)

    def test_missing_html_content(self) -> None:
        """Test error handling when HTML content is missing."""
        import plistlib

        # Create WebArchive with WebMainResource but no WebResourceData
        archive_data = {
            "WebMainResource": {
                "WebResourceMIMEType": "text/html",
                "WebResourceURL": "http://example.com/test.html",
            }
        }
        webarchive_bytes = plistlib.dumps(archive_data, fmt=plistlib.FMT_BINARY)

        converter = WebArchiveToAstConverter()

        with pytest.raises(ParsingError) as exc_info:
            converter.parse(webarchive_bytes)

        assert "WebResourceData" in str(exc_info.value)


@pytest.mark.unit
class TestOptionsHandling:
    """Tests for WebArchive-specific options."""

    def test_options_extract_title_inherited(self) -> None:
        """Test that HTML options are inherited (extract_title)."""
        webarchive_bytes = create_simple_webarchive()

        # With extract_title=True
        options = WebArchiveOptions(extract_title=True)
        converter = WebArchiveToAstConverter(options)
        doc = converter.parse(webarchive_bytes)

        # First child should be title heading
        assert len(doc.children) > 0
        if isinstance(doc.children[0], Heading):
            assert doc.children[0].level == 1

    def test_options_attachment_mode_inherited(self) -> None:
        """Test that HTML attachment options are inherited."""
        webarchive_bytes = create_webarchive_with_image()

        # Test with skip mode
        options = WebArchiveOptions(attachment_mode="skip")
        converter = WebArchiveToAstConverter(options)
        doc = converter.parse(webarchive_bytes)

        assert isinstance(doc, Document)
