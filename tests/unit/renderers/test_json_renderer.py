#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for JSON renderer."""

import json

from all2md.ast import Document, Heading, List, ListItem, Paragraph, Strong, Table, TableCell, TableRow, Text
from all2md.options.json import JsonRendererOptions
from all2md.renderers.json import JsonRenderer


class TestJsonRendererBasic:
    """Test basic JSON rendering functionality."""

    def test_render_simple_table(self):
        """Test rendering a simple table to JSON."""
        # Create a simple table
        header = TableRow(cells=[TableCell(content=[Text(content="name")]), TableCell(content=[Text(content="age")])])
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]),
            TableRow(cells=[TableCell(content=[Text(content="Bob")]), TableCell(content=[Text(content="25")])]),
        ]
        table = Table(header=header, rows=rows)
        heading = Heading(level=1, content=[Text(content="Users")])
        doc = Document(children=[heading, table])

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        # Parse and verify
        data = json.loads(json_str)
        assert "Users" in data
        assert isinstance(data["Users"], list)
        assert len(data["Users"]) == 2
        assert data["Users"][0]["name"] == "Alice"
        assert data["Users"][0]["age"] == 30  # Should be inferred as int

    def test_render_table_without_heading(self):
        """Test rendering table without preceding heading."""
        header = TableRow(cells=[TableCell(content=[Text(content="id")]), TableCell(content=[Text(content="value")])])
        rows = [TableRow(cells=[TableCell(content=[Text(content="1")]), TableCell(content=[Text(content="100")])])]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        # Should have a generic key like "table_1"
        assert "table_1" in data or any(key.startswith("table") for key in data.keys())

    def test_render_list(self):
        """Test rendering lists to JSON."""
        items = [
            ListItem(children=[Paragraph(content=[Text(content="apple")])]),
            ListItem(children=[Paragraph(content=[Text(content="banana")])]),
            ListItem(children=[Paragraph(content=[Text(content="cherry")])]),
        ]
        list_node = List(items=items, ordered=False)
        heading = Heading(level=1, content=[Text(content="Fruits")])
        doc = Document(children=[heading, list_node])

        renderer = JsonRenderer(JsonRendererOptions(extract_mode="lists"))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "Fruits" in data
        assert isinstance(data["Fruits"], list)
        assert len(data["Fruits"]) == 3

    def test_render_empty_document(self):
        """Test rendering empty document."""
        doc = Document(children=[])

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert len(data) == 0


class TestJsonRendererTypeInference:
    """Test type inference during rendering."""

    def test_infer_integers(self):
        """Test integer type inference."""
        header = TableRow(cells=[TableCell(content=[Text(content="value")])])
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="42")])]),
            TableRow(cells=[TableCell(content=[Text(content="100")])]),
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        assert isinstance(table_data[0]["value"], int)
        assert table_data[0]["value"] == 42

    def test_infer_floats(self):
        """Test float type inference."""
        header = TableRow(cells=[TableCell(content=[Text(content="value")])])
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="3.14")])]),
            TableRow(cells=[TableCell(content=[Text(content="2.718")])]),
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        assert isinstance(table_data[0]["value"], float)
        assert table_data[0]["value"] == 3.14

    def test_infer_booleans(self):
        """Test boolean type inference."""
        header = TableRow(
            cells=[TableCell(content=[Text(content="name")]), TableCell(content=[Text(content="active")])]
        )
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="true")])]),
            TableRow(cells=[TableCell(content=[Text(content="Bob")]), TableCell(content=[Text(content="false")])]),
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        assert isinstance(table_data[0]["active"], bool)
        assert table_data[0]["active"] is True
        assert table_data[1]["active"] is False

    def test_infer_null(self):
        """Test null type inference."""
        header = TableRow(cells=[TableCell(content=[Text(content="value")])])
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="null")])]),
            TableRow(cells=[TableCell(content=[Text(content="none")])]),
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        assert table_data[0]["value"] is None
        assert table_data[1]["value"] is None

    def test_no_type_inference(self):
        """Test disabling type inference."""
        header = TableRow(cells=[TableCell(content=[Text(content="value")])])
        rows = [
            TableRow(cells=[TableCell(content=[Text(content="42")])]),
            TableRow(cells=[TableCell(content=[Text(content="true")])]),
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=False))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        # All values should be strings
        assert isinstance(table_data[0]["value"], str)
        assert table_data[0]["value"] == "42"
        assert isinstance(table_data[1]["value"], str)
        assert table_data[1]["value"] == "true"


class TestJsonRendererOptions:
    """Test JSON renderer options."""

    def test_extract_mode_tables_only(self):
        """Test extracting only tables."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        list_node = List(items=[ListItem(children=[Paragraph(content=[Text(content="item")])])], ordered=False)
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Table Section")]),
                table,
                Heading(level=1, content=[Text(content="List Section")]),
                list_node,
            ]
        )

        renderer = JsonRenderer(JsonRendererOptions(extract_mode="tables"))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "Table Section" in data
        assert "List Section" not in data

    def test_extract_mode_lists_only(self):
        """Test extracting only lists."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        list_node = List(items=[ListItem(children=[Paragraph(content=[Text(content="item")])])], ordered=False)
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Table Section")]),
                table,
                Heading(level=1, content=[Text(content="List Section")]),
                list_node,
            ]
        )

        renderer = JsonRenderer(JsonRendererOptions(extract_mode="lists"))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "Table Section" not in data
        assert "List Section" in data

    def test_extract_mode_both(self):
        """Test extracting both tables and lists."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="col")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="val")])])],
        )
        list_node = List(items=[ListItem(children=[Paragraph(content=[Text(content="item")])])], ordered=False)
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Table Section")]),
                table,
                Heading(level=1, content=[Text(content="List Section")]),
                list_node,
            ]
        )

        renderer = JsonRenderer(JsonRendererOptions(extract_mode="both"))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "Table Section" in data
        assert "List Section" in data

    def test_flatten_single_table(self):
        """Test flattening single table output."""
        header = TableRow(cells=[TableCell(content=[Text(content="name")])])
        rows = [TableRow(cells=[TableCell(content=[Text(content="Alice")])])]
        table = Table(header=header, rows=rows)
        heading = Heading(level=1, content=[Text(content="Users")])
        doc = Document(children=[heading, table])

        renderer = JsonRenderer(JsonRendererOptions(flatten_single_table=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        # Should be a list at top level, not wrapped in object
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_table_heading_keys_disabled(self):
        """Test disabling heading-based keys."""
        header = TableRow(cells=[TableCell(content=[Text(content="value")])])
        rows = [TableRow(cells=[TableCell(content=[Text(content="42")])])]
        table = Table(header=header, rows=rows)
        heading = Heading(level=1, content=[Text(content="MyData")])
        doc = Document(children=[heading, table])

        renderer = JsonRenderer(JsonRendererOptions(table_heading_keys=False))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        # Should not use "MyData" as key
        assert "MyData" not in data
        assert any(key.startswith("table") for key in data.keys())

    def test_formatting_options(self):
        """Test JSON formatting options."""
        header = TableRow(cells=[TableCell(content=[Text(content="key")])])
        rows = [TableRow(cells=[TableCell(content=[Text(content="value")])])]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        # Test with different formatting
        renderer = JsonRenderer(JsonRendererOptions(indent=4, ensure_ascii=True, sort_keys=True))
        json_str = renderer.render_to_string(doc)

        # Should be valid JSON
        data = json.loads(json_str)
        assert isinstance(data, dict)


class TestJsonRendererComplexCases:
    """Test complex rendering scenarios."""

    def test_multiple_tables(self):
        """Test rendering multiple tables."""
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
                Heading(level=1, content=[Text(content="Table 1")]),
                table1,
                Heading(level=1, content=[Text(content="Table 2")]),
                table2,
            ]
        )

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        assert "Table 1" in data
        assert "Table 2" in data

    def test_duplicate_headings(self):
        """Test handling duplicate heading names."""
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

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        # Should handle duplicates (e.g., "Data" and "Data_2")
        assert len(data) >= 2

    def test_nested_inline_formatting(self):
        """Test handling nested inline formatting in cells."""
        header = TableRow(cells=[TableCell(content=[Text(content="name")])])
        rows = [
            TableRow(cells=[TableCell(content=[Strong(content=[Text(content="Bold")]), Text(content=" and normal")])])
        ]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        # Should extract plain text
        assert "Bold and normal" in table_data[0]["name"]

    def test_number_formatting_with_commas(self):
        """Test handling numbers formatted with thousand separators."""
        header = TableRow(cells=[TableCell(content=[Text(content="population")])])
        rows = [TableRow(cells=[TableCell(content=[Text(content="1,234,567")])])]
        table = Table(header=header, rows=rows)
        doc = Document(children=[table])

        renderer = JsonRenderer(JsonRendererOptions(type_inference=True))
        json_str = renderer.render_to_string(doc)

        data = json.loads(json_str)
        table_data = list(data.values())[0]
        # Should parse as integer without commas
        assert table_data[0]["population"] == 1234567

    def test_round_trip_preservation(self):
        """Test that data survives a round trip through parser and renderer."""
        original_data = {
            "users": [{"name": "Alice", "age": 30, "active": True}, {"name": "Bob", "age": 25, "active": False}]
        }

        # Parse
        from all2md.parsers.json import JsonParser

        parser = JsonParser()
        doc = parser.parse(json.dumps(original_data))

        # Render back
        renderer = JsonRenderer()
        json_str = renderer.render_to_string(doc)
        result_data = json.loads(json_str)

        # Should match original structure
        assert "users" in result_data
        assert len(result_data["users"]) == 2
        assert result_data["users"][0]["name"] == "Alice"
        assert result_data["users"][0]["age"] == 30
        assert result_data["users"][0]["active"] is True
