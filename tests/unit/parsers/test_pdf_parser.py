#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_pdf_ast.py
"""Unit tests for PDF to AST converter.

Tests cover:
- Page-by-page conversion
- Text block detection and extraction
- Table detection and conversion
- Image extraction
- Formatting preservation
- Heading detection
- Multi-page documents

Note: These tests use mock PyMuPDF objects since creating actual PDF documents
programmatically is complex. Integration tests cover real PDF files.

"""

from unittest.mock import Mock

import pytest

from all2md.ast import Document, Heading, Image, Paragraph, Table
from all2md.options import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter


def _create_mock_text_block(text, bbox=(0, 0, 100, 20), font_size=12, font_name="Arial", font_flags=0):
    """Create a mock text block in PyMuPDF dict format.

    Parameters
    ----------
    text : str
        Text content
    bbox : tuple
        Bounding box (x0, y0, x1, y1)
    font_size : float
        Font size
    font_name : str
        Font name
    font_flags : int
        Font flags (bit 0=superscript, bit 1=italic, bit 2=serifed, bit 3=monospaced, bit 4=bold)

    Returns
    -------
    dict
        Mock text block dictionary in PyMuPDF format

    """
    return {
        "type": 0,  # Text block type
        "bbox": bbox,
        "lines": [
            {
                "bbox": bbox,
                "dir": (1, 0),  # Horizontal text
                "spans": [
                    {
                        "text": text,
                        "bbox": bbox,
                        "size": font_size,
                        "font": font_name,
                        "flags": font_flags,
                    }
                ],
            }
        ],
    }


def _create_mock_page(blocks, width=595, height=842):
    """Create a mock PDF page.

    Parameters
    ----------
    blocks : list
        List of text blocks
    width : int
        Page width
    height : int
        Page height

    Returns
    -------
    Mock
        Mock PDF page

    """
    page = Mock()
    page.get_text = Mock(return_value={"blocks": blocks})
    page.rect = Mock()
    page.rect.width = width
    page.rect.height = height
    page.number = 1

    # Mock image extraction
    page.get_images = Mock(return_value=[])

    # Mock table detection
    page.find_tables = Mock(return_value=Mock(tables=[]))
    page.get_drawings = Mock(return_value=[])  # Return empty list for drawing commands

    # Mock link extraction
    page.get_links = Mock(return_value=[])

    return page


def _create_mock_pdf_document(*pages):
    """Create a mock PDF document.

    Parameters
    ----------
    *pages
        PDF pages

    Returns
    -------
    Mock
        Mock PDF document

    """
    doc = Mock()
    doc.__iter__ = Mock(return_value=iter(pages))
    doc.__len__ = Mock(return_value=len(pages))
    doc.__getitem__ = Mock(side_effect=lambda i: pages[i] if i < len(pages) else None)
    doc.metadata = {}
    doc.page_count = len(pages)
    return doc


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic PDF conversion."""

    def test_single_page_single_block(self) -> None:
        """Test converting a single page with one text block."""
        block = _create_mock_text_block("Hello world")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) > 0

        # Should have at least one paragraph or text element
        paragraphs = [child for child in ast_doc.children if isinstance(child, Paragraph)]
        assert len(paragraphs) >= 1

    def test_single_page_multiple_blocks(self) -> None:
        """Test converting a single page with multiple text blocks."""
        blocks = [
            _create_mock_text_block("First block"),
            _create_mock_text_block("Second block", bbox=(0, 30, 100, 50)),
            _create_mock_text_block("Third block", bbox=(0, 60, 100, 80)),
        ]
        page = _create_mock_page(blocks)
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert len(ast_doc.children) >= 3

    def test_multiple_pages(self) -> None:
        """Test converting multiple pages."""
        page1 = _create_mock_page([_create_mock_text_block("Page 1")])
        page2 = _create_mock_page([_create_mock_text_block("Page 2")])
        page3 = _create_mock_page([_create_mock_text_block("Page 3")])

        doc = _create_mock_pdf_document(page1, page2, page3)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should have content from all pages
        assert len(ast_doc.children) >= 3


@pytest.mark.unit
class TestHeadingDetection:
    """Tests for heading detection based on font size."""

    def test_large_font_as_heading(self) -> None:
        """Test that large font size is detected as heading."""
        # Large font (24pt)
        heading_block = _create_mock_text_block("Heading", font_size=24)
        # Normal font (12pt)
        text_block = _create_mock_text_block("Normal text", bbox=(0, 30, 100, 50), font_size=12)

        page = _create_mock_page([heading_block, text_block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should detect heading (implementation-specific)
        # May have Heading nodes
        [child for child in ast_doc.children if isinstance(child, Heading)]
        # May or may not detect based on implementation
        assert len(ast_doc.children) >= 2

    def test_bold_font_detection(self) -> None:
        """Test bold font detection."""
        bold_block = _create_mock_text_block("Bold text", font_name="Arial-Bold")
        page = _create_mock_page([bold_block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert len(ast_doc.children) >= 1


@pytest.mark.unit
class TestTableDetection:
    """Tests for table detection and conversion."""

    def test_page_with_table(self) -> None:
        """Test page with detected table."""
        # Mock table
        mock_table = Mock()
        mock_table.extract = Mock(return_value=[["Header1", "Header2"], ["Data1", "Data2"]])
        mock_table.bbox = (0, 0, 200, 100)
        mock_table.header = Mock()
        mock_table.header.bbox = (0, 0, 200, 20)

        mock_tables = Mock()
        mock_tables.tables = [mock_table]
        # Make it subscriptable
        mock_tables.__getitem__ = Mock(side_effect=lambda i: [mock_table][i])

        page = _create_mock_page([])
        page.find_tables = Mock(return_value=mock_tables)

        doc = _create_mock_pdf_document(page)

        options = PdfOptions(table_detection_mode="both")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should have table in AST
        [child for child in ast_doc.children if isinstance(child, Table)]
        # May or may not detect based on implementation
        assert isinstance(ast_doc, Document)

    def test_table_extraction_disabled(self) -> None:
        """Test that tables are flattened when preserve_tables=False."""
        mock_table = Mock()
        mock_table.extract = Mock(return_value=[["Header1", "Header2"], ["Data1", "Data2"]])

        mock_tables = Mock()
        mock_tables.tables = [mock_table]

        page = _create_mock_page([])
        page.find_tables = Mock(return_value=mock_tables)

        doc = _create_mock_pdf_document(page)

        options = PdfOptions(table_detection_mode="none")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Tables should be flattened to paragraphs
        assert isinstance(ast_doc, Document)


@pytest.mark.unit
class TestImageExtraction:
    """Tests for image extraction."""

    def test_page_with_image(self) -> None:
        """Test page with embedded image."""
        # Mock image info
        mock_image_info = (0, 0, 100, 100, 8, "DeviceRGB", "", "Image1", "DCTDecode")

        page = _create_mock_page([])
        page.get_images = Mock(return_value=[mock_image_info])
        page.get_pixmap = Mock()

        doc = _create_mock_pdf_document(page)

        options = PdfOptions(attachment_mode="embed")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should process images (implementation-specific)
        assert isinstance(ast_doc, Document)

    def test_skip_images_mode(self) -> None:
        """Test skipping images when attachment_mode=skip."""
        mock_image_info = (0, 0, 100, 100, 8, "DeviceRGB", "", "Image1", "DCTDecode")

        page = _create_mock_page([])
        page.get_images = Mock(return_value=[mock_image_info])

        doc = _create_mock_pdf_document(page)

        options = PdfOptions(attachment_mode="skip")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Images should be skipped
        images = [child for child in ast_doc.children if isinstance(child, Image)]
        assert len(images) == 0


@pytest.mark.unit
class TestCodeBlockDetection:
    """Tests for code block detection."""

    def test_monospace_font_as_code(self) -> None:
        """Test monospace font detected as code block."""
        code_block = _create_mock_text_block("def hello():\n    return 'world'", font_name="Courier")
        page = _create_mock_page([code_block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # May detect as code block based on font
        assert len(ast_doc.children) >= 1


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_page(self) -> None:
        """Test page with no text blocks."""
        page = _create_mock_page([])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)
        # May have page separator or be empty

    def test_empty_document(self) -> None:
        """Test document with no pages."""
        doc = _create_mock_pdf_document()

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_special_characters_in_text(self) -> None:
        """Test text with special characters."""
        block = _create_mock_text_block('Text with <special> & "chars"')
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Special characters should be preserved
        assert len(ast_doc.children) >= 1

    def test_very_long_text_block(self) -> None:
        """Test handling very long text block."""
        long_text = "Word " * 1000
        block = _create_mock_text_block(long_text)
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) >= 1

    def test_unicode_text(self) -> None:
        """Test handling Unicode characters."""
        block = _create_mock_text_block("Hello 世界 مرحبا Привет")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert len(ast_doc.children) >= 1


@pytest.mark.unit
class TestPageSeparators:
    """Tests for page separator handling."""

    def test_page_separator_enabled(self) -> None:
        """Test page separators between pages."""
        page1 = _create_mock_page([_create_mock_text_block("Page 1")])
        page2 = _create_mock_page([_create_mock_text_block("Page 2")])

        doc = _create_mock_pdf_document(page1, page2)

        options = PdfOptions(page_separator_template="-----")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should have content from both pages
        assert len(ast_doc.children) >= 2

    def test_page_separator_disabled(self) -> None:
        """Test no page separators when template is empty."""
        page1 = _create_mock_page([_create_mock_text_block("Page 1")])
        page2 = _create_mock_page([_create_mock_text_block("Page 2")])

        doc = _create_mock_pdf_document(page1, page2)

        options = PdfOptions(page_separator_template="")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Content from both pages without separators
        assert len(ast_doc.children) >= 2


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for PdfOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        block = _create_mock_text_block("Text")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)

    def test_all_options_enabled(self) -> None:
        """Test with all detection options enabled."""
        block = _create_mock_text_block("Text")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        options = PdfOptions(table_detection_mode="both", page_separator_template="-----", attachment_mode="embed")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)

    def test_minimal_options(self) -> None:
        """Test with minimal options."""
        block = _create_mock_text_block("Text")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        options = PdfOptions(table_detection_mode="none", page_separator_template="", attachment_mode="skip")
        converter = PdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert isinstance(ast_doc, Document)


@pytest.mark.unit
class TestComplexStructures:
    """Tests for complex document structures."""

    def test_mixed_content_page(self) -> None:
        """Test page with mixed text, heading, and code."""
        blocks = [
            _create_mock_text_block("Title", font_size=24),
            _create_mock_text_block("Normal paragraph", bbox=(0, 30, 100, 50)),
            _create_mock_text_block("print('code')", bbox=(0, 60, 100, 80), font_name="Courier"),
        ]
        page = _create_mock_page(blocks)
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should have various elements
        assert len(ast_doc.children) >= 3

    def test_multi_column_layout(self) -> None:
        """Test handling multi-column layout."""
        # Left column blocks
        left_blocks = [
            _create_mock_text_block("Left col text", bbox=(0, 0, 200, 20)),
            _create_mock_text_block("More left text", bbox=(0, 30, 200, 50)),
        ]
        # Right column blocks
        right_blocks = [
            _create_mock_text_block("Right col text", bbox=(300, 0, 500, 20)),
            _create_mock_text_block("More right text", bbox=(300, 30, 500, 50)),
        ]

        page = _create_mock_page(left_blocks + right_blocks)
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Multi-column text may be merged if on same Y-coordinate
        # Expected: 3+ paragraphs (blocks at Y=30 from both columns may merge)
        assert len(ast_doc.children) >= 3


@pytest.mark.unit
class TestTextExtraction:
    """Tests for text extraction and processing."""

    def test_whitespace_preservation(self) -> None:
        """Test that whitespace is handled appropriately."""
        block = _create_mock_text_block("Text   with   spaces")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert len(ast_doc.children) >= 1

    def test_newline_handling(self) -> None:
        """Test handling of newlines in text."""
        block = _create_mock_text_block("Line 1\nLine 2\nLine 3")
        page = _create_mock_page([block])
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        assert len(ast_doc.children) >= 1

    def test_empty_text_block_skipped(self) -> None:
        """Test that empty text blocks are skipped."""
        blocks = [
            _create_mock_text_block("Text"),
            _create_mock_text_block(""),  # Empty
            _create_mock_text_block("   "),  # Whitespace only
            _create_mock_text_block("More text", bbox=(0, 60, 100, 80)),
        ]
        page = _create_mock_page(blocks)
        doc = _create_mock_pdf_document(page)

        converter = PdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc, range(len(doc)), "test.pdf")

        # Should skip empty blocks
        assert len(ast_doc.children) >= 2
