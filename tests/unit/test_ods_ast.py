#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_ods_ast.py
"""Unit tests for ODS to AST converter.

Tests cover:
- Basic ODS spreadsheet to AST conversion
- Image extraction from ODS files
- Chart detection in ODS files
- Chart mode options (skip vs data)
- Attachment mode handling

"""

from io import BytesIO

import pytest

from all2md.ast import Document, Heading, Image, Paragraph, Table, Text
from all2md import OdsSpreadsheetOptions
from all2md.parsers.ods_spreadsheet import OdsSpreadsheetToAstConverter

try:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table as OdfTable
    from odf.table import TableCell, TableRow
    from odf.text import P

    HAS_ODFPY = True
except ImportError:
    HAS_ODFPY = False


def create_ods_simple() -> BytesIO:
    """Create a simple ODS file for testing.

    Returns
    -------
    BytesIO
        In-memory ODS file

    """
    doc = OpenDocumentSpreadsheet()

    # Create a table (sheet)
    table = OdfTable(name="Test Sheet")

    # Add header row
    header_row = TableRow()
    for header in ["Name", "Age", "City"]:
        cell = TableCell()
        cell.addElement(P(text=header))
        header_row.addElement(cell)
    table.addElement(header_row)

    # Add data rows
    data = [
        ["Alice", "30", "New York"],
        ["Bob", "25", "London"],
        ["Charlie", "35", "Paris"]
    ]

    for row_data in data:
        row = TableRow()
        for value in row_data:
            cell = TableCell()
            cell.addElement(P(text=value))
            row.addElement(cell)
        table.addElement(row)

    doc.spreadsheet.addElement(table)

    # Save to BytesIO
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output


def create_ods_with_empty_chart() -> BytesIO:
    """Create an ODS file with data that could have a chart.

    Note: Actually embedding charts in ODS is complex, so this just
    creates data that would typically have a chart.

    Returns
    -------
    BytesIO
        In-memory ODS file

    """
    doc = OpenDocumentSpreadsheet()

    # Create a table with chart-worthy data
    table = OdfTable(name="Sales Data")

    # Add header row
    header_row = TableRow()
    for header in ["Month", "Sales"]:
        cell = TableCell()
        cell.addElement(P(text=header))
        header_row.addElement(cell)
    table.addElement(header_row)

    # Add data rows
    data = [
        ["Jan", "100"],
        ["Feb", "150"],
        ["Mar", "200"]
    ]

    for row_data in data:
        row = TableRow()
        for value in row_data:
            cell = TableCell()
            cell.addElement(P(text=value))
            row.addElement(cell)
        table.addElement(row)

    doc.spreadsheet.addElement(table)

    # Save to BytesIO
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output


@pytest.mark.unit
@pytest.mark.skipif(not HAS_ODFPY, reason="odfpy not installed")
class TestOdsBasicConversion:
    """Tests for basic ODS to AST conversion."""

    def test_simple_sheet_conversion(self) -> None:
        """Test converting a simple ODS sheet to AST."""
        ods_data = create_ods_simple()

        converter = OdsSpreadsheetToAstConverter()
        ast_doc = converter.parse(ods_data)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) > 0

        # Should have a heading for sheet title
        heading = ast_doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 2

        # Should have a table
        table = ast_doc.children[1]
        assert isinstance(table, Table)
        assert table.header is not None
        assert len(table.rows) == 3  # Three data rows

    def test_chart_mode_skip(self) -> None:
        """Test that charts are skipped when chart_mode is 'skip'."""
        ods_data = create_ods_with_empty_chart()

        options = OdsSpreadsheetOptions(chart_mode="skip")
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Should have table but no chart placeholder paragraphs
        assert isinstance(ast_doc, Document)

        # Count table nodes
        tables = [child for child in ast_doc.children if isinstance(child, Table)]
        assert len(tables) == 1  # Only the data table

        # No chart detection paragraphs
        chart_paragraphs = [
            child for child in ast_doc.children
            if isinstance(child, Paragraph) and
            any(isinstance(node, Text) and "Chart detected" in node.content
                for node in child.content)
        ]
        assert len(chart_paragraphs) == 0

    def test_chart_mode_data(self) -> None:
        """Test chart_mode data option.

        Note: Since actual chart embedding in ODS is complex,
        this just verifies the option doesn't break conversion.
        """
        ods_data = create_ods_with_empty_chart()

        options = OdsSpreadsheetOptions(chart_mode="data")
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Should still convert successfully
        assert isinstance(ast_doc, Document)

        # Count table nodes
        tables = [child for child in ast_doc.children if isinstance(child, Table)]
        assert len(tables) == 1  # Data table


@pytest.mark.unit
@pytest.mark.skipif(not HAS_ODFPY, reason="odfpy not installed")
class TestOdsImageExtraction:
    """Tests for image extraction from ODS files."""

    def test_image_extraction_skip_mode(self) -> None:
        """Test that images are skipped when attachment_mode is 'skip'."""
        ods_data = create_ods_simple()

        options = OdsSpreadsheetOptions(attachment_mode="skip")
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        assert isinstance(ast_doc, Document)

        # Should have no Image nodes
        images = [child for child in ast_doc.children if isinstance(child, Image)]
        assert len(images) == 0

    def test_image_extraction_alt_text_mode(self) -> None:
        """Test image extraction with alt_text mode (no actual images in fixture)."""
        ods_data = create_ods_simple()

        options = OdsSpreadsheetOptions(attachment_mode="alt_text")
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        assert isinstance(ast_doc, Document)

        # No images in this fixture, but should still convert successfully
        images = [child for child in ast_doc.children if isinstance(child, Image)]
        assert len(images) == 0


@pytest.mark.unit
@pytest.mark.skipif(not HAS_ODFPY, reason="odfpy not installed")
class TestOdsOptions:
    """Tests for ODS conversion options."""

    def test_include_sheet_titles(self) -> None:
        """Test include_sheet_titles option."""
        ods_data = create_ods_simple()

        # With sheet titles
        options = OdsSpreadsheetOptions(include_sheet_titles=True)
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Should have heading for sheet title
        assert any(isinstance(child, Heading) and child.content[0].content == "Test Sheet"
                   for child in ast_doc.children
                   if isinstance(child, Heading) and child.content)

    def test_no_sheet_titles(self) -> None:
        """Test that sheet titles are not included when disabled."""
        ods_data = create_ods_simple()

        # Without sheet titles
        options = OdsSpreadsheetOptions(include_sheet_titles=False)
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Should not have heading for sheet title
        headings = [child for child in ast_doc.children if isinstance(child, Heading)]
        assert len(headings) == 0

    def test_max_rows_option(self) -> None:
        """Test max_rows option limits data rows."""
        ods_data = create_ods_simple()

        # Limit to 2 data rows
        options = OdsSpreadsheetOptions(max_rows=2)
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Find the table
        tables = [child for child in ast_doc.children if isinstance(child, Table)]
        assert len(tables) == 1

        table = tables[0]
        # Should have max 2 data rows (plus header)
        assert len(table.rows) <= 2

    def test_header_case_transformation(self) -> None:
        """Test header_case option transforms header text."""
        ods_data = create_ods_simple()

        # Test upper case transformation
        options = OdsSpreadsheetOptions(header_case="upper")
        converter = OdsSpreadsheetToAstConverter(options=options)
        ast_doc = converter.parse(ods_data)

        # Find the table and check header case
        tables = [child for child in ast_doc.children if isinstance(child, Table)]
        assert len(tables) == 1

        table = tables[0]
        # Headers should be uppercase
        for cell in table.header.cells:
            text_content = cell.content[0].content
            assert text_content.isupper()
