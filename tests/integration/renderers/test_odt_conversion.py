#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_odt_conversion.py
"""Integration tests for ODT renderer.

Tests cover:
- End-to-end ODT rendering workflows
- Custom styles and fonts
- Metadata handling
- Complete document conversion

"""


import pytest

try:
    from odf.opendocument import load as odf_load
    ODFPY_AVAILABLE = True
except ImportError:
    ODFPY_AVAILABLE = False

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options import OdtRendererOptions

if ODFPY_AVAILABLE:
    from all2md.renderers.odt import OdtRenderer


def create_sample_document():
    """Create a sample AST document for testing.

    Returns
    -------
    Document
        A sample document with various elements for testing.

    """
    return Document(
        metadata={"title": "Sample Document", "author": "Test Author"},
        children=[
            Heading(level=1, content=[Text(content="Document Title")]),
            Paragraph(content=[
                Text(content="This is a paragraph with "),
                Strong(content=[Text(content="bold text")]),
                Text(content=" and a "),
                Link(url="https://example.com", content=[Text(content="link")]),
                Text(content=".")
            ]),
            Heading(level=2, content=[Text(content="Lists")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Third item")])])
            ]),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='def hello():\n    print("Hello, world!")', language="python"),
            Heading(level=2, content=[Text(content="Table")]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Value")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alpha")]),
                        TableCell(content=[Text(content="1")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="Beta")]),
                        TableCell(content=[Text(content="2")])
                    ])
                ]
            ),
            Heading(level=2, content=[Text(content="Quote")]),
            BlockQuote(children=[
                Paragraph(content=[Text(content="This is a blockquote.")])
            ])
        ]
    )


@pytest.mark.integration
@pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")
class TestOdtRendering:
    """Integration tests for ODT rendering."""

    def test_full_document_to_odt(self, tmp_path):
        """Test rendering complete document to ODT."""
        doc = create_sample_document()
        renderer = OdtRenderer()
        output_file = tmp_path / "full_document.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify ODT content
        odt_doc = odf_load(str(output_file))

        # Check for tables
        from odf.table import Table as OdfTable
        tables = odt_doc.getElementsByType(OdfTable)
        assert len(tables) >= 1

        # Check for headings
        from odf.text import H
        headings = odt_doc.getElementsByType(H)
        assert len(headings) >= 1

    def test_odt_with_custom_styles(self, tmp_path):
        """Test ODT rendering with custom styles."""
        doc = create_sample_document()
        options = OdtRendererOptions(
            default_font="Liberation Serif",
            default_font_size=12,
            code_font="Liberation Mono"
        )
        renderer = OdtRenderer(options)
        output_file = tmp_path / "custom_styles.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odt_metadata(self, tmp_path):
        """Test ODT metadata handling."""
        doc = create_sample_document()
        renderer = OdtRenderer()
        output_file = tmp_path / "with_metadata.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        meta = odt_doc.meta
        assert meta is not None

    def test_odt_with_nested_lists(self, tmp_path):
        """Test rendering nested lists."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[
                    Paragraph(content=[Text(content="Item 1")]),
                    List(ordered=False, items=[
                        ListItem(children=[Paragraph(content=[Text(content="Nested 1.1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Nested 1.2")])])
                    ])
                ]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ])
        ])
        renderer = OdtRenderer()
        output_file = tmp_path / "nested_lists.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odt_with_complex_table(self, tmp_path):
        """Test rendering complex table."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")]),
                    TableCell(content=[Text(content="Col3")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A1")]),
                        TableCell(content=[Text(content="B1")]),
                        TableCell(content=[Text(content="C1")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="A2")]),
                        TableCell(content=[Text(content="B2")]),
                        TableCell(content=[Text(content="C2")])
                    ])
                ]
            )
        ])
        renderer = OdtRenderer()
        output_file = tmp_path / "complex_table.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.table import Table as OdfTable
        tables = odt_doc.getElementsByType(OdfTable)
        assert len(tables) == 1

    def test_odt_mixed_formatting(self, tmp_path):
        """Test rendering with mixed inline formatting."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Strong(content=[Text(content="bold")]),
                Text(content=" then "),
                Strong(content=[
                    Text(content="bold with "),
                    Link(url="https://example.com", content=[Text(content="link")])
                ])
            ])
        ])
        renderer = OdtRenderer()
        output_file = tmp_path / "mixed_formatting.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()
