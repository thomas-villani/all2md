#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_csv_renderer.py
"""Unit tests for CsvRenderer.

Tests cover:
- Rendering tables to CSV format
- Table selection by index and heading
- Multi-table handling modes
- Merged cell handling
- CSV dialect options
- Edge cases and error handling

"""

import pytest

from all2md.ast import Document, Heading, Paragraph, Table, TableCell, TableRow, Text
from all2md.exceptions import RenderingError
from all2md.options.csv import CsvRendererOptions
from all2md.renderers.csv import CsvRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic CSV rendering."""

    def test_render_simple_table(self) -> None:
        """Test rendering a simple table to CSV."""
        table = Table(
            header=TableRow(
                cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
            ),
            rows=[
                TableRow(cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]),
                TableRow(cells=[TableCell(content=[Text(content="Bob")]), TableCell(content=[Text(content="25")])]),
            ],
        )
        doc = Document(children=[table])
        renderer = CsvRenderer()
        result = renderer.render_to_string(doc)

        expected = "Name,Age\nAlice,30\nBob,25\n"
        assert result == expected

    def test_render_table_without_header(self) -> None:
        """Test rendering a table without header row."""
        table = Table(
            rows=[
                TableRow(cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]),
                TableRow(cells=[TableCell(content=[Text(content="Bob")]), TableCell(content=[Text(content="25")])]),
            ]
        )
        doc = Document(children=[table])
        renderer = CsvRenderer()
        result = renderer.render_to_string(doc)

        expected = "Alice,30\nBob,25\n"
        assert result == expected

    def test_empty_document_raises_error(self) -> None:
        """Test that rendering a document with no tables raises error."""
        doc = Document(children=[Paragraph(content=[Text(content="No tables here")])])
        renderer = CsvRenderer()

        with pytest.raises(RenderingError, match="No tables found"):
            renderer.render_to_string(doc)

    def test_render_with_quotes(self) -> None:
        """Test rendering cells that need quoting."""
        table = Table(
            header=TableRow(
                cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Description")])]
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Alice")]),
                        TableCell(content=[Text(content="Works at ACME, Inc.")]),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])
        renderer = CsvRenderer()
        result = renderer.render_to_string(doc)

        # Cells with commas should be quoted
        assert '"Works at ACME, Inc."' in result


@pytest.mark.unit
class TestTableSelection:
    """Tests for table selection options."""

    def test_select_first_table_by_default(self) -> None:
        """Test that first table is selected by default."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 1")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 2")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 2")])])],
        )
        doc = Document(children=[table1, table2])

        renderer = CsvRenderer()
        result = renderer.render_to_string(doc)

        assert "Table 1" in result
        assert "Table 2" not in result

    def test_select_table_by_index(self) -> None:
        """Test selecting table by index."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 1")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 2")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 2")])])],
        )
        doc = Document(children=[table1, table2])

        options = CsvRendererOptions(table_index=1)
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Table 2" in result
        assert "Table 1" not in result

    def test_select_table_by_heading(self) -> None:
        """Test selecting table by preceding heading."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Introduction")]),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Intro Table")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Intro Data")])])],
                ),
                Heading(level=1, content=[Text(content="Results and Analysis")]),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Results Table")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Results Data")])])],
                ),
            ]
        )

        options = CsvRendererOptions(table_heading="Results")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Results Table" in result
        assert "Intro Table" not in result

    def test_heading_search_case_insensitive(self) -> None:
        """Test that heading search is case-insensitive."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="RESULTS")]),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Data")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="1")])])],
                ),
            ]
        )

        options = CsvRendererOptions(table_heading="results")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Data" in result

    def test_nonexistent_heading_raises_error(self) -> None:
        """Test that searching for nonexistent heading raises error."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Data")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="1")])])],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(table_heading="Nonexistent")
        renderer = CsvRenderer(options)

        with pytest.raises(RenderingError, match="No table found after heading"):
            renderer.render_to_string(doc)


@pytest.mark.unit
class TestMultiTableMode:
    """Tests for multi-table handling."""

    def test_multi_table_mode_all(self) -> None:
        """Test rendering all tables with multi_table_mode='all'."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 1")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 2")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 2")])])],
        )
        doc = Document(children=[table1, table2])

        options = CsvRendererOptions(multi_table_mode="all", table_index=None)
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Table 1" in result
        assert "Table 2" in result

    def test_multi_table_mode_error(self) -> None:
        """Test that multi_table_mode='error' raises error with multiple tables."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 1")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Table 2")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Data 2")])])],
        )
        doc = Document(children=[table1, table2])

        options = CsvRendererOptions(multi_table_mode="error", table_index=None)
        renderer = CsvRenderer(options)

        with pytest.raises(RenderingError, match="multi_table_mode='error'"):
            renderer.render_to_string(doc)

    def test_include_table_headings(self) -> None:
        """Test including headings as comments in multi-table output."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="First Section")]),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col1")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="A")])])],
                ),
                Heading(level=1, content=[Text(content="Second Section")]),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col2")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="B")])])],
                ),
            ]
        )

        options = CsvRendererOptions(multi_table_mode="all", table_index=None, include_table_headings=True)
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "# First Section" in result
        assert "# Second Section" in result


@pytest.mark.unit
class TestMergedCells:
    """Tests for merged cell handling."""

    def test_merged_cells_repeat_mode(self) -> None:
        """Test that merged cells repeat value by default."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Merged")], colspan=2),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(handle_merged_cells="repeat")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have "Merged,Merged"
        assert "Merged,Merged" in result

    def test_merged_cells_blank_mode(self) -> None:
        """Test merged cells with blank mode."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Merged")], colspan=2),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(handle_merged_cells="blank")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have "Merged,"
        lines = result.strip().split("\n")
        assert lines[-1] == "Merged,"

    def test_merged_cells_placeholder_mode(self) -> None:
        """Test merged cells with placeholder mode."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Merged")], colspan=2),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(handle_merged_cells="placeholder")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "[merged]" in result


@pytest.mark.unit
class TestCsvDialect:
    """Tests for CSV dialect options."""

    def test_custom_delimiter(self) -> None:
        """Test using tab as delimiter."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="1")]), TableCell(content=[Text(content="2")])])],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(delimiter="\t")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert "A\tB" in result
        assert "1\t2" in result

    def test_include_bom(self) -> None:
        """Test including UTF-8 BOM."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Data")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="1")])])],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(include_bom=True)
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        assert result.startswith("\ufeff")

    def test_custom_quote_char(self) -> None:
        """Test using custom quote character."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Name")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="O'Brien")])])],
        )
        doc = Document(children=[table])

        options = CsvRendererOptions(quote_char="'", quoting="all")
        renderer = CsvRenderer(options)
        result = renderer.render_to_string(doc)

        # With single quote as quote char and quoting=all, should use single quotes
        assert "'" in result
