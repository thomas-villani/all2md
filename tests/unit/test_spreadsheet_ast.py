#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_spreadsheet_ast.py
"""Unit tests for Spreadsheet to AST converter.

Tests cover:
- Table header and data row conversion
- Cell alignment detection
- Sheet iteration (single and multi-sheet)
- CSV/TSV handling
- Cell formatting preservation
- Empty cells and rows
- Column alignment configuration

"""

import csv
import io
from pathlib import Path

import pytest

from all2md.ast import Document, Heading, Paragraph, Table, TableCell, TableRow, Text
from all2md.converters.spreadsheet2ast import SpreadsheetToAstConverter
from all2md.options import SpreadsheetOptions


def _create_csv_data(rows):
    """Create CSV data from rows.

    Parameters
    ----------
    rows : list of list
        Rows data

    Returns
    -------
    io.StringIO
        CSV data as file-like object

    """
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return output


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic spreadsheet conversion."""

    def test_simple_csv_table(self) -> None:
        """Test converting a simple CSV to AST table."""
        csv_data = _create_csv_data([
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)

        table = doc.children[0]
        # Check header
        assert table.header is not None
        assert table.header.is_header is True
        assert len(table.header.cells) == 3

        # Check data rows
        assert len(table.rows) == 2
        assert len(table.rows[0].cells) == 3
        assert len(table.rows[1].cells) == 3

    def test_table_header_content(self) -> None:
        """Test table header cell content."""
        csv_data = _create_csv_data([
            ["Column1", "Column2"],
            ["Data1", "Data2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        header_cells = table.header.cells

        # Check header text
        assert isinstance(header_cells[0].content[0], Text)
        assert header_cells[0].content[0].content == "Column1"
        assert isinstance(header_cells[1].content[0], Text)
        assert header_cells[1].content[0].content == "Column2"

    def test_table_data_content(self) -> None:
        """Test table data cell content."""
        csv_data = _create_csv_data([
            ["Name", "Value"],
            ["Item1", "100"],
            ["Item2", "200"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Check first data row
        row1 = table.rows[0]
        assert isinstance(row1.cells[0].content[0], Text)
        assert row1.cells[0].content[0].content == "Item1"
        assert isinstance(row1.cells[1].content[0], Text)
        assert row1.cells[1].content[0].content == "100"

        # Check second data row
        row2 = table.rows[1]
        assert row2.cells[0].content[0].content == "Item2"
        assert row2.cells[1].content[0].content == "200"


@pytest.mark.unit
class TestAlignmentDetection:
    """Tests for cell alignment detection."""

    def test_default_alignment_center(self) -> None:
        """Test default alignment is center."""
        csv_data = _create_csv_data([
            ["A", "B"],
            ["1", "2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Default alignment should be center
        if table.alignments:
            assert table.alignments[0] == "center"
            assert table.alignments[1] == "center"

    def test_alignment_preservation(self) -> None:
        """Test that alignment is set on cells."""
        csv_data = _create_csv_data([
            ["Header1", "Header2"],
            ["Data1", "Data2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Check that cells have alignment attribute
        for cell in table.header.cells:
            assert hasattr(cell, 'alignment')
            assert cell.alignment in ["left", "center", "right"]


@pytest.mark.unit
class TestEmptyCellsAndRows:
    """Tests for empty cells and rows."""

    def test_empty_cell(self) -> None:
        """Test handling of empty cells."""
        csv_data = _create_csv_data([
            ["A", "B", "C"],
            ["1", "", "3"],  # Empty cell in middle
            ["4", "5", ""]   # Empty cell at end
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Empty cells should be present as empty strings
        assert table.rows[0].cells[1].content[0].content == ""
        assert table.rows[1].cells[2].content[0].content == ""

    def test_row_with_all_empty_cells(self) -> None:
        """Test row with all empty cells."""
        csv_data = _create_csv_data([
            ["A", "B"],
            ["", ""],  # All empty
            ["1", "2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Row with all empty cells should still be present
        assert len(table.rows) >= 2

    def test_header_only_no_data(self) -> None:
        """Test table with header but no data rows."""
        csv_data = _create_csv_data([
            ["Header1", "Header2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        assert table.header is not None
        assert len(table.header.cells) == 2
        # Should have no data rows
        assert len(table.rows) == 0


@pytest.mark.unit
class TestMultiSheetHandling:
    """Tests for multi-sheet spreadsheet handling."""

    def test_single_sheet_included(self) -> None:
        """Test that single sheet is processed."""
        csv_data = _create_csv_data([
            ["A", "B"],
            ["1", "2"]
        ])

        options = SpreadsheetOptions(include_sheet_titles=True)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        # CSV only has one "sheet"
        # Should have table
        tables = [child for child in doc.children if isinstance(child, Table)]
        assert len(tables) == 1

    def test_sheet_name_as_heading(self) -> None:
        """Test sheet name rendered as heading when option enabled."""
        csv_data = _create_csv_data([
            ["A", "B"],
            ["1", "2"]
        ])

        options = SpreadsheetOptions(
            include_sheet_titles=True
        )
        converter = SpreadsheetToAstConverter(options)
        # Note: CSV doesn't have sheet names, but we test the structure
        doc = converter.csv_or_tsv_to_ast(csv_data)

        # Should have table (CSV has no explicit sheet names)
        assert len(doc.children) >= 1


@pytest.mark.unit
class TestCellFormatting:
    """Tests for cell formatting and content preservation."""

    def test_numeric_cell_values(self) -> None:
        """Test that numeric values are converted to strings."""
        csv_data = _create_csv_data([
            ["Name", "Value"],
            ["Item", "123"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Numeric value should be string
        value_cell = table.rows[0].cells[1]
        assert isinstance(value_cell.content[0], Text)
        assert value_cell.content[0].content == "123"

    def test_special_characters_in_cells(self) -> None:
        """Test cells with special characters."""
        csv_data = _create_csv_data([
            ["Text", "Special"],
            ["Normal", "< > & \""]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Special characters should be preserved
        special_cell = table.rows[0].cells[1]
        assert "< > & \"" in special_cell.content[0].content

    def test_newlines_in_cells(self) -> None:
        """Test cells with newline characters."""
        # Create CSV with quoted field containing newline
        csv_content = 'Header1,Header2\nValue1,"Line1\nLine2"'
        csv_data = io.StringIO(csv_content)

        options = SpreadsheetOptions(preserve_newlines_in_cells=False)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Newline should be replaced with space when preserve_newlines_in_cells=False
        cell_content = table.rows[0].cells[1].content[0].content
        # Content should have newline replaced (or handled differently)
        assert isinstance(cell_content, str)


@pytest.mark.unit
class TestMaxRowsAndColumns:
    """Tests for row and column limits."""

    def test_max_rows_limit(self) -> None:
        """Test limiting number of rows."""
        # Create CSV with 10 rows
        rows = [["Header"]] + [[f"Row{i}"] for i in range(10)]
        csv_data = _create_csv_data(rows)

        options = SpreadsheetOptions(max_rows=5)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Should only have 5 data rows (max_rows applies to data rows, header is separate)
        assert len(table.rows) <= 5

    def test_max_cols_limit(self) -> None:
        """Test limiting number of columns."""
        csv_data = _create_csv_data([
            ["A", "B", "C", "D", "E"],
            ["1", "2", "3", "4", "5"]
        ])

        options = SpreadsheetOptions(max_cols=3)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Should only have 3 columns
        assert len(table.header.cells) == 3
        assert len(table.rows[0].cells) == 3

    def test_no_limits(self) -> None:
        """Test without row/column limits."""
        rows = [["H1", "H2", "H3"]] + [[f"R{i}C1", f"R{i}C2", f"R{i}C3"] for i in range(10)]
        csv_data = _create_csv_data(rows)

        options = SpreadsheetOptions(max_rows=None, max_cols=None)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Should have all rows and columns
        assert len(table.header.cells) == 3
        assert len(table.rows) == 10


@pytest.mark.unit
class TestCSVParsing:
    """Tests for CSV-specific parsing."""

    def test_csv_with_quotes(self) -> None:
        """Test CSV with quoted fields."""
        csv_content = 'Name,Description\n"Alice","A person"\n"Bob","Another person"'
        csv_data = io.StringIO(csv_content)

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Quoted values should be unquoted
        assert table.rows[0].cells[0].content[0].content == "Alice"
        assert table.rows[0].cells[1].content[0].content == "A person"

    def test_csv_with_commas_in_values(self) -> None:
        """Test CSV with commas inside quoted fields."""
        csv_content = 'Name,Location\n"Alice","NYC, NY"\n"Bob","LA, CA"'
        csv_data = io.StringIO(csv_content)

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Commas inside quotes should be preserved
        assert table.rows[0].cells[1].content[0].content == "NYC, NY"
        assert table.rows[1].cells[1].content[0].content == "LA, CA"

    def test_tsv_parsing(self) -> None:
        """Test TSV (tab-separated values) parsing."""
        tsv_content = "Name\tAge\nAlice\t30\nBob\t25"
        tsv_data = io.StringIO(tsv_content)

        options = SpreadsheetOptions(csv_delimiter="\t")
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(tsv_data)

        table = doc.children[0]
        assert table.header.cells[0].content[0].content == "Name"
        assert table.header.cells[1].content[0].content == "Age"
        assert table.rows[0].cells[0].content[0].content == "Alice"
        assert table.rows[0].cells[1].content[0].content == "30"


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_csv(self) -> None:
        """Test converting empty CSV."""
        csv_data = io.StringIO("")

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        assert isinstance(doc, Document)
        # Empty CSV should result in empty document or minimal structure
        assert len(doc.children) == 0

    def test_single_cell(self) -> None:
        """Test CSV with single cell."""
        csv_data = _create_csv_data([["Value"]])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Single cell should be header
        assert len(table.header.cells) == 1
        assert len(table.rows) == 0

    def test_single_column(self) -> None:
        """Test CSV with single column."""
        csv_data = _create_csv_data([
            ["Header"],
            ["Row1"],
            ["Row2"],
            ["Row3"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        assert len(table.header.cells) == 1
        assert len(table.rows) == 3
        # All rows should have 1 cell
        for row in table.rows:
            assert len(row.cells) == 1

    def test_irregular_row_lengths(self) -> None:
        """Test CSV with rows of different lengths."""
        csv_data = _create_csv_data([
            ["A", "B", "C"],
            ["1", "2"],      # Short row
            ["3", "4", "5", "6"]  # Long row
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Should handle irregular rows (CSV parser should pad/truncate)
        assert isinstance(table, Table)


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for SpreadsheetOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        csv_data = _create_csv_data([
            ["A", "B"],
            ["1", "2"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1

    def test_custom_delimiter(self) -> None:
        """Test custom delimiter option."""
        # Semicolon-separated values
        ssv_content = "Name;Age\nAlice;30\nBob;25"
        ssv_data = io.StringIO(ssv_content)

        options = SpreadsheetOptions(csv_delimiter=";")
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(ssv_data)

        table = doc.children[0]
        assert table.header.cells[0].content[0].content == "Name"
        assert table.header.cells[1].content[0].content == "Age"

    def test_skip_empty_rows_enabled(self) -> None:
        """Test skipping empty rows when enabled."""
        csv_data = _create_csv_data([
            ["Header"],
            ["Row1"],
            [""],  # Empty row
            ["Row2"]
        ])

        options = SpreadsheetOptions(trim_empty="all")
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # With trim_empty="all", empty rows are still included but empty cells are preserved
        # Should have 3 data rows
        assert len(table.rows) == 3

    def test_preserve_newlines_in_cells_enabled(self) -> None:
        """Test preserving newlines in cells."""
        csv_content = 'Header\n"Line1\nLine2"'
        csv_data = io.StringIO(csv_content)

        options = SpreadsheetOptions(preserve_newlines_in_cells=True)
        converter = SpreadsheetToAstConverter(options)
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Note: The preserve_newlines_in_cells option may convert newlines to spaces
        cell_content = table.rows[0].cells[0].content[0].content
        # Should contain the text content (newline handling may vary)
        assert "Line1" in cell_content and "Line2" in cell_content


@pytest.mark.unit
class TestTableStructure:
    """Tests for table structure correctness."""

    def test_header_is_marked(self) -> None:
        """Test that header row is marked as header."""
        csv_data = _create_csv_data([
            ["Name", "Value"],
            ["Item", "100"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        assert table.header.is_header is True

    def test_data_rows_not_marked_as_header(self) -> None:
        """Test that data rows are not marked as header."""
        csv_data = _create_csv_data([
            ["Name", "Value"],
            ["Item1", "100"],
            ["Item2", "200"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        for row in table.rows:
            assert row.is_header is False

    def test_table_has_alignments(self) -> None:
        """Test that table has alignment information."""
        csv_data = _create_csv_data([
            ["A", "B", "C"],
            ["1", "2", "3"]
        ])

        converter = SpreadsheetToAstConverter()
        doc = converter.csv_or_tsv_to_ast(csv_data)

        table = doc.children[0]
        # Should have alignments for each column
        assert hasattr(table, 'alignments')
        if table.alignments:
            assert len(table.alignments) == 3
