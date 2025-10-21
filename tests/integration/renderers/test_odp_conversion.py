#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_odp_conversion.py
"""Integration tests for ODP renderer.

Tests cover:
- End-to-end ODP rendering workflows
- Slide splitting and layout
- Multi-slide presentations
- Complete conversion workflows

"""

import pytest

try:
    from odf.opendocument import load as odf_load

    ODFPY_AVAILABLE = True
except ImportError:
    ODFPY_AVAILABLE = False

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.options import OdpRendererOptions

if ODFPY_AVAILABLE:
    from all2md.renderers.odp import OdpRenderer


def create_sample_presentation():
    """Create a sample AST document for presentation testing.

    Returns
    -------
    Document
        A sample presentation document with multiple slides.

    """
    return Document(
        metadata={"title": "Sample Presentation", "author": "Test Author"},
        children=[
            Heading(level=1, content=[Text(content="Title Slide")]),
            Paragraph(content=[Text(content="Introduction")]),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Bullet Points")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="First point")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Second point")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Third point")])]),
                ],
            ),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='def greet():\n    return "Hello"', language="python"),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Data Table")]),
            Table(
                header=TableRow(
                    cells=[TableCell(content=[Text(content="Item")]), TableCell(content=[Text(content="Count")])]
                ),
                rows=[
                    TableRow(
                        cells=[TableCell(content=[Text(content="Alpha")]), TableCell(content=[Text(content="10")])]
                    ),
                    TableRow(
                        cells=[TableCell(content=[Text(content="Beta")]), TableCell(content=[Text(content="20")])]
                    ),
                ],
            ),
        ],
    )


@pytest.mark.integration
@pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")
class TestOdpRendering:
    """Integration tests for ODP rendering."""

    def test_full_presentation_to_odp(self, tmp_path):
        """Test rendering complete presentation to ODP."""
        doc = create_sample_presentation()
        renderer = OdpRenderer()
        output_file = tmp_path / "full_presentation.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify ODP content
        odp_doc = odf_load(str(output_file))

        # Check for pages (slides)
        from odf.draw import Page

        pages = odp_doc.getElementsByType(Page)
        assert len(pages) >= 1

    def test_odp_with_custom_styles(self, tmp_path):
        """Test ODP rendering with custom styles."""
        doc = create_sample_presentation()
        options = OdpRendererOptions(default_font="Liberation Serif", default_font_size=20, title_font_size=40)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "custom_styles.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odp_separator_split(self, tmp_path):
        """Test slide splitting by separator."""
        doc = create_sample_presentation()
        options = OdpRendererOptions(slide_split_mode="separator")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_separator.odp"
        renderer.render(doc, output_file)

        odp_doc = odf_load(str(output_file))
        from odf.draw import Page

        pages = odp_doc.getElementsByType(Page)
        assert len(pages) == 4  # 4 slides from thematic breaks

    def test_odp_heading_split(self, tmp_path):
        """Test slide splitting by heading."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=2, content=[Text(content="Slide 2")]),
                Paragraph(content=[Text(content="Content 2")]),
                Heading(level=2, content=[Text(content="Slide 3")]),
                Paragraph(content=[Text(content="Content 3")]),
            ]
        )
        options = OdpRendererOptions(slide_split_mode="heading", slide_split_heading_level=2)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_heading.odp"
        renderer.render(doc, output_file)

        odp_doc = odf_load(str(output_file))
        from odf.draw import Page

        pages = odp_doc.getElementsByType(Page)
        assert len(pages) == 3

    def test_odp_auto_split(self, tmp_path):
        """Test auto split mode."""
        doc = create_sample_presentation()
        options = OdpRendererOptions(slide_split_mode="auto")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "auto_split.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odp_with_formatted_content(self, tmp_path):
        """Test rendering with formatted content."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Formatted Content")]),
                Paragraph(
                    content=[Text(content="Normal "), Strong(content=[Text(content="bold")]), Text(content=" text.")]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "formatted.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odp_with_lists(self, tmp_path):
        """Test rendering with various list types."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Lists")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Bullet 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Bullet 2")])]),
                    ],
                ),
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Number 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Number 2")])]),
                    ],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "lists.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_odp_with_table(self, tmp_path):
        """Test rendering with table."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Table Slide")]),
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Name")]),
                            TableCell(content=[Text(content="Age")]),
                            TableCell(content=[Text(content="City")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Alice")]),
                                TableCell(content=[Text(content="30")]),
                                TableCell(content=[Text(content="NYC")]),
                            ]
                        )
                    ],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "table_slide.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()
