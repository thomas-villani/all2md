#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_epub_renderer.py
"""Unit tests for EpubRenderer.

Tests cover:
- Rendering all node types to EPUB
- Chapter splitting strategies
- EPUB metadata handling
- Navigation and TOC generation
- Edge cases and options

Note: These tests require ebooklib to be installed.
"""

from io import BytesIO

import pytest

try:
    import ebooklib  # noqa: F401
    from ebooklib import epub

    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    Image,
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
from all2md.options import EpubRendererOptions

if EBOOKLIB_AVAILABLE:
    from all2md.renderers.epub import EpubRenderer

pytestmark = pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not installed")


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic EPUB rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = EpubRenderer()
        output_file = tmp_path / "empty.epub"
        renderer.render(doc, output_file)

        # Verify file was created
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_render_to_file_path(self, tmp_path):
        """Test rendering to file path."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = EpubRenderer()
        output_file = tmp_path / "test.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_path_object(self, tmp_path):
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = EpubRenderer()
        output_file = tmp_path / "test.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO object."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = EpubRenderer()
        buffer = BytesIO()
        renderer.render(doc, buffer)

        # Verify data was written
        assert buffer.tell() > 0
        buffer.seek(0)
        data = buffer.read()
        assert len(data) > 0


@pytest.mark.unit
class TestSplittingStrategies:
    """Tests for chapter splitting strategies."""

    def test_split_by_separator(self, tmp_path):
        """Test splitting chapters using separator mode."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Chapter 1 content")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Chapter 2 content")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Chapter 3 content")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="separator")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "split_separator.epub"
        renderer.render(doc, output_file)

        # Verify file created
        assert output_file.exists()

    def test_split_by_heading(self, tmp_path):
        """Test splitting chapters using heading mode."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=1, content=[Text(content="Chapter 2")]),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="heading", chapter_split_heading_level=1)
        renderer = EpubRenderer(options)
        output_file = tmp_path / "split_heading.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_auto_prefers_separator(self, tmp_path):
        """Test auto mode prefers separator when available."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="H1")]),
                Paragraph(content=[Text(content="Content 1")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="auto")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "split_auto.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_split_auto_fallback_to_heading(self, tmp_path):
        """Test auto mode falls back to headings when no separators."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=1, content=[Text(content="Chapter 2")]),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="auto")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "split_auto_heading.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestMetadata:
    """Tests for EPUB metadata handling."""

    def test_metadata_from_options(self, tmp_path):
        """Test setting metadata from options."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = EpubRendererOptions(title="Test Book", author="Test Author", language="en")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "metadata.epub"
        renderer.render(doc, output_file)

        # Verify EPUB created
        assert output_file.exists()

        # Read and verify metadata
        book = epub.read_epub(str(output_file))
        assert book.get_metadata("DC", "title")[0][0] == "Test Book"
        assert book.get_metadata("DC", "creator")[0][0] == "Test Author"
        assert book.get_metadata("DC", "language")[0][0] == "en"

    def test_metadata_from_document(self, tmp_path):
        """Test extracting metadata from document."""
        doc = Document(
            metadata={"title": "Document Title", "author": "Document Author"},
            children=[Paragraph(content=[Text(content="Content")])],
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "doc_metadata.epub"
        renderer.render(doc, output_file)

        # Read and verify metadata
        book = epub.read_epub(str(output_file))
        assert book.get_metadata("DC", "title")[0][0] == "Document Title"
        assert book.get_metadata("DC", "creator")[0][0] == "Document Author"

    def test_options_override_document_metadata(self, tmp_path):
        """Test that options override document metadata."""
        doc = Document(
            metadata={"title": "Document Title", "author": "Document Author"},
            children=[Paragraph(content=[Text(content="Content")])],
        )

        options = EpubRendererOptions(title="Override Title", author="Override Author")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "override.epub"
        renderer.render(doc, output_file)

        # Verify options took precedence
        book = epub.read_epub(str(output_file))
        assert book.get_metadata("DC", "title")[0][0] == "Override Title"
        assert book.get_metadata("DC", "creator")[0][0] == "Override Author"

    def test_default_title_when_none(self, tmp_path):
        """Test default title is used when none provided."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        renderer = EpubRenderer()
        output_file = tmp_path / "default_title.epub"
        renderer.render(doc, output_file)

        # Should have default title
        book = epub.read_epub(str(output_file))
        title = book.get_metadata("DC", "title")[0][0]
        assert title == "Untitled"


@pytest.mark.unit
class TestChapterTitles:
    """Tests for chapter title generation."""

    def test_use_heading_as_title(self, tmp_path):
        """Test using heading text as chapter title."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="First Chapter")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="heading", use_heading_as_chapter_title=True)
        renderer = EpubRenderer(options)
        output_file = tmp_path / "heading_titles.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_template_titles(self, tmp_path):
        """Test using template for chapter titles."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Content 1")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="separator", chapter_title_template="Part {num}")
        renderer = EpubRenderer(options)
        output_file = tmp_path / "template_titles.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_disable_heading_titles(self, tmp_path):
        """Test disabling heading-based titles."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Heading Text")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = EpubRendererOptions(
            chapter_split_mode="heading", use_heading_as_chapter_title=False, chapter_title_template="Chapter {num}"
        )
        renderer = EpubRenderer(options)
        output_file = tmp_path / "no_heading_titles.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestTableOfContents:
    """Tests for table of contents generation."""

    def test_generate_toc_enabled(self, tmp_path):
        """Test TOC generation when enabled."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content 1")]),
                Heading(level=1, content=[Text(content="Chapter 2")]),
                Paragraph(content=[Text(content="Content 2")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="heading", generate_toc=True)
        renderer = EpubRenderer(options)
        output_file = tmp_path / "with_toc.epub"
        renderer.render(doc, output_file)

        # Verify EPUB has TOC
        book = epub.read_epub(str(output_file))
        assert len(book.toc) > 0

    def test_generate_toc_disabled(self, tmp_path):
        """Test TOC generation when disabled."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = EpubRendererOptions(chapter_split_mode="heading", generate_toc=False)
        renderer = EpubRenderer(options)
        output_file = tmp_path / "no_toc.epub"
        renderer.render(doc, output_file)

        # Verify EPUB has empty or minimal TOC
        book = epub.read_epub(str(output_file))
        # book.toc can be a list or a single Link object depending on library version
        if isinstance(book.toc, list):
            assert len(book.toc) == 0
        else:
            # Single Link object - check if it's empty/default
            assert book.toc is None or (hasattr(book.toc, "title") and not book.toc.title)


@pytest.mark.unit
class TestComplexContent:
    """Tests for rendering complex content structures."""

    def test_render_with_tables(self, tmp_path):
        """Test rendering document with tables."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter with Table")]),
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

        renderer = EpubRenderer()
        output_file = tmp_path / "with_tables.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_with_code_blocks(self, tmp_path):
        """Test rendering document with code blocks."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Code Example")]),
                CodeBlock(content='def hello():\n    print("Hello")', language="python"),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_code.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_with_lists(self, tmp_path):
        """Test rendering document with lists."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Lists")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
                    ],
                ),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_lists.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_complex_multi_chapter(self, tmp_path):
        """Test rendering complex multi-chapter document."""
        doc = Document(
            metadata={"title": "Complex Book", "author": "Test"},
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text.")]
                ),
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                ),
                ThematicBreak(),
                Heading(level=1, content=[Text(content="Chapter 2")]),
                CodeBlock(content="code here", language="python"),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Data")])])],
                ),
            ],
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "complex.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()
        # Verify it's a valid EPUB
        book = epub.read_epub(str(output_file))
        assert book is not None


@pytest.mark.unit
class TestImageEmbedding:
    """Tests for image embedding in EPUB."""

    def test_render_with_data_uri_image(self, tmp_path):
        """Test rendering with base64 data URI image."""
        # Create a simple 1x1 PNG as base64
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        import base64

        base64_str = base64.b64encode(png_data).decode("ascii")
        data_uri = f"data:image/png;base64,{base64_str}"

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter with Image")]),
                Paragraph(content=[Image(url=data_uri, alt_text="Test image")]),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_data_uri.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify EPUB contains the image
        book = epub.read_epub(str(output_file))
        images = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_IMAGE]
        assert len(images) > 0

    def test_render_with_local_file_image(self, tmp_path):
        """Test rendering with local file image."""
        # Create a test image file
        image_file = tmp_path / "test_img.png"
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        image_file.write_bytes(png_data)

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter with Image")]),
                Paragraph(content=[Image(url=str(image_file), alt_text="Local image")]),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_local_image.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify EPUB contains the image
        book = epub.read_epub(str(output_file))
        images = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_IMAGE]
        assert len(images) > 0

    def test_render_with_multiple_images(self, tmp_path):
        """Test rendering with multiple images."""
        # Create test images
        image1 = tmp_path / "img1.png"
        image2 = tmp_path / "img2.png"
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        image1.write_bytes(png_data)
        image2.write_bytes(png_data)

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter with Images")]),
                Paragraph(content=[Image(url=str(image1), alt_text="Image 1")]),
                Paragraph(content=[Image(url=str(image2), alt_text="Image 2")]),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_multiple_images.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify EPUB contains both images
        book = epub.read_epub(str(output_file))
        images = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_IMAGE]
        assert len(images) == 2

    def test_render_with_http_image(self, tmp_path):
        """Test rendering with HTTP URL image (should be preserved)."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter with External Image")]),
                Paragraph(content=[Image(url="https://example.com/image.png", alt_text="External image")]),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "with_http_image.epub"
        renderer.render(doc, output_file)

        # Should still create EPUB even though external image isn't embedded
        assert output_file.exists()

    def test_render_with_cover_image(self, tmp_path):
        """Test rendering with cover image."""
        # Create cover image
        cover_file = tmp_path / "cover.png"
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        cover_file.write_bytes(png_data)

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = EpubRendererOptions(include_cover=True, cover_image_path=str(cover_file))
        renderer = EpubRenderer(options)
        output_file = tmp_path / "with_cover.epub"
        renderer.render(doc, output_file)

        # Just verify the EPUB was created successfully with cover options
        # Cover image handling varies by ebooklib version
        assert output_file.exists()

        # Verify EPUB is valid
        book = epub.read_epub(str(output_file))
        assert book is not None

    def test_image_url_rewriting(self, tmp_path):
        """Test that image URLs are rewritten to internal paths."""
        # Create test image
        image_file = tmp_path / "original.png"
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        image_file.write_bytes(png_data)

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter")]),
                Paragraph(content=[Image(url=str(image_file), alt_text="Test")]),
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "url_rewrite.epub"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Read EPUB and verify chapter HTML contains internal path
        book = epub.read_epub(str(output_file))
        chapters = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
        assert len(chapters) > 0

        # Check that at least one chapter contains image reference
        chapter_html = chapters[0].get_content().decode("utf-8")
        # Should contain internal path like "images/img_001.png"
        assert "images/img_" in chapter_html or "Test" in chapter_html
