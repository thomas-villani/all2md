"""Unit tests for ODF to Markdown conversion.

This module tests the ODF converter's internal methods using mock objects
and controlled inputs to verify correct behavior in isolation.
"""

from unittest.mock import Mock, patch

import pytest

from all2md.parsers.odf2markdown import extract_odf_metadata, odf_to_markdown
from all2md.exceptions import MarkdownConversionError
from all2md.options import OdfOptions
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
        from odf.dc import Creator, Description, Title

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

        with patch('all2md.parsers.odf2markdown.hasattr', return_value=False):
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

        with patch('all2md.parsers.odf2markdown.hasattr', side_effect=lambda obj, attr: attr in ['body']):
            metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.custom['page_count'] == 3
        assert metadata.custom['paragraph_count'] == 2
        assert metadata.custom['table_count'] == 1

    def test_extract_odf_metadata_presentation_type(self):
        """Test document type detection for presentations."""
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.presentation"
        self.mock_doc.meta = None
        self.mock_doc.body = None

        with patch('all2md.parsers.odf2markdown.hasattr', side_effect=lambda obj, attr: attr == 'mimetype'):
            metadata = extract_odf_metadata(self.mock_doc)

        assert metadata.custom['document_type'] == 'presentation'

    def test_extract_odf_metadata_text_type(self):
        """Test document type detection for text documents."""
        self.mock_doc.mimetype = "application/vnd.oasis.opendocument.text"
        self.mock_doc.meta = None
        self.mock_doc.body = None

        with patch('all2md.parsers.odf2markdown.hasattr', side_effect=lambda obj, attr: attr == 'mimetype'):
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

            with patch('all2md.parsers.odf2markdown.extract_odf_metadata') as mock_extract:
                mock_metadata = DocumentMetadata()
                mock_metadata.title = "Test Document"
                mock_extract.return_value = mock_metadata

                with patch('all2md.parsers.odf2markdown.prepend_metadata_if_enabled') as mock_prepend:
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

            with patch('all2md.parsers.odf2markdown.extract_odf_metadata') as mock_extract:
                result = odf_to_markdown("test.odt", options)

                mock_extract.assert_not_called()
                assert not result.startswith("---")
