#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_ini_renderer.py
"""Unit tests for INI rendering from AST.

Tests cover:
- Basic INI rendering
- Section extraction from headings
- Key-value extraction from lists
- Case preservation
- Type inference
- Binary output mode
- Edge cases

"""

from io import StringIO
from pathlib import Path

import pytest

from all2md.ast import Document, Heading, List, ListItem, Paragraph, Strong, Text
from all2md.exceptions import InvalidOptionsError, RenderingError
from all2md.options.ini import IniRendererOptions
from all2md.renderers.ini import DataExtractor, IniRenderer


def create_ini_document(sections: dict[str, dict[str, str]]) -> Document:
    """Helper to create a document from section data.

    Parameters
    ----------
    sections : dict
        Dictionary of {section_name: {key: value, ...}}

    Returns
    -------
    Document
        AST Document with headings and lists

    """
    children = []
    for section_name, values in sections.items():
        # Add section heading
        children.append(Heading(level=1, content=[Text(content=section_name)]))

        # Add key-value list
        list_items = []
        for key, value in values.items():
            if value:
                item_content = [
                    Paragraph(
                        content=[
                            Strong(content=[Text(content=key)]),
                            Text(content=f": {value}"),
                        ]
                    )
                ]
            else:
                item_content = [
                    Paragraph(
                        content=[
                            Strong(content=[Text(content=key)]),
                        ]
                    )
                ]
            list_items.append(ListItem(children=item_content))

        if list_items:
            children.append(List(items=list_items, ordered=False))

    return Document(children=children)


@pytest.mark.unit
class TestIniBasicRendering:
    """Tests for basic INI rendering functionality."""

    def test_render_simple_document(self) -> None:
        """Test rendering a simple document to INI."""
        doc = create_ini_document({"server": {"host": "localhost", "port": "8080"}})
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "[server]" in result
        assert "host = localhost" in result
        assert "port = 8080" in result

    def test_render_multiple_sections(self) -> None:
        """Test rendering document with multiple sections."""
        doc = create_ini_document({"server": {"host": "localhost"}, "database": {"name": "mydb"}})
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "[server]" in result
        assert "[database]" in result
        assert "host = localhost" in result
        assert "name = mydb" in result

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        # Should return empty or minimal INI
        assert isinstance(result, str)


@pytest.mark.unit
class TestIniSectionExtraction:
    """Tests for section extraction from headings."""

    def test_heading_becomes_section(self) -> None:
        """Test that headings become INI sections."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="my_section")]),
                List(
                    items=[
                        ListItem(
                            children=[
                                Paragraph(
                                    content=[
                                        Strong(content=[Text(content="key")]),
                                        Text(content=": value"),
                                    ]
                                )
                            ]
                        )
                    ],
                    ordered=False,
                ),
            ]
        )
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "[my_section]" in result

    def test_only_level1_headings_create_sections(self) -> None:
        """Test that only level 1 headings create sections."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="section")]),
                Heading(level=2, content=[Text(content="subsection")]),
                List(
                    items=[
                        ListItem(
                            children=[
                                Paragraph(
                                    content=[
                                        Strong(content=[Text(content="key")]),
                                        Text(content=": value"),
                                    ]
                                )
                            ]
                        )
                    ],
                    ordered=False,
                ),
            ]
        )
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "[section]" in result
        assert "[subsection]" not in result


@pytest.mark.unit
class TestIniKeyValueExtraction:
    """Tests for key-value pair extraction."""

    def test_extract_key_value_with_colon(self) -> None:
        """Test extraction of key: value format."""
        doc = create_ini_document({"section": {"key": "value"}})
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "key = value" in result

    def test_extract_key_without_value(self) -> None:
        """Test extraction of key without value."""
        doc = create_ini_document({"section": {"key": ""}})
        options = IniRendererOptions(allow_no_value=True)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        assert "[section]" in result


@pytest.mark.unit
class TestIniCasePreservation:
    """Tests for case preservation options."""

    def test_preserve_case_enabled(self) -> None:
        """Test case preservation when enabled."""
        doc = create_ini_document({"MySection": {"MyKey": "value"}})
        options = IniRendererOptions(preserve_case=True)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        assert "MyKey" in result

    def test_preserve_case_disabled(self) -> None:
        """Test case normalization when preserve_case is disabled."""
        doc = create_ini_document({"MySection": {"MyKey": "value"}})
        options = IniRendererOptions(preserve_case=False)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        # ConfigParser lowercases by default
        assert "mykey" in result or "MyKey" in result


@pytest.mark.unit
class TestIniTypeInference:
    """Tests for type inference option."""

    def test_boolean_inference_true(self) -> None:
        """Test boolean value inference for true values."""
        doc = create_ini_document({"section": {"enabled": "yes"}})
        options = IniRendererOptions(type_inference=True)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        assert "enabled = true" in result

    def test_boolean_inference_false(self) -> None:
        """Test boolean value inference for false values."""
        doc = create_ini_document({"section": {"enabled": "no"}})
        options = IniRendererOptions(type_inference=True)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        assert "enabled = false" in result

    def test_number_comma_removal(self) -> None:
        """Test that thousand separators are removed."""
        doc = create_ini_document({"section": {"count": "1,000,000"}})
        options = IniRendererOptions(type_inference=True)
        renderer = IniRenderer(options)
        result = renderer.render_to_string(doc)

        assert "count = 1000000" in result


@pytest.mark.unit
class TestIniFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file_path(self, tmp_path: Path) -> None:
        """Test rendering to file path."""
        doc = create_ini_document({"section": {"key": "value"}})
        output_file = tmp_path / "output.ini"

        renderer = IniRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "[section]" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Test rendering to Path object."""
        doc = create_ini_document({"section": {"key": "value"}})
        output_file = tmp_path / "output.ini"

        renderer = IniRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        doc = create_ini_document({"section": {"key": "value"}})
        output = StringIO()

        renderer = IniRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "[section]" in result

    def test_render_to_binary_stream(self) -> None:
        """Test rendering to binary stream."""
        doc = create_ini_document({"section": {"key": "value"}})

        class BinaryStream:
            def __init__(self):
                self.data = b""
                self.mode = "wb"

            def write(self, data):
                self.data = data

        output = BinaryStream()
        renderer = IniRenderer()
        renderer.render(doc, output)

        assert b"[section]" in output.data


@pytest.mark.unit
class TestDataExtractor:
    """Tests for DataExtractor helper class."""

    def test_extractor_creates_default_section(self) -> None:
        """Test that extractor creates DEFAULT section when no heading."""
        doc = Document(
            children=[
                List(
                    items=[
                        ListItem(
                            children=[
                                Paragraph(
                                    content=[
                                        Strong(content=[Text(content="key")]),
                                        Text(content=": value"),
                                    ]
                                )
                            ]
                        )
                    ],
                    ordered=False,
                )
            ]
        )
        extractor = DataExtractor(IniRendererOptions())
        data = extractor.extract(doc)

        assert "DEFAULT" in data
        assert data["DEFAULT"]["key"] == "value"


@pytest.mark.unit
class TestIniEdgeCases:
    """Tests for edge cases."""

    def test_empty_string_value(self) -> None:
        """Test rendering empty string value."""
        doc = create_ini_document({"section": {"key": ""}})
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "[section]" in result

    def test_special_characters_in_value(self) -> None:
        """Test rendering value with special characters."""
        doc = create_ini_document({"section": {"url": "http://example.com?foo=bar"}})
        renderer = IniRenderer()
        result = renderer.render_to_string(doc)

        assert "url = http://example.com?foo=bar" in result

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            IniRenderer(options="invalid")

    def test_unsupported_output_type(self) -> None:
        """Test that unsupported output type raises error."""
        doc = create_ini_document({"section": {"key": "value"}})
        renderer = IniRenderer()

        with pytest.raises(RenderingError):
            renderer.render(doc, 12345)  # type: ignore
