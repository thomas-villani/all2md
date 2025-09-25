"""Integration tests for all2md CLI functionality.

This module tests end-to-end CLI functionality including file processing,
option propagation, and error handling.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from all2md.cli import main
from all2md.exceptions import MarkdownConversionError, InputError
from tests.utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.integration
@pytest.mark.cli
class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_html_conversion_with_options(self):
        """Test HTML conversion with various CLI options."""
        # Create test HTML file
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Document</title>
</head>
<body>
    <h1>Main Heading</h1>
    <p>This is a <strong>test</strong> document with <em>emphasis</em>.</p>
    <ul>
        <li>First item</li>
        <li>Second item</li>
    </ul>
    <script>alert('dangerous');</script>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content)

        output_file = self.temp_dir / "output.md"

        # Test with title extraction and dangerous element stripping
        result = main([
            str(html_file),
            "--out", str(output_file),
            "--html-extract-title",
            "--html-strip-dangerous-elements",
            "--markdown-emphasis-symbol", "_"
        ])

        assert result == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "# Test Document" in content  # Title should be extracted
        assert "Main Heading" in content
        assert "_emphasis_" in content  # Should use underscore emphasis
        assert "alert" not in content  # Script should be stripped

    def test_pdf_conversion_with_pages(self):
        """Test PDF conversion with page selection."""
        # Create a mock PDF file (we'll mock the conversion)
        pdf_file = self.temp_dir / "test.pdf"
        pdf_file.write_text("Mock PDF content")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Test PDF\n\nContent from pages 1-2"

            result = main([
                str(pdf_file),
                "--pdf-pages", "1,2",
                "--pdf-password", "secret",
                "--pdf-no-detect-columns"
            ])

            assert result == 0
            # Verify the correct options were passed
            mock_to_markdown.assert_called_once()
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert 'pages' in kwargs
            assert kwargs['pages'] == [1, 2]
            assert kwargs['password'] == 'secret'
            assert kwargs['detect_columns'] is False

    def test_format_override(self):
        """Test format override functionality."""
        # Create an HTML file that we'll treat as text
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML Content</h1>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "<h1>HTML Content</h1>"

            result = main([
                str(html_file),
                "--format", "txt"
            ])

            assert result == 0
            # Verify format was overridden
            call_args = mock_to_markdown.call_args
            assert call_args[1]['format'] == 'txt'

    def test_attachment_validation_warning(self, capsys):
        """Test warning when attachment-output-dir used without download mode."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "Test"

            result = main([
                str(html_file),
                "--attachment-output-dir", "./images"
            ])

            assert result == 0

            # Check warning was printed
            captured = capsys.readouterr()
            assert "Warning" in captured.err
            assert "attachment mode is 'alt_text'" in captured.err

    def test_logging_level_configuration(self):
        """Test that logging level is properly configured."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "Test"

            with patch('logging.basicConfig') as mock_logging:
                result = main([
                    str(html_file),
                    "--log-level", "DEBUG"
                ])

                assert result == 0
                # Verify logging was configured with DEBUG level
                mock_logging.assert_called_once()
                call_args = mock_logging.call_args
                assert call_args[1]['level'] == 10  # logging.DEBUG

    def test_attachment_options_propagation(self):
        """Test that attachment options are properly propagated."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test <img src='image.png' alt='test'></p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "Test ![test](images/image.png)"

            result = main([
                str(html_file),
                "--attachment-mode", "download",
                "--attachment-output-dir", "./images",
                "--attachment-base-url", "https://example.com"
            ])

            assert result == 0

            # Verify attachment options were passed
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['attachment_mode'] == 'download'
            assert kwargs['attachment_output_dir'] == './images'
            assert kwargs['attachment_base_url'] == 'https://example.com'

    def test_markdown_options_propagation(self):
        """Test that Markdown formatting options are properly propagated."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p><em>italic</em> and <ul><li>item</li></ul></p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "_italic_ and\n\n- item"

            result = main([
                str(html_file),
                "--markdown-emphasis-symbol", "_",
                "--markdown-bullet-symbols", "•→◦",
                "--markdown-page-separator", "====="
            ])

            assert result == 0

            # Verify Markdown options were passed
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['emphasis_symbol'] == '_'
            assert kwargs['bullet_symbols'] == '•→◦'
            assert kwargs['page_separator'] == '====='

    def test_file_not_found_error(self, capsys):
        """Test error handling when input file doesn't exist."""
        nonexistent_file = self.temp_dir / "nonexistent.pdf"

        result = main([str(nonexistent_file)])

        assert result == 1
        captured = capsys.readouterr()
        assert "Error: Input file does not exist" in captured.err

    def test_conversion_error_handling(self, capsys):
        """Test error handling for conversion errors."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.side_effect = MarkdownConversionError("Test conversion error")

            result = main([str(html_file)])

            assert result == 1
            captured = capsys.readouterr()
            assert "Error: Test conversion error" in captured.err

    def test_import_error_handling(self, capsys):
        """Test error handling for missing dependencies."""
        pdf_file = self.temp_dir / "test.pdf"
        pdf_file.write_text("Mock PDF")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.side_effect = ImportError("PyMuPDF not found")

            result = main([str(pdf_file)])

            assert result == 1
            captured = capsys.readouterr()
            assert "Missing dependency" in captured.err
            assert "pip install all2md[full]" in captured.err

    def test_unexpected_error_handling(self, capsys):
        """Test error handling for unexpected errors."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.side_effect = RuntimeError("Unexpected error")

            result = main([str(html_file)])

            assert result == 1
            captured = capsys.readouterr()
            assert "Unexpected error: Unexpected error" in captured.err

    def test_output_file_creation(self):
        """Test output file creation and directory handling."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test</h1>")

        # Create nested output path
        output_dir = self.temp_dir / "nested" / "dir"
        output_file = output_dir / "output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Test"

            result = main([
                str(html_file),
                "--out", str(output_file)
            ])

            assert result == 0
            assert output_file.exists()
            assert output_file.read_text(encoding="utf-8") == "# Test"

    def test_stdout_output(self, capsys):
        """Test output to stdout when no output file specified."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test</h1>")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Test Content"

            result = main([str(html_file)])

            assert result == 0
            captured = capsys.readouterr()
            assert "# Test Content" in captured.out

    def test_complex_option_combination(self):
        """Test complex combination of multiple options."""
        html_file = self.temp_dir / "complex.html"
        html_file.write_text("""
        <html>
        <head><title>Complex Test</title></head>
        <body>
            <h1>Heading</h1>
            <p><strong>Bold</strong> and <em>italic</em> text.</p>
            <img src="test.png" alt="Test image">
            <script>alert('remove me');</script>
        </body>
        </html>
        """)

        output_file = self.temp_dir / "complex_output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Complex Test\n\n## Heading\n\n**Bold** and _italic_ text.\n\n![Test image](images/test.png)"

            result = main([
                str(html_file),
                "--out", str(output_file),
                "--format", "html",
                "--html-extract-title",
                "--html-strip-dangerous-elements",
                "--attachment-mode", "download",
                "--attachment-output-dir", "images",
                "--markdown-emphasis-symbol", "_",
                "--markdown-bullet-symbols", "•→◦",
                "--log-level", "INFO"
            ])

            assert result == 0

            # Verify all options were passed correctly
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['format'] == 'html'
            assert kwargs['extract_title'] is True
            assert kwargs['strip_dangerous_elements'] is True
            assert kwargs['attachment_mode'] == 'download'
            assert kwargs['attachment_output_dir'] == 'images'
            assert kwargs['emphasis_symbol'] == '_'
            assert kwargs['bullet_symbols'] == '•→◦'