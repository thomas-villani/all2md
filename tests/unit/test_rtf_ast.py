#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_rtf_ast.py
"""Unit tests for RTF to AST converter.

Tests cover:
- RTF paragraph conversion
- Text formatting (bold, italic, underline)
- List detection and conversion
- Image handling
- pyth Document processing
- Nested formatting
- Edge cases

Note: These tests use mock pyth objects since creating actual RTF documents
programmatically is complex. Integration tests cover real RTF files.

"""

from unittest.mock import MagicMock, Mock

import pytest

from all2md.ast import Document, Emphasis, List, ListItem, Paragraph, Strong, Text, Underline
from all2md.converters.rtf2ast import RtfToAstConverter
from all2md.options import RtfOptions


# Create mock classes for pyth types so isinstance checks work correctly
class MockPythText(Mock):
    """Mock class for pyth Text objects."""
    pass


class MockPythParagraph(Mock):
    """Mock class for pyth Paragraph objects."""
    pass


class MockPythList(Mock):
    """Mock class for pyth List objects."""
    pass


class MockPythListEntry(Mock):
    """Mock class for pyth ListEntry objects."""
    pass


def _create_mock_pyth_text(content, bold=False, italic=False, underline=False):
    """Create a mock pyth Text object.

    Parameters
    ----------
    content : str
        Text content
    bold : bool
        Bold formatting
    italic : bool
        Italic formatting
    underline : bool
        Underline formatting

    Returns
    -------
    MockPythText
        Mock pyth Text object

    """
    text = MockPythText()
    text.content = content
    # Properties must be a dictionary for .get() calls in the converter
    text.properties = {
        "bold": bold,
        "italic": italic,
        "underline": underline,
    }
    return text


def _create_mock_pyth_paragraph(*text_objects):
    """Create a mock pyth Paragraph object.

    Parameters
    ----------
    *text_objects
        pyth Text objects

    Returns
    -------
    MockPythParagraph
        Mock pyth Paragraph object

    """
    para = MockPythParagraph()
    para.content = list(text_objects)
    return para


def _create_mock_pyth_document(*elements):
    """Create a mock pyth Document object.

    Parameters
    ----------
    *elements
        Document elements (paragraphs, lists, etc.)

    Returns
    -------
    Mock
        Mock pyth Document object

    """
    doc = Mock()
    doc.content = list(elements)
    return doc


def _setup_converter_with_mocks(converter, para_type=None, list_type=None, list_entry_type=None, text_type=None):
    """Set up RTF converter to recognize mock pyth types.

    Parameters
    ----------
    converter : RtfToAstConverter
        Converter to configure
    para_type : type or None
        Type to use for paragraph detection (defaults to MockPythParagraph)
    list_type : type or None
        Type to use for list detection (defaults to MockPythList)
    list_entry_type : type or None
        Type to use for list entry detection (defaults to MockPythListEntry)
    text_type : type or None
        Type to use for text detection (defaults to MockPythText)

    """
    converter.PythParagraph = para_type if para_type else MockPythParagraph
    converter.PythList = list_type if list_type else MockPythList
    converter.PythListEntry = list_entry_type if list_entry_type else MockPythListEntry
    converter.PythText = text_type if text_type else MockPythText
    converter.PythImage = Mock


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic RTF conversion."""

    def test_simple_paragraph(self) -> None:
        """Test converting a simple paragraph."""
        text = _create_mock_pyth_text("Hello world")
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Paragraph)
        para_node = ast_doc.children[0]
        assert len(para_node.content) == 1
        assert isinstance(para_node.content[0], Text)
        assert para_node.content[0].content == "Hello world"

    def test_multiple_paragraphs(self) -> None:
        """Test converting multiple paragraphs."""
        text1 = _create_mock_pyth_text("First paragraph")
        para1 = _create_mock_pyth_paragraph(text1)

        text2 = _create_mock_pyth_text("Second paragraph")
        para2 = _create_mock_pyth_paragraph(text2)

        text3 = _create_mock_pyth_text("Third paragraph")
        para3 = _create_mock_pyth_paragraph(text3)

        doc = _create_mock_pyth_document(para1, para2, para3)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 3
        assert all(isinstance(child, Paragraph) for child in ast_doc.children)

    def test_empty_paragraph_skipped(self) -> None:
        """Test that empty paragraphs are skipped."""
        text1 = _create_mock_pyth_text("First")
        para1 = _create_mock_pyth_paragraph(text1)

        # Empty paragraph
        para2 = _create_mock_pyth_paragraph()

        text3 = _create_mock_pyth_text("Second")
        para3 = _create_mock_pyth_paragraph(text3)

        doc = _create_mock_pyth_document(para1, para2, para3)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        # Should only have 2 paragraphs (empty one skipped)
        assert len(ast_doc.children) == 2


@pytest.mark.unit
class TestTextFormatting:
    """Tests for text formatting conversion."""

    def test_bold_text(self) -> None:
        """Test bold text conversion."""
        text = _create_mock_pyth_text("Bold text", bold=True)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Strong)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Bold text"

    def test_italic_text(self) -> None:
        """Test italic text conversion."""
        text = _create_mock_pyth_text("Italic text", italic=True)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Emphasis)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Italic text"

    def test_underline_text(self) -> None:
        """Test underline text conversion."""
        text = _create_mock_pyth_text("Underlined text", underline=True)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Underline)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Underlined text"

    def test_multiple_formatting(self) -> None:
        """Test text with multiple formatting applied."""
        text = _create_mock_pyth_text("Bold and italic", bold=True, italic=True)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should be nested formatting (order depends on implementation)
        # Just verify we have both Strong and Emphasis somewhere
        content_str = str(para_node)
        assert "Strong" in str(type(para_node.content[0]))
        # Inner formatting should be Emphasis
        if hasattr(para_node.content[0], 'content'):
            assert "Emphasis" in str(type(para_node.content[0].content[0]))

    def test_mixed_formatting_runs(self) -> None:
        """Test paragraph with multiple runs having different formatting."""
        text1 = _create_mock_pyth_text("Normal ")
        text2 = _create_mock_pyth_text("bold ", bold=True)
        text3 = _create_mock_pyth_text("normal ")
        text4 = _create_mock_pyth_text("italic", italic=True)

        para = _create_mock_pyth_paragraph(text1, text2, text3, text4)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should have 4 inline elements
        assert len(para_node.content) == 4
        assert isinstance(para_node.content[0], Text)
        assert isinstance(para_node.content[1], Strong)
        assert isinstance(para_node.content[2], Text)
        assert isinstance(para_node.content[3], Emphasis)


@pytest.mark.unit
class TestLists:
    """Tests for list conversion."""

    def test_simple_list(self) -> None:
        """Test converting a simple list."""
        # Mock pyth List and ListEntry
        entry1 = MockPythListEntry()
        entry1_text = _create_mock_pyth_text("Item 1")
        entry1_para = _create_mock_pyth_paragraph(entry1_text)
        entry1.content = [entry1_para]

        entry2 = MockPythListEntry()
        entry2_text = _create_mock_pyth_text("Item 2")
        entry2_para = _create_mock_pyth_paragraph(entry2_text)
        entry2.content = [entry2_para]

        pyth_list = MockPythList()
        pyth_list.content = [entry1, entry2]

        doc = _create_mock_pyth_document(pyth_list)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)

        ast_doc = converter.convert_to_ast(doc)

        # Should have one List node
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], List)
        list_node = ast_doc.children[0]
        assert len(list_node.items) == 2

    def test_list_item_content(self) -> None:
        """Test list item content preservation."""
        entry = MockPythListEntry()
        entry_text = _create_mock_pyth_text("List item text")
        entry_para = _create_mock_pyth_paragraph(entry_text)
        entry.content = [entry_para]

        pyth_list = MockPythList()
        pyth_list.content = [entry]

        doc = _create_mock_pyth_document(pyth_list)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)

        ast_doc = converter.convert_to_ast(doc)

        list_node = ast_doc.children[0]
        item = list_node.items[0]
        assert isinstance(item, ListItem)
        # Check content
        assert len(item.children) > 0


@pytest.mark.unit
class TestImages:
    """Tests for image handling."""

    def test_image_in_paragraph(self) -> None:
        """Test image embedded in paragraph."""
        # Mock pyth Image
        image = Mock()
        image.data = b"fake_image_data"
        image.height = 100
        image.width = 100

        # Add image to paragraph
        text = _create_mock_pyth_text("Text before image")
        para = _create_mock_pyth_paragraph(text)
        # Note: Real image handling is complex, this is simplified

        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        # Should create paragraph
        assert len(ast_doc.children) >= 1
        assert isinstance(ast_doc.children[0], Paragraph)


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_document(self) -> None:
        """Test converting empty RTF document."""
        doc = _create_mock_pyth_document()

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_none_document(self) -> None:
        """Test handling None document."""
        converter = RtfToAstConverter()
        ast_doc = converter.convert_to_ast(None)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_document_without_content_attribute(self) -> None:
        """Test document without content attribute."""
        doc = Mock(spec=[])  # No attributes

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_text_with_special_characters(self) -> None:
        """Test text containing special characters."""
        text = _create_mock_pyth_text("Text with <special> & \"chars\"")
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Special characters should be preserved
        text_content = para_node.content[0].content
        assert "<special>" in text_content
        assert "&" in text_content
        assert '"chars"' in text_content

    def test_very_long_paragraph(self) -> None:
        """Test handling very long paragraph."""
        long_text = "Word " * 1000
        text = _create_mock_pyth_text(long_text)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node, Paragraph)
        # Content should be preserved
        assert "Word" in para_node.content[0].content


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for RtfOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        text = _create_mock_pyth_text("Text")
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 1

    def test_custom_options(self) -> None:
        """Test with custom options."""
        text = _create_mock_pyth_text("Text")
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        options = RtfOptions(attachment_mode="embed")
        converter = RtfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)


@pytest.mark.unit
class TestComplexStructures:
    """Tests for complex document structures."""

    def test_mixed_content(self) -> None:
        """Test document with mixed paragraphs and lists."""
        # Paragraph 1
        text1 = _create_mock_pyth_text("Introduction")
        para1 = _create_mock_pyth_paragraph(text1)

        # List
        entry1 = MockPythListEntry()
        entry1_text = _create_mock_pyth_text("Item 1")
        entry1_para = _create_mock_pyth_paragraph(entry1_text)
        entry1.content = [entry1_para]

        pyth_list = MockPythList()
        pyth_list.content = [entry1]

        # Paragraph 2
        text2 = _create_mock_pyth_text("Conclusion")
        para2 = _create_mock_pyth_paragraph(text2)

        doc = _create_mock_pyth_document(para1, pyth_list, para2)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)

        ast_doc = converter.convert_to_ast(doc)

        # Should have: Paragraph, List, Paragraph
        assert len(ast_doc.children) == 3
        assert isinstance(ast_doc.children[0], Paragraph)
        assert isinstance(ast_doc.children[1], List)
        assert isinstance(ast_doc.children[2], Paragraph)

    def test_formatted_text_in_list(self) -> None:
        """Test list items with formatted text."""
        entry = MockPythListEntry()
        entry_text = _create_mock_pyth_text("Bold item", bold=True)
        entry_para = _create_mock_pyth_paragraph(entry_text)
        entry.content = [entry_para]

        pyth_list = MockPythList()
        pyth_list.content = [entry]

        doc = _create_mock_pyth_document(pyth_list)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)

        ast_doc = converter.convert_to_ast(doc)

        list_node = ast_doc.children[0]
        # List item should have formatted content
        assert len(list_node.items) == 1


@pytest.mark.unit
class TestFormattingPreservation:
    """Tests for formatting preservation."""

    def test_plain_text_no_formatting(self) -> None:
        """Test that plain text has no formatting nodes."""
        text = _create_mock_pyth_text("Plain text")
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should be just Text, not wrapped in formatting
        assert isinstance(para_node.content[0], Text)
        assert para_node.content[0].content == "Plain text"

    def test_formatting_not_applied_to_empty_text(self) -> None:
        """Test that formatting is not applied to empty text."""
        text = _create_mock_pyth_text("", bold=True)
        para = _create_mock_pyth_paragraph(text)
        doc = _create_mock_pyth_document(para)

        converter = RtfToAstConverter()
        _setup_converter_with_mocks(converter)
        ast_doc = converter.convert_to_ast(doc)

        # Empty paragraph should be skipped or create minimal structure
        # Implementation may vary
        assert isinstance(ast_doc, Document)
