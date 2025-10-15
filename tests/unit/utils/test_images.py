#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for image handling utilities.

This module tests the image data URI parsing and decoding functions in
all2md.utils.images, including SVG support and parameter handling.
"""

import base64

from all2md.utils.images import decode_base64_image, parse_image_data_uri


class TestDecodeBase64Image:
    """Test suite for decode_base64_image function."""

    def test_simple_png_data_uri(self):
        """Test decoding a simple PNG data URI."""
        # Create a minimal valid PNG (1x1 transparent pixel)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode('utf-8')
        data_uri = f"data:image/png;base64,{b64_str}"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is not None
        assert fmt == "png"
        assert len(image_bytes) > 0

    def test_svg_xml_data_uri(self):
        """Test decoding SVG data URI with image/svg+xml MIME type."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        b64_data = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        data_uri = f"data:image/svg+xml;base64,{b64_data}"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is not None
        assert fmt == "svg"
        assert b'<svg' in image_bytes

    def test_jpeg_data_uri(self):
        """Test decoding JPEG data URI."""
        # Use a small valid JPEG (just the header)
        jpeg_data = base64.b64decode("/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBw==")
        b64_str = base64.b64encode(jpeg_data).decode('utf-8')
        data_uri = f"data:image/jpeg;base64,{b64_str}"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is not None
        assert fmt == "jpg"

    def test_invalid_base64_returns_none(self):
        """Test that invalid base64 data returns None."""
        data_uri = "data:image/png;base64,invalid!!!base64"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is None
        assert fmt is None

    def test_missing_mime_type_returns_none(self):
        """Test that data URI without proper MIME type returns None."""
        data_uri = "data:text/plain;base64,SGVsbG8="

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is None
        assert fmt is None

    def test_unsupported_format_returns_none(self):
        """Test that unsupported image format returns None."""
        data_uri = "data:image/unknown;base64,AQIDBA=="

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is None
        assert fmt is None

    def test_empty_data_uri_returns_none(self):
        """Test that empty data URI returns None."""
        image_bytes, fmt = decode_base64_image("")

        assert image_bytes is None
        assert fmt is None

    def test_non_string_input_returns_none(self):
        """Test that non-string input returns None."""
        image_bytes, fmt = decode_base64_image(None)  # type: ignore

        assert image_bytes is None
        assert fmt is None


class TestParseImageDataUri:
    """Test suite for parse_image_data_uri function."""

    def test_simple_png_data_uri(self):
        """Test parsing a simple PNG data URI."""
        data_uri = "data:image/png;base64,iVBORw0KG"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['mime_type'] == "image/png"
        assert result['format'] == "png"
        assert result['encoding'] == "base64"
        assert result['data'] == "iVBORw0KG"

    def test_svg_xml_data_uri(self):
        """Test parsing SVG data URI with image/svg+xml."""
        data_uri = "data:image/svg+xml;base64,PHN2Zz4="

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['mime_type'] == "image/svg+xml"
        assert result['format'] == "svg"
        assert result['encoding'] == "base64"

    def test_data_uri_with_charset(self):
        """Test parsing data URI with charset parameter."""
        data_uri = "data:text/plain;charset=utf-8;base64,SGVsbG8="

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['mime_type'] == "text/plain"
        assert result['encoding'] == "base64"
        assert result['charset'] == "utf-8"
        assert "charset=utf-8" in result['params']

    def test_data_uri_without_base64(self):
        """Test parsing data URI without base64 encoding."""
        data_uri = "data:text/plain,Hello%20World"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['mime_type'] == "text/plain"
        assert result['encoding'] == "url"
        assert result['data'] == "Hello%20World"

    def test_data_uri_with_multiple_parameters(self):
        """Test parsing data URI with multiple parameters."""
        data_uri = "data:image/png;name=test.png;base64,iVBORw0KG"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['mime_type'] == "image/png"
        assert result['encoding'] == "base64"
        assert len(result['params']) == 2
        assert "base64" in result['params']

    def test_malformed_data_uri_returns_none(self):
        """Test that malformed data URI returns None."""
        data_uri = "not a data uri"

        result = parse_image_data_uri(data_uri)

        assert result is None

    def test_empty_data_uri_returns_none(self):
        """Test that empty data URI returns None."""
        result = parse_image_data_uri("")

        assert result is None

    def test_jpeg_format_mapping(self):
        """Test that image/jpeg is mapped to jpg format."""
        data_uri = "data:image/jpeg;base64,/9j/4AAQ"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result['format'] == "jpg"
