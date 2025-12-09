#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for image handling utilities.

This module tests the image data URI parsing and decoding functions in
all2md.utils.images, including SVG support and parameter handling.
"""

import base64
from pathlib import Path

from all2md.utils.images import (
    decode_base64_image,
    decode_base64_image_to_file,
    detect_image_format_from_bytes,
    get_image_format_from_path,
    is_data_uri,
    parse_image_data_uri,
)


class TestDecodeBase64Image:
    """Test suite for decode_base64_image function."""

    def test_simple_png_data_uri(self):
        """Test decoding a simple PNG data URI."""
        # Create a minimal valid PNG (1x1 transparent pixel)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is not None
        assert fmt == "png"
        assert len(image_bytes) > 0

    def test_svg_xml_data_uri(self):
        """Test decoding SVG data URI with image/svg+xml MIME type."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        b64_data = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        data_uri = f"data:image/svg+xml;base64,{b64_data}"

        image_bytes, fmt = decode_base64_image(data_uri)

        assert image_bytes is not None
        assert fmt == "svg"
        assert b"<svg" in image_bytes

    def test_jpeg_data_uri(self):
        """Test decoding JPEG data URI."""
        # Use a small valid JPEG (just the header)
        jpeg_data = base64.b64decode("/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBw==")
        b64_str = base64.b64encode(jpeg_data).decode("utf-8")
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
        assert result["mime_type"] == "image/png"
        assert result["format"] == "png"
        assert result["encoding"] == "base64"
        assert result["data"] == "iVBORw0KG"

    def test_svg_xml_data_uri(self):
        """Test parsing SVG data URI with image/svg+xml."""
        data_uri = "data:image/svg+xml;base64,PHN2Zz4="

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result["mime_type"] == "image/svg+xml"
        assert result["format"] == "svg"
        assert result["encoding"] == "base64"

    def test_data_uri_with_charset(self):
        """Test parsing data URI with charset parameter."""
        data_uri = "data:text/plain;charset=utf-8;base64,SGVsbG8="

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result["mime_type"] == "text/plain"
        assert result["encoding"] == "base64"
        assert result["charset"] == "utf-8"
        assert "charset=utf-8" in result["params"]

    def test_data_uri_without_base64(self):
        """Test parsing data URI without base64 encoding."""
        data_uri = "data:text/plain,Hello%20World"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result["mime_type"] == "text/plain"
        assert result["encoding"] == "url"
        assert result["data"] == "Hello%20World"

    def test_data_uri_with_multiple_parameters(self):
        """Test parsing data URI with multiple parameters."""
        data_uri = "data:image/png;name=test.png;base64,iVBORw0KG"

        result = parse_image_data_uri(data_uri)

        assert result is not None
        assert result["mime_type"] == "image/png"
        assert result["encoding"] == "base64"
        assert len(result["params"]) == 2
        assert "base64" in result["params"]

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
        assert result["format"] == "jpg"


class TestDecodeBase64ImageToFile:
    """Test suite for decode_base64_image_to_file function."""

    def test_decode_png_to_file(self):
        """Test decoding PNG data URI to temporary file."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        temp_path = decode_base64_image_to_file(data_uri, delete_on_exit=False)

        try:
            assert temp_path is not None
            assert Path(temp_path).exists()
            assert temp_path.endswith(".png")

            # Verify content
            with open(temp_path, "rb") as f:
                content = f.read()
            assert content == png_data
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def test_decode_to_custom_directory(self, tmp_path):
        """Test decoding to custom output directory."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        temp_path = decode_base64_image_to_file(data_uri, output_dir=tmp_path, delete_on_exit=False)

        try:
            assert temp_path is not None
            assert str(tmp_path) in temp_path
            assert Path(temp_path).exists()
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def test_decode_svg_to_file(self):
        """Test decoding SVG data URI to file."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>'
        b64_data = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        data_uri = f"data:image/svg+xml;base64,{b64_data}"

        temp_path = decode_base64_image_to_file(data_uri, delete_on_exit=False)

        try:
            assert temp_path is not None
            assert temp_path.endswith(".svg")
            assert Path(temp_path).exists()

            with open(temp_path, "rb") as f:
                content = f.read()
            assert b"<svg" in content
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def test_invalid_data_uri_returns_none(self):
        """Test that invalid data URI returns None."""
        result = decode_base64_image_to_file("data:image/png;base64,invalid!!!")
        assert result is None

    def test_empty_data_uri_returns_none(self):
        """Test that empty data URI returns None."""
        result = decode_base64_image_to_file("")
        assert result is None

    def test_delete_on_exit_default(self):
        """Test that delete_on_exit defaults to True."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        # With default delete_on_exit=True, file should be created
        temp_path = decode_base64_image_to_file(data_uri)

        assert temp_path is not None
        assert Path(temp_path).exists()
        # Cleanup manually since we're not exiting Python
        Path(temp_path).unlink(missing_ok=True)

    def test_multiple_formats(self):
        """Test decoding multiple image formats to files."""
        formats = {
            "jpg": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBw==",
            "gif": "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
            "webp": "UklGRh4AAABXRUJQVlA4TBEAAAAvAAAAAAfQ//73v/+BiOh/AAA=",
        }

        for ext, b64_data in formats.items():
            mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
            data_uri = f"data:{mime};base64,{b64_data}"

            temp_path = decode_base64_image_to_file(data_uri, delete_on_exit=False)

            try:
                assert temp_path is not None
                assert temp_path.endswith(f".{ext}")
                assert Path(temp_path).exists()
            finally:
                if temp_path:
                    Path(temp_path).unlink(missing_ok=True)


class TestIsDataUri:
    """Test suite for is_data_uri function."""

    def test_valid_data_uri_returns_true(self):
        """Test that valid data URI returns True."""
        assert is_data_uri("data:image/png;base64,iVBORw0KG") is True

    def test_http_url_returns_false(self):
        """Test that HTTP URL returns False."""
        assert is_data_uri("http://example.com/image.png") is False

    def test_https_url_returns_false(self):
        """Test that HTTPS URL returns False."""
        assert is_data_uri("https://example.com/image.png") is False

    def test_file_path_returns_false(self):
        """Test that file path returns False."""
        assert is_data_uri("/path/to/file.png") is False

    def test_empty_string_returns_false(self):
        """Test that empty string returns False."""
        assert is_data_uri("") is False

    def test_none_returns_false(self):
        """Test that None returns False."""
        assert is_data_uri(None) is False  # type: ignore

    def test_data_uri_without_mime_type(self):
        """Test data URI without MIME type."""
        assert is_data_uri("data:,Hello") is True

    def test_data_uri_text_plain(self):
        """Test text/plain data URI."""
        assert is_data_uri("data:text/plain;base64,SGVsbG8=") is True

    def test_non_string_input(self):
        """Test that non-string input returns False."""
        assert is_data_uri(12345) is False  # type: ignore
        assert is_data_uri([]) is False  # type: ignore


class TestDetectImageFormatFromBytes:
    """Test suite for detect_image_format_from_bytes function."""

    def test_detect_png(self):
        """Test PNG format detection."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        assert detect_image_format_from_bytes(png_bytes) == "png"

    def test_detect_jpeg(self):
        """Test JPEG format detection."""
        jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 29
        assert detect_image_format_from_bytes(jpeg_bytes) == "jpg"

    def test_detect_gif87a(self):
        """Test GIF87a format detection."""
        gif_bytes = b"GIF87a" + b"\x00" * 26
        assert detect_image_format_from_bytes(gif_bytes) == "gif"

    def test_detect_gif89a(self):
        """Test GIF89a format detection."""
        gif_bytes = b"GIF89a" + b"\x00" * 26
        assert detect_image_format_from_bytes(gif_bytes) == "gif"

    def test_detect_webp(self):
        """Test WebP format detection."""
        webp_bytes = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 20
        assert detect_image_format_from_bytes(webp_bytes) == "webp"

    def test_detect_bmp(self):
        """Test BMP format detection."""
        bmp_bytes = b"BM" + b"\x00" * 30
        assert detect_image_format_from_bytes(bmp_bytes) == "bmp"

    def test_detect_tiff_little_endian(self):
        """Test TIFF little-endian format detection."""
        tiff_bytes = b"II*\x00" + b"\x00" * 28
        assert detect_image_format_from_bytes(tiff_bytes) == "tiff"

    def test_detect_tiff_big_endian(self):
        """Test TIFF big-endian format detection."""
        tiff_bytes = b"MM\x00*" + b"\x00" * 28
        assert detect_image_format_from_bytes(tiff_bytes) == "tiff"

    def test_detect_ico(self):
        """Test ICO format detection."""
        ico_bytes = b"\x00\x00\x01\x00" + b"\x00" * 28
        assert detect_image_format_from_bytes(ico_bytes) == "ico"

    def test_detect_svg_with_svg_tag(self):
        """Test SVG format detection with <svg tag."""
        svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'>"
        assert detect_image_format_from_bytes(svg_bytes) == "svg"

    def test_detect_svg_with_xml_declaration(self):
        """Test SVG format detection with <?xml declaration."""
        svg_bytes = b"<?xml version='1.0'?><svg>"
        assert detect_image_format_from_bytes(svg_bytes) == "svg"

    def test_detect_svg_with_leading_whitespace(self):
        """Test SVG format detection with leading whitespace."""
        svg_bytes = b"  \n  <svg xmlns='http://www.w3.org/2000/svg'>"
        assert detect_image_format_from_bytes(svg_bytes) == "svg"

    def test_unknown_format_returns_none(self):
        """Test that unknown format returns None."""
        unknown_bytes = b"UNKNOWN" + b"\x00" * 25
        assert detect_image_format_from_bytes(unknown_bytes) is None

    def test_too_short_data_returns_none(self):
        """Test that too short data returns None."""
        assert detect_image_format_from_bytes(b"ABC") is None

    def test_empty_data_returns_none(self):
        """Test that empty data returns None."""
        assert detect_image_format_from_bytes(b"") is None

    def test_none_data_returns_none(self):
        """Test that None data returns None."""
        assert detect_image_format_from_bytes(None) is None  # type: ignore

    def test_real_png_bytes(self):
        """Test with real PNG data."""
        real_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        assert detect_image_format_from_bytes(real_png) == "png"


class TestGetImageFormatFromPath:
    """Test suite for get_image_format_from_path function."""

    def test_png_extension(self):
        """Test PNG file extension."""
        assert get_image_format_from_path("image.png") == "png"

    def test_jpg_extension(self):
        """Test JPG file extension."""
        assert get_image_format_from_path("photo.jpg") == "jpg"

    def test_jpeg_extension(self):
        """Test JPEG file extension."""
        assert get_image_format_from_path("photo.jpeg") == "jpeg"

    def test_gif_extension(self):
        """Test GIF file extension."""
        assert get_image_format_from_path("animation.gif") == "gif"

    def test_svg_extension(self):
        """Test SVG file extension."""
        assert get_image_format_from_path("icon.svg") == "svg"

    def test_webp_extension(self):
        """Test WebP file extension."""
        assert get_image_format_from_path("modern.webp") == "webp"

    def test_bmp_extension(self):
        """Test BMP file extension."""
        assert get_image_format_from_path("bitmap.bmp") == "bmp"

    def test_tiff_extension(self):
        """Test TIFF file extension."""
        assert get_image_format_from_path("scan.tiff") == "tiff"

    def test_tif_extension(self):
        """Test TIF file extension."""
        assert get_image_format_from_path("scan.tif") == "tif"

    def test_ico_extension(self):
        """Test ICO file extension."""
        assert get_image_format_from_path("favicon.ico") == "ico"

    def test_uppercase_extension(self):
        """Test uppercase extension is handled."""
        assert get_image_format_from_path("IMAGE.PNG") == "png"

    def test_mixed_case_extension(self):
        """Test mixed case extension is handled."""
        assert get_image_format_from_path("photo.JpG") == "jpg"

    def test_path_object(self):
        """Test with Path object."""
        assert get_image_format_from_path(Path("image.png")) == "png"

    def test_non_image_extension(self):
        """Test non-image file returns None."""
        assert get_image_format_from_path("document.pdf") is None

    def test_text_file(self):
        """Test text file returns None."""
        assert get_image_format_from_path("readme.txt") is None

    def test_no_extension(self):
        """Test file without extension returns None."""
        assert get_image_format_from_path("filename") is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert get_image_format_from_path("") is None

    def test_none_input(self):
        """Test None input returns None."""
        assert get_image_format_from_path(None) is None  # type: ignore

    def test_complex_path(self):
        """Test complex file path."""
        assert get_image_format_from_path("/path/to/images/photo.jpg") == "jpg"

    def test_windows_path(self):
        """Test Windows-style path."""
        assert get_image_format_from_path("C:\\Users\\Images\\photo.png") == "png"

    def test_dot_in_filename(self):
        """Test filename with multiple dots."""
        assert get_image_format_from_path("my.image.file.png") == "png"


class TestEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_decode_and_detect_format_consistency(self):
        """Test that decoded image bytes match detected format."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        # Decode from data URI
        image_bytes, fmt = decode_base64_image(data_uri)

        # Detect from bytes
        detected_fmt = detect_image_format_from_bytes(image_bytes)

        assert fmt == "png"
        assert detected_fmt == "png"

    def test_workflow_decode_to_file_and_read_format(self):
        """Test complete workflow: decode to file, read format from path."""
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        b64_str = base64.b64encode(png_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_str}"

        # Decode to file
        temp_path = decode_base64_image_to_file(data_uri, delete_on_exit=False)

        try:
            assert temp_path is not None

            # Get format from path
            fmt_from_path = get_image_format_from_path(temp_path)
            assert fmt_from_path == "png"

            # Read file and detect format
            with open(temp_path, "rb") as f:
                content = f.read()
            detected_fmt = detect_image_format_from_bytes(content)
            assert detected_fmt == "png"

        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def test_all_supported_formats_roundtrip(self):
        """Test roundtrip for all supported image formats."""
        test_data = {
            "png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 24,
            "jpg": b"\xff\xd8\xff" + b"\x00" * 29,
            "gif": b"GIF89a" + b"\x00" * 26,
            "webp": b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 20,
            "bmp": b"BM" + b"\x00" * 30,
        }

        for fmt, img_bytes in test_data.items():
            # Create data URI
            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            mime = "image/jpeg" if fmt == "jpg" else f"image/{fmt}"
            data_uri = f"data:{mime};base64,{b64_data}"

            # Decode
            decoded_bytes, decoded_fmt = decode_base64_image(data_uri)

            # Verify
            assert decoded_bytes is not None
            assert decoded_fmt in [fmt, "jpg" if fmt == "jpeg" else fmt]

            # Detect format from bytes
            detected = detect_image_format_from_bytes(decoded_bytes)
            assert detected == fmt
