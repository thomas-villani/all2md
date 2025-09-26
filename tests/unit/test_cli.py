"""Unit tests for all2md CLI functionality.

This module tests the command-line interface components including argument parsing,
option mapping, and validation logic.
"""

import argparse
from unittest.mock import Mock, patch

import pytest

from all2md.cli import create_parser, parse_pdf_pages
from all2md.cli_builder import DynamicCLIBuilder


@pytest.mark.unit
@pytest.mark.cli
class TestDynamicCLIBuilder:
    """Test dynamic CLI builder functionality."""

    def test_pdf_pages_parsing_valid(self):
        """Test parsing of valid PDF page numbers."""
        # Single page
        assert parse_pdf_pages("5") == [5]

        # Multiple pages
        assert parse_pdf_pages("1,2,3") == [1, 2, 3]

        # Pages with spaces
        assert parse_pdf_pages("1, 2, 3") == [1, 2, 3]

        # Mixed formatting
        assert parse_pdf_pages("0,5, 10,15") == [0, 5, 10, 15]

    def test_pdf_pages_parsing_invalid(self):
        """Test parsing of invalid PDF page numbers raises error."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("invalid")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("1,invalid,3")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_pdf_pages("1.5,2")

    def test_snake_to_kebab_conversion(self):
        """Test conversion of snake_case to kebab-case."""
        builder = DynamicCLIBuilder()

        assert builder.snake_to_kebab("test_field") == "test-field"
        assert builder.snake_to_kebab("simple") == "simple"
        assert builder.snake_to_kebab("multiple_word_field") == "multiple-word-field"
        assert builder.snake_to_kebab("detect_columns") == "detect-columns"

    def test_cli_name_inference(self):
        """Test CLI name inference from field names."""
        builder = DynamicCLIBuilder()

        # Basic inference
        assert builder.infer_cli_name("test_field") == "--test-field"

        # With format prefix
        assert builder.infer_cli_name("detect_columns", "pdf") == "--pdf-detect-columns"

        # Boolean with True default (should get --no-* form)
        assert builder.infer_cli_name("detect_columns", "pdf", True) == "--pdf-no-detect-columns"

        # Markdown options
        assert builder.infer_cli_name("emphasis_symbol", "markdown") == "--markdown-emphasis-symbol"

    def test_argument_mapping_pdf_options(self):
        """Test mapping of PDF-specific CLI arguments with new dynamic system."""
        builder = DynamicCLIBuilder()

        # Create mock parsed args with the new naming convention
        parsed_args = Mock()
        parsed_args.input = "test.pdf"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.about = False
        parsed_args.version = False
        parsed_args.options_json = None

        # PDF options (new format)
        parsed_args.pdf_pages = "1,2,3"
        parsed_args.pdf_password = "secret"
        parsed_args.pdf_detect_columns = False  # This would be set by --pdf-no-detect-columns

        # Markdown options (new format)
        parsed_args.markdown_emphasis_symbol = "_"

        # Mock vars to simulate the argument namespace
        with patch('builtins.vars', return_value={
            'input': 'test.pdf',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'about': False,
            'version': False,
            'options_json': None,
            'pdf_pages': '1,2,3',
            'pdf_password': 'secret',
            'pdf_detect_columns': False,
            'markdown_emphasis_symbol': '_',
        }):
            options = builder.map_args_to_options(parsed_args)

        # Check PDF options mapping
        assert 'pages' in options
        assert options['pages'] == [1, 2, 3]
        assert options['password'] == 'secret'
        assert options['detect_columns'] is False

        # Check Markdown options mapping
        assert options['emphasis_symbol'] == '_'

    def test_list_int_processing(self):
        """Test processing of list_int type arguments."""
        builder = DynamicCLIBuilder()

        # Mock field and metadata for pages field
        from dataclasses import field
        mock_field = Mock()
        mock_field.type = list[int] | None
        mock_field.default = None

        metadata = {"type": "list_int"}

        # Test valid comma-separated integers
        result = builder._process_argument_value(mock_field, metadata, "1,2,3", "pdf_pages")
        assert result == [1, 2, 3]

        # Test single integer
        result = builder._process_argument_value(mock_field, metadata, "5", "pdf_pages")
        assert result == [5]

        # Test with spaces
        result = builder._process_argument_value(mock_field, metadata, "1, 2, 3", "pdf_pages")
        assert result == [1, 2, 3]

        # Test invalid input returns None
        result = builder._process_argument_value(mock_field, metadata, "1,invalid,3", "pdf_pages")
        assert result is None



@pytest.mark.unit
@pytest.mark.cli
class TestCLIParser:
    """Test CLI argument parser functionality."""

    def test_create_parser_basic(self):
        """Test basic parser creation and help text."""
        parser = create_parser()
        assert parser.prog == "all2md"
        assert "Convert documents to Markdown format" in parser.description

    def test_parser_required_arguments(self):
        """Test that input argument is optional at parser level but validated in main()."""
        parser = create_parser()

        # Should succeed with input file
        args = parser.parse_args(["test.pdf"])
        assert args.input == "test.pdf"

        # Should succeed without input file at parser level (validation happens in main)
        args = parser.parse_args([])
        assert args.input is None

        # Should succeed with --about flag and no input file
        args = parser.parse_args(["--about"])
        assert args.about is True
        assert args.input is None

    def test_parser_format_choices(self):
        """Test format argument choices."""
        parser = create_parser()

        # Valid format choices
        valid_formats = ["auto", "pdf", "docx", "pptx", "html", "eml", "rtf", "ipynb", "csv", "tsv", "xlsx", "image", "txt"]
        for fmt in valid_formats:
            args = parser.parse_args(["test.pdf", "--format", fmt])
            assert args.format == fmt

        # Invalid format choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--format", "invalid"])

    def test_parser_log_level_choices(self):
        """Test log level argument choices."""
        parser = create_parser()

        # Valid log level choices
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in valid_levels:
            args = parser.parse_args(["test.pdf", "--log-level", level])
            assert args.log_level == level

        # Invalid log level should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--log-level", "INVALID"])

    def test_parser_dynamic_arguments_exist(self):
        """Test that dynamically generated arguments exist in the parser."""
        parser = create_parser()

        # Test that PDF options exist
        args = parser.parse_args(["test.pdf", "--pdf-pages", "1,2,3"])
        assert hasattr(args, 'pdf_pages')
        assert args.pdf_pages == "1,2,3"

        # Test that HTML options exist
        args = parser.parse_args(["test.html", "--html-extract-title"])
        assert hasattr(args, 'html_extract_title')
        assert args.html_extract_title is True

        # Test that Markdown options exist
        args = parser.parse_args(["test.pdf", "--markdown-emphasis-symbol", "_"])
        assert hasattr(args, 'markdown_emphasis_symbol')
        assert args.markdown_emphasis_symbol == "_"

    def test_parser_boolean_no_flags(self):
        """Test --no-* flags for boolean options with True defaults."""
        parser = create_parser()

        # Test --pdf-no-detect-columns flag
        args = parser.parse_args(["test.pdf", "--pdf-no-detect-columns"])
        assert hasattr(args, 'pdf_detect_columns')
        assert args.pdf_detect_columns is False

        # Test --html-no-use-hash-headings flag
        args = parser.parse_args(["test.html", "--html-no-use-hash-headings"])
        assert hasattr(args, 'html_use_hash_headings')
        assert args.html_use_hash_headings is False

        # Test --markdown-no-escape-special flag
        args = parser.parse_args(["test.pdf", "--markdown-no-escape-special"])
        assert hasattr(args, 'markdown_escape_special')
        assert args.markdown_escape_special is False

    def test_parser_boolean_flags(self):
        """Test boolean flag arguments."""
        parser = create_parser()

        # Test HTML flags
        args = parser.parse_args(["test.html", "--html-extract-title", "--html-strip-dangerous-elements"])
        assert args.html_extract_title is True
        assert args.html_strip_dangerous_elements is True

        # Test PowerPoint flags
        args = parser.parse_args(["test.pptx", "--pptx-slide-numbers"])
        assert args.pptx_slide_numbers is True

        # Test negative flags
        args = parser.parse_args(["test.eml", "--eml-no-include-headers", "--eml-no-preserve-thread-structure"])
        assert args.eml_include_headers is False
        assert args.eml_preserve_thread_structure is False
