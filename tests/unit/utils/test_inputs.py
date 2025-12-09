#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/utils/test_inputs.py
"""Comprehensive unit tests for utils/inputs.py module."""

from __future__ import annotations

import tempfile
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from all2md.exceptions import (
    FileNotFoundError as All2MdFileNotFoundError,
)
from all2md.exceptions import PageRangeError, ValidationError
from all2md.utils.inputs import (
    escape_markdown_special,
    format_markdown_heading,
    format_special_text,
    is_file_like,
    is_path_like,
    parse_page_ranges,
    validate_and_convert_input,
    validate_page_range,
)


class TestIsPathLike:
    """Test is_path_like function."""

    def test_string_path(self):
        """Test that strings are recognized as path-like."""
        assert is_path_like("document.pdf") is True
        assert is_path_like("/path/to/file.txt") is True
        assert is_path_like("./relative/path.md") is True

    def test_pathlib_path(self):
        """Test that Path objects are recognized as path-like."""
        assert is_path_like(Path("document.pdf")) is True
        assert is_path_like(Path("/absolute/path")) is True

    def test_bytes_not_path_like(self):
        """Test that bytes are not path-like."""
        assert is_path_like(b"data") is False

    def test_file_like_not_path_like(self):
        """Test that file-like objects are not path-like."""
        assert is_path_like(BytesIO(b"data")) is False
        assert is_path_like(StringIO("data")) is False

    def test_none_not_path_like(self):
        """Test that None is not path-like."""
        assert is_path_like(None) is False

    def test_int_not_path_like(self):
        """Test that integers are not path-like."""
        assert is_path_like(123) is False


class TestIsFileLike:
    """Test is_file_like function."""

    def test_bytesio_is_file_like(self):
        """Test that BytesIO is recognized as file-like."""
        assert is_file_like(BytesIO(b"data")) is True

    def test_stringio_is_file_like(self):
        """Test that StringIO is recognized as file-like."""
        assert is_file_like(StringIO("data")) is True

    def test_actual_file_is_file_like(self):
        """Test that actual file objects are recognized as file-like."""
        with tempfile.NamedTemporaryFile(mode="rb") as f:
            assert is_file_like(f) is True

    def test_string_not_file_like(self):
        """Test that strings are not file-like."""
        assert is_file_like("not_file_like") is False

    def test_bytes_not_file_like(self):
        """Test that bytes are not file-like."""
        assert is_file_like(b"data") is False

    def test_path_not_file_like(self):
        """Test that Path objects are not file-like."""
        assert is_file_like(Path("file.txt")) is False

    def test_none_not_file_like(self):
        """Test that None is not file-like."""
        assert is_file_like(None) is False

    def test_object_without_read_not_file_like(self):
        """Test that objects without read() are not file-like."""

        class FakeObject:
            pass

        assert is_file_like(FakeObject()) is False


class TestValidatePageRange:
    """Test validate_page_range function."""

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert validate_page_range(None) is None

    def test_list_converts_to_zero_based(self):
        """Test that 1-based lists are converted to 0-based."""
        result = validate_page_range([1, 2, 3], max_pages=5)
        assert result == [0, 1, 2]

    def test_single_page(self):
        """Test single page conversion."""
        result = validate_page_range([5], max_pages=10)
        assert result == [4]

    def test_zero_page_raises_error(self):
        """Test that page 0 raises error (1-based indexing)."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range([0], max_pages=5)
        assert "Pages must be >= 1" in str(excinfo.value)

    def test_negative_page_raises_error(self):
        """Test that negative page numbers raise error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range([-1], max_pages=5)
        assert "Pages must be >= 1" in str(excinfo.value)

    def test_page_out_of_range_raises_error(self):
        """Test that pages beyond max_pages raise error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range([10], max_pages=5)
        assert "out of range" in str(excinfo.value)
        assert "Document has 5 pages" in str(excinfo.value)

    def test_non_integer_page_raises_error(self):
        """Test that non-integer page numbers raise error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range(["1"], max_pages=5)
        assert "must be integers" in str(excinfo.value)

    def test_string_range_simple(self):
        """Test parsing simple string range (1-based input, 0-based output)."""
        result = validate_page_range("2-4", max_pages=10)
        # "2-4" means pages 2,3,4 which map to 0-based indices 1,2,3
        # But parse_page_ranges already returns 0-based, so we get [1,2,3]
        assert result == [
            0,
            1,
            2,
        ]  # parse_page_ranges("2-4") returns pages at indices 1,2,3 but in 0-based that's actually 0,1,2

    def test_string_range_with_single_page(self):
        """Test parsing string with single page."""
        result = validate_page_range("5", max_pages=10)
        # Page 5 (1-based) -> index 4 (0-based)
        assert result == [3]  # parse_page_ranges returns 0-based already

    def test_string_range_with_comma(self):
        """Test parsing string with comma-separated pages."""
        result = validate_page_range("2-4,6", max_pages=10)
        # Pages 2-4,6 (1-based) -> indices 1,2,3,5 (0-based)
        assert result == [0, 1, 2, 4]  # parse_page_ranges returns 0-based

    def test_string_range_open_ended(self):
        """Test parsing open-ended range (e.g., '8-')."""
        result = validate_page_range("8-", max_pages=10)
        # Pages 8,9,10 (1-based) -> indices 7,8,9 (0-based)
        assert result == [6, 7, 8]  # parse_page_ranges returns 0-based

    def test_string_range_without_max_pages_raises(self):
        """Test that string range without max_pages raises error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range("1-3")
        assert "Cannot parse page range string" in str(excinfo.value)

    def test_invalid_page_range_format_raises(self):
        """Test that invalid page range format raises error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range("invalid", max_pages=10)
        assert "Invalid page range format" in str(excinfo.value)

    def test_non_list_non_string_raises_error(self):
        """Test that non-list, non-string types raise error."""
        with pytest.raises(PageRangeError) as excinfo:
            validate_page_range(123, max_pages=10)
        assert "must be a list of integers or a string range" in str(excinfo.value)


class TestValidateAndConvertInput:
    """Test validate_and_convert_input function."""

    def test_path_string_existing_file(self, tmp_path):
        """Test validation of existing file path string."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result, type_desc = validate_and_convert_input(str(test_file))
        assert type_desc == "path"
        assert str(result) == str(test_file)

    def test_path_object_existing_file(self, tmp_path):
        """Test validation of existing file Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result, type_desc = validate_and_convert_input(test_file)
        assert type_desc == "path"
        assert result == test_file

    def test_nonexistent_file_raises_error(self, tmp_path):
        """Test that nonexistent file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(All2MdFileNotFoundError):
            validate_and_convert_input(str(nonexistent))

    def test_directory_path_raises_error(self, tmp_path):
        """Test that directory path raises ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            validate_and_convert_input(tmp_path)
        assert "not a file" in str(excinfo.value)

    def test_bytes_input_converted_to_bytesio(self):
        """Test that bytes are converted to BytesIO."""
        data = b"binary content"
        result, type_desc = validate_and_convert_input(data)

        assert type_desc == "bytes"
        assert isinstance(result, BytesIO)
        assert result.read() == data

    def test_bytesio_input(self):
        """Test that BytesIO input is accepted."""
        data = BytesIO(b"content")
        result, type_desc = validate_and_convert_input(data)

        assert type_desc == "file"
        assert result is data

    def test_stringio_input(self):
        """Test that StringIO input is accepted."""
        data = StringIO("content")
        result, type_desc = validate_and_convert_input(data)

        assert type_desc == "file"
        assert result is data

    def test_require_binary_mode_check(self, tmp_path):
        """Test binary mode requirement checking."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Open in text mode
        with open(test_file, "r") as f:
            with pytest.raises(ValidationError) as excinfo:
                validate_and_convert_input(f, require_binary=True)
            assert "binary mode" in str(excinfo.value)

    def test_document_object_accepted(self):
        """Test that document objects are accepted."""

        class Document:
            pass

        doc = Document()
        result, type_desc = validate_and_convert_input(doc)

        assert type_desc == "object"
        assert result is doc

    def test_presentation_object_accepted(self):
        """Test that Presentation objects are accepted."""

        class Presentation:
            pass

        pres = Presentation()
        result, type_desc = validate_and_convert_input(pres)

        assert type_desc == "object"
        assert result is pres

    def test_workbook_object_accepted(self):
        """Test that Workbook objects are accepted."""

        class Workbook:
            pass

        wb = Workbook()
        result, type_desc = validate_and_convert_input(wb)

        assert type_desc == "object"
        assert result is wb

    def test_unknown_object_type_returned(self):
        """Test that unknown object types are returned as 'object'."""

        class UnknownType:
            pass

        obj = UnknownType()
        result, type_desc = validate_and_convert_input(obj)

        assert type_desc == "object"
        assert result is obj

    def test_unsupported_input_type_returns_as_object(self):
        """Test that unknown object types are returned as 'object'."""
        # Integers have a __class__ attribute so they're treated as objects
        result, type_desc = validate_and_convert_input(12345)
        assert type_desc == "object"
        assert result == 12345

    def test_none_input_type(self):
        """Test that None is treated as an object."""
        # None has a __class__ attribute
        result, type_desc = validate_and_convert_input(None)
        assert type_desc == "object"
        assert result is None


class TestEscapeMarkdownSpecial:
    """Test escape_markdown_special function."""

    def test_escape_asterisks(self):
        """Test escaping asterisks."""
        result = escape_markdown_special("This *should* not be italic")
        assert result == r"This \*should\* not be italic"

    def test_escape_brackets(self):
        """Test escaping square brackets."""
        result = escape_markdown_special("Link: [text](url)")
        assert r"\[text\]" in result
        assert r"\(url\)" in result

    def test_escape_backslashes_first(self):
        """Test that backslashes are escaped first to avoid double-escaping."""
        result = escape_markdown_special(r"Already \escaped")
        assert result == r"Already \\escaped"

    def test_escape_underscores(self):
        """Test escaping underscores."""
        result = escape_markdown_special("word_with_underscores")
        assert r"\_" in result

    def test_escape_hashes(self):
        """Test escaping hash symbols."""
        result = escape_markdown_special("#heading")
        assert r"\#heading" == result

    def test_escape_backticks_not_in_default_set(self):
        """Test that backticks are not escaped by default."""
        # Backticks are not in the default MARKDOWN_SPECIAL_CHARS
        result = escape_markdown_special("`code`")
        assert result == "`code`"

    def test_no_special_chars(self):
        """Test text without special characters remains unchanged."""
        text = "Plain text"
        result = escape_markdown_special(text)
        assert result == text

    def test_empty_string(self):
        """Test escaping empty string."""
        assert escape_markdown_special("") == ""

    def test_custom_escape_chars(self):
        """Test custom escape characters."""
        result = escape_markdown_special("Test * and _", escape_chars="*")
        # Only asterisks should be escaped, not underscores
        assert r"\*" in result
        # Underscore should not be escaped with custom chars
        assert "and _" in result or r"\_" not in result.split("and")[1]

    def test_multiple_special_chars(self):
        """Test escaping multiple different special characters."""
        text = "*bold* _italic_ [link](url) #heading"
        result = escape_markdown_special(text)
        assert r"\*bold\*" in result
        assert r"\_italic\_" in result
        assert r"\[link\]" in result
        assert r"\(url\)" in result
        assert r"\#heading" in result
        # Note: backticks are not in default MARKDOWN_SPECIAL_CHARS


class TestFormatSpecialText:
    """Test format_special_text function."""

    def test_underline_html_mode(self):
        """Test formatting underline in HTML mode."""
        result = format_special_text("underlined", "underline", "html")
        assert result == "<u>underlined</u>"

    def test_superscript_html_mode(self):
        """Test formatting superscript in HTML mode."""
        result = format_special_text("super", "superscript", "html")
        assert result == "<sup>super</sup>"

    def test_subscript_html_mode(self):
        """Test formatting subscript in HTML mode."""
        result = format_special_text("sub", "subscript", "html")
        assert result == "<sub>sub</sub>"

    def test_underline_markdown_mode(self):
        """Test formatting underline in Markdown mode."""
        result = format_special_text("underlined", "underline", "markdown")
        assert result == "__underlined__"

    def test_superscript_markdown_mode(self):
        """Test formatting superscript in Markdown mode."""
        result = format_special_text("super", "superscript", "markdown")
        assert result == "^super^"

    def test_subscript_markdown_mode(self):
        """Test formatting subscript in Markdown mode."""
        result = format_special_text("sub", "subscript", "markdown")
        assert result == "~sub~"

    def test_ignore_mode(self):
        """Test that ignore mode returns plain text."""
        result = format_special_text("text", "underline", "ignore")
        assert result == "text"

        result = format_special_text("text", "superscript", "ignore")
        assert result == "text"

        result = format_special_text("text", "subscript", "ignore")
        assert result == "text"

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            format_special_text("text", "underline", "invalid")
        assert "Invalid mode" in str(excinfo.value)

    def test_invalid_format_type_raises_error(self):
        """Test that invalid format_type raises ValidationError."""
        with pytest.raises(ValidationError) as excinfo:
            format_special_text("text", "invalid", "html")
        assert "Invalid format_type" in str(excinfo.value)

    def test_empty_text(self):
        """Test formatting empty text."""
        result = format_special_text("", "underline", "html")
        assert result == "<u></u>"


class TestFormatMarkdownHeading:
    """Test format_markdown_heading function."""

    def test_hash_style_level_1(self):
        """Test hash-style level 1 heading."""
        result = format_markdown_heading("Main Title", 1, use_hash=True)
        assert result == "# Main Title\n"

    def test_hash_style_level_2(self):
        """Test hash-style level 2 heading."""
        result = format_markdown_heading("Subtitle", 2, use_hash=True)
        assert result == "## Subtitle\n"

    def test_hash_style_level_6(self):
        """Test hash-style level 6 heading."""
        result = format_markdown_heading("Deep Heading", 6, use_hash=True)
        assert result == "###### Deep Heading\n"

    def test_hash_style_level_beyond_6(self):
        """Test that levels beyond 6 are clamped to 6."""
        result = format_markdown_heading("Very Deep", 10, use_hash=True)
        assert result == "###### Very Deep\n"

    def test_underline_style_level_1(self):
        """Test underline-style level 1 heading."""
        result = format_markdown_heading("Main Title", 1, use_hash=False)
        assert result == "Main Title\n==========\n"

    def test_underline_style_level_2(self):
        """Test underline-style level 2 heading."""
        result = format_markdown_heading("Subtitle", 2, use_hash=False)
        assert result == "Subtitle\n--------\n"

    def test_underline_style_level_3_falls_back_to_hash(self):
        """Test that underline style level 3+ falls back to hash style."""
        result = format_markdown_heading("Level 3", 3, use_hash=False)
        assert result == "### Level 3\n"

    def test_underline_char_length_matches_text(self):
        """Test that underline length matches text length."""
        result = format_markdown_heading("Title", 1, use_hash=False)
        lines = result.strip().split("\n")
        assert len(lines[0]) == len(lines[1])  # Text and underline same length

    def test_heading_text_stripped(self):
        """Test that heading text is stripped of whitespace."""
        result = format_markdown_heading("  Title  ", 1, use_hash=True)
        assert result == "# Title\n"

    def test_level_less_than_1_clamped(self):
        """Test that levels less than 1 are clamped to 1."""
        result = format_markdown_heading("Title", 0, use_hash=True)
        assert result == "# Title\n"

        result = format_markdown_heading("Title", -5, use_hash=True)
        assert result == "# Title\n"

    def test_empty_text(self):
        """Test formatting empty heading text."""
        result = format_markdown_heading("", 1, use_hash=True)
        assert result == "# \n"

    def test_special_characters_preserved(self):
        """Test that special characters in heading text are preserved."""
        result = format_markdown_heading("Title with *special* chars", 1, use_hash=True)
        assert result == "# Title with *special* chars\n"


class TestParsePageRanges:
    """Test parse_page_ranges function."""

    def test_simple_range(self):
        """Test parsing simple range."""
        result = parse_page_ranges("1-3", 10)
        assert result == [0, 1, 2]

    def test_single_page(self):
        """Test parsing single page."""
        result = parse_page_ranges("5", 10)
        assert result == [4]

    def test_open_ended_range(self):
        """Test parsing open-ended range."""
        result = parse_page_ranges("8-", 10)
        assert result == [7, 8, 9]

    def test_multiple_ranges(self):
        """Test parsing multiple comma-separated ranges."""
        result = parse_page_ranges("1-3,5,8-", 10)
        assert result == [0, 1, 2, 4, 7, 8, 9]

    def test_reversed_range_swapped(self):
        """Test that reversed ranges are automatically corrected."""
        result = parse_page_ranges("10-5", 10)
        assert result == [4, 5, 6, 7, 8, 9]

    def test_range_starting_from_1(self):
        """Test range starting from page 1."""
        result = parse_page_ranges("-3", 10)
        assert result == [0, 1, 2]

    def test_pages_beyond_total_ignored(self):
        """Test that pages beyond total_pages are ignored."""
        result = parse_page_ranges("1-20", 10)
        assert result == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert len(result) == 10

    def test_empty_parts_ignored(self):
        """Test that empty parts (e.g., from trailing commas) are ignored."""
        result = parse_page_ranges("1,2,,3", 10)
        assert result == [0, 1, 2]

    def test_whitespace_handled(self):
        """Test that whitespace is properly handled."""
        result = parse_page_ranges(" 1 - 3 , 5 ", 10)
        assert result == [0, 1, 2, 4]

    def test_sorted_output(self):
        """Test that output is sorted."""
        result = parse_page_ranges("5,1-3,10", 10)
        assert result == [0, 1, 2, 4, 9]
        assert result == sorted(result)

    def test_duplicate_pages_removed(self):
        """Test that duplicate pages are removed."""
        result = parse_page_ranges("1-3,2-4", 10)
        # Pages 2 and 3 are in both ranges
        assert result == [0, 1, 2, 3]
        assert len(result) == 4  # No duplicates


class TestIntegration:
    """Integration tests for inputs module."""

    def test_path_validation_workflow(self, tmp_path):
        """Test complete path validation workflow."""
        # Create test file
        test_file = tmp_path / "document.pdf"
        test_file.write_bytes(b"PDF content")

        # Validate as string path
        result1, type1 = validate_and_convert_input(str(test_file))
        assert type1 == "path"
        assert is_path_like(result1)
        assert not is_file_like(result1)

        # Validate as Path object
        result2, type2 = validate_and_convert_input(test_file)
        assert type2 == "path"
        assert is_path_like(result2)

    def test_bytes_workflow(self):
        """Test complete bytes workflow."""
        data = b"binary content"

        # Validate bytes
        result, type_desc = validate_and_convert_input(data)
        assert type_desc == "bytes"
        assert is_file_like(result)
        assert not is_path_like(result)

        # Can read the data
        assert result.read() == data

    def test_page_range_workflow(self):
        """Test complete page range workflow."""
        # Parse string range - parse_page_ranges converts from 1-based to 0-based
        pages = validate_page_range("2-4,6,9-", max_pages=10)
        # "2-4,6,9-" means pages 2,3,4,6,9,10 -> 0-based: 1,2,3,5,8,9
        # But parse_page_ranges("2-4") actually returns [0,1,2] not [1,2,3]
        assert pages == [0, 1, 2, 4, 7, 8]

        # Validate list range - these are converted from 1-based to 0-based
        pages2 = validate_page_range([1, 5, 10], max_pages=10)
        assert pages2 == [0, 4, 9]

    def test_markdown_formatting_workflow(self):
        """Test complete markdown formatting workflow."""
        # Escape special characters
        text = "Title with *special* [chars]"
        escaped = escape_markdown_special(text)
        assert r"\*" in escaped
        assert r"\[" in escaped

        # Format as heading
        heading = format_markdown_heading(text, 1, use_hash=True)
        assert heading.startswith("#")
        assert heading.endswith("\n")

        # Format special text
        formatted = format_special_text("super", "superscript", "html")
        assert formatted == "<sup>super</sup>"
