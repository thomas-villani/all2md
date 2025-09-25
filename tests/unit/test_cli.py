"""Unit tests for all2md CLI functionality.

This module tests the command-line interface components including argument parsing,
option mapping, and validation logic.
"""

import argparse
from unittest.mock import Mock, patch

import pytest

from all2md.cli import _map_cli_args_to_options, create_parser, parse_pdf_pages
from all2md.exceptions import MdparseConversionError, MdparseInputError


@pytest.mark.unit
@pytest.mark.cli
class TestCLIArgumentMapping:
    """Test CLI argument mapping functionality."""

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

    def test_argument_mapping_pdf_options(self):
        """Test mapping of PDF-specific CLI arguments."""
        # Create mock parsed args
        parsed_args = Mock()
        parsed_args.input = "test.pdf"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.attachment_mode = "alt_text"
        parsed_args.attachment_output_dir = None
        parsed_args.attachment_base_url = None
        parsed_args.markdown_emphasis_symbol = "_"
        parsed_args.markdown_bullet_symbols = "*-+"
        parsed_args.markdown_page_separator = "-----"
        parsed_args.pdf_pages = "1,2,3"
        parsed_args.pdf_password = "secret"
        parsed_args.pdf_detect_columns = False
        parsed_args.html_extract_title = False
        parsed_args.html_strip_dangerous_elements = False
        parsed_args.pptx_slide_numbers = False
        parsed_args.pptx_include_notes = True
        parsed_args.eml_include_headers = True
        parsed_args.eml_preserve_thread_structure = True

        # Mock vars() to return dict representation
        with patch('all2md.cli.vars', return_value={
            'input': 'test.pdf',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'attachment_mode': 'alt_text',
            'attachment_output_dir': None,
            'attachment_base_url': None,
            'markdown_emphasis_symbol': '_',
            'markdown_bullet_symbols': '*-+',
            'markdown_page_separator': '-----',
            'pdf_pages': '1,2,3',
            'pdf_password': 'secret',
            'pdf_detect_columns': False,
            'html_extract_title': False,
            'html_strip_dangerous_elements': False,
            'pptx_slide_numbers': False,
            'pptx_include_notes': True,
            'eml_include_headers': True,
            'eml_preserve_thread_structure': True,
        }):
            options = _map_cli_args_to_options(parsed_args)

        # Check PDF options mapping
        assert options['pages'] == [1, 2, 3]
        assert options['password'] == 'secret'
        assert options['detect_columns'] is False

        # Check Markdown options mapping
        assert options['emphasis_symbol'] == '_'

    def test_argument_mapping_html_options(self):
        """Test mapping of HTML-specific CLI arguments."""
        parsed_args = Mock()
        parsed_args.input = "test.html"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.attachment_mode = "download"
        parsed_args.attachment_output_dir = "./images"
        parsed_args.attachment_base_url = "https://example.com"
        parsed_args.markdown_emphasis_symbol = "*"
        parsed_args.markdown_bullet_symbols = "*-+"
        parsed_args.markdown_page_separator = "-----"
        parsed_args.pdf_pages = None
        parsed_args.pdf_password = None
        parsed_args.pdf_detect_columns = True
        parsed_args.html_extract_title = True
        parsed_args.html_strip_dangerous_elements = True
        parsed_args.pptx_slide_numbers = False
        parsed_args.pptx_include_notes = True
        parsed_args.eml_include_headers = True
        parsed_args.eml_preserve_thread_structure = True

        with patch('all2md.cli.vars', return_value={
            'input': 'test.html',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'attachment_mode': 'download',
            'attachment_output_dir': './images',
            'attachment_base_url': 'https://example.com',
            'markdown_emphasis_symbol': '*',
            'markdown_bullet_symbols': '*-+',
            'markdown_page_separator': '-----',
            'pdf_pages': None,
            'pdf_password': None,
            'pdf_detect_columns': True,
            'html_extract_title': True,
            'html_strip_dangerous_elements': True,
            'pptx_slide_numbers': False,
            'pptx_include_notes': True,
            'eml_include_headers': True,
            'eml_preserve_thread_structure': True,
        }):
            options = _map_cli_args_to_options(parsed_args)

        # Check HTML options mapping
        assert options['extract_title'] is True
        assert options['strip_dangerous_elements'] is True

        # Check attachment options mapping
        assert options['attachment_mode'] == 'download'
        assert options['attachment_output_dir'] == './images'
        assert options['attachment_base_url'] == 'https://example.com'

    def test_argument_mapping_pptx_options(self):
        """Test mapping of PowerPoint-specific CLI arguments."""
        parsed_args = Mock()
        parsed_args.input = "test.pptx"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.attachment_mode = "base64"
        parsed_args.attachment_output_dir = None
        parsed_args.attachment_base_url = None
        parsed_args.markdown_emphasis_symbol = "*"
        parsed_args.markdown_bullet_symbols = "*-+"
        parsed_args.markdown_page_separator = "-----"
        parsed_args.pdf_pages = None
        parsed_args.pdf_password = None
        parsed_args.pdf_detect_columns = True
        parsed_args.html_extract_title = False
        parsed_args.html_strip_dangerous_elements = False
        parsed_args.pptx_slide_numbers = True
        parsed_args.pptx_include_notes = False
        parsed_args.eml_include_headers = True
        parsed_args.eml_preserve_thread_structure = True

        with patch('all2md.cli.vars', return_value={
            'input': 'test.pptx',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'attachment_mode': 'base64',
            'attachment_output_dir': None,
            'attachment_base_url': None,
            'markdown_emphasis_symbol': '*',
            'markdown_bullet_symbols': '*-+',
            'markdown_page_separator': '-----',
            'pdf_pages': None,
            'pdf_password': None,
            'pdf_detect_columns': True,
            'html_extract_title': False,
            'html_strip_dangerous_elements': False,
            'pptx_slide_numbers': True,
            'pptx_include_notes': False,
            'eml_include_headers': True,
            'eml_preserve_thread_structure': True,
        }):
            options = _map_cli_args_to_options(parsed_args)

        # Check PowerPoint options mapping
        assert options['slide_numbers'] is True
        assert options['include_notes'] is False
        assert options['attachment_mode'] == 'base64'

    def test_argument_mapping_eml_options(self):
        """Test mapping of email-specific CLI arguments."""
        parsed_args = Mock()
        parsed_args.input = "test.eml"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.attachment_mode = "skip"
        parsed_args.attachment_output_dir = None
        parsed_args.attachment_base_url = None
        parsed_args.markdown_emphasis_symbol = "*"
        parsed_args.markdown_bullet_symbols = "*-+"
        parsed_args.markdown_page_separator = "-----"
        parsed_args.pdf_pages = None
        parsed_args.pdf_password = None
        parsed_args.pdf_detect_columns = True
        parsed_args.html_extract_title = False
        parsed_args.html_strip_dangerous_elements = False
        parsed_args.pptx_slide_numbers = False
        parsed_args.pptx_include_notes = True
        parsed_args.eml_include_headers = False
        parsed_args.eml_preserve_thread_structure = False

        with patch('all2md.cli.vars', return_value={
            'input': 'test.eml',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'attachment_mode': 'skip',
            'attachment_output_dir': None,
            'attachment_base_url': None,
            'markdown_emphasis_symbol': '*',
            'markdown_bullet_symbols': '*-+',
            'markdown_page_separator': '-----',
            'pdf_pages': None,
            'pdf_password': None,
            'pdf_detect_columns': True,
            'html_extract_title': False,
            'html_strip_dangerous_elements': False,
            'pptx_slide_numbers': False,
            'pptx_include_notes': True,
            'eml_include_headers': False,
            'eml_preserve_thread_structure': False,
        }):
            options = _map_cli_args_to_options(parsed_args)

        # Check email options mapping
        assert options['include_headers'] is False
        assert options['preserve_thread_structure'] is False
        assert options['attachment_mode'] == 'skip'

    def test_argument_mapping_defaults_excluded(self):
        """Test that default values are not included in options."""
        parsed_args = Mock()
        parsed_args.input = "test.html"
        parsed_args.out = None
        parsed_args.format = "auto"
        parsed_args.log_level = "WARNING"
        parsed_args.attachment_mode = "alt_text"  # Default value
        parsed_args.attachment_output_dir = None
        parsed_args.attachment_base_url = None
        parsed_args.markdown_emphasis_symbol = "*"  # Default value
        parsed_args.markdown_bullet_symbols = "*-+"  # Default value
        parsed_args.markdown_page_separator = "-----"  # Default value
        parsed_args.pdf_pages = None
        parsed_args.pdf_password = None
        parsed_args.pdf_detect_columns = True  # Default value
        parsed_args.html_extract_title = False  # Default value
        parsed_args.html_strip_dangerous_elements = False  # Default value
        parsed_args.pptx_slide_numbers = False  # Default value
        parsed_args.pptx_include_notes = True  # Default value
        parsed_args.eml_include_headers = True  # Default value
        parsed_args.eml_preserve_thread_structure = True  # Default value

        with patch('all2md.cli.vars', return_value={
            'input': 'test.html',
            'out': None,
            'format': 'auto',
            'log_level': 'WARNING',
            'attachment_mode': 'alt_text',
            'attachment_output_dir': None,
            'attachment_base_url': None,
            'markdown_emphasis_symbol': '*',
            'markdown_bullet_symbols': '*-+',
            'markdown_page_separator': '-----',
            'pdf_pages': None,
            'pdf_password': None,
            'pdf_detect_columns': True,
            'html_extract_title': False,
            'html_strip_dangerous_elements': False,
            'pptx_slide_numbers': False,
            'pptx_include_notes': True,
            'eml_include_headers': True,
            'eml_preserve_thread_structure': True,
        }):
            options = _map_cli_args_to_options(parsed_args)

        # Should be empty since all are default values
        expected_empty_keys = [
            'attachment_mode', 'emphasis_symbol', 'bullet_symbols', 'page_separator',
            'extract_title', 'strip_dangerous_elements', 'slide_numbers',
            'include_headers', 'preserve_thread_structure', 'detect_columns'
        ]

        for key in expected_empty_keys:
            assert key not in options, f"Default value {key} should not be in options"


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
        """Test that required arguments are properly configured."""
        parser = create_parser()

        # Should succeed with input file
        args = parser.parse_args(["test.pdf"])
        assert args.input == "test.pdf"

        # Should fail without input file
        with pytest.raises(SystemExit):
            parser.parse_args([])

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

    def test_parser_attachment_mode_choices(self):
        """Test attachment mode argument choices."""
        parser = create_parser()

        # Valid attachment mode choices
        valid_modes = ["skip", "alt_text", "download", "base64"]
        for mode in valid_modes:
            args = parser.parse_args(["test.pdf", "--attachment-mode", mode])
            assert args.attachment_mode == mode

        # Invalid attachment mode should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["test.pdf", "--attachment-mode", "invalid"])

    def test_parser_pdf_detect_columns_defaults(self):
        """Test PDF detect columns default behavior."""
        parser = create_parser()

        # Default should be True
        args = parser.parse_args(["test.pdf"])
        assert args.pdf_detect_columns is True

        # --pdf-detect-columns should set True
        args = parser.parse_args(["test.pdf", "--pdf-detect-columns"])
        assert args.pdf_detect_columns is True

        # --pdf-no-detect-columns should set False
        args = parser.parse_args(["test.pdf", "--pdf-no-detect-columns"])
        assert args.pdf_detect_columns is False

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