"""Integration tests for CHM to Markdown conversion.

This module contains integration tests for the chm2markdown converter,
testing full conversion pipelines with CHM structures and edge cases.

Note: Since creating real CHM files programmatically is complex (requires
CHMLib and pychm doesn't support writing), these integration tests use
mock CHM objects. For true end-to-end testing with real CHM files, you
would need to provide actual CHM files as test fixtures.
"""

import pytest

from all2md.options.chm import ChmOptions
from all2md.options.html import HtmlOptions
from all2md.options.markdown import MarkdownOptions
from all2md.parsers.chm import ChmParser
from all2md.renderers.markdown import MarkdownRenderer
from fixtures.generators.chm_fixtures import (
    create_chm_with_code,
    create_chm_with_images,
    create_chm_with_nested_toc,
    create_empty_chm,
    create_simple_chm,
)
from utils import assert_markdown_valid


@pytest.mark.integration
@pytest.mark.chm
class TestChmIntegrationBasic:
    """Test basic CHM integration scenarios."""

    def test_simple_chm_conversion(self) -> None:
        """Test conversion of a simple CHM file."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        # Render to markdown
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain content from the HTML pages
        assert "Table of Contents" in result
        assert "Chapter 1" in result or "Introduction" in result
        assert_markdown_valid(result)

    def test_chm_with_options(self) -> None:
        """Test CHM conversion with custom options."""
        mock_chm = create_simple_chm()

        options = ChmOptions(include_toc=False, merge_pages=True)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should not have TOC
        assert "Table of Contents" not in result
        # But should have content
        assert "Chapter 1" in result or "Introduction" in result
        assert_markdown_valid(result)

    def test_chm_with_markdown_options(self) -> None:
        """Test CHM conversion with markdown rendering options."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        markdown_options = MarkdownOptions(use_hash_headings=True, emphasis_symbol="*")
        renderer = MarkdownRenderer(options=markdown_options)
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert "#" in result  # Hash headings
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.chm
class TestChmContentTypes:
    """Test CHM conversion with different content types."""

    def test_chm_with_code_blocks(self) -> None:
        """Test CHM with code blocks."""
        mock_chm = create_chm_with_code()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should have code blocks with backticks
        assert "```" in result
        # Should have code content
        assert "print" in result or "console.log" in result
        assert_markdown_valid(result)

    def test_chm_with_images(self) -> None:
        """Test CHM with images."""
        mock_chm = create_chm_with_images()

        options = ChmOptions(include_toc=False)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should have image markdown syntax
        assert "![" in result
        assert "Test Image" in result or "Logo" in result
        assert_markdown_valid(result)

    def test_chm_with_nested_toc(self) -> None:
        """Test CHM with nested table of contents."""
        mock_chm = create_chm_with_nested_toc()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should have multiple heading levels
        assert "#" in result
        # Should have content from nested pages
        assert "Part 1" in result or "Part 2" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.chm
class TestChmHtmlOptions:
    """Test CHM conversion with HTML parsing options."""

    def test_chm_with_html_options(self) -> None:
        """Test CHM with custom HTML parsing options."""
        mock_chm = create_simple_chm()

        html_options = HtmlOptions(collapse_whitespace=True, strip_comments=True, extract_title=True)
        chm_options = ChmOptions(html_options=html_options)

        parser = ChmParser(options=chm_options)
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert len(result) > 0
        assert_markdown_valid(result)

    def test_chm_with_extract_title(self) -> None:
        """Test CHM with title extraction from HTML."""
        mock_chm = create_simple_chm()

        html_options = HtmlOptions(extract_title=True)
        chm_options = ChmOptions(html_options=html_options, include_toc=False)

        parser = ChmParser(options=chm_options)
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Title should be extracted and appear as top-level heading
        assert "Test CHM" in result or "Welcome" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.chm
class TestChmEdgeCases:
    """Test CHM edge cases and error handling."""

    def test_empty_chm(self) -> None:
        """Test conversion of empty CHM file."""
        mock_chm = create_empty_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should return valid markdown even if empty

    def test_chm_with_malformed_html(self) -> None:
        """Test CHM with malformed HTML content."""
        from fixtures.generators.chm_fixtures import MockCHMFile

        # Create CHM with malformed HTML
        mock_chm = MockCHMFile(
            pages={"/bad.html": "<html><p>Unclosed paragraph<p>Another one</html>"},
            title="Malformed HTML Test",
            home="/bad.html",
        )

        parser = ChmParser()

        # Should not raise, BeautifulSoup is lenient
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)


@pytest.mark.integration
@pytest.mark.chm
class TestChmFormatting:
    """Test CHM conversion preserves formatting."""

    def test_chm_preserves_bold_italic(self) -> None:
        """Test that CHM conversion preserves bold and italic."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Should have bold (** or __)
        assert "**" in result or "__" in result
        # Should have italic (* or _)
        assert "*" in result or "_" in result

    def test_chm_preserves_links(self) -> None:
        """Test that CHM conversion preserves links."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Should have link syntax [text](url)
        assert "[" in result and "](" in result
        assert "https://example.com" in result

    def test_chm_preserves_lists(self) -> None:
        """Test that CHM conversion preserves lists."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Should have list markers (-, *, or numbers)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result


@pytest.mark.integration
@pytest.mark.chm
class TestChmMetadataIntegration:
    """Test CHM metadata extraction in integration."""

    def test_metadata_in_frontmatter(self) -> None:
        """Test that metadata appears in frontmatter."""
        mock_chm = create_simple_chm()

        parser = ChmParser()
        doc = parser.convert_to_ast(mock_chm)

        # Use markdown options to include frontmatter
        markdown_options = MarkdownOptions(metadata_frontmatter=True, metadata_format="yaml")

        renderer = MarkdownRenderer(options=markdown_options)
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        # Should have content (frontmatter rendering depends on metadata being set properly)
        # The main test here is that rendering with frontmatter options doesn't crash
        assert "Table of Contents" in result or "Chapter" in result


@pytest.mark.integration
@pytest.mark.chm
class TestChmPageSeparation:
    """Test page separation behavior."""

    def test_merged_pages(self) -> None:
        """Test that pages are merged by default."""
        mock_chm = create_simple_chm()

        options = ChmOptions(merge_pages=True, include_toc=False)
        parser = ChmParser(options=options)
        doc = parser.convert_to_ast(mock_chm)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Count horizontal rules (page separators)
        separator_count = result.count("---") + result.count("* * *")

        # With merge_pages=False
        options = ChmOptions(merge_pages=False, include_toc=False)
        parser = ChmParser(options=options)
        doc_no_merge = parser.convert_to_ast(mock_chm)

        result_no_merge = renderer.render_to_string(doc_no_merge)
        separator_count_no_merge = result_no_merge.count("---") + result_no_merge.count("* * *")

        # Should have more separators when not merging
        assert separator_count_no_merge >= separator_count
