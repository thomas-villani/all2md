"""Integration tests for Safari WebArchive to Markdown conversion.

This module contains integration tests for the webarchive parser,
testing full conversion pipelines with real WebArchive structures and edge cases.
"""

import io
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
from utils import assert_markdown_valid

from all2md import to_markdown as webarchive_to_markdown
from all2md.exceptions import MalformedFileError, ParsingError, ValidationError
from all2md.options import MarkdownOptions
from all2md.options.webarchive import WebArchiveOptions


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationBasic:
    """Test basic WebArchive integration scenarios."""

    def test_simple_webarchive_conversion(self, temp_dir):
        """Test conversion of a simple WebArchive file."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(str(webarchive_file))

        assert isinstance(result, str)
        assert "Test WebArchive Document" in result
        assert "**bold**" in result
        assert "*italic*" in result
        assert "[link](https://example.com)" in result
        assert "* First item" in result
        assert "* Second item" in result
        assert "* Third item" in result
        assert_markdown_valid(result)

    def test_simple_webarchive_with_bytesio(self):
        """Test conversion of WebArchive from BytesIO."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = io.BytesIO(webarchive_content)

        result = webarchive_to_markdown(webarchive_file, source_format="webarchive")

        assert isinstance(result, str)
        assert "Test WebArchive Document" in result
        assert "**bold**" in result
        assert_markdown_valid(result)

    def test_simple_webarchive_with_pathlib_path(self, temp_dir):
        """Test conversion with pathlib.Path object."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(Path(webarchive_file))

        assert isinstance(result, str)
        assert "Test WebArchive Document" in result
        assert_markdown_valid(result)

    def test_simple_webarchive_with_string_path(self, temp_dir):
        """Test conversion with string path."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(str(webarchive_file))

        assert isinstance(result, str)
        assert "Test WebArchive Document" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationImages:
    """Test WebArchive integration with image handling."""

    def test_webarchive_with_image_base64(self, temp_dir):
        """Test WebArchive with images using base64 embedding."""
        webarchive_content = create_webarchive_with_image()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        options = WebArchiveOptions(attachment_mode="base64")
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test WebArchive with Image" in result
        # Base64 data URLs may be blocked, so check for alt text
        assert "![Test image]" in result
        assert_markdown_valid(result)

    def test_webarchive_with_image_skip(self, temp_dir):
        """Test WebArchive with images using skip mode."""
        webarchive_content = create_webarchive_with_image()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        options = WebArchiveOptions(attachment_mode="skip")
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test WebArchive with Image" in result
        assert_markdown_valid(result)

    def test_webarchive_with_image_extract_resources(self, temp_dir):
        """Test WebArchive with resource extraction enabled."""
        webarchive_content = create_webarchive_with_image()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        image_dir = temp_dir / "images"
        options = WebArchiveOptions(extract_subresources=True, attachment_output_dir=str(image_dir))
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test WebArchive with Image" in result
        # Should have extracted the image
        assert image_dir.exists()
        extracted_files = list(image_dir.glob("*.png"))
        assert len(extracted_files) > 0
        assert_markdown_valid(result)

    def test_webarchive_with_multiple_assets(self, temp_dir):
        """Test WebArchive with multiple embedded assets."""
        webarchive_content = create_webarchive_with_multiple_assets()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        resource_dir = temp_dir / "resources"
        options = WebArchiveOptions(extract_subresources=True, attachment_output_dir=str(resource_dir))
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "WebArchive with Multiple Assets" in result
        # Should have extracted multiple resources
        assert resource_dir.exists()
        extracted_files = list(resource_dir.glob("*"))
        assert len(extracted_files) >= 2  # At least 2 images
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationSubframes:
    """Test WebArchive integration with subframe handling."""

    def test_webarchive_with_subframes_enabled(self, temp_dir):
        """Test WebArchive with subframes when enabled."""
        webarchive_content = create_webarchive_with_subframes()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        options = WebArchiveOptions(handle_subframes=True)
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "Main Document" in result
        # Should include nested frame content
        assert "Nested Frame" in result
        assert "Frame Content" in result
        assert "inside the nested frame" in result
        assert_markdown_valid(result)

    def test_webarchive_with_subframes_disabled(self, temp_dir):
        """Test WebArchive with subframes when disabled."""
        webarchive_content = create_webarchive_with_subframes()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        options = WebArchiveOptions(handle_subframes=False)
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert "Main Document" in result
        # Should NOT include nested frame content
        assert "inside the nested frame" not in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationComplexStructure:
    """Test WebArchive integration with complex HTML structures."""

    def test_webarchive_with_complex_html(self, temp_dir):
        """Test WebArchive with complex HTML structure."""
        webarchive_content = create_webarchive_with_complex_html()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(str(webarchive_file))

        assert isinstance(result, str)
        assert "Complex WebArchive Document" in result
        # Should handle various HTML elements
        assert "Centered Section" in result
        assert "> This is a blockquote" in result
        assert "```" in result or "    " in result  # Code blocks
        assert "function example()" in result
        # Nested lists
        assert "First item" in result
        assert "Nested item 1" in result
        # Complex table
        assert "Header 1" in result
        assert "Sub Header 1" in result
        assert "Row 1 Cell 1" in result
        assert_markdown_valid(result)

    def test_webarchive_table_processing(self, temp_dir):
        """Test WebArchive table processing specifically."""
        webarchive_content = create_webarchive_with_complex_html()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(str(webarchive_file))

        assert isinstance(result, str)
        # Should contain table structure
        assert "|" in result  # Markdown table syntax
        # Should have table content
        assert "Header 1" in result
        assert "Header Group" in result
        assert "Row 1 Cell 1" in result
        assert "Merged cells content" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationErrorHandling:
    """Test WebArchive integration error handling scenarios."""

    def test_nonexistent_file(self):
        """Test handling of nonexistent WebArchive file."""
        with pytest.raises((MalformedFileError, ParsingError)):
            webarchive_to_markdown("nonexistent.webarchive")

    def test_malformed_webarchive_file(self, temp_dir):
        """Test handling of malformed WebArchive file."""
        malformed_content = create_malformed_webarchive()
        webarchive_file = create_webarchive_file(malformed_content, temp_dir)

        with pytest.raises(ParsingError) as exc_info:
            webarchive_to_markdown(str(webarchive_file))

        assert "WebMainResource" in str(exc_info.value)

    def test_invalid_plist_file(self, temp_dir):
        """Test handling of invalid plist file."""
        invalid_content = create_invalid_plist()
        webarchive_file = create_webarchive_file(invalid_content, temp_dir)

        with pytest.raises((MalformedFileError, ParsingError)):
            webarchive_to_markdown(str(webarchive_file))

    def test_empty_webarchive_file(self, temp_dir):
        """Test handling of empty WebArchive file."""
        empty_file = temp_dir / "empty.webarchive"
        empty_file.write_bytes(b"")

        with pytest.raises((ParsingError, MalformedFileError)):
            webarchive_to_markdown(empty_file)

    def test_invalid_input_type(self):
        """Test handling of invalid input types."""
        with pytest.raises((MalformedFileError, AttributeError, TypeError, ValidationError)):
            webarchive_to_markdown(123)  # Invalid type

    def test_directory_instead_of_file(self, temp_dir):
        """Test handling when directory is passed instead of file."""
        with pytest.raises((MalformedFileError, ParsingError, PermissionError, ValidationError)):
            webarchive_to_markdown(temp_dir)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationOptions:
    """Test WebArchive integration with various option configurations."""

    def test_webarchive_with_custom_markdown_options(self, temp_dir):
        """Test WebArchive conversion with custom Markdown options."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        md_options = MarkdownOptions(emphasis_symbol="_", bullet_symbols="+-*")
        parser_options = WebArchiveOptions()
        result = webarchive_to_markdown(webarchive_file, parser_options=parser_options, renderer_options=md_options)

        assert isinstance(result, str)
        # Should use custom emphasis symbol
        assert "_italic_" in result or "__bold__" in result
        assert_markdown_valid(result)

    def test_webarchive_options_inheritance(self, temp_dir):
        """Test that WebArchive options properly inherit from HTML options."""
        webarchive_content = create_simple_webarchive()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        options = WebArchiveOptions(extract_title=True, strip_dangerous_elements=True, extract_subresources=False)
        result = webarchive_to_markdown(webarchive_file, parser_options=options)

        assert isinstance(result, str)
        assert_markdown_valid(result)

    def test_all_option_combinations(self, temp_dir):
        """Test various option combinations work correctly."""
        webarchive_content = create_webarchive_with_image()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        option_combinations = [
            (WebArchiveOptions(), None),  # Default options
            (WebArchiveOptions(extract_subresources=True, attachment_output_dir=str(temp_dir / "res1")), None),
            (WebArchiveOptions(handle_subframes=False), None),
            (WebArchiveOptions(extract_title=True), None),
            (
                WebArchiveOptions(extract_subresources=True, attachment_output_dir=str(temp_dir / "res2")),
                MarkdownOptions(emphasis_symbol="_"),
            ),
        ]

        for parser_options, renderer_options in option_combinations:
            result = webarchive_to_markdown(
                webarchive_file, parser_options=parser_options, renderer_options=renderer_options
            )

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
class TestWebArchiveIntegrationEncoding:
    """Test WebArchive integration with different character encodings."""

    def test_webarchive_non_utf8_encoding(self, temp_dir):
        """Test WebArchive with non-UTF-8 encoded content."""
        webarchive_content = create_webarchive_with_different_encoding()
        webarchive_file = create_webarchive_file(webarchive_content, temp_dir)

        result = webarchive_to_markdown(str(webarchive_file))

        assert isinstance(result, str)
        assert "Test Encoding" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.webarchive
@pytest.mark.slow
class TestWebArchiveIntegrationPerformance:
    """Test WebArchive integration performance scenarios."""

    def test_large_webarchive_performance(self, temp_dir):
        """Test performance with larger WebArchive structures."""
        # Use complex WebArchive for performance testing
        webarchive_content = create_webarchive_with_complex_html()

        # Test multiple times to check for consistency
        for _i in range(3):
            webarchive_file = create_webarchive_file(webarchive_content, temp_dir)
            result = webarchive_to_markdown(str(webarchive_file))

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)

    def test_multiple_webarchive_conversions(self, temp_dir):
        """Test multiple WebArchive conversions in sequence."""
        results = []

        # Convert different WebArchive types
        webarchive_generators = [
            create_simple_webarchive,
            create_webarchive_with_image,
            create_webarchive_with_subframes,
            create_webarchive_with_complex_html,
        ]

        for webarchive_generator in webarchive_generators:
            webarchive_content = webarchive_generator()
            webarchive_file = create_webarchive_file(webarchive_content, temp_dir)
            result = webarchive_to_markdown(str(webarchive_file))

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)
            results.append(result)

        # Verify all conversions were different
        assert len(set(results)) == len(results)

    def test_repeated_resource_processing(self, temp_dir):
        """Test performance with repeated resource processing."""
        webarchive_content = create_webarchive_with_multiple_assets()

        # Convert same file multiple times
        for _i in range(3):
            webarchive_file = create_webarchive_file(webarchive_content, temp_dir)
            resource_dir = temp_dir / f"resources_{_i}"
            options = WebArchiveOptions(extract_subresources=True, attachment_output_dir=str(resource_dir))
            result = webarchive_to_markdown(webarchive_file, parser_options=options)

            assert isinstance(result, str)
            assert_markdown_valid(result)
