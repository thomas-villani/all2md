#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_csv_parser.py
"""Unit tests for CSV/TSV to AST converter.

Tests cover:
- Basic CSV/TSV parsing
- Delimiter detection and handling
- Encoding detection
- Header handling
- Max rows/cols limits
- Empty file handling
- Edge cases

"""

from io import BytesIO, StringIO
from pathlib import Path

import pytest

from all2md.ast import Document, Table
from all2md.options.csv import CsvOptions
from all2md.parsers.csv import (
    CsvToAstConverter,
    _detect_csv_tsv_content,
    _make_csv_dialect,
    _validate_csv_delimiter,
)


@pytest.mark.unit
class TestCsvBasicParsing:
    """Tests for basic CSV parsing functionality."""

    def test_parse_simple_csv(self) -> None:
        """Test parsing a simple CSV file."""
        csv_content = b"name,age,city\nAlice,30,Boston\nBob,25,Seattle"
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)

    def test_parse_csv_from_string_path(self, tmp_path: Path) -> None:
        """Test parsing CSV from file path."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\nval1,val2")

        converter = CsvToAstConverter()
        doc = converter.parse(str(csv_file))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_parse_csv_from_path_object(self, tmp_path: Path) -> None:
        """Test parsing CSV from Path object."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("header1,header2\ndata1,data2")

        converter = CsvToAstConverter()
        doc = converter.parse(csv_file)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_parse_empty_csv(self) -> None:
        """Test parsing an empty CSV file."""
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(b""))

        assert isinstance(doc, Document)
        assert len(doc.children) == 0


@pytest.mark.unit
class TestTsvParsing:
    """Tests for TSV parsing functionality."""

    def test_parse_tsv_by_extension(self, tmp_path: Path) -> None:
        """Test parsing TSV file based on .tsv extension."""
        tsv_file = tmp_path / "test.tsv"
        tsv_file.write_text("name\tage\nAlice\t30")

        converter = CsvToAstConverter()
        doc = converter.parse(tsv_file)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)

    def test_parse_tsv_with_explicit_delimiter(self) -> None:
        """Test parsing TSV with explicit tab delimiter."""
        tsv_content = b"col1\tcol2\tcol3\nval1\tval2\tval3"
        options = CsvOptions(delimiter="\t")
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(tsv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1


@pytest.mark.unit
class TestDelimiterDetection:
    """Tests for delimiter detection functionality."""

    def test_detect_comma_delimiter(self) -> None:
        """Test detection of comma-separated values."""
        csv_content = b"a,b,c\n1,2,3\n4,5,6"
        options = CsvOptions(detect_csv_dialect=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_detect_semicolon_delimiter(self) -> None:
        """Test detection of semicolon-separated values."""
        csv_content = b"a;b;c\n1;2;3\n4;5;6"
        options = CsvOptions(detect_csv_dialect=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_detect_pipe_delimiter(self) -> None:
        """Test detection of pipe-separated values."""
        csv_content = b"a|b|c\n1|2|3\n4|5|6"
        options = CsvOptions(detect_csv_dialect=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_explicit_delimiter_overrides_detection(self) -> None:
        """Test that explicit delimiter takes precedence."""
        # Content with commas, but we force semicolon
        csv_content = b"a;b;c\n1;2;3"
        options = CsvOptions(delimiter=";")
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1


@pytest.mark.unit
class TestEncodingHandling:
    """Tests for encoding detection and handling."""

    def test_utf8_encoding(self) -> None:
        """Test parsing UTF-8 encoded CSV."""
        csv_content = "name,city\nMüller,München\nCafé,Zürich".encode("utf-8")
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_utf8_bom_encoding(self) -> None:
        """Test parsing UTF-8 with BOM."""
        csv_content = b"\xef\xbb\xbfname,value\ntest,123"
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_latin1_encoding(self) -> None:
        """Test parsing Latin-1 encoded CSV."""
        csv_content = "name,city\nMüller,Paris".encode("latin-1")
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1


@pytest.mark.unit
class TestHeaderHandling:
    """Tests for header row handling."""

    def test_with_header_row(self) -> None:
        """Test parsing with header row enabled."""
        csv_content = b"name,age\nAlice,30\nBob,25"
        options = CsvOptions(has_header=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        table = doc.children[0]
        assert isinstance(table, Table)
        # First row should be header
        assert len(table.rows) >= 1

    def test_without_header_row(self) -> None:
        """Test parsing without header row."""
        csv_content = b"Alice,30\nBob,25"
        options = CsvOptions(has_header=False)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        table = doc.children[0]
        assert isinstance(table, Table)

    def test_header_case_transformation_upper(self) -> None:
        """Test header case transformation to uppercase."""
        csv_content = b"name,age\nAlice,30"
        options = CsvOptions(has_header=True, header_case="upper")
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_header_case_transformation_lower(self) -> None:
        """Test header case transformation to lowercase."""
        csv_content = b"NAME,AGE\nAlice,30"
        options = CsvOptions(has_header=True, header_case="lower")
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestRowColumnLimits:
    """Tests for max_rows and max_cols options."""

    def test_max_rows_limit(self) -> None:
        """Test limiting number of rows."""
        csv_content = b"col1,col2\nrow1,val1\nrow2,val2\nrow3,val3\nrow4,val4"
        options = CsvOptions(max_rows=2)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)
        # Should have table and truncation indicator
        assert len(doc.children) >= 1

    def test_max_cols_limit(self) -> None:
        """Test limiting number of columns."""
        csv_content = b"col1,col2,col3,col4\nval1,val2,val3,val4"
        options = CsvOptions(max_cols=2)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_skip_empty_rows(self) -> None:
        """Test skipping empty rows."""
        csv_content = b"\n\nname,age\nAlice,30\n\n"
        options = CsvOptions(skip_empty_rows=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_strip_whitespace(self) -> None:
        """Test stripping whitespace from cells."""
        csv_content = b"  name  ,  age  \n  Alice  ,  30  "
        options = CsvOptions(strip_whitespace=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestQuoteHandling:
    """Tests for quote character handling."""

    def test_quoted_fields(self) -> None:
        """Test parsing fields with quotes."""
        csv_content = b'"name","description"\n"Alice","Said, ""Hello"""\n"Bob","Works here"'
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_custom_quote_char(self) -> None:
        """Test parsing with custom quote character."""
        csv_content = b"'name','value'\n'test','hello'"
        options = CsvOptions(quote_char="'")
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestContentDetection:
    """Tests for CSV/TSV content detection."""

    def test_detect_csv_content(self) -> None:
        """Test detection of CSV content."""
        csv_content = b"col1,col2,col3\nval1,val2,val3\nval4,val5,val6"
        assert _detect_csv_tsv_content(csv_content) is True

    def test_detect_tsv_content(self) -> None:
        """Test detection of TSV content."""
        tsv_content = b"col1\tcol2\tcol3\nval1\tval2\tval3\nval4\tval5\tval6"
        assert _detect_csv_tsv_content(tsv_content) is True

    def test_non_csv_content(self) -> None:
        """Test that non-CSV content is not detected."""
        non_csv = b"This is just plain text without delimiters."
        assert _detect_csv_tsv_content(non_csv) is False

    def test_single_line_not_csv(self) -> None:
        """Test that single line is not detected as CSV."""
        single_line = b"just,one,line"
        assert _detect_csv_tsv_content(single_line) is False


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for helper functions."""

    def test_make_csv_dialect_with_comma(self) -> None:
        """Test creating dialect with comma delimiter."""
        dialect = _make_csv_dialect(delimiter=",")
        assert dialect.delimiter == ","

    def test_make_csv_dialect_with_tab(self) -> None:
        """Test creating dialect with tab delimiter."""
        dialect = _make_csv_dialect(delimiter="\t")
        assert dialect.delimiter == "\t"

    def test_make_csv_dialect_with_quote_char(self) -> None:
        """Test creating dialect with custom quote char."""
        dialect = _make_csv_dialect(quotechar="'")
        assert dialect.quotechar == "'"

    def test_validate_csv_delimiter_valid(self) -> None:
        """Test delimiter validation with valid delimiter."""
        sample = "col1,col2,col3\nval1,val2,val3\nval4,val5,val6"
        dialect = _make_csv_dialect(delimiter=",")
        assert _validate_csv_delimiter(sample, dialect) is True

    def test_validate_csv_delimiter_invalid(self) -> None:
        """Test delimiter validation with wrong delimiter."""
        sample = "col1;col2;col3\nval1;val2;val3"
        dialect = _make_csv_dialect(delimiter=",")
        # Wrong delimiter should produce single column
        assert _validate_csv_delimiter(sample, dialect) is False


@pytest.mark.unit
class TestStringIOInput:
    """Tests for StringIO input handling."""

    def test_parse_from_stringio(self) -> None:
        """Test parsing from StringIO directly."""
        csv_content = StringIO("name,age\nAlice,30\nBob,25")
        converter = CsvToAstConverter()
        # This tests the _read_text_stream_for_csv path for StringIO
        doc = converter.csv_to_ast(csv_content, delimiter=",")

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_column_csv(self) -> None:
        """Test CSV with single column."""
        csv_content = b"name\nAlice\nBob"
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_csv_with_empty_cells(self) -> None:
        """Test CSV with empty cells."""
        csv_content = b"name,age,city\nAlice,,Boston\n,25,"
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_csv_with_newlines_in_quoted_fields(self) -> None:
        """Test CSV with newlines inside quoted fields."""
        csv_content = b'"name","description"\n"Alice","Line1\nLine2"'
        converter = CsvToAstConverter()
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_dialect_detection_fallback(self) -> None:
        """Test dialect detection fallback on error."""
        # Malformed content that might cause sniffer to fail
        csv_content = b"a,b,c\n1,2,3"
        options = CsvOptions(detect_csv_dialect=True)
        converter = CsvToAstConverter(options)
        doc = converter.parse(BytesIO(csv_content))

        assert isinstance(doc, Document)

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            CsvToAstConverter(options="invalid")
