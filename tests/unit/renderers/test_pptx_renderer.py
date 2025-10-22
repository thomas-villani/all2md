#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_pptx_renderer.py
"""Unit tests for PptxRenderer.

Tests cover:
- Rendering all node types to PPTX
- Slide splitting strategies
- Slide layout and formatting
- Edge cases and options

Note: These tests require python-pptx to be installed.
PPTX content verification is limited as we mainly test structure.
"""

from io import BytesIO

import pytest

try:
    from pptx import Presentation

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

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
from all2md.options import PptxRendererOptions

if PPTX_AVAILABLE:
    from all2md.renderers.pptx import PptxRenderer

pytestmark = pytest.mark.skipif(not PPTX_AVAILABLE, reason="python-pptx not installed")


@pytest.mark.unit
@pytest.mark.pptx
class TestBasicRendering:
    """Tests for basic PPTX rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = PptxRenderer()
        output_file = tmp_path / "empty.pptx"
        renderer.render(doc, output_file)

        # Verify file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0

        # Verify it's a valid PPTX
        prs = Presentation(str(output_file))
        assert prs is not None

    def test_render_to_file_path(self, tmp_path):
        """Test rendering to file path string."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = PptxRenderer()
        output_file = tmp_path / "test.pptx"
        renderer.render(doc, str(output_file))

        assert output_file.exists()

    def test_render_to_path_object(self, tmp_path):
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = PptxRenderer()
        output_file = tmp_path / "test.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = PptxRenderer()
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

        renderer = PptxRenderer()
        output_file = tmp_path / "single.pptx"
        renderer.render(doc, output_file)

        # Verify slide count
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1


@pytest.mark.unit
@pytest.mark.pptx
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

        options = PptxRendererOptions(slide_split_mode="separator")
        renderer = PptxRenderer(options)
        output_file = tmp_path / "split_separator.pptx"
        renderer.render(doc, output_file)

        # Verify slide count
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 3

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

        options = PptxRendererOptions(slide_split_mode="heading", slide_split_heading_level=2)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "split_heading.pptx"
        renderer.render(doc, output_file)

        # Verify slide count
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 3

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

        options = PptxRendererOptions(slide_split_mode="auto")
        renderer = PptxRenderer(options)
        output_file = tmp_path / "split_auto.pptx"
        renderer.render(doc, output_file)

        # Should split by separator, creating 2 slides
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 2

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

        options = PptxRendererOptions(slide_split_mode="auto")
        renderer = PptxRenderer(options)
        output_file = tmp_path / "split_auto_heading.pptx"
        renderer.render(doc, output_file)

        # Should split by H2, creating 2 slides
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 2

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
        options = PptxRendererOptions(slide_split_mode="heading", slide_split_heading_level=2)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "split_h2.pptx"
        renderer.render(doc, output_file)

        # Should have 3 slides (H1+content, H2, H2)
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 3


@pytest.mark.unit
@pytest.mark.pptx
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

        options = PptxRendererOptions(slide_split_mode="heading", use_heading_as_slide_title=True)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "heading_titles.pptx"
        renderer.render(doc, output_file)

        # Verify slide has title
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        assert slide.shapes.title.text == "My Slide Title"

    def test_disable_heading_titles(self, tmp_path):
        """Test disabling heading-based titles."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Heading Text")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = PptxRendererOptions(slide_split_mode="heading", use_heading_as_slide_title=False)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "no_heading_titles.pptx"
        renderer.render(doc, output_file)

        # Verify slide has no title (empty)
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        assert slide.shapes.title.text == ""


@pytest.mark.unit
@pytest.mark.pptx
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

        renderer = PptxRenderer()
        output_file = tmp_path / "paragraphs.pptx"
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

        renderer = PptxRenderer()
        output_file = tmp_path / "formatted.pptx"
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

        renderer = PptxRenderer()
        output_file = tmp_path / "code.pptx"
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

        renderer = PptxRenderer()
        output_file = tmp_path / "lists.pptx"
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

        renderer = PptxRenderer()
        output_file = tmp_path / "table.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        # Verify table was created
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        # Check that a table shape exists (basic verification)
        has_table = any(hasattr(shape, "table") for shape in slide.shapes)
        assert has_table


@pytest.mark.unit
@pytest.mark.pptx
class TestOptions:
    """Tests for rendering options."""

    def test_default_font_size(self, tmp_path):
        """Test default font size option."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = PptxRendererOptions(default_font_size=24)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "font_size.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_title_font_size(self, tmp_path):
        """Test title font size option."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Title")])])

        options = PptxRendererOptions(title_font_size=36)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "title_size.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_default_font(self, tmp_path):
        """Test default font option."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = PptxRendererOptions(default_font="Arial")
        renderer = PptxRenderer(options)
        output_file = tmp_path / "font.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pptx
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

        renderer = PptxRenderer()
        output_file = tmp_path / "complex.pptx"
        renderer.render(doc, output_file)

        # Verify presentation created with correct slide count
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 4

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

        renderer = PptxRenderer()
        output_file = tmp_path / "nested.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pptx
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

        renderer = PptxRenderer()
        output_file = tmp_path / "with_notes.pptx"
        renderer.render(doc, output_file)

        # Verify notes were added
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1
        slide = prs.slides[0]
        notes_text = slide.notes_slide.notes_text_frame.text
        assert "speaker notes" in notes_text.lower()

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

        options = PptxRendererOptions(include_notes=False)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "no_notes.pptx"
        renderer.render(doc, output_file)

        # Verify notes were not added (or are empty)
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        notes_text = slide.notes_slide.notes_text_frame.text.strip()
        # Notes should be empty or only contain the "Speaker Notes" heading as regular content
        assert "These should not appear" not in notes_text

    def test_render_slide_without_notes_section(self, tmp_path):
        """Test rendering slide without speaker notes section."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide Title")]),
                Paragraph(content=[Text(content="Slide content")]),
            ]
        )

        renderer = PptxRenderer()
        output_file = tmp_path / "no_notes_section.pptx"
        renderer.render(doc, output_file)

        # Should not crash, notes should be empty
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        notes_text = slide.notes_slide.notes_text_frame.text.strip()
        assert notes_text == ""

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

        renderer = PptxRenderer()
        output_file = tmp_path / "formatted_notes.pptx"
        renderer.render(doc, output_file)

        # Verify notes contain the text
        prs = Presentation(str(output_file))
        slide = prs.slides[0]
        notes_text = slide.notes_slide.notes_text_frame.text
        assert "Bold" in notes_text
        assert "italic" in notes_text

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

        renderer = PptxRenderer()
        output_file = tmp_path / "multi_notes.pptx"
        renderer.render(doc, output_file)

        # Verify each slide has correct notes
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 3

        notes1 = prs.slides[0].notes_slide.notes_text_frame.text
        assert "Notes for slide 1" in notes1

        notes2 = prs.slides[1].notes_slide.notes_text_frame.text
        assert "Notes for slide 2" in notes2

        notes3 = prs.slides[2].notes_slide.notes_text_frame.text.strip()
        assert notes3 == ""  # No notes for slide 3


@pytest.mark.unit
@pytest.mark.pptx
class TestForceTextboxBullets:
    """Tests for force_textbox_bullets option."""

    def test_force_textbox_bullets_enabled_by_default(self, tmp_path):
        """Test that force_textbox_bullets is enabled by default."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide with List")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )

        renderer = PptxRenderer()
        output_file = tmp_path / "bullets_default.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify PPTX was created successfully
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1

    def test_force_textbox_bullets_enabled_explicit(self, tmp_path):
        """Test force_textbox_bullets explicitly enabled."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide with List")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )

        options = PptxRendererOptions(force_textbox_bullets=True)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "bullets_enabled.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify PPTX structure
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1

        # Check that the slide has text content
        slide = prs.slides[0]
        text_found = False
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                if "Item" in shape.text_frame.text:
                    text_found = True
        assert text_found

    def test_force_textbox_bullets_disabled(self, tmp_path):
        """Test force_textbox_bullets disabled for strict templates."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Slide with List")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )

        options = PptxRendererOptions(force_textbox_bullets=False)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "bullets_disabled.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify PPTX structure
        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1

        # Content should still be rendered, just without OOXML bullet manipulation
        slide = prs.slides[0]
        text_found = False
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                if "Item" in shape.text_frame.text:
                    text_found = True
        assert text_found

    def test_force_textbox_bullets_with_nested_lists(self, tmp_path):
        """Test force_textbox_bullets with nested lists."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Nested Lists")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 1")]),
                                List(
                                    ordered=False,
                                    items=[
                                        ListItem(children=[Paragraph(content=[Text(content="Subitem 1.1")])]),
                                        ListItem(children=[Paragraph(content=[Text(content="Subitem 1.2")])]),
                                    ],
                                ),
                            ]
                        ),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )

        # Test with bullets enabled
        options = PptxRendererOptions(force_textbox_bullets=True)
        renderer = PptxRenderer(options)
        output_file = tmp_path / "nested_bullets_enabled.pptx"
        renderer.render(doc, output_file)

        assert output_file.exists()

        prs = Presentation(str(output_file))
        assert len(prs.slides) == 1

    def test_force_textbox_bullets_ordered_lists_unaffected(self, tmp_path):
        """Test that force_textbox_bullets only affects unordered lists."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Ordered List")]),
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Third")])]),
                    ],
                ),
            ]
        )

        # Ordered lists use manual numbering regardless of this option
        options_enabled = PptxRendererOptions(force_textbox_bullets=True)
        options_disabled = PptxRendererOptions(force_textbox_bullets=False)

        # Test with enabled
        renderer = PptxRenderer(options_enabled)
        output_enabled = tmp_path / "ordered_enabled.pptx"
        renderer.render(doc, output_enabled)
        assert output_enabled.exists()

        # Test with disabled
        renderer = PptxRenderer(options_disabled)
        output_disabled = tmp_path / "ordered_disabled.pptx"
        renderer.render(doc, output_disabled)
        assert output_disabled.exists()

        # Both should have manual numbering
        prs_enabled = Presentation(str(output_enabled))
        prs_disabled = Presentation(str(output_disabled))
        assert len(prs_enabled.slides) == 1
        assert len(prs_disabled.slides) == 1
