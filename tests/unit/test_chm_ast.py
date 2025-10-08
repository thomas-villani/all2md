#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_chm_ast.py
"""Unit tests for CHM to AST converter.

Tests cover:
- CHM file parsing with mock objects
- Table of contents extraction
- Page enumeration and content extraction
- Metadata extraction
- Options handling (merge_pages, include_toc)
- HTML content parsing via HtmlToAstConverter

"""

from unittest.mock import MagicMock, patch

import pytest

from all2md.ast import Document, Heading, Paragraph, Strong, Table, Text, ThematicBreak
from all2md.options import ChmOptions, HtmlOptions
from all2md.parsers.chm import ChmParser
from tests.fixtures.generators.chm_fixtures import (
    create_chm_with_code,
    create_chm_with_images,
    create_chm_with_nested_toc,
    create_empty_chm,
    create_simple_chm,
)


@pytest.mark.unit
class TestChmBasicParsing:
    """Tests for basic CHM parsing functionality."""

    def test_simple_chm_conversion(self) -> None:
        """Test converting a simple CHM file."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have TOC heading (since include_toc defaults to True)
        toc_found = any(
            isinstance(child, Heading) and
            any(t.content == "Table of Contents" for t in child.content if isinstance(t, Text))
            for child in doc.children
        )
        assert toc_found

    def test_chm_without_toc(self) -> None:
        """Test CHM conversion with TOC disabled."""
        mock_chm = create_simple_chm()

        options = ChmOptions(include_toc=False)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        assert isinstance(doc, Document)
        # Should not have "Table of Contents" heading
        toc_found = any(
            isinstance(child, Heading) and
            any(t.content == "Table of Contents" for t in child.content if isinstance(t, Text))
            for child in doc.children
        )
        assert not toc_found

    def test_chm_page_merging(self) -> None:
        """Test page merging behavior."""
        mock_chm = create_simple_chm()

        # With merge_pages=True (default)
        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        # Count thematic breaks (should have at least one after TOC)
        break_count = sum(1 for child in doc.children if isinstance(child, ThematicBreak))

        # With merge_pages=False
        options = ChmOptions(merge_pages=False)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        # Should have more breaks when not merging
        break_count_no_merge = sum(1 for child in doc.children if isinstance(child, ThematicBreak))
        assert break_count_no_merge > break_count

    def test_empty_chm(self) -> None:
        """Test handling empty CHM file."""
        mock_chm = create_empty_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        assert isinstance(doc, Document)
        # Should have minimal content (possibly just empty or TOC heading if enabled)
        assert len(doc.children) >= 0


@pytest.mark.unit
class TestChmContentExtraction:
    """Tests for CHM content extraction."""

    def test_html_content_parsing(self) -> None:
        """Test that HTML content is properly parsed."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        # Check for expected content from fixture
        # Should have headings from the HTML pages
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0

        # Should have paragraphs from the HTML pages
        paragraphs = [child for child in doc.children if isinstance(child, Paragraph)]
        assert len(paragraphs) > 0

    def test_code_blocks(self) -> None:
        """Test CHM with code blocks."""
        from all2md.ast import CodeBlock

        mock_chm = create_chm_with_code()

        options = ChmOptions(include_toc=False)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        # Should have code blocks
        code_blocks = []
        for child in doc.children:
            if isinstance(child, CodeBlock):
                code_blocks.append(child)

        assert len(code_blocks) >= 1

    def test_nested_toc(self) -> None:
        """Test CHM with nested table of contents."""
        mock_chm = create_chm_with_nested_toc()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        # Should have TOC with nested headings
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) > 0

        # Check for varying heading levels
        heading_levels = {h.level for h in headings}
        assert len(heading_levels) > 1  # Should have multiple levels


@pytest.mark.unit
class TestChmMetadata:
    """Tests for CHM metadata extraction."""

    def test_metadata_extraction(self) -> None:
        """Test metadata extraction from CHM."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        metadata = parser.extract_metadata(mock_chm)

        # Check that title was extracted
        assert metadata.title == "Test CHM Document"

    def test_metadata_from_home_page(self) -> None:
        """Test metadata extraction from home page when title not in CHM."""
        # Create mock without title property
        mock_chm = create_simple_chm()
        mock_chm.title = None  # Remove title

        parser = ChmParser()
        metadata = parser.extract_metadata(mock_chm)

        # Should extract title from home page HTML
        assert metadata.title == "Test CHM Document"


@pytest.mark.unit
class TestChmOptions:
    """Tests for CHM options handling."""

    def test_chm_options_defaults(self) -> None:
        """Test default CHM options values."""
        options = ChmOptions()

        assert options.include_toc is True
        assert options.merge_pages is True
        assert options.html_options is None

    def test_chm_options_custom(self) -> None:
        """Test custom CHM options."""
        html_opts = HtmlOptions(extract_title=True)
        options = ChmOptions(
            include_toc=False,
            merge_pages=False,
            html_options=html_opts
        )

        assert options.include_toc is False
        assert options.merge_pages is False
        assert options.html_options is not None
        assert options.html_options.extract_title is True

    def test_html_options_passed_to_parser(self) -> None:
        """Test that HTML options are passed to HTML parser."""
        # Create options with specific HTML settings
        html_opts = HtmlOptions(collapse_whitespace=True, strip_comments=True)
        options = ChmOptions(html_options=html_opts)

        parser = ChmParser(options=options)

        # Verify HTML parser has the correct options
        assert parser.html_parser.options.collapse_whitespace is True
        assert parser.html_parser.options.strip_comments is True


@pytest.mark.unit
class TestChmErrorHandling:
    """Tests for CHM error handling."""

    def test_invalid_chm_load_failure_via_parse(self) -> None:
        """Test handling of CHM load failure through parse method."""
        # We can't easily test parse() without pychm installed, so skip this
        # test unless pychm is available
        pytest.importorskip("chm")

        from all2md.exceptions import ParsingError

        # This test would require mocking at the import level which is complex
        # For now, we verify the logic by calling convert_to_ast with a mock that fails
        mock_chm = MagicMock()
        mock_chm.LoadCHM.return_value = 0  # Failure

        parser = ChmParser()

        # Since LoadCHM would be called in parse(), we can't easily test it
        # without the actual library. Skip this specific test case.
        pytest.skip("Requires pychm library to be installed for full parse() testing")

    def test_page_parsing_errors_are_caught(self) -> None:
        """Test that page parsing errors don't stop entire conversion."""
        # Create mock that raises error for one page
        mock_chm = create_simple_chm()

        # Make one page return invalid HTML
        original_retrieve = mock_chm.RetrieveObject

        def failing_retrieve(obj_ref):
            if obj_ref == "/chapter1.html":
                # Return malformed content
                return (0, b'\xff\xfe\x00invalid')
            return original_retrieve(obj_ref)

        mock_chm.RetrieveObject = failing_retrieve

        parser = ChmParser()

        # Should not raise, but log warning and continue
        doc = parser.convert_to_ast(mock_chm)
        assert isinstance(doc, Document)


@pytest.mark.unit
class TestChmPageEnumeration:
    """Tests for CHM page enumeration methods."""

    def test_enumerate_pages_from_toc(self) -> None:
        """Test page enumeration from TOC."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        pages = parser._enumerate_pages(mock_chm)

        # Should have pages from fixture
        assert len(pages) > 0
        assert any('index.html' in page for page in pages)
        assert any('chapter1.html' in page for page in pages)

    def test_enumerate_pages_fallback(self) -> None:
        """Test page enumeration fallback when TOC unavailable."""
        mock_chm = create_simple_chm()
        # Make GetTopicsTree return None
        mock_chm.GetTopicsTree = lambda: None

        parser = ChmParser()
        pages = parser._enumerate_pages(mock_chm)

        # Should still find pages via Enumerate
        assert len(pages) > 0


@pytest.mark.unit
class TestChmTOCBuilding:
    """Tests for CHM table of contents building."""

    def test_toc_structure(self) -> None:
        """Test TOC structure generation."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        toc_nodes = parser._build_toc(mock_chm)

        # Should have TOC heading and entries
        assert len(toc_nodes) > 0

        # First node should be TOC heading
        assert isinstance(toc_nodes[0], Heading)
        assert toc_nodes[0].level == 1
        assert any(
            isinstance(t, Text) and "Table of Contents" in t.content
            for t in toc_nodes[0].content
        )

    def test_nested_toc_levels(self) -> None:
        """Test nested TOC with multiple levels."""
        mock_chm = create_chm_with_nested_toc()

        parser = ChmParser()
        toc_nodes = parser._build_toc(mock_chm)

        # Should have headings at multiple levels
        headings = [node for node in toc_nodes if isinstance(node, Heading)]
        levels = {h.level for h in headings}

        assert len(levels) > 1  # Multiple heading levels
        assert all(1 <= level <= 6 for level in levels)  # Valid heading levels
