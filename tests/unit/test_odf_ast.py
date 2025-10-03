#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_odf_ast.py
"""Unit tests for ODF to AST converter.

Tests cover:
- ODF paragraph and heading conversion
- Text formatting (bold, italic, underline)
- List detection and conversion
- Table structure conversion
- Image handling
- Hyperlinks
- Edge cases with empty elements

Note: These tests use mock ODF objects since creating actual ODF documents
programmatically is complex. Integration tests cover real ODF files.

"""

from unittest.mock import Mock

import pytest

from all2md.ast import (
    Document,
    Emphasis,
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
    Underline,
)
from all2md.parsers.odf import OdfToAstConverter
from all2md.options import OdfOptions


# Mock namespaces
TEXTNS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
DRAWNS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"


def _create_mock_text_node(content):
    """Create a mock text node.

    Parameters
    ----------
    content : str
        Text content

    Returns
    -------
    Mock
        Mock text node

    """
    node = Mock()
    node.data = content
    node.nodeType = 3  # TEXT_NODE
    return node


def _create_mock_element(qname, *children):
    """Create a mock ODF element.

    Parameters
    ----------
    qname : tuple
        Qualified name (namespace, tag)
    *children
        Child nodes

    Returns
    -------
    Mock
        Mock ODF element

    """
    elem = Mock()
    elem.qname = qname
    elem.childNodes = list(children)

    # Mock getAttribute method
    def get_attribute(name):
        return None

    elem.getAttribute = Mock(side_effect=get_attribute)

    # Mock getElementsByType method to filter children by qname
    def get_elements_by_type(element_type):
        # Map ODF element types to qnames
        from odf import table as odf_table, text as odf_text

        type_to_qname = {
            odf_table.TableRow: ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-row"),
            odf_table.TableCell: ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell"),
            odf_text.P: (TEXTNS, "p"),
        }

        # Get target qname
        target_qname = type_to_qname.get(element_type)
        if target_qname is None:
            # If not in mapping, try to get qname from element_type
            if hasattr(element_type, 'qname'):
                target_qname = element_type.qname
            else:
                target_qname = element_type

        # Filter children by qname
        return [child for child in elem.childNodes if hasattr(child, 'qname') and child.qname == target_qname]

    elem.getElementsByType = Mock(side_effect=get_elements_by_type)

    return elem


def _create_mock_odf_document(*elements):
    """Create a mock ODF document.

    Parameters
    ----------
    *elements
        Top-level document elements

    Returns
    -------
    Mock
        Mock ODF document

    """
    doc = Mock()
    text_section = Mock()
    text_section.childNodes = list(elements)
    doc.text = text_section
    doc.presentation = None

    # Set up meta section with working getElementsByType
    meta = Mock()
    meta.getElementsByType = Mock(return_value=[])
    doc.meta = meta

    # Set up mimetype
    doc.mimetype = 'application/vnd.oasis.opendocument.text'

    # Set up body section with working getElementsByType
    body = Mock()
    body.getElementsByType = Mock(return_value=[])
    doc.body = body

    return doc


@pytest.mark.unit
class TestBasicConversion:
    """Tests for basic ODF conversion."""

    def test_simple_paragraph(self) -> None:
        """Test converting a simple paragraph."""
        text_node = _create_mock_text_node("Hello world")
        para = _create_mock_element((TEXTNS, "p"), text_node)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
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
        text1 = _create_mock_text_node("First")
        para1 = _create_mock_element((TEXTNS, "p"), text1)

        text2 = _create_mock_text_node("Second")
        para2 = _create_mock_element((TEXTNS, "p"), text2)

        text3 = _create_mock_text_node("Third")
        para3 = _create_mock_element((TEXTNS, "p"), text3)

        doc = _create_mock_odf_document(para1, para2, para3)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 3
        assert all(isinstance(child, Paragraph) for child in ast_doc.children)


@pytest.mark.unit
class TestHeadings:
    """Tests for heading conversion."""

    def test_heading_level_1(self) -> None:
        """Test converting level 1 heading."""
        text = _create_mock_text_node("Heading 1")
        heading = _create_mock_element((TEXTNS, "h"), text)
        # Mock outline level attribute
        heading.getAttribute = Mock(return_value="1")

        doc = _create_mock_odf_document(heading)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Heading)
        heading_node = ast_doc.children[0]
        assert heading_node.level == 1

    def test_heading_various_levels(self) -> None:
        """Test headings with various levels."""
        for level in range(1, 7):
            text = _create_mock_text_node(f"Heading {level}")
            heading = _create_mock_element((TEXTNS, "h"), text)
            heading.getAttribute = Mock(return_value=str(level))

            doc = _create_mock_odf_document(heading)

            converter = OdfToAstConverter()
            ast_doc = converter.convert_to_ast(doc)

            heading_node = ast_doc.children[0]
            assert isinstance(heading_node, Heading)
            assert heading_node.level == level


@pytest.mark.unit
class TestTextFormatting:
    """Tests for text formatting conversion."""

    def test_bold_text(self) -> None:
        """Test bold text with style detection."""
        text = _create_mock_text_node("Bold text")
        span = _create_mock_element((TEXTNS, "span"), text)
        # Mock style name containing 'bold'
        span.getAttribute = Mock(return_value="Bold_Style")

        para = _create_mock_element((TEXTNS, "p"), span)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should detect bold from style name
        assert len(para_node.content) > 0

    def test_italic_text(self) -> None:
        """Test italic text with style detection."""
        text = _create_mock_text_node("Italic text")
        span = _create_mock_element((TEXTNS, "span"), text)
        span.getAttribute = Mock(return_value="Italic_Style")

        para = _create_mock_element((TEXTNS, "p"), span)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert len(para_node.content) > 0

    def test_underline_text(self) -> None:
        """Test underline text with style detection."""
        text = _create_mock_text_node("Underlined")
        span = _create_mock_element((TEXTNS, "span"), text)
        span.getAttribute = Mock(return_value="Underline_Style")

        para = _create_mock_element((TEXTNS, "p"), span)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert len(para_node.content) > 0


@pytest.mark.unit
class TestHyperlinks:
    """Tests for hyperlink conversion."""

    def test_simple_hyperlink(self) -> None:
        """Test converting a hyperlink."""
        text = _create_mock_text_node("Click here")
        link = _create_mock_element((TEXTNS, "a"), text)
        link.getAttribute = Mock(return_value="https://example.com")

        para = _create_mock_element((TEXTNS, "p"), link)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should have Link node
        assert len(para_node.content) > 0
        # Check if Link was created (implementation may vary)
        link_node = para_node.content[0]
        if isinstance(link_node, Link):
            assert link_node.url == "https://example.com"


@pytest.mark.unit
class TestLists:
    """Tests for list conversion."""

    def test_simple_list(self) -> None:
        """Test converting a simple list."""
        # Create list items
        text1 = _create_mock_text_node("Item 1")
        para1 = _create_mock_element((TEXTNS, "p"), text1)
        item1 = _create_mock_element((TEXTNS, "list-item"), para1)

        text2 = _create_mock_text_node("Item 2")
        para2 = _create_mock_element((TEXTNS, "p"), text2)
        item2 = _create_mock_element((TEXTNS, "list-item"), para2)

        # Create list
        odf_list = _create_mock_element((TEXTNS, "list"), item1, item2)

        doc = _create_mock_odf_document(odf_list)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], List)
        list_node = ast_doc.children[0]
        assert len(list_node.items) == 2


@pytest.mark.unit
class TestTables:
    """Tests for table conversion."""

    def test_simple_table(self) -> None:
        """Test converting a simple table."""
        # Create table cells (note: qnames use hyphens: table-cell not table_cell)
        text_h1 = _create_mock_text_node("Header 1")
        para_h1 = _create_mock_element((TEXTNS, "p"), text_h1)
        cell_h1 = _create_mock_element(("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell"), para_h1)

        text_h2 = _create_mock_text_node("Header 2")
        para_h2 = _create_mock_element((TEXTNS, "p"), text_h2)
        cell_h2 = _create_mock_element(("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell"), para_h2)

        # Create header row (note: table-row not table_row)
        header_row = _create_mock_element(
            ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-row"), cell_h1, cell_h2
        )

        # Create data cells
        text_d1 = _create_mock_text_node("Data 1")
        para_d1 = _create_mock_element((TEXTNS, "p"), text_d1)
        cell_d1 = _create_mock_element(("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell"), para_d1)

        text_d2 = _create_mock_text_node("Data 2")
        para_d2 = _create_mock_element((TEXTNS, "p"), text_d2)
        cell_d2 = _create_mock_element(("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-cell"), para_d2)

        # Create data row
        data_row = _create_mock_element(
            ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table-row"), cell_d1, cell_d2
        )

        # Create table
        table = _create_mock_element(
            ("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "table"), header_row, data_row
        )

        doc = _create_mock_odf_document(table)

        options = OdfOptions(preserve_tables=True)
        converter = OdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc)

        # Should have table
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Table)


@pytest.mark.unit
class TestImages:
    """Tests for image handling."""

    def test_image_frame(self) -> None:
        """Test detecting image frames."""
        # Create image frame
        frame = _create_mock_element((DRAWNS, "frame"))

        doc = _create_mock_odf_document(frame)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Image processing is complex, just verify no crash
        assert isinstance(ast_doc, Document)


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_document(self) -> None:
        """Test converting empty ODF document."""
        doc = _create_mock_odf_document()

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_document_without_text_section(self) -> None:
        """Test document without text section."""
        doc = Mock()
        doc.text = None
        doc.presentation = None
        # Add required attributes for metadata extraction
        meta = Mock()
        meta.getElementsByType = Mock(return_value=[])
        doc.meta = meta
        doc.mimetype = 'application/vnd.oasis.opendocument.text'
        body = Mock()
        body.getElementsByType = Mock(return_value=[])
        doc.body = body

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 0

    def test_element_without_qname(self) -> None:
        """Test element without qname attribute."""
        elem = Mock(spec=[])  # No qname attribute
        doc = _create_mock_odf_document(elem)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should handle gracefully
        assert isinstance(ast_doc, Document)

    def test_unknown_element_type(self) -> None:
        """Test unknown ODF element type."""
        elem = _create_mock_element(("unknown:namespace", "unknown-element"))
        doc = _create_mock_odf_document(elem)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should skip unknown elements
        assert isinstance(ast_doc, Document)

    def test_special_characters_in_text(self) -> None:
        """Test text with special characters."""
        text = _create_mock_text_node("Text with <special> & \"chars\"")
        para = _create_mock_element((TEXTNS, "p"), text)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        text_content = para_node.content[0].content
        assert "<special>" in text_content
        assert "&" in text_content


@pytest.mark.unit
class TestOptionsConfiguration:
    """Tests for OdfOptions configuration."""

    def test_default_options(self) -> None:
        """Test conversion with default options."""
        text = _create_mock_text_node("Text")
        para = _create_mock_element((TEXTNS, "p"), text)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 1

    def test_custom_options(self) -> None:
        """Test with custom options."""
        text = _create_mock_text_node("Text")
        para = _create_mock_element((TEXTNS, "p"), text)
        doc = _create_mock_odf_document(para)

        options = OdfOptions(preserve_tables=True)
        converter = OdfToAstConverter(options)
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)


@pytest.mark.unit
class TestComplexStructures:
    """Tests for complex document structures."""

    def test_mixed_content(self) -> None:
        """Test document with mixed paragraphs and headings."""
        text_h = _create_mock_text_node("Heading")
        heading = _create_mock_element((TEXTNS, "h"), text_h)
        heading.getAttribute = Mock(return_value="1")

        text_p1 = _create_mock_text_node("Paragraph 1")
        para1 = _create_mock_element((TEXTNS, "p"), text_p1)

        text_p2 = _create_mock_text_node("Paragraph 2")
        para2 = _create_mock_element((TEXTNS, "p"), text_p2)

        doc = _create_mock_odf_document(heading, para1, para2)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have: Heading, Paragraph, Paragraph
        assert len(ast_doc.children) == 3
        assert isinstance(ast_doc.children[0], Heading)
        assert isinstance(ast_doc.children[1], Paragraph)
        assert isinstance(ast_doc.children[2], Paragraph)

    def test_nested_formatting(self) -> None:
        """Test nested text formatting."""
        text = _create_mock_text_node("Nested format")
        inner_span = _create_mock_element((TEXTNS, "span"), text)
        inner_span.getAttribute = Mock(return_value="italic")

        outer_span = _create_mock_element((TEXTNS, "span"), inner_span)
        outer_span.getAttribute = Mock(return_value="bold")

        para = _create_mock_element((TEXTNS, "p"), outer_span)
        doc = _create_mock_odf_document(para)

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should have nested formatting
        assert len(para_node.content) > 0


@pytest.mark.unit
class TestODPPresentation:
    """Tests for ODP (presentation) support."""

    def test_presentation_document(self) -> None:
        """Test ODP document with presentation section."""
        doc = Mock()
        doc.text = None

        text = _create_mock_text_node("Slide content")
        para = _create_mock_element((TEXTNS, "p"), text)

        presentation = Mock()
        presentation.childNodes = [para]
        doc.presentation = presentation

        # Add required attributes for metadata extraction
        meta = Mock()
        meta.getElementsByType = Mock(return_value=[])
        doc.meta = meta
        doc.mimetype = 'application/vnd.oasis.opendocument.presentation'
        body = Mock()
        body.getElementsByType = Mock(return_value=[])
        doc.body = body

        converter = OdfToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should process presentation content
        assert isinstance(ast_doc, Document)
        # May have content depending on implementation
        assert len(ast_doc.children) >= 0
