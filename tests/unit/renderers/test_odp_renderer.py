#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_odp_renderer.py
"""Unit tests for OdpRenderer.

Tests cover:
- Rendering all node types to ODP
- Slide splitting strategies
- Slide layout and formatting
- Edge cases and options

Note: These tests require odfpy to be installed.
"""

from io import BytesIO

import pytest

try:
    from odf.opendocument import load as odf_load
    ODFPY_AVAILABLE = True
except ImportError:
    ODFPY_AVAILABLE = False

from all2md.ast import (
    Code,
    CodeBlock,
    Document,
    Emphasis,
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


pytestmark = pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic ODP rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = OdpRenderer()
        output_file = tmp_path / "empty.odp"
        renderer.render(doc, output_file)

        # Verify file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_render_to_file_path(self, tmp_path):
        """Test rendering to file path string."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test content")])
        ])
        renderer = OdpRenderer()
        output_file = tmp_path / "test.odp"
        renderer.render(doc, str(output_file))

        assert output_file.exists()

    def test_render_to_path_object(self, tmp_path):
        """Test rendering to Path object."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test content")])
        ])
        renderer = OdpRenderer()
        output_file = tmp_path / "test.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO object."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test content")])
        ])
        renderer = OdpRenderer()
        buffer = BytesIO()
        renderer.render(doc, buffer)

        # Verify data was written
        assert buffer.tell() > 0
        buffer.seek(0)
        data = buffer.read()
        assert len(data) > 0

    def test_render_single_slide(self, tmp_path):
        """Test rendering document to single slide."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Slide Title")]),
            Paragraph(content=[Text(content="Slide content")])
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "single.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestSplittingStrategies:
    """Tests for slide splitting strategies."""

    def test_split_by_separator(self, tmp_path):
        """Test splitting slides using separator mode."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Slide 1 content")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Slide 2 content")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Slide 3 content")])
        ])

        options = OdpRendererOptions(slide_split_mode="separator")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_separator.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_by_heading(self, tmp_path):
        """Test splitting slides using heading mode."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Slide 1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="Slide 2")]),
            Paragraph(content=[Text(content="Content 2")]),
            Heading(level=2, content=[Text(content="Slide 3")]),
            Paragraph(content=[Text(content="Content 3")])
        ])

        options = OdpRendererOptions(
            slide_split_mode="heading",
            slide_split_heading_level=2
        )
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_heading.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_auto_prefers_separator(self, tmp_path):
        """Test auto mode prefers separator when available."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="H2")]),
            Paragraph(content=[Text(content="Content 1")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Content 2")])
        ])

        options = OdpRendererOptions(slide_split_mode="auto")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_auto.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_auto_fallback_to_heading(self, tmp_path):
        """Test auto mode falls back to headings when no separators."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Slide 1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="Slide 2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])

        options = OdpRendererOptions(slide_split_mode="auto")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_auto_heading.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_respects_heading_level(self, tmp_path):
        """Test splitting respects heading level setting."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="H2")]),
            Paragraph(content=[Text(content="Content 2")]),
            Heading(level=2, content=[Text(content="H2 Again")]),
            Paragraph(content=[Text(content="Content 3")])
        ])

        # Split on H2
        options = OdpRendererOptions(
            slide_split_mode="heading",
            slide_split_heading_level=2
        )
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_h2.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestSlideTitles:
    """Tests for slide title generation."""

    def test_use_heading_as_title(self, tmp_path):
        """Test using heading text as slide title."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="My Slide Title")]),
            Paragraph(content=[Text(content="Content")])
        ])

        options = OdpRendererOptions(
            slide_split_mode="heading",
            use_heading_as_slide_title=True
        )
        renderer = OdpRenderer(options)
        output_file = tmp_path / "heading_titles.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_disable_heading_titles(self, tmp_path):
        """Test disabling heading-based titles."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Heading Text")]),
            Paragraph(content=[Text(content="Content")])
        ])

        options = OdpRendererOptions(
            slide_split_mode="heading",
            use_heading_as_slide_title=False
        )
        renderer = OdpRenderer(options)
        output_file = tmp_path / "no_heading_titles.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestContentRendering:
    """Tests for rendering various content types."""

    def test_render_paragraphs(self, tmp_path):
        """Test rendering paragraphs."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="First paragraph")]),
            Paragraph(content=[Text(content="Second paragraph")])
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "paragraphs.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_formatted_text(self, tmp_path):
        """Test rendering text with formatting."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Formatting")]),
            Paragraph(content=[
                Text(content="Normal "),
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" text.")
            ])
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "formatted.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_code(self, tmp_path):
        """Test rendering inline code and code blocks."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Code")]),
            Paragraph(content=[
                Text(content="Inline "),
                Code(content="code"),
                Text(content=" here.")
            ]),
            CodeBlock(content='def hello():\n    print("Hi")', language="python")
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "code.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_lists(self, tmp_path):
        """Test rendering bullet and numbered lists."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Lists")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Bullet 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Bullet 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Bullet 3")])])
            ]),
            List(ordered=True, items=[
                ListItem(children=[Paragraph(content=[Text(content="Number 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Number 2")])])
            ])
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "lists.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_tables(self, tmp_path):
        """Test rendering tables."""
        doc = Document(children=[
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
            )
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "table.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestOptions:
    """Tests for rendering options."""

    def test_default_font_size(self, tmp_path):
        """Test default font size option."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ])

        options = OdpRendererOptions(default_font_size=24)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "font_size.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_title_font_size(self, tmp_path):
        """Test title font size option."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Title")])
        ])

        options = OdpRendererOptions(title_font_size=36)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "title_size.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_default_font(self, tmp_path):
        """Test default font option."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ])

        options = OdpRendererOptions(default_font="Liberation Serif")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "font.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestComplexPresentation:
    """Tests for rendering complex presentations."""

    def test_render_multi_slide_presentation(self, tmp_path):
        """Test rendering multi-slide presentation with various content."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Presentation Title")]),
            Paragraph(content=[Text(content="Introduction slide")]),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Bullet Points")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Point 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Point 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Point 3")])])
            ]),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='print("Hello")', language="python"),
            ThematicBreak(),
            Heading(level=2, content=[Text(content="Data Table")]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Item")]),
                    TableCell(content=[Text(content="Count")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="10")])
                    ])
                ]
            )
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "complex.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_nested_content(self, tmp_path):
        """Test rendering nested and complex content structures."""
        doc = Document(children=[
            Heading(level=2, content=[
                Text(content="Title with "),
                Strong(content=[Text(content="bold")])
            ]),
            Paragraph(content=[
                Text(content="Mix of "),
                Strong(content=[Text(content="bold")]),
                Text(content=", "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=", and "),
                Code(content="code"),
                Text(content=".")
            ])
        ])

        renderer = OdpRenderer()
        output_file = tmp_path / "nested.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()
