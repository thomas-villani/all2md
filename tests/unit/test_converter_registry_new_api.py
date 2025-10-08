"""Tests for the new converter registry API with parser/renderer architecture.

This test module verifies that the registry correctly handles the new
parser_class/renderer_class based architecture and that deprecated
converter_module/converter_function patterns are no longer supported.
"""

import pytest

from all2md.converter_registry import registry
from all2md.exceptions import FormatError
from all2md.options import DocxOptions, HtmlOptions, PdfOptions


class TestRegistryNewAPI:
    """Test the new registry API methods."""

    def setup_method(self):
        """Ensure registry is initialized before each test."""
        registry.auto_discover()

    def test_get_options_class_for_pdf(self):
        """Test that get_parser_options_class returns correct options class for PDF."""
        options_class = registry.get_parser_options_class("pdf")
        assert options_class is not None
        assert options_class == PdfOptions

    def test_get_options_class_for_docx(self):
        """Test that get_parser_options_class returns correct options class for DOCX."""
        options_class = registry.get_parser_options_class("docx")
        assert options_class is not None
        assert options_class == DocxOptions

    def test_get_options_class_for_html(self):
        """Test that get_parser_options_class returns correct options class for HTML."""
        options_class = registry.get_parser_options_class("html")
        assert options_class is not None
        assert options_class == HtmlOptions

    def test_get_options_class_for_unknown_format(self):
        """Test that get_parser_options_class raises FormatError for unknown formats."""
        with pytest.raises(FormatError) as exc_info:
            registry.get_parser_options_class("unknown_format_xyz")

        assert "unknown_format_xyz" in str(exc_info.value).lower()

    def test_get_parser_returns_parser_class(self):
        """Test that get_parser returns a parser class."""
        parser_class = registry.get_parser("pdf")
        assert parser_class is not None
        assert hasattr(parser_class, "parse")

        # Verify it's a class, not an instance
        assert isinstance(parser_class, type)

    def test_get_parser_for_multiple_formats(self):
        """Test that get_parser works for multiple formats."""
        formats = ["pdf", "docx", "html", "pptx", "ipynb"]

        for format_name in formats:
            try:
                parser_class = registry.get_parser(format_name)
                assert parser_class is not None
                assert hasattr(parser_class, "parse")
            except FormatError:
                # Some formats might not be available due to missing dependencies
                pytest.skip(f"Format {format_name} not available")

    def test_markdown_format_registered(self):
        """Test that markdown format is registered in the registry."""
        # Markdown is a special format - it's primarily used for parsing markdown
        # The renderer (MarkdownRenderer) is shared across all formats
        formats = registry.list_formats()
        assert "markdown" in formats

        # Should be able to get parser and options
        parser_class = registry.get_parser("markdown")
        assert parser_class is not None

        options_class = registry.get_parser_options_class("markdown")
        assert options_class is not None

    def test_converter_metadata_has_parser_class(self):
        """Test that registered converters have parser_class in metadata."""
        formats = registry.list_formats()

        for format_name in formats:
            metadata_list = registry.get_format_info(format_name)
            assert metadata_list is not None
            assert len(metadata_list) > 0

            # New architecture: parser_class or renderer_class should be set
            # Some formats like MediaWiki and PlainText are renderer-only (no parser)
            # Check the highest priority (first) converter
            metadata = metadata_list[0]
            assert (metadata.parser_class is not None or
                   metadata.renderer_class is not None)

            # Old architecture fields should be empty or not used
            # (They might still exist for backward compat but shouldn't be relied upon)

    def test_old_get_converter_method_removed(self):
        """Test that the old get_converter method no longer exists."""
        # Verify the deprecated method has been removed
        assert not hasattr(registry, "get_converter")

    def test_parser_instantiation_with_options(self):
        """Test that parsers can be instantiated with options."""
        parser_class = registry.get_parser("pdf")
        options = PdfOptions(pages=[0, 1])

        # Should be able to instantiate parser with options
        parser = parser_class(options=options)
        assert parser is not None
        assert hasattr(parser, "parse")

    def test_registry_list_formats_returns_multiple(self):
        """Test that registry discovers and lists multiple formats."""
        formats = registry.list_formats()

        # Should have at least these core formats
        expected_formats = ["pdf", "docx", "html"]

        for expected in expected_formats:
            assert expected in formats, f"Expected format '{expected}' not found in registry"

        # Should have multiple formats registered
        assert len(formats) >= 5, f"Expected at least 5 formats, got {len(formats)}"

    def test_format_detection_uses_parser_metadata(self):
        """Test that format detection works with parser metadata."""
        # Test with PDF magic bytes
        pdf_content = b"%PDF-1.4\n"
        detected = registry.detect_format(pdf_content)
        assert detected == "pdf"

        # Test with HTML content
        html_content = b"<!DOCTYPE html><html></html>"
        detected = registry.detect_format(html_content)
        assert detected == "html"

    def test_format_detection_with_text_streams(self):
        """Test that format detection handles text streams (StringIO) correctly."""
        from io import BytesIO, StringIO

        # Test with BytesIO (binary stream) - should work as before
        pdf_bytes = b"%PDF-1.4\nBinary PDF content"
        binary_stream = BytesIO(pdf_bytes)
        detected = registry.detect_format(binary_stream)
        assert detected == "pdf"

        # Test with StringIO (text stream) - content should be encoded to bytes
        # StringIO contains text that would be PDF magic bytes if encoded
        pdf_text = "%PDF-1.4\nText PDF content"
        text_stream = StringIO(pdf_text)
        detected = registry.detect_format(text_stream)
        assert detected == "pdf"

        # Test with HTML in StringIO
        html_text = "<!DOCTYPE html><html><body>Test</body></html>"
        html_stream = StringIO(html_text)
        detected = registry.detect_format(html_stream)
        assert detected == "html"

    def test_options_class_can_be_instantiated(self):
        """Test that options classes returned by get_parser_options_class are usable."""
        options_class = registry.get_parser_options_class("pdf")

        # Should be able to instantiate with default values
        options = options_class()
        assert options is not None

        # Should be able to instantiate with custom values
        options = options_class(pages=[0, 1, 2])
        assert options.pages == [0, 1, 2]


class TestRegistryAutoDiscovery:
    """Test that auto-discovery properly registers parsers."""

    def test_auto_discover_idempotent(self):
        """Test that auto_discover can be called multiple times safely."""
        # Get initial format count
        initial_formats = set(registry.list_formats())

        # Call auto_discover again
        registry.auto_discover()

        # Should have same formats (no duplicates)
        current_formats = set(registry.list_formats())
        assert initial_formats == current_formats

        # Should have key formats
        assert "pdf" in current_formats
        assert "docx" in current_formats
        assert "html" in current_formats

    def test_auto_discover_registers_parser_classes(self):
        """Test that auto_discover registers parser_class or renderer_class for each format."""
        registry.auto_discover()

        for format_name in registry.list_formats():
            metadata_list = registry.get_format_info(format_name)
            assert metadata_list is not None
            assert len(metadata_list) > 0

            # Each format should have at least one parser_class or renderer_class
            # Some formats like MediaWiki and PlainText are renderer-only (no parser)
            # Check the highest priority (first) converter
            metadata = metadata_list[0]
            assert (metadata.parser_class is not None or
                   metadata.renderer_class is not None)


class TestEndToEndParsing:
    """Test end-to-end parsing workflow with new architecture."""

    def setup_method(self):
        """Ensure registry is initialized."""
        registry.auto_discover()

    def test_pdf_parser_workflow(self):
        """Test the complete parser workflow for PDF format."""
        # Skip if PDF dependencies not available
        try:
            parser_class = registry.get_parser("pdf")
        except Exception:
            pytest.skip("PDF parser dependencies not available")

        options_class = registry.get_parser_options_class("pdf")
        assert options_class is not None

        # Create options
        options = options_class(extract_metadata=True)

        # Instantiate parser
        parser = parser_class(options=options)
        assert parser is not None

    def test_html_parser_workflow(self):
        """Test the complete parser workflow for HTML format."""
        # Skip if HTML dependencies not available
        try:
            parser_class = registry.get_parser("html")
        except Exception:
            pytest.skip("HTML parser dependencies not available")

        options_class = registry.get_parser_options_class("html")
        assert options_class is not None

        # Create options
        options = options_class(extract_title=True)

        # Instantiate parser
        parser = parser_class(options=options)
        assert parser is not None

        # Test parsing simple HTML
        html_content = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        ast_doc = parser.parse(html_content)

        assert ast_doc is not None
        assert hasattr(ast_doc, "children")


class TestMultiConverterSupport:
    """Test support for multiple converters per format with priority-based selection."""

    def setup_method(self):
        """Set up test with fresh registry."""
        registry.auto_discover()

    def test_multiple_converters_same_format(self):
        """Test that multiple converters can be registered for the same format."""
        from all2md.converter_metadata import ConverterMetadata

        # Create two test converters for a fake format
        metadata1 = ConverterMetadata(
            format_name="test_format",
            parser_class="all2md.parsers.html.HtmlToAstConverter",
            priority=5
        )
        metadata2 = ConverterMetadata(
            format_name="test_format",
            parser_class="all2md.parsers.markdown.MarkdownToAstConverter",
            priority=10
        )

        # Register both
        registry.register(metadata1)
        registry.register(metadata2)

        # Should have both registered
        metadata_list = registry.get_format_info("test_format")
        assert metadata_list is not None
        assert len(metadata_list) == 2

        # Should be sorted by priority (highest first)
        assert metadata_list[0].priority == 10
        assert metadata_list[1].priority == 5

    def test_priority_based_parser_selection(self):
        """Test that get_parser selects highest priority available parser."""
        from all2md.converter_metadata import ConverterMetadata

        # Create test converters with different priorities
        # Higher priority parser
        metadata_high = ConverterMetadata(
            format_name="test_priority",
            parser_class="all2md.parsers.html.HtmlToAstConverter",
            priority=100
        )
        # Lower priority parser
        metadata_low = ConverterMetadata(
            format_name="test_priority",
            parser_class="all2md.parsers.markdown.MarkdownToAstConverter",
            priority=50
        )

        # Register in reverse priority order
        registry.register(metadata_low)
        registry.register(metadata_high)

        # Should get the high priority parser
        parser_class = registry.get_parser("test_priority")
        assert parser_class is not None
        # The high priority one is HtmlToAstConverter
        assert "Html" in parser_class.__name__

    def test_parser_only_registration(self):
        """Test registering a parser-only converter without renderer."""
        from all2md.converter_metadata import ConverterMetadata

        # Register parser-only converter
        metadata = ConverterMetadata(
            format_name="test_parser_only",
            parser_class="all2md.parsers.html.HtmlToAstConverter",
            renderer_class=None,
            priority=10
        )
        registry.register(metadata)

        # Should be able to get parser
        parser_class = registry.get_parser("test_parser_only")
        assert parser_class is not None

        # Should raise error when getting renderer
        with pytest.raises(FormatError):
            registry.get_renderer("test_parser_only")

    def test_renderer_only_registration(self):
        """Test registering a renderer-only converter without parser."""
        from all2md.converter_metadata import ConverterMetadata

        # Register renderer-only converter
        metadata = ConverterMetadata(
            format_name="test_renderer_only",
            parser_class=None,
            renderer_class="all2md.renderers.markdown.MarkdownRenderer",
            priority=10
        )
        registry.register(metadata)

        # Should be able to get renderer
        renderer_class = registry.get_renderer("test_renderer_only")
        assert renderer_class is not None

        # Should raise error when getting parser
        with pytest.raises(FormatError):
            registry.get_parser("test_renderer_only")

    def test_mixed_parser_renderer_converters(self):
        """Test format with separate parser and renderer converters."""
        from all2md.converter_metadata import ConverterMetadata

        # Register parser-only converter
        parser_metadata = ConverterMetadata(
            format_name="test_mixed",
            parser_class="all2md.parsers.html.HtmlToAstConverter",
            renderer_class=None,
            priority=10
        )
        # Register renderer-only converter
        renderer_metadata = ConverterMetadata(
            format_name="test_mixed",
            parser_class=None,
            renderer_class="all2md.renderers.markdown.MarkdownRenderer",
            priority=5
        )

        registry.register(parser_metadata)
        registry.register(renderer_metadata)

        # Should be able to get both
        parser_class = registry.get_parser("test_mixed")
        assert parser_class is not None

        renderer_class = registry.get_renderer("test_mixed")
        assert renderer_class is not None

        # Should have two converters for this format
        metadata_list = registry.get_format_info("test_mixed")
        assert len(metadata_list) == 2
