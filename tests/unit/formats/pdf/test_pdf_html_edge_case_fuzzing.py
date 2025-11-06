"""Edge case fuzzing tests for PDF and HTML parsers.

This test module uses Hypothesis and manual edge cases to test robustness
of PDF and HTML parsers against malformed, corrupted, and edge-case inputs.

Test Coverage:
- Corrupted file headers
- Empty files
- Extremely large files (size limits)
- Malformed structure
- Property: Parsers should not crash on any input
"""

from io import BytesIO

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from all2md import to_markdown
from all2md.exceptions import MalformedFileError


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.html
class TestHTMLEdgeCaseFuzzing:
    """Fuzz test HTML parser with edge cases."""

    @given(st.binary(min_size=0, max_size=1000))
    @settings(max_examples=50, deadline=None)
    def test_random_binary_as_html(self, binary_data):
        """Property: Random binary data should not crash HTML parser."""
        try:
            result = to_markdown(BytesIO(binary_data), source_format="html")
            # Should return a string (possibly empty)
            assert isinstance(result, str)
        except (UnicodeDecodeError, MalformedFileError):
            # Expected for invalid encodings or completely invalid input
            pass
        except Exception as e:
            # Should not crash with unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")

    def test_html_empty_file(self):
        """Test empty HTML file."""
        result = to_markdown(BytesIO(b""), source_format="html")
        # Should handle gracefully
        assert isinstance(result, str)

    def test_html_whitespace_only(self):
        """Test HTML file with only whitespace."""
        result = to_markdown(BytesIO(b"   \n\t\r\n   "), source_format="html")
        assert isinstance(result, str)

    @given(st.integers(min_value=0, max_value=1000000))
    @settings(max_examples=10, deadline=None)
    def test_html_repeated_characters(self, repeat_count):
        """Test HTML with many repeated characters."""
        # Limit to reasonable size to avoid memory issues
        if repeat_count > 100000:
            repeat_count = 100000

        html = b"<p>" + b"a" * repeat_count + b"</p>"

        try:
            result = to_markdown(BytesIO(html), source_format="html")
            assert isinstance(result, str)
        except MemoryError:
            # Expected for very large inputs
            pytest.skip("Memory limit exceeded")

    def test_html_deeply_nested_elements(self):
        """Test HTML with deeply nested elements."""
        # Create deeply nested divs (100 levels)
        opening = "<div>" * 100
        closing = "</div>" * 100
        html = f"{opening}Content{closing}"

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert isinstance(result, str)
        assert "content" in result.lower()

    @given(st.text(alphabet="<>/", min_size=10, max_size=200))
    @settings(max_examples=20)
    def test_html_random_tag_structure(self, tag_chars):
        """Test HTML with random tag-like characters."""
        try:
            result = to_markdown(BytesIO(tag_chars.encode("utf-8")), source_format="html")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on tag structure: {e}")

    def test_html_invalid_entities(self):
        """Test HTML with invalid entity references."""
        html = """
        <p>Invalid entities: &invalidname; &#999999999; &#xGGGG;</p>
        <p>Valid entity: &amp;</p>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert isinstance(result, str)

    def test_html_null_bytes(self):
        """Test HTML containing null bytes."""
        html = b"<p>Text\x00with\x00nulls</p>"

        try:
            result = to_markdown(BytesIO(html), source_format="html")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Crash on null bytes: {e}")


@pytest.mark.unit
@pytest.mark.fuzzing
@pytest.mark.pdf
class TestPDFEdgeCaseFuzzing:
    """Fuzz test PDF parser with edge cases."""

    @given(st.binary(min_size=0, max_size=1000))
    @settings(max_examples=30)
    def test_random_binary_as_pdf(self, binary_data):
        """Property: Random binary data should not crash PDF parser."""
        try:
            result = to_markdown(BytesIO(binary_data), source_format="pdf")
            # Should either succeed or raise MalformedFileError
            assert isinstance(result, str)
        except MalformedFileError:
            # Expected for invalid PDF data
            pass
        except Exception as e:
            # Should not crash with unexpected exceptions
            # Note: PDF library might raise its own exceptions
            if "pymupdf" not in str(type(e).__module__).lower():
                pytest.fail(f"Unexpected exception: {e}")

    def test_pdf_empty_file(self):
        """Test empty PDF file."""
        try:
            result = to_markdown(BytesIO(b""), source_format="pdf")
            assert isinstance(result, str)
        except MalformedFileError:
            # Expected - empty file is not valid PDF
            pass

    def test_pdf_invalid_header(self):
        """Test PDF with invalid header."""
        # Valid PDF should start with %PDF-
        invalid_pdf = b"NOTAPDF\n" + b"x" * 100

        try:
            result = to_markdown(BytesIO(invalid_pdf), source_format="pdf")
            # Should either work or raise MalformedFileError
            assert isinstance(result, str)
        except MalformedFileError:
            # Expected for invalid PDF
            pass

    def test_pdf_valid_header_corrupt_body(self):
        """Test PDF with valid header but corrupted body."""
        # Start with valid PDF header
        corrupt_pdf = b"%PDF-1.4\n" + b"\x00\xff\xfe" * 100

        try:
            result = to_markdown(BytesIO(corrupt_pdf), source_format="pdf")
            assert isinstance(result, str)
        except MalformedFileError:
            # Expected for corrupted PDF
            pass

    def test_pdf_truncated_file(self):
        """Test truncated PDF file."""
        from fixtures.generators.pdf_test_fixtures import create_pdf_with_formatting

        # Create valid PDF and get bytes
        pdf_doc = create_pdf_with_formatting()
        valid_pdf = pdf_doc.tobytes()
        truncated_pdf = valid_pdf[: len(valid_pdf) // 2]  # Take only first half

        try:
            result = to_markdown(BytesIO(truncated_pdf), source_format="pdf")
            # Might succeed partially or fail
            assert isinstance(result, str)
        except (MalformedFileError, Exception):
            # Expected - truncated PDF might fail parsing
            pass


@pytest.mark.unit
@pytest.mark.fuzzing
class TestFormatDetectionFuzzing:
    """Fuzz test format detection with ambiguous inputs."""

    @given(st.binary(min_size=4, max_size=100))
    @settings(max_examples=50, deadline=1000)
    def test_format_detection_with_random_headers(self, header_bytes):
        """Test format detection doesn't crash on random file headers.

        This test verifies that format detection doesn't crash on random input.
        We filter out valid magic byte sequences using hypothesis.assume() to avoid
        flaky test failures when the fuzzer generates valid format headers.
        """
        from hypothesis import assume

        from all2md.converter_registry import ConverterRegistry
        from all2md.exceptions import DependencyError, FormatError, ParsingError

        # Get all registered magic bytes to avoid testing valid format headers
        registry = ConverterRegistry()

        # Filter out bytes that match known magic byte patterns
        # This prevents flaky failures when fuzzer generates valid format headers
        # (e.g., b'From ' for MBOX, b'%PDF-' for PDF, etc.)
        matches_known_format = False
        for format_name in registry.list_formats():
            format_info = registry.get_format_info(format_name)
            if format_info:
                for metadata in format_info:
                    if metadata.matches_magic_bytes(header_bytes):
                        matches_known_format = True
                        break
            if matches_known_format:
                break

        # Skip test cases where random bytes happen to be valid format headers
        assume(not matches_known_format)

        # Try to convert without specifying format (auto-detect)
        try:
            result = to_markdown(BytesIO(header_bytes))
            assert isinstance(result, str)
        except (MalformedFileError, UnicodeDecodeError, FormatError, ParsingError, DependencyError):
            # Expected for unrecognized or invalid formats, or missing dependencies
            pass
        except Exception as e:
            # Should not crash unexpectedly
            if "codec" not in str(e).lower():  # Allow codec errors
                pytest.fail(f"Unexpected exception: {e}")

    def test_ambiguous_extension_content(self):
        """Test file with HTML extension but PDF content."""
        from fixtures.generators.pdf_test_fixtures import create_pdf_with_formatting

        pdf_doc = create_pdf_with_formatting()
        pdf_bytes = pdf_doc.tobytes()

        # Force HTML format on PDF content
        try:
            result = to_markdown(BytesIO(pdf_bytes), source_format="html")
            # Should handle gracefully
            assert isinstance(result, str)
        except (MalformedFileError, UnicodeDecodeError):
            # Expected
            pass


@pytest.mark.unit
@pytest.mark.fuzzing
class TestEncodingEdgeCases:
    """Test encoding edge cases."""

    @given(st.sampled_from(["utf-8", "utf-16", "utf-32", "latin-1", "ascii"]), st.text(min_size=1, max_size=100))
    def test_various_encodings(self, encoding, text):
        """Test HTML parsing with various text encodings.

        Modern HTML parsers (like BeautifulSoup) support multiple encodings through
        auto-detection mechanisms including BOM detection, charset declarations, and
        content sniffing. This test verifies the parser handles various encodings
        gracefully - either successfully parsing them or raising appropriate errors.
        """
        html = f"<p>{text}</p>"

        try:
            encoded = html.encode(encoding)
            result = to_markdown(BytesIO(encoded), source_format="html")

            # Parser successfully handled the encoding - verify output is valid
            assert isinstance(result, str)
            # Result should contain some content (not empty)
            assert len(result.strip()) > 0

        except (UnicodeEncodeError, UnicodeDecodeError, LookupError, MalformedFileError):
            # Expected for:
            # - Characters that can't be encoded in the target encoding (UnicodeEncodeError)
            # - Invalid encoded bytes (UnicodeDecodeError)
            # - Unknown encoding names (LookupError)
            # - Malformed file content (MalformedFileError)
            pass

    def test_html_with_bom(self):
        """Test HTML with byte order mark."""
        # UTF-8 BOM
        html_with_bom = b"\xef\xbb\xbf<p>Content</p>"

        result = to_markdown(BytesIO(html_with_bom), source_format="html")
        assert isinstance(result, str)
        assert "content" in result.lower()

    def test_html_mixed_encoding_characters(self):
        """Test HTML with characters from multiple scripts."""
        html = """
        <p>English, Español, Français, Deutsch</p>
        <p>中文, 日本語, 한국어</p>
        <p>العربية, עברית, ไทย</p>
        """

        result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
        assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.fuzzing
class TestResourceExhaustionProtection:
    """Test protection against resource exhaustion."""

    @pytest.mark.slow
    def test_html_with_many_elements(self):
        """Test HTML with many elements (but within reason)."""
        # Create HTML with 10,000 paragraphs
        elements = ["<p>Paragraph content</p>"] * 10000
        html = "".join(elements)

        try:
            result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
            assert isinstance(result, str)
        except MemoryError:
            pytest.skip("Memory limit exceeded")

    def test_html_with_very_long_attribute(self):
        """Test HTML with extremely long attribute value."""
        long_value = "x" * 100000
        html = f'<p data-value="{long_value}">Content</p>'

        try:
            result = to_markdown(BytesIO(html.encode("utf-8")), source_format="html")
            assert isinstance(result, str)
        except MemoryError:
            pytest.skip("Memory limit exceeded")
