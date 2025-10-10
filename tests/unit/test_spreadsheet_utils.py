#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for shared spreadsheet utility functions."""

from all2md.ast import Table, TableCell, TableRow, Text
from all2md.utils.spreadsheet import (
    build_table_ast,
    create_table_cell,
    sanitize_cell_text,
    transform_header_case,
    trim_columns,
    trim_rows,
)


class TestSanitizeCellText:
    """Tests for sanitize_cell_text function."""

    def test_none_value(self):
        """Test that None is converted to empty string."""
        result = sanitize_cell_text(None)
        assert result == ""

    def test_string_value(self):
        """Test that string values are preserved."""
        result = sanitize_cell_text("test value")
        assert result == "test value"

    def test_numeric_value(self):
        """Test that numeric values are converted to strings."""
        result = sanitize_cell_text(123)
        assert result == "123"

    def test_newlines_without_preserve(self):
        """Test that newlines are replaced with spaces by default."""
        result = sanitize_cell_text("line1\nline2\rline3\r\nline4")
        assert result == "line1 line2 line3 line4"

    def test_newlines_with_preserve(self):
        """Test that newlines are preserved as <br> tags when requested."""
        result = sanitize_cell_text("line1\nline2\rline3\r\nline4", preserve_newlines=True)
        assert result == "line1<br>line2<br>line3<br>line4"


class TestBuildTableAst:
    """Tests for build_table_ast function."""

    def test_simple_table(self):
        """Test building a simple table with header and data rows."""
        header = ["Col1", "Col2", "Col3"]
        rows = [["A1", "B1", "C1"], ["A2", "B2", "C2"]]
        alignments = ["left", "center", "right"]

        table = build_table_ast(header, rows, alignments)

        assert isinstance(table, Table)
        assert table.header is not None
        assert len(table.header.cells) == 3
        assert len(table.rows) == 2
        assert table.alignments == ["left", "center", "right"]

    def test_header_cells_alignment(self):
        """Test that header cells have correct alignment."""
        header = ["Col1", "Col2"]
        rows = []
        alignments = ["left", "right"]

        table = build_table_ast(header, rows, alignments)

        assert table.header.cells[0].alignment == "left"
        assert table.header.cells[1].alignment == "right"

    def test_data_cells_content(self):
        """Test that data cells contain correct content."""
        header = ["H1"]
        rows = [["Data1"], ["Data2"]]
        alignments = ["center"]

        table = build_table_ast(header, rows, alignments)

        assert len(table.rows) == 2
        assert table.rows[0].cells[0].content[0].content == "Data1"
        assert table.rows[1].cells[0].content[0].content == "Data2"


class TestCreateTableCell:
    """Tests for create_table_cell function."""

    def test_simple_cell(self):
        """Test creating a simple cell without spans."""
        cell = create_table_cell("test")

        assert isinstance(cell, TableCell)
        assert cell.content[0].content == "test"
        assert cell.alignment == "center"
        assert cell.colspan == 1
        assert cell.rowspan == 1

    def test_cell_with_alignment(self):
        """Test creating a cell with custom alignment."""
        cell = create_table_cell("test", alignment="left")

        assert cell.alignment == "left"

    def test_cell_with_spans(self):
        """Test creating a cell with colspan and rowspan."""
        cell = create_table_cell("test", colspan=2, rowspan=3)

        assert cell.colspan == 2
        assert cell.rowspan == 3


class TestTransformHeaderCase:
    """Tests for transform_header_case function."""

    def test_preserve_case(self):
        """Test that preserve mode keeps original case."""
        header = ["Header1", "HEADER2", "header3"]
        result = transform_header_case(header, "preserve")
        assert result == ["Header1", "HEADER2", "header3"]

    def test_title_case(self):
        """Test title case transformation."""
        header = ["header one", "HEADER TWO", "header_three"]
        result = transform_header_case(header, "title")
        assert result == ["Header One", "Header Two", "Header_Three"]

    def test_upper_case(self):
        """Test upper case transformation."""
        header = ["header1", "Header2", "HEADER3"]
        result = transform_header_case(header, "upper")
        assert result == ["HEADER1", "HEADER2", "HEADER3"]

    def test_lower_case(self):
        """Test lower case transformation."""
        header = ["HEADER1", "Header2", "header3"]
        result = transform_header_case(header, "lower")
        assert result == ["header1", "header2", "header3"]


class TestTrimRows:
    """Tests for trim_rows function."""

    def test_no_trimming(self):
        """Test that 'none' mode does no trimming."""
        rows = [["", ""], ["A", "B"], ["", ""]]
        result = trim_rows(rows, "none")
        assert len(result) == 3

    def test_trim_leading(self):
        """Test trimming leading empty rows."""
        rows = [["", ""], ["", ""], ["A", "B"], ["C", "D"]]
        result = trim_rows(rows, "leading")
        assert len(result) == 2
        assert result[0] == ["A", "B"]

    def test_trim_trailing(self):
        """Test trimming trailing empty rows."""
        rows = [["A", "B"], ["C", "D"], ["", ""], ["", ""]]
        result = trim_rows(rows, "trailing")
        assert len(result) == 2
        assert result[0] == ["A", "B"]

    def test_trim_both(self):
        """Test trimming both leading and trailing empty rows."""
        rows = [["", ""], ["A", "B"], ["C", "D"], ["", ""]]
        result = trim_rows(rows, "both")
        assert len(result) == 2
        assert result[0] == ["A", "B"]
        assert result[1] == ["C", "D"]


class TestTrimColumns:
    """Tests for trim_columns function."""

    def test_no_trimming(self):
        """Test that 'none' mode does no trimming."""
        rows = [["", "A", "B", ""], ["", "C", "D", ""]]
        result = trim_columns(rows, "none")
        assert len(result[0]) == 4

    def test_trim_leading(self):
        """Test trimming leading empty columns."""
        rows = [["", "", "A", "B"], ["", "", "C", "D"]]
        result = trim_columns(rows, "leading")
        assert len(result[0]) == 2
        assert result[0] == ["A", "B"]

    def test_trim_trailing(self):
        """Test trimming trailing empty columns."""
        rows = [["A", "B", "", ""], ["C", "D", "", ""]]
        result = trim_columns(rows, "trailing")
        assert len(result[0]) == 2
        assert result[0] == ["A", "B"]

    def test_trim_both(self):
        """Test trimming both leading and trailing empty columns."""
        rows = [["", "A", "B", ""], ["", "C", "D", ""]]
        result = trim_columns(rows, "both")
        assert len(result[0]) == 2
        assert result[0] == ["A", "B"]
        assert result[1] == ["C", "D"]

    def test_partial_empty_columns(self):
        """Test that partially empty columns are not trimmed."""
        rows = [["", "A", "B"], ["X", "C", "D"]]
        result = trim_columns(rows, "leading")
        # First column has "X" in second row, so it shouldn't be trimmed
        assert len(result[0]) == 3
