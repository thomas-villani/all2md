"""Unit tests for ODF to Markdown conversion.

This module tests the ODF converter's internal methods using mock objects
and controlled inputs to verify correct behavior in isolation.
"""

from unittest.mock import Mock, patch

import pytest

from all2md.converters.odf2markdown import OdfConverter, extract_odf_metadata, odf_to_markdown
from all2md.exceptions import MarkdownConversionError
from all2md.options import MarkdownOptions, OdfOptions
from all2md.utils.metadata import DocumentMetadata


# Mock ODF element classes
class MockElement:
    """Mock ODF element with configurable properties."""

    def __init__(self, qname=None, attributes=None, child_nodes=None, text_data=None):
        self.qname = qname
        self.attributes = attributes or {}
        self.childNodes = child_nodes or []
        self.nodeType = 1  # Element node type
        self.TEXT_NODE = 3
        self.data = text_data

    def getAttribute(self, name):
        return self.attributes.get(name)


class MockTextNode:
    """Mock text node."""

    def __init__(self, text_data):
        self.data = text_data
        self.nodeType = 3  # Text node type
        self.TEXT_NODE = 3


class MockDocument:
    """Mock OpenDocument."""

    def __init__(self):
        self.styles = Mock()
        self.automaticstyles = Mock()
        self.text = Mock()
        self.presentation = Mock()

    def getPart(self, href):
        return b"mock_image_data"


class MockStyle:
    """Mock ODF style."""

    def __init__(self, name=None, properties=None):
        self.name = name
        self.childNodes = []
        self.attributes = {"name": name} if name else {}

        if properties:
            text_props = Mock()
            text_props.getAttribute = Mock(side_effect=lambda attr: properties.get(attr))
            self.childNodes.append(text_props)

    def getAttribute(self, name):
        return self.attributes.get(name)


class MockTextProperties:
    """Mock text properties for style formatting."""

    def __init__(self, fontweight=None, fontstyle=None):
        self.fontweight = fontweight
        self.fontstyle = fontstyle

    def getAttribute(self, attr):
        if attr == "fontweight":
            return self.fontweight
        elif attr == "fontstyle":
            return self.fontstyle
        return None


@pytest.mark.unit
@pytest.mark.odf
class TestOdfConverter:
    """Test OdfConverter class methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_doc = MockDocument()
        self.options = OdfOptions()
        self.converter = OdfConverter(self.mock_doc, self.options)

    def test_init(self):
        """Test OdfConverter initialization."""
        assert self.converter.doc == self.mock_doc
        assert self.converter.options == self.options
        assert isinstance(self.converter.md_options, MarkdownOptions)
        assert self.converter.style_cache == {}
        assert self.converter.list_level == 0

    def test_get_style_properties_cached(self):
        """Test style properties caching."""
        # Pre-populate cache
        self.converter.style_cache["TestStyle"] = {"bold": True, "italic": False}

        result = self.converter._get_style_properties("TestStyle")

        assert result == {"bold": True, "italic": False}
        # Should not call doc.styles since it's cached

    def test_get_style_properties_bold_italic(self):
        """Test extracting bold and italic properties from style."""
        from odf.style import STYLENS

        mock_style = Mock()

        # Create mock text properties element with correct qname
        text_props = Mock()
        text_props.qname = (STYLENS, 'text-properties')
        text_props.getAttribute = Mock(side_effect=lambda attr: {
            "fontweight": "bold",
            "fontstyle": "italic"
        }.get(attr))
        mock_style.childNodes = [text_props]

        self.mock_doc.styles.getStyleByName.return_value = mock_style

        result = self.converter._get_style_properties("BoldItalicStyle")

        assert result == {"bold": True, "italic": True}
        assert self.converter.style_cache["BoldItalicStyle"] == {"bold": True, "italic": True}

    def test_get_style_properties_no_style(self):
        """Test default properties when style not found."""
        self.mock_doc.styles.getStyleByName.return_value = None

        result = self.converter._get_style_properties("NonexistentStyle")

        assert result == {"bold": False, "italic": False}

    def test_get_style_properties_error_handling(self):
        """Test error handling in style parsing."""
        self.mock_doc.styles.getStyleByName.side_effect = Exception("Style error")

        result = self.converter._get_style_properties("ErrorStyle")

        assert result == {"bold": False, "italic": False}

    def test_process_text_runs_simple_text(self):
        """Test processing simple text content."""
        text_node = MockTextNode("Hello World")
        element = MockElement(child_nodes=[text_node])

        result = self.converter._process_text_runs(element)

        assert result == "Hello World"

    def test_process_text_runs_formatted_span(self):
        """Test processing formatted text spans."""
        from odf.text import TEXTNS

        # Mock bold span
        text_node = MockTextNode("Bold Text")
        span = MockElement(
            qname=(TEXTNS, 'span'),
            attributes={"stylename": "BoldStyle"},
            child_nodes=[text_node]
        )
        element = MockElement(child_nodes=[span])

        # Mock style properties
        self.converter.style_cache["BoldStyle"] = {"bold": True, "italic": False}

        result = self.converter._process_text_runs(element)

        assert result == "**Bold Text**"

    def test_process_text_runs_hyperlink(self):
        """Test processing hyperlinks."""
        from odf.text import TEXTNS

        text_node = MockTextNode("Link Text")
        link = MockElement(
            qname=(TEXTNS, 'a'),
            attributes={"href": "https://example.com"},
            child_nodes=[text_node]
        )
        element = MockElement(child_nodes=[link])

        result = self.converter._process_text_runs(element)

        assert result == "[Link Text](https://example.com)"

    def test_process_text_runs_spaces(self):
        """Test processing space elements."""
        from odf.text import TEXTNS

        text1 = MockTextNode("Word")
        space = MockElement(qname=(TEXTNS, 's'))
        text2 = MockTextNode("Word")
        element = MockElement(child_nodes=[text1, space, text2])

        result = self.converter._process_text_runs(element)

        assert result == "Word Word"

    def test_process_paragraph_simple(self):
        """Test processing simple paragraph."""
        from odf.text import TEXTNS

        text_node = MockTextNode("Paragraph content")
        para = MockElement(
            qname=(TEXTNS, 'p'),
            child_nodes=[text_node]
        )

        result = self.converter._process_paragraph(para)

        assert result == "Paragraph content"

    def test_process_paragraph_heading(self):
        """Test processing heading element."""
        from odf.text import TEXTNS

        text_node = MockTextNode("Heading Text")
        heading = MockElement(
            qname=(TEXTNS, 'h'),
            attributes={"outlinelevel": "2"},
            child_nodes=[text_node]
        )

        result = self.converter._process_paragraph(heading)

        assert result == "## Heading Text"

    def test_process_paragraph_empty(self):
        """Test processing empty paragraph."""
        from odf.text import TEXTNS

        para = MockElement(qname=(TEXTNS, 'p'), child_nodes=[])

        result = self.converter._process_paragraph(para)

        assert result == ""

    def test_is_ordered_list_numbered(self):
        """Test detection of ordered list."""
        from odf.text import TEXTNS

        # Mock list element
        lst = MockElement(attributes={"stylename": "NumberedListStyle"})

        # Mock list style with numbered level
        level_style = MockElement(qname=(TEXTNS, 'list-level-style-number'))
        list_style = MockElement(
            qname=(TEXTNS, 'list-style'),
            attributes={"name": "NumberedListStyle"},
            child_nodes=[level_style]
        )

        self.mock_doc.automaticstyles.childNodes = [list_style]

        result = self.converter._is_ordered_list(lst)

        assert result is True

    def test_is_ordered_list_bulleted(self):
        """Test detection of unordered list."""
        from odf.text import TEXTNS

        # Mock list element
        lst = MockElement(attributes={"stylename": "BulletListStyle"})

        # Mock list style with bullet level
        level_style = MockElement(qname=(TEXTNS, 'list-level-style-bullet'))
        list_style = MockElement(
            qname=(TEXTNS, 'list-style'),
            attributes={"name": "BulletListStyle"},
            child_nodes=[level_style]
        )

        self.mock_doc.automaticstyles.childNodes = [list_style]

        result = self.converter._is_ordered_list(lst)

        assert result is False

    def test_is_ordered_list_no_style(self):
        """Test list detection with no style."""
        lst = MockElement(attributes={})

        result = self.converter._is_ordered_list(lst)

        assert result is False

    def test_process_list_unordered(self):
        """Test processing unordered list."""
        from odf.text import TEXTNS

        # Mock list items
        text1 = MockTextNode("Item 1")
        para1 = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text1])
        item1 = MockElement(qname=(TEXTNS, 'list-item'), child_nodes=[para1])

        text2 = MockTextNode("Item 2")
        para2 = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text2])
        item2 = MockElement(qname=(TEXTNS, 'list-item'), child_nodes=[para2])

        lst = MockElement(
            qname=(TEXTNS, 'list'),
            attributes={"stylename": "BulletStyle"},
            child_nodes=[item1, item2]
        )

        # Mock as unordered list
        with patch.object(self.converter, '_is_ordered_list', return_value=False):
            result = self.converter._process_list(lst)

        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_process_list_ordered(self):
        """Test processing ordered list."""
        from odf.text import TEXTNS

        # Mock list items
        text1 = MockTextNode("First item")
        para1 = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text1])
        item1 = MockElement(qname=(TEXTNS, 'list-item'), child_nodes=[para1])

        text2 = MockTextNode("Second item")
        para2 = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text2])
        item2 = MockElement(qname=(TEXTNS, 'list-item'), child_nodes=[para2])

        lst = MockElement(
            qname=(TEXTNS, 'list'),
            attributes={"stylename": "NumberStyle"},
            child_nodes=[item1, item2]
        )

        # Mock as ordered list
        with patch.object(self.converter, '_is_ordered_list', return_value=True):
            result = self.converter._process_list(lst)

        assert "1. First item" in result
        assert "2. Second item" in result

    def test_process_table_basic(self):
        """Test processing basic table."""

        # Mock table cells
        header1 = Mock()
        header1.getElementsByType.return_value = []
        header2 = Mock()
        header2.getElementsByType.return_value = []

        data1 = Mock()
        data1.getElementsByType.return_value = []
        data2 = Mock()
        data2.getElementsByType.return_value = []

        # Mock table rows
        header_row = Mock()
        header_row.getElementsByType.return_value = [header1, header2]

        data_row = Mock()
        data_row.getElementsByType.return_value = [data1, data2]

        # Mock table
        table_mock = Mock()
        table_mock.getElementsByType.return_value = [header_row, data_row]

        with patch.object(self.converter, '_process_element') as mock_process:
            mock_process.side_effect = ["H1", "H2", "C1", "C2"]

            result = self.converter._process_table(table_mock)

        assert "| H1 | H2 |" in result
        assert "| --- | --- |" in result
        assert "| C1 | C2 |" in result

    def test_process_table_disabled(self):
        """Test table processing when disabled."""
        disabled_preserve = self.options.create_updated(preserve_tables=False)
        # self.options.preserve_tables = False
        self.converter = OdfConverter(self.mock_doc, disabled_preserve)

        table_mock = Mock()

        result = self.converter._process_table(table_mock)

        assert result == ""

    def test_process_image_basic(self):
        """Test processing image element."""
        from odf import draw

        # Mock image elements
        image_element = Mock()
        image_element.getAttribute.return_value = "Pictures/image1.png"

        frame = Mock()
        frame.getElementsByType = Mock(side_effect=lambda elem_type: {
            draw.Image: [image_element]
        }.get(elem_type, []))

        # Mock successful image data retrieval
        self.mock_doc.getPart = Mock(return_value=b"mock_image_data")

        with patch('all2md.converters.odf2markdown.process_attachment') as mock_process:
            mock_process.return_value = "![image](image1.png)"

            result = self.converter._process_image(frame)

        assert result == "![image](image1.png)"
        mock_process.assert_called_once()

    def test_process_image_no_href(self):
        """Test processing image with no href."""
        image_element = Mock()
        image_element.getAttribute.return_value = None

        frame = Mock()
        frame.getElementsByType.return_value = [image_element]

        result = self.converter._process_image(frame)

        assert result == ""

    def test_process_image_missing_from_package(self):
        """Test processing image missing from package."""
        from odf import draw

        image_element = Mock()
        image_element.getAttribute.return_value = "missing_image.png"

        frame = Mock()
        frame.getElementsByType = Mock(side_effect=lambda elem_type: {
            draw.Image: [image_element]
        }.get(elem_type, []))

        # Mock getPart to raise KeyError
        self.mock_doc.getPart = Mock(side_effect=KeyError("Image not found"))

        result = self.converter._process_image(frame)

        assert result == ""

    def test_convert_basic_document(self):
        """Test converting basic document structure."""
        from odf.text import TEXTNS

        # Mock document content
        text_node = MockTextNode("Document content")
        para = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text_node])

        self.mock_doc.text.childNodes = [para]

        result = self.converter.convert()

        assert "Document content" in result

    def test_convert_presentation_document(self):
        """Test converting presentation document."""
        from odf.text import TEXTNS

        # Mock presentation content
        text_node = MockTextNode("Slide content")
        para = MockElement(qname=(TEXTNS, 'p'), child_nodes=[text_node])

        # Remove text attribute to test presentation path
        del self.mock_doc.text
        self.mock_doc.presentation.childNodes = [para]

        result = self.converter.convert()

        assert "Slide content" in result


@pytest.mark.unit
@pytest.mark.odf
class TestOdfToMarkdownFunction:
    """Test the main odf_to_markdown function."""

    def test_odf_to_markdown_with_options(self):
        """Test odf_to_markdown with custom options."""
        options = OdfOptions(preserve_tables=False)

        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_load.return_value = mock_doc

            result = odf_to_markdown("test.odt", options)

            assert isinstance(result, str)

    def test_odf_to_markdown_default_options(self):
        """Test odf_to_markdown with default options."""
        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_load.return_value = mock_doc

            result = odf_to_markdown("test.odt")

            assert isinstance(result, str)

    def test_odf_to_markdown_missing_dependency(self):
        """Test error handling when odfpy is not available."""
        with patch('odf.opendocument.load') as mock_load:
            mock_load.side_effect = ImportError("No module named odfpy")

            with pytest.raises(MarkdownConversionError) as exc_info:
                odf_to_markdown("test.odt")

            assert "odfpy library is required" in str(exc_info.value)
            assert exc_info.value.conversion_stage == "dependency_check"

    def test_odf_to_markdown_document_error(self):
        """Test error handling when document cannot be loaded."""
        with patch('odf.opendocument.load') as mock_load:
            mock_load.side_effect = Exception("Corrupted document")

            with pytest.raises(MarkdownConversionError) as exc_info:
                odf_to_markdown("test.odt")

            assert "Failed to open ODF document" in str(exc_info.value)
            assert exc_info.value.conversion_stage == "document_opening"

    def test_odf_to_markdown_file_object(self):
        """Test odf_to_markdown with file-like object."""
        from io import BytesIO

        file_obj = BytesIO(b"mock odf data")

        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_load.return_value = mock_doc

            result = odf_to_markdown(file_obj)

            assert isinstance(result, str)
            mock_load.assert_called_once_with(file_obj)

    def test_odf_to_markdown_path_object(self):
        """Test odf_to_markdown with Path object."""
        from pathlib import Path

        path_obj = Path("test.odt")

        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_load.return_value = mock_doc

            result = odf_to_markdown(path_obj)

            assert isinstance(result, str)
            mock_load.assert_called_once_with(path_obj)


@pytest.mark.unit
@pytest.mark.odf
class TestOdfMetadataExtraction:
    """Test ODF metadata extraction functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_doc = Mock()

    def test_extract_odf_metadata_basic(self):
        """Test basic metadata extraction from ODF document."""
        # Mock meta elements
        mock_title = Mock()
        mock_title.__str__ = Mock(return_value="Test Document")

        mock_creator = Mock()
        mock_creator.__str__ = Mock(return_value="Test Author")

        mock_description = Mock()
        mock_description.__str__ = Mock(return_value="Test Description")

        # Mock meta object with getElementsByType
        mock_meta = Mock()

        # Import the actual ODF classes for proper matching
        from odf.dc import Title, Creator, Description

        mock_meta.getElementsByType = lambda elem_type: {
            Title: [mock_title],
            Creator: [mock_creator],
            Description: [mock_description]
        }.get(elem_type, [])

        self.mock_doc.meta = mock_meta
        # Mock the hasattr and mimetype to avoid errors
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.text"
        self.mock_doc.body = None

        metadata = extract_odf_metadata(self.mock_doc)
        assert isinstance(metadata, DocumentMetadata)
        assert metadata.title == "Test Document"
        assert metadata.author == "Test Author"
        assert metadata.subject == "Test Description"

    def test_extract_odf_metadata_keywords(self):
        """Test keyword extraction from ODF document."""
        mock_keyword1 = Mock()
        mock_keyword1.__str__ = Mock(return_value="python, conversion")

        mock_keyword2 = Mock()
        mock_keyword2.__str__ = Mock(return_value="odf; markdown")

        mock_meta = Mock()

        # Import the actual ODF classes
        from odf.meta import Keyword

        mock_meta.getElementsByType = lambda elem_type: {
            Keyword: [mock_keyword1, mock_keyword2]
        }.get(elem_type, [])

        self.mock_doc.meta = mock_meta
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.text"
        self.mock_doc.body = None

        metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.keywords == ["python", "conversion", "odf", "markdown"]

    def test_extract_odf_metadata_creation_date(self):
        """Test creation date extraction from ODF document."""
        mock_date = Mock()
        mock_date.__str__ = Mock(return_value="2025-09-26T10:00:00Z")

        mock_meta = Mock()

        # Import the actual ODF classes
        from odf.meta import CreationDate

        mock_meta.getElementsByType = lambda elem_type: {
            CreationDate: [mock_date]
        }.get(elem_type, [])

        self.mock_doc.meta = mock_meta
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.text"
        self.mock_doc.body = None

        metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.creation_date == "2025-09-26T10:00:00Z"

    def test_extract_odf_metadata_no_meta(self):
        """Test metadata extraction when no meta section exists."""
        self.mock_doc.meta = None

        with patch('all2md.converters.odf2markdown.hasattr', return_value=False):
            metadata = extract_odf_metadata(self.mock_doc)

        assert isinstance(metadata, DocumentMetadata)
        assert metadata.title is None
        assert metadata.author is None

    def test_extract_odf_metadata_document_statistics(self):
        """Test document statistics extraction."""
        # Mock document body with various elements
        mock_pages = [Mock(), Mock(), Mock()]  # 3 pages
        mock_paragraphs = [Mock(), Mock()]  # 2 paragraphs
        mock_tables = [Mock()]  # 1 table

        mock_body = Mock()
        mock_body.getElementsByType = Mock(side_effect=lambda elem_type: {
            'Page': mock_pages,
            'P': mock_paragraphs,
            'Table': mock_tables
        }.get(elem_type.__name__, []))

        self.mock_doc.body = mock_body
        self.mock_doc.meta = None

        with patch('all2md.converters.odf2markdown.hasattr', side_effect=lambda obj, attr: attr in ['body']):
            metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.custom['page_count'] == 3
        assert metadata.custom['paragraph_count'] == 2
        assert metadata.custom['table_count'] == 1

    def test_extract_odf_metadata_presentation_type(self):
        """Test document type detection for presentations."""
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.presentation"
        self.mock_doc.meta = None
        self.mock_doc.body = None

        with patch('all2md.converters.odf2markdown.hasattr', side_effect=lambda obj, attr: attr == 'mimetype'):
            metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.custom['document_type'] == 'presentation'

    def test_extract_odf_metadata_text_type(self):
        """Test document type detection for text documents."""
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.text"
        self.mock_doc.meta = None
        self.mock_doc.body = None

        with patch('all2md.converters.odf2markdown.hasattr', side_effect=lambda obj, attr: attr == 'mimetype'):
            metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.custom['document_type'] == 'text'

    def test_odf_to_markdown_with_metadata_extraction(self):
        """Test odf_to_markdown with metadata extraction enabled."""
        options = OdfOptions(extract_metadata=True)

        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_doc.meta = Mock()
            mock_doc.meta.getElementsByType = Mock(return_value=[])
            mock_load.return_value = mock_doc

            with patch('all2md.converters.odf2markdown.extract_odf_metadata') as mock_extract:
                mock_metadata = DocumentMetadata()
                mock_metadata.title = "Test Document"
                mock_extract.return_value = mock_metadata

                with patch('all2md.converters.odf2markdown.prepend_metadata_if_enabled') as mock_prepend:
                    mock_prepend.return_value = "---\ntitle: Test Document\n---\n\nContent"

                    result = odf_to_markdown("test.odt", options)

                    mock_extract.assert_called_once_with(mock_doc)
                    mock_prepend.assert_called_once()
                    assert "---" in result
                    assert "title: Test Document" in result

    def test_odf_to_markdown_without_metadata_extraction(self):
        """Test odf_to_markdown with metadata extraction disabled."""
        options = OdfOptions(extract_metadata=False)

        with patch('odf.opendocument.load') as mock_load:
            mock_doc = MockDocument()
            mock_doc.text.childNodes = []
            mock_load.return_value = mock_doc

            with patch('all2md.converters.odf2markdown.extract_odf_metadata') as mock_extract:
                result = odf_to_markdown("test.odt", options)

                mock_extract.assert_not_called()
                assert not result.startswith("---")
