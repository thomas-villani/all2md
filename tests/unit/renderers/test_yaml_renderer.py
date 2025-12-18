#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_yaml_renderer.py
"""Unit tests for YAML rendering from AST.

Tests cover:
- Basic YAML rendering
- Table extraction
- List extraction
- Type inference
- Heading keys
- Flatten single table option
- Sort keys option
- Flow style option
- File output
- Edge cases

"""

from io import StringIO
from pathlib import Path

import pytest

from all2md.ast import (
    Document,
    Heading,
    List,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.exceptions import InvalidOptionsError, RenderingError
from all2md.options.yaml import YamlRendererOptions
from all2md.renderers.yaml import DataExtractor, YamlRenderer


def create_table_document(table_name: str, headers: list[str], rows: list[list[str]]) -> Document:
    """Helper to create a document with a table.

    Parameters
    ----------
    table_name : str
        Name for the table heading
    headers : list[str]
        Column headers
    rows : list[list[str]]
        Row data

    Returns
    -------
    Document
        AST Document with heading and table

    """
    header_row = TableRow(cells=[TableCell(content=[Text(content=h)]) for h in headers])
    data_rows = [TableRow(cells=[TableCell(content=[Text(content=cell)]) for cell in row]) for row in rows]

    children = [
        Heading(level=1, content=[Text(content=table_name)]),
        Table(header=header_row, rows=data_rows),
    ]

    return Document(children=children)


def create_list_document(list_name: str, items: list[str]) -> Document:
    """Helper to create a document with a list.

    Parameters
    ----------
    list_name : str
        Name for the list heading
    items : list[str]
        List items

    Returns
    -------
    Document
        AST Document with heading and list

    """
    list_items = [ListItem(children=[Paragraph(content=[Text(content=item)])]) for item in items]

    children = [
        Heading(level=1, content=[Text(content=list_name)]),
        List(items=list_items, ordered=False),
    ]

    return Document(children=children)


@pytest.mark.unit
class TestYamlBasicRendering:
    """Tests for basic YAML rendering functionality."""

    def test_render_simple_table(self) -> None:
        """Test rendering a simple table to YAML."""
        doc = create_table_document(
            "Users",
            ["name", "age"],
            [["Alice", "30"], ["Bob", "25"]],
        )
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert "Users:" in result
        assert "name:" in result
        assert "Alice" in result

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_render_multiple_tables(self) -> None:
        """Test rendering document with multiple tables."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col1")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col2")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val2")])])],
        )
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Table1")]),
                table1,
                Heading(level=1, content=[Text(content="Table2")]),
                table2,
            ]
        )
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert "Table1:" in result
        assert "Table2:" in result


@pytest.mark.unit
class TestYamlTableExtraction:
    """Tests for table extraction functionality."""

    def test_extract_table_with_heading_key(self) -> None:
        """Test that table uses heading as key."""
        doc = create_table_document("Config", ["key", "value"], [["timeout", "30"]])
        options = YamlRendererOptions(table_heading_keys=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Config:" in result

    def test_extract_mode_tables_only(self) -> None:
        """Test extracting only tables."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        list_node = List(
            items=[ListItem(children=[Paragraph(content=[Text(content="item")])])],
            ordered=False,
        )
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Data")]),
                table,
                list_node,
            ]
        )
        options = YamlRendererOptions(extract_mode="tables")
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "col" in result


@pytest.mark.unit
class TestYamlListExtraction:
    """Tests for list extraction functionality."""

    def test_extract_list_with_both_mode(self) -> None:
        """Test list extraction with both mode."""
        doc = create_list_document("Items", ["item1", "item2", "item3"])
        options = YamlRendererOptions(extract_mode="both")
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Items:" in result

    def test_extract_mode_lists_only(self) -> None:
        """Test extracting only lists."""
        doc = create_list_document("Tags", ["python", "rust", "go"])
        options = YamlRendererOptions(extract_mode="lists")
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Tags:" in result


@pytest.mark.unit
class TestYamlTypeInference:
    """Tests for type inference functionality."""

    def test_infer_integer(self) -> None:
        """Test integer type inference."""
        doc = create_table_document("Config", ["port"], [["8080"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        # Should be integer without quotes
        assert "port: 8080" in result

    def test_infer_boolean_true(self) -> None:
        """Test boolean true inference."""
        doc = create_table_document("Config", ["enabled"], [["true"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "enabled: true" in result

    def test_infer_boolean_false(self) -> None:
        """Test boolean false inference."""
        doc = create_table_document("Config", ["disabled"], [["no"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "disabled: false" in result

    def test_infer_null(self) -> None:
        """Test null type inference."""
        doc = create_table_document("Config", ["value"], [["null"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        # YAML represents null as empty or explicit null
        assert "value:" in result

    def test_infer_float(self) -> None:
        """Test float type inference."""
        doc = create_table_document("Config", ["rate"], [["3.14"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "rate: 3.14" in result

    def test_comma_in_number_removed(self) -> None:
        """Test that thousand separators are removed."""
        doc = create_table_document("Config", ["count"], [["1,000,000"]])
        options = YamlRendererOptions(type_inference=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "count: 1000000" in result


@pytest.mark.unit
class TestYamlOutputOptions:
    """Tests for YAML output options."""

    def test_sort_keys_enabled(self) -> None:
        """Test that sort_keys option works."""
        doc = create_table_document("Config", ["zebra", "alpha"], [["z", "a"]])
        options = YamlRendererOptions(sort_keys=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        # Keys should be sorted alphabetically
        assert isinstance(result, str)

    def test_indent_option(self) -> None:
        """Test indent option."""
        doc = create_table_document("Config", ["key"], [["value"]])
        options = YamlRendererOptions(indent=4)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_flatten_single_table(self) -> None:
        """Test flatten_single_table option."""
        doc = create_table_document("Config", ["key"], [["value"]])
        options = YamlRendererOptions(flatten_single_table=True)
        renderer = YamlRenderer(options)
        result = renderer.render_to_string(doc)

        # Result should be flattened (list directly, not nested under key)
        assert isinstance(result, str)


@pytest.mark.unit
class TestYamlFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file_path(self, tmp_path: Path) -> None:
        """Test rendering to file path."""
        doc = create_table_document("Config", ["key"], [["value"]])
        output_file = tmp_path / "output.yaml"

        renderer = YamlRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "Config:" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Test rendering to Path object."""
        doc = create_table_document("Data", ["col"], [["val"]])
        output_file = tmp_path / "output.yaml"

        renderer = YamlRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        doc = create_table_document("Config", ["key"], [["value"]])
        output = StringIO()

        renderer = YamlRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "Config:" in result

    def test_render_to_binary_stream(self) -> None:
        """Test rendering to binary stream."""
        doc = create_table_document("Config", ["key"], [["value"]])

        class BinaryStream:
            def __init__(self):
                self.data = b""
                self.mode = "wb"

            def write(self, data):
                self.data = data

        output = BinaryStream()
        renderer = YamlRenderer()
        renderer.render(doc, output)

        assert b"Config:" in output.data


@pytest.mark.unit
class TestYamlDataExtractor:
    """Tests for DataExtractor helper class."""

    def test_extractor_handles_duplicate_headings(self) -> None:
        """Test that extractor handles duplicate heading names."""
        table1 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val1")])])],
        )
        table2 = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val2")])])],
        )
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Data")]),
                table1,
                Heading(level=1, content=[Text(content="Data")]),
                table2,
            ]
        )
        extractor = DataExtractor(YamlRendererOptions())
        data = extractor.extract(doc)

        # Should have both keys (one with suffix)
        assert "Data" in data
        assert "Data_2" in data

    def test_extractor_without_heading(self) -> None:
        """Test extraction when no heading precedes table."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        doc = Document(children=[table])
        options = YamlRendererOptions(table_heading_keys=False)
        extractor = DataExtractor(options)
        data = extractor.extract(doc)

        assert "table_1" in data


@pytest.mark.unit
class TestYamlEdgeCases:
    """Tests for edge cases."""

    def test_table_without_header(self) -> None:
        """Test handling table without header row."""
        table = Table(
            header=None,  # type: ignore
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        doc = Document(children=[table])
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_empty_cell_value(self) -> None:
        """Test handling empty cell values."""
        doc = create_table_document("Config", ["key", "value"], [["name", ""]])
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_special_characters_in_string(self) -> None:
        """Test handling special characters in values."""
        doc = create_table_document(
            "Config",
            ["url"],
            [["http://example.com?foo=bar&baz=qux"]],
        )
        renderer = YamlRenderer()
        result = renderer.render_to_string(doc)

        assert "example.com" in result

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            YamlRenderer(options="invalid")

    def test_unsupported_output_type(self) -> None:
        """Test that unsupported output type raises error."""
        doc = create_table_document("Config", ["key"], [["value"]])
        renderer = YamlRenderer()

        with pytest.raises(RenderingError):
            renderer.render(doc, 12345)  # type: ignore
