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

import importlib.util
from io import BytesIO

import pytest

ODFPY_AVAILABLE = importlib.util.find_spec("odf") is not None

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
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = OdpRenderer()
        output_file = tmp_path / "test.odp"
        renderer.render(doc, str(output_file))

        assert output_file.exists()

    def test_render_to_path_object(self, tmp_path):
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = OdpRenderer()
        output_file = tmp_path / "test.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
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
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "single.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestSplittingStrategies:
    """Tests for slide splitting strategies."""

    def test_split_by_separator(self, tmp_path):
        """Test splitting slides using separator mode."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Slide 1 content")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Slide 2 content")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Slide 3 content")]),
            ]
        )

        options = OdpRendererOptions(slide_split_mode="separator")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_separator.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_by_heading(self, tmp_path):
        """Test splitting slides using heading mode."""
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

        assert output_file.exists()

    def test_split_auto_prefers_separator(self, tmp_path):
        """Test auto mode prefers separator when available."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="H2")]),
                Paragraph(content=[Text(content="Content 1")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = OdpRendererOptions(slide_split_mode="auto")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_auto.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_auto_fallback_to_heading(self, tmp_path):
        """Test auto mode falls back to headings when no separators."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=2, content=[Text(content="Slide 2")]),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = OdpRendererOptions(slide_split_mode="auto")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_auto_heading.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_respects_heading_level(self, tmp_path):
        """Test splitting respects heading level setting."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="H1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=2, content=[Text(content="H2")]),
                Paragraph(content=[Text(content="Content 2")]),
                Heading(level=2, content=[Text(content="H2 Again")]),
                Paragraph(content=[Text(content="Content 3")]),
            ]
        )

        # Split on H2
        options = OdpRendererOptions(slide_split_mode="heading", slide_split_heading_level=2)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "split_h2.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestSlideTitles:
    """Tests for slide title generation."""

    def test_use_heading_as_title(self, tmp_path):
        """Test using heading text as slide title."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="My Slide Title")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = OdpRendererOptions(slide_split_mode="heading", use_heading_as_slide_title=True)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "heading_titles.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_disable_heading_titles(self, tmp_path):
        """Test disabling heading-based titles."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Heading Text")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = OdpRendererOptions(slide_split_mode="heading", use_heading_as_slide_title=False)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "no_heading_titles.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestContentRendering:
    """Tests for rendering various content types."""

    def test_render_paragraphs(self, tmp_path):
        """Test rendering paragraphs."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "paragraphs.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_formatted_text(self, tmp_path):
        """Test rendering text with formatting."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Formatting")]),
                Paragraph(
                    content=[
                        Text(content="Normal "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text."),
                    ]
                ),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "formatted.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_code(self, tmp_path):
        """Test rendering inline code and code blocks."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Code")]),
                Paragraph(content=[Text(content="Inline "), Code(content="code"), Text(content=" here.")]),
                CodeBlock(content='def hello():\n    print("Hi")', language="python"),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "code.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_lists(self, tmp_path):
        """Test rendering bullet and numbered lists."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Lists")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Bullet 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Bullet 2")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Bullet 3")])]),
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

    def test_render_tables(self, tmp_path):
        """Test rendering tables."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Table")]),
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Value")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="Alpha")]), TableCell(content=[Text(content="1")])]
                        ),
                        TableRow(
                            cells=[TableCell(content=[Text(content="Beta")]), TableCell(content=[Text(content="2")])]
                        ),
                    ],
                ),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "table.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestOptions:
    """Tests for rendering options."""

    def test_default_font_size(self, tmp_path):
        """Test default font size option."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = OdpRendererOptions(default_font_size=24)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "font_size.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_title_font_size(self, tmp_path):
        """Test title font size option."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Title")])])

        options = OdpRendererOptions(title_font_size=36)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "title_size.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_default_font(self, tmp_path):
        """Test default font option."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

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
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Presentation Title")]),
                Paragraph(content=[Text(content="Introduction slide")]),
                ThematicBreak(),
                Heading(level=2, content=[Text(content="Bullet Points")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Point 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Point 2")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Point 3")])]),
                    ],
                ),
                ThematicBreak(),
                Heading(level=2, content=[Text(content="Code Example")]),
                CodeBlock(content='print("Hello")', language="python"),
                ThematicBreak(),
                Heading(level=2, content=[Text(content="Data Table")]),
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Item")]), TableCell(content=[Text(content="Count")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="10")])]
                        )
                    ],
                ),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "complex.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_nested_content(self, tmp_path):
        """Test rendering nested and complex content structures."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Title with "), Strong(content=[Text(content="bold")])]),
                Paragraph(
                    content=[
                        Text(content="Mix of "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=", "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=", and "),
                        Code(content="code"),
                        Text(content="."),
                    ]
                ),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "nested.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestSpeakerNotes:
    """Tests for speaker notes rendering."""

    def test_render_with_speaker_notes(self, tmp_path):
        """Test rendering slide with speaker notes."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
                Heading(level=3, content=[Text(content="Speaker Notes")]),
                Paragraph(content=[Text(content="These are speaker notes")]),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "with_notes.odp"
        renderer.render(doc, output_file)

        # Verify file was created successfully
        assert output_file.exists()

        # Verify notes were added by checking ODP structure
        from odf import draw, presentation
        from odf.opendocument import load

        odp = load(str(output_file))
        pages = odp.presentation.getElementsByType(draw.Page)
        assert len(pages) >= 1

        # Check for notes element
        page = pages[0]
        notes_elements = page.getElementsByType(presentation.Notes)
        assert len(notes_elements) > 0, "Should have notes element"

    def test_render_without_notes_when_disabled(self, tmp_path):
        """Test that notes are not rendered when include_notes=False."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
                Heading(level=3, content=[Text(content="Speaker Notes")]),
                Paragraph(content=[Text(content="These should not appear")]),
            ]
        )

        options = OdpRendererOptions(include_notes=False)
        renderer = OdpRenderer(options)
        output_file = tmp_path / "no_notes.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify no notes were added
        from odf import draw, presentation
        from odf.opendocument import load

        odp = load(str(output_file))
        pages = odp.presentation.getElementsByType(draw.Page)
        page = pages[0]
        notes_elements = page.getElementsByType(presentation.Notes)
        assert len(notes_elements) == 0, "Should not have notes when disabled"

    def test_render_slide_without_notes_section(self, tmp_path):
        """Test rendering slide without speaker notes section."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "no_notes_section.odp"
        renderer.render(doc, output_file)

        # Should not crash
        assert output_file.exists()

        # Verify no notes element
        from odf import draw, presentation
        from odf.opendocument import load

        odp = load(str(output_file))
        pages = odp.presentation.getElementsByType(draw.Page)
        page = pages[0]
        notes_elements = page.getElementsByType(presentation.Notes)
        assert len(notes_elements) == 0

    def test_render_notes_with_formatting(self, tmp_path):
        """Test rendering speaker notes with formatting."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
                Heading(level=3, content=[Text(content="Speaker Notes")]),
                Paragraph(
                    content=[
                        Strong(content=[Text(content="Bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text"),
                    ]
                ),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "formatted_notes.odp"
        renderer.render(doc, output_file)

        # Verify notes element exists
        assert output_file.exists()

        from odf import draw, presentation
        from odf.opendocument import load

        odp = load(str(output_file))
        pages = odp.presentation.getElementsByType(draw.Page)
        page = pages[0]
        notes_elements = page.getElementsByType(presentation.Notes)
        assert len(notes_elements) > 0

    def test_render_multiple_slides_with_notes(self, tmp_path):
        """Test rendering multiple slides each with their own notes."""
        doc = Document(
            children=[
                # Slide 1
                Heading(level=2, content=[Text(content="Slide 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=3, content=[Text(content="Speaker Notes")]),
                Paragraph(content=[Text(content="Notes for slide 1")]),
                ThematicBreak(),
                # Slide 2
                Heading(level=2, content=[Text(content="Slide 2")]),
                Paragraph(content=[Text(content="Content 2")]),
                Heading(level=3, content=[Text(content="Speaker Notes")]),
                Paragraph(content=[Text(content="Notes for slide 2")]),
                ThematicBreak(),
                # Slide 3 without notes
                Heading(level=2, content=[Text(content="Slide 3")]),
                Paragraph(content=[Text(content="Content 3")]),
            ]
        )

        renderer = OdpRenderer()
        output_file = tmp_path / "multi_notes.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify each slide has correct notes status
        from odf import draw, presentation
        from odf.opendocument import load

        odp = load(str(output_file))
        pages = odp.presentation.getElementsByType(draw.Page)
        assert len(pages) == 3

        # Slide 1 and 2 should have notes
        notes1 = pages[0].getElementsByType(presentation.Notes)
        assert len(notes1) > 0, "Slide 1 should have notes"

        notes2 = pages[1].getElementsByType(presentation.Notes)
        assert len(notes2) > 0, "Slide 2 should have notes"

        # Slide 3 should not have notes
        notes3 = pages[2].getElementsByType(presentation.Notes)
        assert len(notes3) == 0, "Slide 3 should not have notes"


@pytest.mark.unit
class TestRenderToBytes:
    """Tests for render_to_bytes method."""

    def test_render_to_bytes_returns_bytes(self):
        """Test render_to_bytes returns valid bytes."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = OdpRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert len(result) > 0
        # ODP files start with PK (ZIP magic bytes)
        assert result[:2] == b"PK"

    def test_render_to_bytes_with_complex_content(self):
        """Test render_to_bytes with complex document."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Title")]),
                Paragraph(content=[Strong(content=[Text(content="Bold text")])]),
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )
        renderer = OdpRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert len(result) > 100  # Should have substantial content


@pytest.mark.unit
class TestCreatorMetadata:
    """Tests for creator metadata option."""

    def test_creator_metadata_set(self, tmp_path):
        """Test creator metadata is set in document."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        options = OdpRendererOptions(creator="Test Application 1.0")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "with_creator.odp"
        renderer.render(doc, output_file)

        # Verify file was created successfully
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_creator_metadata_default(self, tmp_path):
        """Test default creator metadata (None)."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        options = OdpRendererOptions()  # No creator set
        renderer = OdpRenderer(options)
        output_file = tmp_path / "no_creator.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestImageRendering:
    """Tests for image rendering."""

    def test_render_image_no_url(self, tmp_path):
        """Test rendering image with no URL (should be skipped)."""
        from all2md.ast import Image

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Images")]),
                Paragraph(content=[Text(content="Before image")]),
                Image(url="", alt_text="Empty URL"),  # Empty URL
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "no_url.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_image_local_file(self, tmp_path):
        """Test rendering local image file."""
        from all2md.ast import Image

        # Create a simple test image
        image_file = tmp_path / "test.png"
        # Minimal valid PNG (1x1 transparent)
        png_data = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,  # PNG signature
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,  # IHDR chunk
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x08,
                0x06,
                0x00,
                0x00,
                0x00,
                0x1F,
                0x15,
                0xC4,
                0x89,
                0x00,
                0x00,
                0x00,
                0x0A,
                0x49,
                0x44,
                0x41,
                0x54,  # IDAT chunk
                0x78,
                0x9C,
                0x63,
                0x00,
                0x01,
                0x00,
                0x00,
                0x05,
                0x00,
                0x01,
                0x0D,
                0x0A,
                0x2D,
                0xB4,
                0x00,
                0x00,
                0x00,
                0x00,
                0x49,
                0x45,
                0x4E,
                0x44,  # IEND chunk
                0xAE,
                0x42,
                0x60,
                0x82,
            ]
        )
        image_file.write_bytes(png_data)

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Images")]),
                Image(url=str(image_file), alt_text="Test image"),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "local_image.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_base64_image(self, tmp_path):
        """Test rendering base64 encoded image."""
        from all2md.ast import Image

        # Minimal 1x1 PNG as base64
        base64_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Base64 Image")]),
                Image(url=base64_png, alt_text="Base64 image"),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "base64_image.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestLinkRendering:
    """Tests for link rendering."""

    def test_render_link(self, tmp_path):
        """Test rendering a link."""
        from all2md.ast import Link

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Links")]),
                Paragraph(
                    content=[
                        Text(content="Visit "),
                        Link(url="https://example.com", content=[Text(content="Example")]),
                        Text(content=" for more."),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "links.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_link_with_formatting(self, tmp_path):
        """Test rendering a link with formatted text."""
        from all2md.ast import Link

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Link(
                            url="https://example.com",
                            content=[Strong(content=[Text(content="Bold Link")])],
                        ),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "formatted_link.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestCommentRendering:
    """Tests for comment rendering modes."""

    def test_comment_native_mode(self, tmp_path):
        """Test comment in native annotation mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Comments")]),
                Paragraph(content=[Text(content="Before comment")]),
                Comment(content="This is a comment"),
            ]
        )
        options = OdpRendererOptions(comment_mode="native")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "comment_native.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_comment_visible_mode(self, tmp_path):
        """Test comment in visible mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Comments")]),
                Comment(content="Visible comment"),
            ]
        )
        options = OdpRendererOptions(comment_mode="visible")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "comment_visible.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_comment_ignore_mode(self, tmp_path):
        """Test comment in ignore mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Comments")]),
                Comment(content="Ignored comment"),
            ]
        )
        options = OdpRendererOptions(comment_mode="ignore")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "comment_ignore.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_comment_with_metadata(self, tmp_path):
        """Test comment with author and date metadata."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(
                    content="Comment with metadata",
                    metadata={"author": "John Doe", "date": "2025-01-01", "label": "1"},
                ),
            ]
        )
        options = OdpRendererOptions(comment_mode="native")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "comment_metadata.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_comment_visible_with_metadata(self, tmp_path):
        """Test visible comment with author metadata."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(
                    content="Comment content",
                    metadata={"author": "Jane", "date": "2025-12-01"},
                ),
            ]
        )
        options = OdpRendererOptions(comment_mode="visible")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "comment_visible_meta.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_inline_comment_native(self, tmp_path):
        """Test inline comment in native mode."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        CommentInline(content="inline note"),
                        Text(content=" inline."),
                    ]
                ),
            ]
        )
        options = OdpRendererOptions(comment_mode="native")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "inline_native.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_inline_comment_visible(self, tmp_path):
        """Test inline comment in visible mode."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="visible note", metadata={"author": "Bob", "label": "A"}),
                    ]
                ),
            ]
        )
        options = OdpRendererOptions(comment_mode="visible")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "inline_visible.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_inline_comment_ignore(self, tmp_path):
        """Test inline comment in ignore mode."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="ignored"),
                    ]
                ),
            ]
        )
        options = OdpRendererOptions(comment_mode="ignore")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "inline_ignore.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering."""

    def test_render_inline_math(self, tmp_path):
        """Test rendering inline math."""
        from all2md.ast import MathInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="The equation "),
                        MathInline(content="E = mc^2"),
                        Text(content=" is famous."),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "inline_math.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_math_block(self, tmp_path):
        """Test rendering math block."""
        from all2md.ast import MathBlock

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Math")]),
                MathBlock(content="\\int_0^\\infty e^{-x} dx = 1"),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "math_block.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestDefinitionListRendering:
    """Tests for definition list rendering."""

    def test_render_definition_list(self, tmp_path):
        """Test rendering a definition list."""
        from all2md.ast import DefinitionDescription, DefinitionList, DefinitionTerm

        term1 = DefinitionTerm(content=[Text(content="Term 1")])
        desc1 = DefinitionDescription(content=[Text(content="Description for term 1")])
        term2 = DefinitionTerm(content=[Text(content="Term 2")])
        desc2a = DefinitionDescription(content=[Text(content="First description")])
        desc2b = DefinitionDescription(content=[Text(content="Second description")])

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Definitions")]),
                DefinitionList(items=[(term1, [desc1]), (term2, [desc2a, desc2b])]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "def_list.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestBlockQuoteRendering:
    """Tests for block quote rendering."""

    def test_render_block_quote(self, tmp_path):
        """Test rendering a block quote."""
        from all2md.ast import BlockQuote

        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Quotes")]),
                BlockQuote(children=[Paragraph(content=[Text(content="A wise quote.")])]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "blockquote.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_nested_block_quote(self, tmp_path):
        """Test rendering nested block quotes."""
        from all2md.ast import BlockQuote

        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="Outer quote")]),
                        BlockQuote(children=[Paragraph(content=[Text(content="Inner quote")])]),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "nested_quote.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestAdditionalFormattingNodes:
    """Tests for additional formatting nodes."""

    def test_render_strikethrough(self, tmp_path):
        """Test rendering strikethrough text."""
        from all2md.ast import Strikethrough

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Normal and "),
                        Strikethrough(content=[Text(content="deleted")]),
                        Text(content=" text."),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "strikethrough.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_subscript(self, tmp_path):
        """Test rendering subscript text."""
        from all2md.ast import Subscript

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="H"),
                        Subscript(content=[Text(content="2")]),
                        Text(content="O"),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "subscript.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_superscript(self, tmp_path):
        """Test rendering superscript text."""
        from all2md.ast import Superscript

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="x"),
                        Superscript(content=[Text(content="2")]),
                        Text(content=" + y"),
                        Superscript(content=[Text(content="2")]),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "superscript.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_underline(self, tmp_path):
        """Test rendering underlined text."""
        from all2md.ast import Underline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Normal and "),
                        Underline(content=[Text(content="underlined")]),
                        Text(content=" text."),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "underline.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_line_break(self, tmp_path):
        """Test rendering line breaks."""
        from all2md.ast import LineBreak

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line one"),
                        LineBreak(),
                        Text(content="Line two"),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "line_break.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_thematic_break(self, tmp_path):
        """Test rendering thematic break in content."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        # Use separator mode to not split slides
        options = OdpRendererOptions(slide_split_mode="heading")
        renderer = OdpRenderer(options)
        output_file = tmp_path / "thematic.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestFootnoteRendering:
    """Tests for footnote rendering."""

    def test_render_footnote_reference(self, tmp_path):
        """Test rendering footnote reference."""
        from all2md.ast import FootnoteReference

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with footnote"),
                        FootnoteReference(identifier="1"),
                        Text(content="."),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "footnote_ref.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_footnote_definition(self, tmp_path):
        """Test rendering footnote definition (should be skipped)."""
        from all2md.ast import FootnoteDefinition

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Main text")]),
                FootnoteDefinition(
                    identifier="1",
                    content=[Paragraph(content=[Text(content="Footnote content")])],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "footnote_def.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestTableAdvanced:
    """Tests for advanced table rendering."""

    def test_table_without_header(self, tmp_path):
        """Test rendering table without header row."""
        table = Table(
            header=None,
            rows=[
                TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]),
                TableRow(cells=[TableCell(content=[Text(content="C")]), TableCell(content=[Text(content="D")])]),
            ],
        )
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Table")]),
                table,
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "no_header.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_table_with_colspan(self, tmp_path):
        """Test rendering table with colspan."""
        table = Table(
            header=TableRow(
                cells=[
                    TableCell(content=[Text(content="Header 1")]),
                    TableCell(content=[Text(content="Header 2")]),
                    TableCell(content=[Text(content="Header 3")]),
                ]
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Spans 2")], colspan=2),
                        TableCell(content=[Text(content="Normal")]),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])
        renderer = OdpRenderer()
        output_file = tmp_path / "colspan.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_table_with_rowspan(self, tmp_path):
        """Test rendering table with rowspan."""
        table = Table(
            header=TableRow(
                cells=[
                    TableCell(content=[Text(content="A")]),
                    TableCell(content=[Text(content="B")]),
                ]
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Spans 2 rows")], rowspan=2),
                        TableCell(content=[Text(content="B1")]),
                    ]
                ),
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="B2")]),
                    ]
                ),
            ],
        )
        doc = Document(children=[table])
        renderer = OdpRenderer()
        output_file = tmp_path / "rowspan.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_empty_table(self, tmp_path):
        """Test rendering empty table."""
        table = Table(header=None, rows=[])
        doc = Document(children=[Heading(level=2, content=[Text(content="Empty")]), table])
        renderer = OdpRenderer()
        output_file = tmp_path / "empty_table.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestHTMLHandling:
    """Tests for HTML node handling."""

    def test_skip_html_block(self, tmp_path):
        """Test that HTML blocks are skipped."""
        from all2md.ast import HTMLBlock

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                HTMLBlock(content="<div>HTML content</div>"),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "html_block.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_skip_html_inline(self, tmp_path):
        """Test that inline HTML is skipped."""
        from all2md.ast import HTMLInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        HTMLInline(content="<span>inline</span>"),
                        Text(content=" more"),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "html_inline.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestNestedLists:
    """Tests for nested list rendering."""

    def test_render_nested_unordered_list(self, tmp_path):
        """Test rendering nested unordered lists."""
        inner_list = List(
            ordered=False,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="Inner 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Inner 2")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Outer 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Outer 2")]), inner_list]),
                    ],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "nested_ul.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_nested_ordered_list(self, tmp_path):
        """Test rendering nested ordered lists."""
        inner_list = List(
            ordered=True,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="a")])]),
                ListItem(children=[Paragraph(content=[Text(content="b")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="2")]), inner_list]),
                    ],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "nested_ol.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestOptionsValidation:
    """Tests for options validation."""

    def test_invalid_options_type(self):
        """Test that invalid options type raises error."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            OdpRenderer(options="invalid")

    def test_valid_options_object(self, tmp_path):
        """Test valid options object is accepted."""
        options = OdpRendererOptions(
            slide_split_mode="heading",
            slide_split_heading_level=2,
            use_heading_as_slide_title=True,
            default_font_size=18,
            title_font_size=32,
        )
        renderer = OdpRenderer(options)
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        output_file = tmp_path / "valid_opts.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases."""

    def test_document_with_only_headings(self, tmp_path):
        """Test document with only headings."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="H1")]),
                Heading(level=2, content=[Text(content="H2")]),
                Heading(level=3, content=[Text(content="H3")]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "only_headings.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_very_long_text(self, tmp_path):
        """Test rendering very long text content."""
        long_text = "This is a very long paragraph. " * 100
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Long Content")]),
                Paragraph(content=[Text(content=long_text)]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "long_text.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_special_characters_in_text(self, tmp_path):
        """Test rendering special characters."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Special: <>&\"' and unicode: \u00e9\u00f1\u00fc"),
                    ]
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "special_chars.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_empty_paragraph(self, tmp_path):
        """Test rendering empty paragraph."""
        doc = Document(
            children=[
                Paragraph(content=[]),
                Paragraph(content=[Text(content="After empty")]),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "empty_para.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_mixed_content_types(self, tmp_path):
        """Test rendering mixed content types in one slide."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Mixed Content")]),
                Paragraph(
                    content=[
                        Strong(content=[Text(content="Bold")]),
                        Text(content=", "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=", and "),
                        Code(content="code"),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Bullet")])]),
                    ],
                ),
                CodeBlock(content="print('Hello')", language="python"),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Val")])])],
                ),
            ]
        )
        renderer = OdpRenderer()
        output_file = tmp_path / "mixed.odp"
        renderer.render(doc, output_file)

        assert output_file.exists()
