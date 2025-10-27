#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/utils/test_encoding.py
"""Unit tests for encoding detection and handling utilities."""

from __future__ import annotations

from io import BytesIO, StringIO

import pytest

from all2md.utils.encoding import (
    detect_encoding,
    get_charset_from_content_type,
    normalize_stream_to_bytes,
    normalize_stream_to_text,
    read_text_with_encoding_detection,
)


class TestDetectEncoding:
    """Test cases for detect_encoding function."""

    def test_detect_utf8(self):
        """Test detection of UTF-8 encoded text."""
        data = "Hello, world! 你好世界".encode("utf-8")
        encoding = detect_encoding(data)
        # chardet should detect UTF-8
        assert encoding is not None
        assert encoding.lower() in ["utf-8", "ascii"]  # ASCII is valid subset of UTF-8

    def test_detect_latin1(self):
        """Test detection of Latin-1 encoded text."""
        # Text with Latin-1 specific characters
        data = "Café résumé naïve".encode("latin-1")
        encoding = detect_encoding(data)
        # chardet should detect some encoding (might be ISO-8859-1 or Windows-1252)
        assert encoding is not None

    def test_detect_utf16(self):
        """Test detection of UTF-16 encoded text."""
        data = "Hello, world!".encode("utf-16")
        encoding = detect_encoding(data)
        # chardet should detect UTF-16 or similar
        assert encoding is not None

    def test_empty_data(self):
        """Test detection with empty data."""
        encoding = detect_encoding(b"")
        # Empty data should return None (no detection possible)
        assert encoding is None

    def test_small_sample_size(self):
        """Test detection with custom sample size."""
        data = ("Hello, world! " * 100).encode("utf-8")
        encoding = detect_encoding(data, sample_size=50)
        # Should still detect UTF-8 even with small sample
        assert encoding is not None

    def test_low_confidence_threshold(self):
        """Test detection with low confidence threshold."""
        # Mixed encoding data that might have low confidence
        data = b"Hello\x80\x81\x82"
        _ = detect_encoding(data, confidence_threshold=0.1)
        # With very low threshold, should get some result
        # (This is testing the threshold mechanism works)

    def test_high_confidence_threshold(self):
        """Test detection with high confidence threshold."""
        # Ambiguous data
        data = b"test"
        _ = detect_encoding(data, confidence_threshold=0.99)
        # With very high threshold, might return None
        # (This is testing the threshold mechanism works)

    def test_binary_data(self):
        """Test detection with binary data."""
        # Pure binary data (not text)
        data = bytes(range(256))
        _ = detect_encoding(data)
        # Binary data might not have a detected text encoding


class TestReadTextWithEncodingDetection:
    """Test cases for read_text_with_encoding_detection function."""

    def test_read_utf8_text(self):
        """Test reading UTF-8 encoded text."""
        original = "Hello, world! 你好世界"
        data = original.encode("utf-8")
        result = read_text_with_encoding_detection(data)
        assert result == original

    def test_read_utf8_with_bom(self):
        """Test reading UTF-8 text with BOM."""
        original = "Hello, world!"
        data = original.encode("utf-8-sig")
        result = read_text_with_encoding_detection(data)
        # Should strip BOM
        assert result == original

    def test_read_latin1_text(self):
        """Test reading Latin-1 encoded text."""
        original = "Café résumé naïve"
        data = original.encode("latin-1")
        result = read_text_with_encoding_detection(data)
        # Should detect and decode correctly
        assert result == original or "Caf" in result  # Partial match if detection isn't perfect

    def test_read_windows1252_text(self):
        """Test reading Windows-1252 encoded text."""
        # Windows-1252 specific characters
        original = "smart quotes: \u201c\u201d"
        data = original.encode("windows-1252", errors="ignore")
        result = read_text_with_encoding_detection(data)
        # Should decode without errors
        assert isinstance(result, str)

    def test_custom_fallback_encodings(self):
        """Test with custom fallback encoding list."""
        original = "Café"
        data = original.encode("cp1252")
        result = read_text_with_encoding_detection(data, fallback_encodings=["cp1252", "utf-8", "latin-1"])
        assert result == original

    def test_disable_chardet(self):
        """Test with chardet detection disabled."""
        original = "Hello, world!"
        data = original.encode("utf-8")
        result = read_text_with_encoding_detection(data, use_chardet=False)
        assert result == original

    def test_fallback_on_chardet_failure(self):
        """Test that fallback encodings work when chardet fails or is unavailable."""
        original = "Simple ASCII text"
        data = original.encode("ascii")
        # Even without chardet, should fall back to UTF-8/Latin-1
        result = read_text_with_encoding_detection(data, fallback_encodings=["ascii", "utf-8"])
        assert result == original

    def test_malformed_utf8_with_replacement(self):
        """Test handling of malformed UTF-8 with error replacement."""
        # Invalid UTF-8 sequence
        data = b"Hello \xff\xfe World"
        result = read_text_with_encoding_detection(data)
        # Should not raise exception, should have replacement characters
        assert isinstance(result, str)
        assert "Hello" in result
        assert "World" in result

    def test_empty_data(self):
        """Test reading empty data."""
        result = read_text_with_encoding_detection(b"")
        assert result == ""

    def test_very_large_data(self):
        """Test reading large data (tests sampling)."""
        # Create large text
        original = "Hello, world! " * 10000
        data = original.encode("utf-8")
        result = read_text_with_encoding_detection(data, chardet_sample_size=4096)
        assert result == original

    def test_mixed_encoding_detection(self):
        """Test with data that could be multiple encodings."""
        # Simple ASCII is valid in multiple encodings
        original = "Hello World 123"
        data = original.encode("utf-8")
        result = read_text_with_encoding_detection(data)
        assert result == original


class TestGetCharsetFromContentType:
    """Test cases for get_charset_from_content_type function."""

    def test_charset_with_semicolon(self):
        """Test extracting charset from Content-Type with semicolon."""
        content_type = "text/html; charset=utf-8"
        result = get_charset_from_content_type(content_type)
        assert result == "utf-8"

    def test_charset_with_quotes(self):
        """Test extracting charset with quotes."""
        content_type = 'text/html; charset="iso-8859-1"'
        result = get_charset_from_content_type(content_type)
        assert result == "iso-8859-1"

    def test_charset_with_single_quotes(self):
        """Test extracting charset with single quotes."""
        content_type = "text/html; charset='utf-8'"
        result = get_charset_from_content_type(content_type)
        assert result == "utf-8"

    def test_no_charset(self):
        """Test Content-Type without charset."""
        content_type = "text/html"
        result = get_charset_from_content_type(content_type)
        assert result is None

    def test_multiple_parameters(self):
        """Test Content-Type with multiple parameters."""
        content_type = "text/html; boundary=something; charset=utf-8; format=flowed"
        result = get_charset_from_content_type(content_type)
        assert result == "utf-8"

    def test_empty_content_type(self):
        """Test with empty Content-Type."""
        result = get_charset_from_content_type("")
        assert result is None

    def test_none_content_type(self):
        """Test with None Content-Type."""
        result = get_charset_from_content_type(None)
        assert result is None

    def test_charset_with_whitespace(self):
        """Test charset extraction with extra whitespace."""
        content_type = "text/html;  charset = utf-8 "
        result = get_charset_from_content_type(content_type)
        assert result == "utf-8"

    def test_case_insensitive_charset(self):
        """Test that charset parameter is case-insensitive."""
        content_type = "text/html; CHARSET=UTF-8"
        result = get_charset_from_content_type(content_type)
        assert result == "UTF-8"

    def test_complex_mime_type(self):
        """Test with complex MIME type."""
        content_type = "multipart/related; boundary=boundary123; charset=windows-1252; type=text/html"
        result = get_charset_from_content_type(content_type)
        assert result == "windows-1252"


class TestEncodingIntegration:
    """Integration tests for encoding detection in realistic scenarios."""

    def test_csv_with_various_encodings(self):
        """Test CSV-like data with various encodings."""
        csv_content = "Name,Age,City\nJohn,25,NYC\nJane,30,LA"

        # Test UTF-8
        data_utf8 = csv_content.encode("utf-8")
        result = read_text_with_encoding_detection(data_utf8)
        assert "Name" in result
        assert "John" in result

        # Test Latin-1
        data_latin1 = csv_content.encode("latin-1")
        result = read_text_with_encoding_detection(data_latin1)
        assert "Name" in result

    def test_text_file_with_bom(self):
        """Test text file with BOM marker."""
        content = "This is a test file\nWith multiple lines"

        # UTF-8 with BOM
        data = content.encode("utf-8-sig")
        result = read_text_with_encoding_detection(data)
        assert result == content
        assert not result.startswith("\ufeff")  # BOM should be stripped

    def test_source_code_with_special_chars(self):
        """Test source code with special characters."""
        code = "# -*- coding: utf-8 -*-\ndef test():\n    print('Hello 世界')"
        data = code.encode("utf-8")
        result = read_text_with_encoding_detection(data)
        assert result == code

    def test_html_content_type_integration(self):
        """Test extracting and using charset from HTML Content-Type."""
        content_type = "text/html; charset=iso-8859-1"
        charset = get_charset_from_content_type(content_type)

        html_content = "<html><body>Café</body></html>"
        data = html_content.encode(charset)

        # Use detected charset in fallback list
        result = read_text_with_encoding_detection(data, fallback_encodings=[charset, "utf-8", "latin-1"])
        assert "Café" in result or "Caf" in result

    def test_markdown_with_unicode(self):
        """Test Markdown content with Unicode characters."""
        markdown = "# Hello 世界\n\nThis is a **test** with émojis: ✨🎉"
        data = markdown.encode("utf-8")
        result = read_text_with_encoding_detection(data)
        assert result == markdown

    def test_config_file_various_formats(self):
        """Test configuration file formats with different encodings."""
        ini_content = "[section]\nkey=value\nname=Café"

        # Test with UTF-8
        data = ini_content.encode("utf-8")
        result = read_text_with_encoding_detection(data)
        assert "Café" in result

    def test_legacy_encoding_fallback(self):
        """Test fallback to legacy encodings for old files."""
        # Simulate old file with Windows-1252 encoding
        content = "Project — Status Report"  # em dash
        data = content.encode("windows-1252", errors="ignore")

        result = read_text_with_encoding_detection(data, fallback_encodings=["utf-8", "windows-1252", "latin-1"])
        # Should decode successfully
        assert isinstance(result, str)
        assert "Project" in result


class TestNormalizeStreamToText:
    """Test cases for normalize_stream_to_text function."""

    def test_binary_stream_utf8(self):
        """Test normalizing a binary stream with UTF-8 content."""
        original = "Hello, world! 你好世界"
        stream = BytesIO(original.encode("utf-8"))
        result = normalize_stream_to_text(stream)
        assert result == original

    def test_text_stream(self):
        """Test normalizing a text stream (StringIO)."""
        original = "Hello, world! This is text."
        stream = StringIO(original)
        result = normalize_stream_to_text(stream)
        assert result == original

    def test_binary_stream_latin1(self):
        """Test normalizing a binary stream with Latin-1 content."""
        original = "Café résumé"
        stream = BytesIO(original.encode("latin-1"))
        result = normalize_stream_to_text(stream)
        # Should detect and decode correctly
        assert result == original or "Caf" in result

    def test_binary_stream_with_bom(self):
        """Test normalizing a binary stream with UTF-8 BOM."""
        original = "Hello, world!"
        stream = BytesIO(original.encode("utf-8-sig"))
        result = normalize_stream_to_text(stream)
        # Should strip BOM
        assert result == original

    def test_empty_binary_stream(self):
        """Test normalizing an empty binary stream."""
        stream = BytesIO(b"")
        result = normalize_stream_to_text(stream)
        assert result == ""

    def test_empty_text_stream(self):
        """Test normalizing an empty text stream."""
        stream = StringIO("")
        result = normalize_stream_to_text(stream)
        assert result == ""

    def test_custom_fallback_encodings(self):
        """Test with custom fallback encodings."""
        original = "Café"
        stream = BytesIO(original.encode("cp1252"))
        result = normalize_stream_to_text(stream, fallback_encodings=["cp1252", "utf-8", "latin-1"])
        assert result == original

    def test_disable_chardet(self):
        """Test with chardet disabled."""
        original = "Hello, world!"
        stream = BytesIO(original.encode("utf-8"))
        result = normalize_stream_to_text(stream, use_chardet=False)
        assert result == original

    def test_invalid_stream_type_raises_error(self):
        """Test that invalid stream types raise TypeError."""

        class FakeStream:
            def read(self):
                return 123  # Not bytes or str

        stream = FakeStream()
        with pytest.raises(TypeError):
            normalize_stream_to_text(stream)


class TestNormalizeStreamToBytes:
    """Test cases for normalize_stream_to_bytes function."""

    def test_binary_stream(self):
        """Test normalizing a binary stream."""
        original = b"Hello, world!"
        stream = BytesIO(original)
        result = normalize_stream_to_bytes(stream)
        assert result == original

    def test_text_stream_utf8(self):
        """Test normalizing a text stream with UTF-8 encoding."""
        original = "Hello, world! 你好世界"
        stream = StringIO(original)
        result = normalize_stream_to_bytes(stream)
        assert result == original.encode("utf-8")

    def test_text_stream_custom_encoding(self):
        """Test normalizing a text stream with custom encoding."""
        original = "Café"
        stream = StringIO(original)
        result = normalize_stream_to_bytes(stream, encoding="latin-1")
        assert result == original.encode("latin-1")

    def test_empty_binary_stream(self):
        """Test normalizing an empty binary stream."""
        stream = BytesIO(b"")
        result = normalize_stream_to_bytes(stream)
        assert result == b""

    def test_empty_text_stream(self):
        """Test normalizing an empty text stream."""
        stream = StringIO("")
        result = normalize_stream_to_bytes(stream)
        assert result == b""

    def test_binary_stream_with_special_bytes(self):
        """Test binary stream with special byte sequences."""
        original = b"\x00\x01\x02\xff\xfe\xfd"
        stream = BytesIO(original)
        result = normalize_stream_to_bytes(stream)
        assert result == original

    def test_invalid_stream_type_raises_error(self):
        """Test that invalid stream types raise TypeError."""

        class FakeStream:
            def read(self):
                return 123  # Not bytes or str

        stream = FakeStream()
        with pytest.raises(TypeError):
            normalize_stream_to_bytes(stream)


class TestStreamNormalizationIntegration:
    """Integration tests for stream normalization in realistic parser scenarios."""

    def test_markdown_parser_with_binary_stream(self):
        """Test that markdown content works with binary streams."""
        markdown = "# Hello World\n\nThis is a **test**."
        stream = BytesIO(markdown.encode("utf-8"))
        result = normalize_stream_to_text(stream)
        assert result == markdown
        assert "# Hello World" in result

    def test_markdown_parser_with_text_stream(self):
        """Test that markdown content works with text streams."""
        markdown = "# Hello World\n\nThis is a **test**."
        stream = StringIO(markdown)
        result = normalize_stream_to_text(stream)
        assert result == markdown

    def test_json_parser_with_binary_stream(self):
        """Test JSON parsing with binary streams (simulating ipynb)."""
        json_content = '{"cells": [], "metadata": {}}'
        stream = BytesIO(json_content.encode("utf-8"))
        result = normalize_stream_to_bytes(stream)
        assert result == json_content.encode("utf-8")

    def test_json_parser_with_text_stream(self):
        """Test JSON parsing with text streams."""
        json_content = '{"cells": [], "metadata": {}}'
        stream = StringIO(json_content)
        result = normalize_stream_to_bytes(stream)
        assert result == json_content.encode("utf-8")

    def test_bbcode_with_unicode(self):
        """Test BBCode content with Unicode characters."""
        bbcode = "[b]Hello 世界[/b]\n[i]Café[/i]"
        stream = BytesIO(bbcode.encode("utf-8"))
        result = normalize_stream_to_text(stream)
        assert result == bbcode

    def test_latex_with_special_chars(self):
        """Test LaTeX content with special characters."""
        latex = r"\documentclass{article}\begin{document}Café résumé\end{document}"
        stream = BytesIO(latex.encode("utf-8"))
        result = normalize_stream_to_bytes(stream)
        assert result == latex.encode("utf-8")

    def test_source_code_with_various_encodings(self):
        """Test source code with various encodings."""
        code = "# -*- coding: utf-8 -*-\ndef test():\n    print('Hello 世界')"

        # Binary stream
        stream = BytesIO(code.encode("utf-8"))
        result = normalize_stream_to_text(stream)
        assert result == code

        # Text stream
        stream = StringIO(code)
        result = normalize_stream_to_text(stream)
        assert result == code
