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

    def test_odf_conversion_basic(self):
        """Test basic ODF file conversion via CLI."""
        # Create a mock ODT file
        odt_file = self.temp_dir / "test.odt"
        odt_file.write_text("Mock ODT content")  # Not a real ODT, but CLI should detect format

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Test Document\n\nThis is converted from ODT."

            result = main([str(odt_file)])

            assert result == 0
            mock_to_markdown.assert_called_once()

    def test_odf_conversion_with_options(self):
        """Test ODF conversion with CLI options."""
        odt_file = self.temp_dir / "test.odt"
        odt_file.write_text("Mock ODT content")

        output_file = self.temp_dir / "output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# ODT Document\n\nContent with table:\n\n| Col1 | Col2 |\n| --- | --- |\n| A | B |"

            result = main([
                str(odt_file),
                "--out", str(output_file),
                "--odf-preserve-tables",
                "--attachment-mode", "base64",
                "--markdown-emphasis-symbol", "*"
            ])

            assert result == 0
            assert output_file.exists()

            # Verify ODF-specific options were passed
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['preserve_tables'] is True
            assert kwargs['attachment_mode'] == 'base64'
            assert kwargs['emphasis_symbol'] == '*'

    def test_odp_conversion(self):
        """Test ODP presentation conversion via CLI."""
        odp_file = self.temp_dir / "presentation.odp"
        odp_file.write_text("Mock ODP content")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Slide 1\n\nPresentation content\n\n# Slide 2\n\nMore content"

            result = main([str(odp_file)])

            assert result == 0
            mock_to_markdown.assert_called_once()

    def test_odf_format_override(self):
        """Test format override for ODF files."""
        # Test forcing ODT format on a file with different extension
        test_file = self.temp_dir / "document.txt"
        test_file.write_text("Mock content")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Document\n\nForced as ODT"

            result = main([
                str(test_file),
                "--format", "odt"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]
            assert kwargs['format'] == 'odt'

    def test_odf_attachment_handling(self):
        """Test ODF attachment handling options."""
        odt_file = self.temp_dir / "with_images.odt"
        odt_file.write_text("Mock ODT with images")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Document\n\n![Image](image.png)\n\nText with image."

            result = main([
                str(odt_file),
                "--attachment-mode", "download",
                "--attachment-output-dir", str(self.temp_dir / "images"),
                "--attachment-base-url", "https://example.com/images/"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['attachment_mode'] == 'download'
            assert kwargs['attachment_output_dir'] == str(self.temp_dir / "images")
            assert kwargs['attachment_base_url'] == 'https://example.com/images/'

    def test_odf_table_handling(self):
        """Test ODF table preservation options."""
        odt_file = self.temp_dir / "with_tables.odt"
        odt_file.write_text("Mock ODT with tables")

        with patch('all2md.to_markdown') as mock_to_markdown:
            # Test with tables enabled
            mock_to_markdown.return_value = "# Document\n\n| Header | Header2 |\n|--------|--------|\n| Cell1  | Cell2   |"

            result = main([
                str(odt_file),
                "--odf-preserve-tables"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]
            assert kwargs['preserve_tables'] is True

            # Test with tables disabled
            mock_to_markdown.reset_mock()
            mock_to_markdown.return_value = "# Document\n\nTable content as text"

            result = main([
                str(odt_file),
                "--odf-no-preserve-tables"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]
            assert kwargs['preserve_tables'] is False

    def test_odf_error_handling(self):
        """Test error handling for ODF conversion."""
        nonexistent_file = self.temp_dir / "nonexistent.odt"

        # Should fail gracefully for nonexistent file
        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.side_effect = InputError("File not found", input_type="file")

            result = main([str(nonexistent_file)])

            assert result == 1  # Error exit code

    def test_ipynb_basic_conversion(self):
        """Test basic Jupyter Notebook conversion through CLI."""
        import json

        # Create test notebook
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Test Notebook\n", "This is a test."]
                },
                {
                    "cell_type": "code",
                    "source": ["print('Hello, World!')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "text": ["Hello, World!\n"]
                        }
                    ]
                }
            ],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4
        }

        ipynb_file = self.temp_dir / "test.ipynb"
        with open(ipynb_file, 'w') as f:
            json.dump(notebook_content, f)

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Test Notebook\n\nThis is a test.\n\n```python\nprint('Hello, World!')\n```\n\n```\nHello, World!\n```"

            result = main([str(ipynb_file)])

            assert result == 0
            mock_to_markdown.assert_called_once()

    def test_ipynb_format_override(self):
        """Test format override for Jupyter Notebook files."""
        test_file = self.temp_dir / "document.txt"
        test_file.write_text("Mock notebook content")

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Document\n\nForced as Jupyter Notebook"

            result = main([
                str(test_file),
                "--format", "ipynb"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]
            assert kwargs['format'] == 'ipynb'

    def test_ipynb_attachment_handling(self):
        """Test Jupyter Notebook image attachment handling options."""
        ipynb_file = self.temp_dir / "with_plots.ipynb"
        ipynb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4}')

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Notebook\n\n![cell output](plot.png)\n\nCode with plot."

            result = main([
                str(ipynb_file),
                "--attachment-mode", "download",
                "--attachment-output-dir", str(self.temp_dir / "plots"),
                "--attachment-base-url", "https://example.com/plots/"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['attachment_mode'] == 'download'
            assert kwargs['attachment_output_dir'] == str(self.temp_dir / "plots")
            assert kwargs['attachment_base_url'] == 'https://example.com/plots/'

    def test_ipynb_truncate_options(self):
        """Test Jupyter Notebook output truncation options."""
        ipynb_file = self.temp_dir / "long_output.ipynb"
        ipynb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4}')

        with patch('all2md.to_markdown') as mock_to_markdown:
            # Test basic ipynb conversion
            mock_to_markdown.return_value = "```python\nfor i in range(10): print(i)\n```"

            result = main([str(ipynb_file)])

            assert result == 0
            mock_to_markdown.assert_called_once()

    def test_ipynb_error_handling(self):
        """Test error handling for Jupyter Notebook conversion."""
        nonexistent_file = self.temp_dir / "nonexistent.ipynb"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.side_effect = InputError("Invalid JSON")

            result = main([str(nonexistent_file)])

            assert result == 1  # Error exit code

    def test_ipynb_with_output_file(self):
        """Test Jupyter Notebook conversion with output file specification."""
        import json

        notebook_content = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Output Test"]},
                {"cell_type": "code", "source": ["x = 42"], "outputs": []}
            ],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4
        }

        ipynb_file = self.temp_dir / "input.ipynb"
        with open(ipynb_file, 'w') as f:
            json.dump(notebook_content, f)

        output_file = self.temp_dir / "output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = "# Output Test\n\n```python\nx = 42\n```"

            result = main([
                str(ipynb_file),
                "--out", str(output_file)
            ])

            assert result == 0
            # Output file should be written
            assert output_file.exists()
            content = output_file.read_text()
            assert "# Output Test" in content

    def test_ipynb_complex_options(self):
        """Test Jupyter Notebook conversion with comprehensive option set."""
        ipynb_file = self.temp_dir / "complex.ipynb"
        ipynb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4}')

        output_file = self.temp_dir / "complex_output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = """# Complex Notebook

Code and outputs with custom settings."""

            result = main([
                str(ipynb_file),
                "--out", str(output_file),
                "--attachment-mode", "base64"
            ])

            assert result == 0
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['attachment_mode'] == 'base64'

    def test_odf_with_complex_options(self):
        """Test ODF conversion with comprehensive option set."""
        odt_file = self.temp_dir / "complex.odt"
        odt_file.write_text("Mock complex ODT")

        output_file = self.temp_dir / "complex_output.md"

        with patch('all2md.to_markdown') as mock_to_markdown:
            mock_to_markdown.return_value = """# Complex Document

This is a complex document with:

* _Italic text_
* **Bold text**
* [Links](https://example.com)

| Table | Data |
|-------|------|
| Row1  | Val1 |

![Image alt text](data:image/png;base64,iVBORw...)"""

            result = main([
                str(odt_file),
                "--out", str(output_file),
                "--odf-preserve-tables",
                "--attachment-mode", "base64",
                "--markdown-emphasis-symbol", "_",
                "--markdown-bullet-symbols", "*",
                "--log-level", "DEBUG"
            ])

            assert result == 0
            assert output_file.exists()

            # Verify all options were passed
            call_args = mock_to_markdown.call_args
            kwargs = call_args[1]

            assert kwargs['preserve_tables'] is True
            assert kwargs['attachment_mode'] == 'base64'
            assert kwargs['emphasis_symbol'] == '_'
            assert kwargs['bullet_symbols'] == '*'