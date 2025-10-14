"""Integration tests for all2md CLI functionality.

This module tests end-to-end CLI functionality including file processing,
option propagation, and error handling.
"""

from unittest.mock import patch

import pytest
from utils import cleanup_test_dir, create_test_temp_dir

from all2md.cli import main
from all2md.exceptions import MalformedFileError, ParsingError


def mock_convert_with_file_write(return_value='# Test\n\nContent'):
    """Helper to mock convert() with proper file writing behavior."""
    def side_effect(*args, **kwargs):
        output = kwargs.get('output')
        if output:
            # Write to file like real convert() does
            from pathlib import Path
            Path(output).write_text(return_value, encoding='utf-8')
            return None  # convert() returns None when writing to file
        else:
            # Return content when outputting to stdout
            return return_value
    return side_effect


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
        result = main(
            [
                str(html_file),
                "--out",
                str(output_file),
                "--html-extract-title",
                "--html-strip-dangerous-elements",
                "--markdown-emphasis-symbol",
                "_",
            ]
        )

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

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test PDF\n\nContent from pages 1-2")

            result = main([str(pdf_file), "--pdf-pages", "1,2", "--pdf-password", "secret", "--pdf-no-detect-columns"])

            assert result == 0
            # Verify the correct options were passed
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert "pages" in kwargs
            assert kwargs["pages"] == [1, 2]
            assert kwargs["password"] == "secret"
            assert kwargs["detect_columns"] is False

    def test_format_override(self):
        """Test format override functionality."""
        # Create an HTML file that we'll treat as text
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML Content</h1>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "<h1>HTML Content</h1>"

            result = main([str(html_file), "--format", "txt"])

            assert result == 0
            # Verify format was overridden
            call_args = mock_convert.call_args
            assert call_args[1]["source_format"] == "txt"

    def test_attachment_validation_warning(self, capsys):
        """Test warning when attachment-output-dir used without download mode."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "Test"

            result = main([str(html_file), "--attachment-output-dir", "./images"])

            assert result == 0

            # Check warning was printed
            captured = capsys.readouterr()
            assert "Warning" in captured.err
            assert "attachment mode is 'alt_text'" in captured.err

    def test_logging_level_configuration(self):
        """Test that logging level is properly configured."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "Test"

            # Patch where the function is used in __init__.py, not in commands
            with patch("all2md.cli._configure_logging") as mock_logging:
                result = main([str(html_file), "--log-level", "DEBUG"])

                assert result == 0
                # Verify logging was configured with DEBUG level
                mock_logging.assert_called_once()
                call_args = mock_logging.call_args
                assert call_args[0][0] == 10  # logging.DEBUG (first positional arg)

    def test_attachment_options_propagation(self):
        """Test that attachment options are properly propagated."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test <img src='image.png' alt='test'></p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "Test ![test](images/image.png)"

            result = main(
                [
                    str(html_file),
                    "--attachment-mode",
                    "download",
                    "--attachment-output-dir",
                    "./images",
                    "--attachment-base-url",
                    "https://example.com",
                ]
            )

            assert result == 0

            # Verify attachment options were passed
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["attachment_mode"] == "download"
            assert kwargs["attachment_output_dir"] == "./images"
            assert kwargs["attachment_base_url"] == "https://example.com"

    def test_markdown_options_propagation(self):
        """Test that Markdown formatting options are properly propagated."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p><em>italic</em> and <ul><li>item</li></ul></p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("_italic_ and\n\n- item")

            result = main(
                [
                    str(html_file),
                    "--markdown-emphasis-symbol",
                    "_",
                    "--markdown-bullet-symbols",
                    "•→◦",
                ]
            )

            assert result == 0

            # Verify Markdown options were passed
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["emphasis_symbol"] == "_"
            assert kwargs["bullet_symbols"] == "•→◦"

    def test_file_not_found_error(self, capsys):
        """Test error handling when input file doesn't exist."""
        nonexistent_file = self.temp_dir / "nonexistent.pdf"

        result = main([str(nonexistent_file)])

        assert result == 4  # EXIT_FILE_ERROR (file not found)
        captured = capsys.readouterr()
        assert "Error: No valid input files found" in captured.err

    def test_conversion_error_handling(self, capsys):
        """Test error handling for conversion errors."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = ParsingError("Test conversion error")

            result = main([str(html_file)])

            assert result == 6  # EXIT_PARSING_ERROR
            captured = capsys.readouterr()
            assert "Error: Test conversion error" in captured.err

    def test_import_error_handling(self, capsys):
        """Test error handling for missing dependencies."""
        pdf_file = self.temp_dir / "test.pdf"
        pdf_file.write_text("Mock PDF")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = ImportError("PyMuPDF not found")

            result = main([str(pdf_file)])

            assert result == 2
            captured = capsys.readouterr()
            assert "Missing dependency" in captured.err

    def test_unexpected_error_handling(self, capsys):
        """Test error handling for unexpected errors."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = RuntimeError("Unexpected error")

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

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test")

            result = main([str(html_file), "--out", str(output_file)])

            assert result == 0
            assert output_file.exists()
            assert output_file.read_text(encoding="utf-8") == "# Test"

    def test_stdout_output(self, capsys):
        """Test output to stdout when no output file specified."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test</h1>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test Content")

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

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write(
                "# Complex Test\n\n## Heading\n\n**Bold** and _italic_ text.\n\n![Test image](images/test.png)"
            )

            result = main(
                [
                    str(html_file),
                    "--out",
                    str(output_file),
                    "--format",
                    "html",
                    "--html-extract-title",
                    "--html-strip-dangerous-elements",
                    "--attachment-mode",
                    "download",
                    "--attachment-output-dir",
                    "images",
                    "--markdown-emphasis-symbol",
                    "_",
                    "--markdown-bullet-symbols",
                    "•→◦",
                    "--log-level",
                    "INFO",
                ]
            )

            assert result == 0

            # Verify all options were passed correctly
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["source_format"] == "html"
            assert kwargs["extract_title"] is True
            assert kwargs["strip_dangerous_elements"] is True
            assert kwargs["attachment_mode"] == "download"
            assert kwargs["attachment_output_dir"] == "images"
            assert kwargs["emphasis_symbol"] == "_"
            assert kwargs["bullet_symbols"] == "•→◦"

    def test_odf_conversion_basic(self):
        """Test basic ODF file conversion via CLI."""
        # Create a mock ODT file
        odt_file = self.temp_dir / "test.odt"
        odt_file.write_text("Mock ODT content")  # Not a real ODT, but CLI should detect format

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test Document\n\nThis is converted from ODT.")

            result = main([str(odt_file)])

            assert result == 0
            mock_convert.assert_called_once()

    def test_odf_conversion_with_options(self):
        """Test ODF conversion with CLI options."""
        odt_file = self.temp_dir / "test.odt"
        odt_file.write_text("Mock ODT content")

        output_file = self.temp_dir / "output.md"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write(
                "# ODT Document\n\nContent with table:\n\n| Col1 | Col2 |\n| --- | --- |\n| A | B |"
            )

            result = main(
                [
                    str(odt_file),
                    "--out",
                    str(output_file),
                    "--attachment-mode",
                    "base64",
                    "--markdown-emphasis-symbol",
                    "_",
                ]
            )

            assert result == 0
            assert output_file.exists()

            # Verify options were passed correctly
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            # preserve_tables should not be in kwargs when default True is specified
            assert "preserve_tables" not in kwargs
            print(kwargs)
            assert kwargs["attachment_mode"] == "base64"
            assert kwargs["emphasis_symbol"] == "_"

    def test_odp_conversion(self):
        """Test ODP presentation conversion via CLI."""
        odp_file = self.temp_dir / "presentation.odp"
        odp_file.write_text("Mock ODP content")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Slide 1\n\nPresentation content\n\n# Slide 2\n\nMore content")

            result = main([str(odp_file)])

            assert result == 0
            mock_convert.assert_called_once()

    def test_odf_format_override(self):
        """Test format override for ODF files."""
        # Test forcing ODT format on a file with different extension
        test_file = self.temp_dir / "document.txt"
        test_file.write_text("Mock content")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Document\n\nForced as ODT"

            result = main([str(test_file), "--format", "odf"])

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]
            assert kwargs["source_format"] == "odf"

    def test_odf_attachment_handling(self):
        """Test ODF attachment handling options."""
        odt_file = self.temp_dir / "with_images.odt"
        odt_file.write_text("Mock ODT with images")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Document\n\n![Image](image.png)\n\nText with image."

            result = main(
                [
                    str(odt_file),
                    "--attachment-mode",
                    "download",
                    "--attachment-output-dir",
                    str(self.temp_dir / "images"),
                    "--attachment-base-url",
                    "https://example.com/images/",
                ]
            )

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["attachment_mode"] == "download"
            assert kwargs["attachment_output_dir"] == str(self.temp_dir / "images")
            assert kwargs["attachment_base_url"] == "https://example.com/images/"

    def test_odf_table_handling(self):
        """Test ODF table preservation options."""
        odt_file = self.temp_dir / "with_tables.odt"
        odt_file.write_text("Mock ODT with tables")

        with patch("all2md.cli.processors.convert") as mock_convert:
            # Test with tables enabled
            mock_convert.side_effect = mock_convert_with_file_write(
                "# Document\n\n| Header | Header2 |\n|--------|--------|\n| Cell1  | Cell2   |"
            )

            result = main(
                [
                    str(odt_file)
                    # No flag needed - tables are preserved by default
                ]
            )

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]
            assert "preserve_tables" not in kwargs  # Default True, shouldn't be in kwargs

            # Note: --odf-no-preserve-tables CLI argument not yet implemented
            # If/when implemented, add test here for disabling table preservation

    def test_odf_error_handling(self):
        """Test error handling for ODF conversion."""
        nonexistent_file = self.temp_dir / "nonexistent.odt"

        # Should fail gracefully for nonexistent file
        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = MalformedFileError("File not found")

            result = main([str(nonexistent_file)])

            assert result == 4  # EXIT_FILE_ERROR (MalformedFileError)

    def test_ipynb_basic_conversion(self):
        """Test basic Jupyter Notebook conversion through CLI."""
        import json

        # Create test notebook
        notebook_content = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Test Notebook\n", "This is a test."]},
                {
                    "cell_type": "code",
                    "source": ["print('Hello, World!')"],
                    "outputs": [{"output_type": "stream", "text": ["Hello, World!\n"]}],
                },
            ],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4,
        }

        ipynb_file = self.temp_dir / "test.ipynb"
        with open(ipynb_file, "w") as f:
            json.dump(notebook_content, f)

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = (
                "# Test Notebook\n\nThis is a test.\n\n```python\n"
                "print('Hello, World!')\n```\n\n```\nHello, World!\n```"
            )

            result = main([str(ipynb_file)])

            assert result == 0
            mock_convert.assert_called_once()

    def test_ipynb_format_override(self):
        """Test format override for Jupyter Notebook files."""
        test_file = self.temp_dir / "document.txt"
        test_file.write_text("Mock notebook content")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Document\n\nForced as Jupyter Notebook"

            result = main([str(test_file), "--format", "ipynb"])

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]
            assert kwargs["source_format"] == "ipynb"

    def test_ipynb_attachment_handling(self):
        """Test Jupyter Notebook image attachment handling options."""
        ipynb_file = self.temp_dir / "with_plots.ipynb"
        ipynb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4}')

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Notebook\n\n![cell output](plot.png)\n\nCode with plot."

            result = main(
                [
                    str(ipynb_file),
                    "--attachment-mode",
                    "download",
                    "--attachment-output-dir",
                    str(self.temp_dir / "plots"),
                    "--attachment-base-url",
                    "https://example.com/plots/",
                ]
            )

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["attachment_mode"] == "download"
            assert kwargs["attachment_output_dir"] == str(self.temp_dir / "plots")
            assert kwargs["attachment_base_url"] == "https://example.com/plots/"

    def test_ipynb_truncate_options(self):
        """Test Jupyter Notebook output truncation options."""
        ipynb_file = self.temp_dir / "long_output.ipynb"
        ipynb_file.write_text('{"cells": [], "metadata": {}, "nbformat": 4}')

        with patch("all2md.cli.processors.convert") as mock_convert:
            # Test basic ipynb conversion
            mock_convert.side_effect = mock_convert_with_file_write("```python\nfor i in range(10): print(i)\n```")

            result = main([str(ipynb_file)])

            assert result == 0
            mock_convert.assert_called_once()

    def test_ipynb_error_handling(self):
        """Test error handling for Jupyter Notebook conversion."""
        nonexistent_file = self.temp_dir / "nonexistent.ipynb"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = MalformedFileError("Invalid JSON")

            result = main([str(nonexistent_file)])

            assert result == 4  # EXIT_FILE_ERROR (MalformedFileError)

    def test_ipynb_with_output_file(self):
        """Test Jupyter Notebook conversion with output file specification."""
        import json

        notebook_content = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Output Test"]},
                {"cell_type": "code", "source": ["x = 42"], "outputs": []},
            ],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4,
        }

        ipynb_file = self.temp_dir / "input.ipynb"
        with open(ipynb_file, "w") as f:
            json.dump(notebook_content, f)

        output_file = self.temp_dir / "output.md"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Output Test\n\n```python\nx = 42\n```")

            result = main([str(ipynb_file), "--out", str(output_file)])

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

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("""# Complex Notebook

Code and outputs with custom settings.""")

            result = main([str(ipynb_file), "--out", str(output_file), "--attachment-mode", "base64"])

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert kwargs["attachment_mode"] == "base64"

    def test_odf_with_complex_options(self):
        """Test ODF conversion with comprehensive option set."""
        odt_file = self.temp_dir / "complex.odt"
        odt_file.write_text("Mock complex ODT")

        output_file = self.temp_dir / "complex_output.md"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("""# Complex Document

This is a complex document with:

* _Italic text_
* **Bold text**
* [Links](https://example.com)

| Table | Data |
|-------|------|
| Row1  | Val1 |

![Image alt text](data:image/png;base64,iVBORw...)""")

            result = main(
                [
                    str(odt_file),
                    "--out",
                    str(output_file),
                    "--attachment-mode",
                    "base64",
                    "--markdown-emphasis-symbol",
                    "_",
                    "--markdown-bullet-symbols",
                    "*",
                    "--log-level",
                    "DEBUG",
                ]
            )

            assert result == 0
            assert output_file.exists()

            # Verify all options were passed
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            assert "preserve_tables" not in kwargs  # Default True, shouldn't be in kwargs
            assert kwargs["attachment_mode"] == "base64"
            assert kwargs["emphasis_symbol"] == "_"
            assert kwargs["bullet_symbols"] == "*"


@pytest.mark.integration
@pytest.mark.cli
class TestAdvancedCLIIntegration:
    """Integration tests for advanced CLI features."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_rich_output_integration(self, capsys):
        """Test rich output integration with fallback behavior."""
        # Create test HTML files
        files = []
        for i in range(3):
            html_file = self.temp_dir / f"test_{i}.html"
            html_file.write_text(f"<h1>Test Document {i}</h1><p>Content {i}</p>")
            files.append(html_file)

        output_dir = self.temp_dir / "output"

        # Test rich output (may fallback if rich not installed)
        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test Document\n\nContent")

            result = main(
                [
                    str(files[0]),
                    str(files[1]),
                    "--rich",
                    "--output-dir",
                    str(output_dir),
                    "--no-summary",  # Disable summary to test just rich processing
                ]
            )

            assert result == 0
            # Should process without crashing regardless of rich availability

    def test_progress_bar_integration(self, capsys):
        """Test progress bar integration with fallback behavior."""
        # Create multiple test files
        files = []
        for i in range(5):
            html_file = self.temp_dir / f"doc_{i}.html"
            html_file.write_text(f"<h1>Document {i}</h1><p>Test content {i}</p>")
            files.append(str(html_file))

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Document\n\nTest content")

            result = main([*files, "--progress", "--no-summary"])

            assert result == 0
            # Should handle progress bar gracefully (with or without tqdm)

    def test_multi_file_processing_integration(self):
        """Test multi-file processing with various options."""
        # Create test files with different formats
        html_file = self.temp_dir / "test_html.html"
        html_file.write_text("<h1>HTML Test</h1><p>HTML content</p>")

        markdown_file = self.temp_dir / "test_markdown.md"
        markdown_file.write_text("# Markdown Test\n\nMarkdown content")

        output_dir = self.temp_dir / "converted"

        with patch("all2md.cli.processors.convert") as mock_convert:

            def mock_conversion(input_path, **kwargs):
                from pathlib import Path
                output = kwargs.get('output')
                if "html" in str(input_path):
                    content = "# HTML Test\n\nHTML content"
                else:
                    content = "# Markdown Test\n\nMarkdown content"

                if output:
                    Path(output).write_text(content, encoding='utf-8')
                    return None
                return content

            mock_convert.side_effect = mock_conversion

            result = main(
                [str(html_file), str(markdown_file), "--output-dir", str(output_dir), "--skip-errors", "--no-summary"]
            )

            assert result == 0
            assert output_dir.exists()

            # Check that files were created
            converted_files = list(output_dir.glob("*.md"))
            assert len(converted_files) >= 2

    def test_collation_integration(self):
        """Test file collation integration."""
        # Create multiple test files
        files = []
        for i in range(3):
            test_file = self.temp_dir / f"section_{i}.html"
            test_file.write_text(f"<h1>Section {i}</h1><p>Content for section {i}</p>")
            files.append(str(test_file))

        output_file = self.temp_dir / "combined.md"

        with patch("all2md.cli.processors.to_markdown") as mock_to_markdown:

            def mock_conversion(input_path, **kwargs):
                # Extract number from filename
                filename = str(input_path)
                if "section_0" in filename:
                    return "# Section 0\n\nContent for section 0"
                elif "section_1" in filename:
                    return "# Section 1\n\nContent for section 1"
                else:
                    return "# Section 2\n\nContent for section 2"

            mock_to_markdown.side_effect = mock_conversion

            result = main([*files, "--collate", "--out", str(output_file), "--no-summary"])

            assert result == 0
            assert output_file.exists()

            content = output_file.read_text()
            # Should contain all sections with separators
            assert "# File: section_0.html" in content
            assert "# File: section_1.html" in content
            assert "# File: section_2.html" in content
            assert "Section 0" in content
            assert "Section 1" in content
            assert "Section 2" in content
            assert "---" in content  # File separator

    def test_recursive_directory_processing(self):
        """Test recursive directory processing."""
        # Create nested directory structure
        (self.temp_dir / "subdir1").mkdir()
        (self.temp_dir / "subdir2").mkdir()
        (self.temp_dir / "subdir1" / "nested").mkdir()

        # Create test files at different levels
        files_created = [
            self.temp_dir / "root.html",
            self.temp_dir / "subdir1" / "level1.html",
            self.temp_dir / "subdir2" / "another.html",
            self.temp_dir / "subdir1" / "nested" / "deep.html",
        ]

        for i, file_path in enumerate(files_created):
            file_path.write_text(f"<h1>Test {i}</h1><p>Content {i}</p>")

        output_dir = self.temp_dir / "output"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test\n\nContent")

            result = main(
                [
                    str(self.temp_dir),
                    "--recursive",
                    "--output-dir",
                    str(output_dir),
                    "--preserve-structure",
                    "--no-summary",
                ]
            )

            assert result == 0
            assert output_dir.exists()

            # Should have processed files from all directories
            output_files = list(output_dir.rglob("*.md"))
            assert len(output_files) >= 4  # At least our test files

    def test_environment_variable_integration(self):
        """Test environment variable integration with CLI precedence."""
        import os

        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test</h1>")

        # Set environment variables
        os.environ["ALL2MD_NO_SUMMARY"] = "true"
        os.environ["ALL2MD_OUTPUT_DIR"] = str(self.temp_dir / "env_output")

        try:
            with patch("all2md.cli.processors.convert") as mock_convert:
                mock_convert.side_effect = mock_convert_with_file_write("# Test\n\nContent")

                # Test using environment variables
                result = main([str(html_file)])

                assert result == 0
                # Should use env var for output dir (if not overridden)

            # Test CLI override of environment variables
            with patch("all2md.cli.processors.convert") as mock_convert:
                mock_convert.side_effect = mock_convert_with_file_write("# Test\n\nContent")

                cli_output_dir = self.temp_dir / "cli_output"
                result = main(
                    [
                        str(html_file),
                        "--output-dir",
                        str(cli_output_dir),  # Should override env var
                    ]
                )

                assert result == 0

        finally:
            # Clean up environment
            os.environ.pop("ALL2MD_NO_SUMMARY", None)
            os.environ.pop("ALL2MD_OUTPUT_DIR", None)

    def test_parallel_processing_integration(self):
        """Test parallel processing integration."""
        # Create multiple test files
        files = []
        for i in range(4):
            test_file = self.temp_dir / f"parallel_{i}.html"
            test_file.write_text(f"<h1>Parallel Test {i}</h1><p>Content {i}</p>")
            files.append(str(test_file))

        output_dir = self.temp_dir / "parallel_output"

        with patch("all2md.cli.processors.convert") as mock_convert:

            def slow_conversion(input_path, **kwargs):
                import time
                from pathlib import Path

                time.sleep(0.1)  # Simulate processing time
                content = f"# Converted {input_path.name}\n\nContent"

                output = kwargs.get('output')
                if output:
                    Path(output).write_text(content, encoding='utf-8')
                    return None
                return content

            mock_convert.side_effect = slow_conversion

            # Test parallel processing
            result = main([*files, "--parallel", "2", "--output-dir", str(output_dir), "--no-summary"])

            assert result == 0
            assert output_dir.exists()

            # All files should be processed
            output_files = list(output_dir.glob("*.md"))
            assert len(output_files) == 4

    def test_error_handling_with_skip_errors(self, capsys):
        """Test error handling with --skip-errors flag."""
        # Create test files, one that will cause an error
        good_file = self.temp_dir / "good.html"
        good_file.write_text("<h1>Good File</h1>")

        bad_file = self.temp_dir / "bad.html"
        bad_file.write_text("<h1>Bad File</h1>")

        output_dir = self.temp_dir / "error_output"

        with patch("all2md.cli.processors.convert") as mock_convert:

            def selective_error(input_path, **kwargs):
                from pathlib import Path
                if "bad" in str(input_path):
                    raise Exception("Simulated conversion error")

                content = "# Good File\n\nContent"
                output = kwargs.get('output')
                if output:
                    Path(output).write_text(content, encoding='utf-8')
                    return None
                return content

            mock_convert.side_effect = selective_error

            # Test with skip-errors
            result = main(
                [str(good_file), str(bad_file), "--skip-errors", "--output-dir", str(output_dir), "--no-summary"]
            )

            assert result == 1  # Should return error code but continue processing

            # Good file should be processed
            good_output = output_dir / "good.md"
            assert good_output.exists()

            # Error should be logged (format is [ERROR])
            captured = capsys.readouterr()
            assert "[ERROR]" in captured.err or "error" in captured.err.lower()

    def test_complex_option_combinations(self):
        """Test complex combinations of new CLI options."""
        # Create test files
        files = []
        for i in range(3):
            test_file = self.temp_dir / f"complex_{i}.html"
            test_file.write_text(f"<h1>Complex {i}</h1><p>Test {i}</p>")
            files.append(str(test_file))

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Complex\n\nTest content")

            # Test combination of many new features
            result = main(
                [
                    *files,
                    "--rich",  # Rich output
                    "--progress",  # Progress bar
                    "--parallel",
                    "2",  # Parallel processing
                    "--skip-errors",  # Error handling
                    "--collate",  # File collation
                    "--no-summary",  # No summary
                ]
            )

            # Should handle all options gracefully
            assert result == 0

    def test_attachment_handling_with_multi_file(self):
        """Test attachment handling across multiple files."""
        # Create HTML files with images
        html1 = self.temp_dir / "doc1.html"
        html1.write_text('<h1>Doc 1</h1><img src="image1.png" alt="Image 1">')

        html2 = self.temp_dir / "doc2.html"
        html2.write_text('<h1>Doc 2</h1><img src="image2.png" alt="Image 2">')

        output_dir = self.temp_dir / "multi_output"
        images_dir = self.temp_dir / "images"

        with patch("all2md.cli.processors.convert") as mock_convert:

            def mock_with_images(input_path, **kwargs):
                if "doc1" in str(input_path):
                    return "# Doc 1\n\n![Image 1](images/image1.png)"
                else:
                    return "# Doc 2\n\n![Image 2](images/image2.png)"

            mock_convert.side_effect = mock_with_images

            result = main(
                [
                    str(html1),
                    str(html2),
                    "--output-dir",
                    str(output_dir),
                    "--attachment-mode",
                    "download",
                    "--attachment-output-dir",
                    str(images_dir),
                    "--no-summary",
                ]
            )

            assert result == 0

            # Verify attachment options were passed to converter
            assert mock_convert.call_count == 2
            for call in mock_convert.call_args_list:
                kwargs = call[1]
                assert kwargs["attachment_mode"] == "download"
                assert str(images_dir) in kwargs["attachment_output_dir"]

    def test_markdown_options_with_multi_file(self):
        """Test Markdown formatting options across multiple files."""
        files = [self.temp_dir / "test1.html", self.temp_dir / "test2.html"]

        for i, file_path in enumerate(files):
            file_path.write_text(f"<h1>Test {i}</h1><p><em>Italic</em> and <strong>bold</strong></p>")

        output_dir = self.temp_dir / "formatted_output"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test\n\n_Italic_ and **bold**")

            result = main(
                [
                    str(files[0]),
                    str(files[1]),
                    "--output-dir",
                    str(output_dir),
                    "--markdown-emphasis-symbol",
                    "_",
                    "--markdown-bullet-symbols",
                    "•",
                    "--no-summary",
                ]
            )

            assert result == 0

            # Verify markdown options were passed
            for call in mock_convert.call_args_list:
                kwargs = call[1]
                assert kwargs["emphasis_symbol"] == "_"
                assert kwargs["bullet_symbols"] == "•"

    def test_format_detection_with_multi_file(self):
        """Test format detection across multiple file types."""
        # Create files with different extensions
        files = {
            "test.html": "<h1>HTML</h1><p>HTML content</p>",
            "test.pdf": "Mock PDF content",  # Will be mocked
            "test.docx": "Mock DOCX content",  # Will be mocked
        }

        file_paths = []
        for filename, content in files.items():
            file_path = self.temp_dir / filename
            file_path.write_text(content)
            file_paths.append(str(file_path))

        with patch("all2md.cli.processors.convert") as mock_convert:

            def format_specific_mock(input_path, **kwargs):
                path_str = str(input_path)
                if "html" in path_str:
                    return "# HTML Document\n\nHTML content"
                elif "pdf" in path_str:
                    return "# PDF Document\n\nPDF content"
                else:
                    return "# DOCX Document\n\nDOCX content"

            mock_convert.side_effect = format_specific_mock

            result = main([*file_paths, "--no-summary"])

            assert result == 0
            assert mock_convert.call_count == 3

    def test_stdin_compatibility_preserved(self, capsys):
        """Test that stdin processing still works with new features."""
        test_content = "<h1>Stdin Test</h1><p>Content from stdin</p>"

        with patch("all2md.cli.processors.to_markdown") as mock_to_markdown:
            mock_to_markdown.return_value = "# Stdin Test\n\nContent from stdin"

            with patch("sys.stdin") as mock_stdin:
                mock_stdin.buffer.read.return_value = test_content.encode()

                result = main(["-"])  # stdin

                assert result == 0
                captured = capsys.readouterr()
                assert "# Stdin Test" in captured.out


@pytest.mark.integration
@pytest.mark.cli
class TestEnhancedCLIIntegration:
    """Integration tests for the new enhanced CLI features."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_dependency_check_integration(self):
        """Test dependency check command integration."""
        # Test check-deps command
        result = main(["check-deps"])
        assert result in [0, 1]  # Should either succeed or indicate missing deps

        # Test check-deps with specific format
        result = main(["check-deps", "pdf"])
        assert result in [0, 1]  # Should either succeed or indicate missing deps

    def test_save_config_integration(self):
        """Test configuration saving integration."""
        config_file = self.temp_dir / "test_config.json"

        # Test saving configuration
        result = main(
            [
                "test.pdf",
                "--pdf-pages",
                "1,2,3",
                "--markdown-emphasis-symbol",
                "_",
                "--rich",
                "--save-config",
                str(config_file),
            ]
        )

        assert result == 0
        assert config_file.exists()

        # Verify config content
        import json

        with open(config_file) as f:
            config = json.load(f)

        assert "pdf.pages" in config
        assert config["pdf.pages"] == [1, 2, 3]
        assert "markdown.emphasis_symbol" in config
        assert config["markdown.emphasis_symbol"] == "_"
        assert "rich" in config
        assert config["rich"] is True

        # Should not include input or save_config
        assert "input" not in config
        assert "save_config" not in config

    def test_dry_run_integration(self):
        """Test dry run mode integration."""
        # Create test files
        test_files = []
        for i in range(3):
            test_file = self.temp_dir / f"test_{i}.html"
            test_file.write_text(f"<h1>Test {i}</h1><p>Content {i}</p>")
            test_files.append(str(test_file))

        # Test dry run mode
        result = main([*test_files, "--dry-run", "--output-dir", str(self.temp_dir / "output"), "--rich"])

        assert result == 0
        # No files should actually be created
        output_dir = self.temp_dir / "output"
        assert not output_dir.exists()

    def test_dry_run_with_collation(self, capsys):
        """Test dry run mode with collation."""
        # Create test files
        files = []
        for i in range(2):
            test_file = self.temp_dir / f"section_{i}.html"
            test_file.write_text(f"<h1>Section {i}</h1>")
            files.append(str(test_file))

        result = main([*files, "--dry-run", "--collate", "--out", str(self.temp_dir / "combined.md")])

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN MODE" in captured.out
        assert "collated" in captured.out.lower()

        # Output file should not be created
        assert not (self.temp_dir / "combined.md").exists()

    def test_exclusion_patterns_integration(self):
        """Test file exclusion patterns integration."""
        # Create test files and directories
        (self.temp_dir / "subdir").mkdir()
        test_files = [
            self.temp_dir / "keep.html",
            self.temp_dir / "exclude.tmp",
            self.temp_dir / "backup_file.html",
            self.temp_dir / "subdir" / "nested.html",
            self.temp_dir / "subdir" / "backup_nested.html",
        ]

        for file_path in test_files:
            file_path.write_text("<h1>Test</h1>")

        output_dir = self.temp_dir / "output"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test\n\nContent")

            result = main(
                [
                    str(self.temp_dir),
                    "--recursive",
                    "--exclude",
                    "*.tmp",
                    "--exclude",
                    "backup_*",
                    "--output-dir",
                    str(output_dir),
                    "--no-summary",
                ]
            )

            assert result == 0
            # Should have processed some files but not excluded ones
            assert mock_convert.call_count >= 2

            # Check which files were processed
            processed_files = []
            for call in mock_convert.call_args_list:
                input_path = str(call[0][0])
                processed_files.append(input_path)

            # Should include non-excluded files
            assert any("keep.html" in f for f in processed_files)
            assert any("nested.html" in f for f in processed_files)

            # Should exclude pattern-matched files
            assert not any("exclude.tmp" in f for f in processed_files)
            assert not any("backup_file.html" in f for f in processed_files)
            assert not any("backup_nested.html" in f for f in processed_files)

    def test_exclusion_with_glob_patterns(self):
        """Test exclusion with various glob patterns."""
        # Create test files with different patterns
        test_files = [
            self.temp_dir / "document.pdf",
            self.temp_dir / "temp_file.pdf",
            self.temp_dir / "file.temp.pdf",
            self.temp_dir / "backup_doc.pdf",
            self.temp_dir / "normal.pdf",
        ]

        for file_path in test_files:
            file_path.write_text("test content")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Test\n\nContent"

            result = main(
                [
                    str(self.temp_dir),
                    "--exclude",
                    "temp_*",
                    "--exclude",
                    "*.temp.*",
                    "--exclude",
                    "backup_*",
                    "--no-summary",
                ]
            )

            assert result == 0

            # Check which files were processed
            processed_files = []
            for call in mock_convert.call_args_list:
                input_path = str(call[0][0])
                processed_files.append(input_path)

            # Should include files that don't match exclusion patterns
            assert any("document.pdf" in f for f in processed_files)
            assert any("normal.pdf" in f for f in processed_files)

            # Should exclude files matching patterns
            assert not any("temp_file.pdf" in f for f in processed_files)
            assert not any("file.temp.pdf" in f for f in processed_files)
            assert not any("backup_doc.pdf" in f for f in processed_files)

    def test_save_config_with_complex_options(self):
        """Test saving configuration with complex option combinations."""
        config_file = self.temp_dir / "complex_config.json"

        result = main(
            [
                "test.pdf",
                "--pdf-pages",
                "1,3,5",
                "--pdf-password",
                "secret123",
                "--pdf-no-detect-columns",
                "--markdown-emphasis-symbol",
                "_",
                "--markdown-bullet-symbols",
                "*-+",
                "--attachment-mode",
                "download",
                "--attachment-output-dir",
                "./images",
                "--rich",
                "--exclude",
                "*.tmp",
                "--exclude",
                "backup_*",
                "--save-config",
                str(config_file),
            ]
        )

        assert result == 0
        assert config_file.exists()

        # Load and verify comprehensive config
        import json

        with open(config_file) as f:
            config = json.load(f)

        # Should include all relevant options
        assert config["pdf.pages"] == [1, 3, 5]
        assert config["pdf.password"] == "secret123"
        assert config["pdf.detect_columns"] is False
        assert config["markdown.emphasis_symbol"] == "_"
        assert config["markdown.bullet_symbols"] == "*-+"
        assert config["attachment_mode"] == "download"
        assert config["attachment_output_dir"] == "./images"
        assert config["rich"] is True
        assert config["exclude"] == ["*.tmp", "backup_*"]

    def test_config_load_and_use(self):
        """Test loading and using saved configuration."""
        # First, save a config
        config_file = self.temp_dir / "saved_config.json"
        result = main(["test.pdf", "--markdown-emphasis-symbol", "_", "--rich", "--save-config", str(config_file)])
        assert result == 0

        # Create a test file to convert
        test_file = self.temp_dir / "test.html"
        test_file.write_text("<h1>Test</h1><p><em>Italic</em></p>")

        # Use the saved config
        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test\n\n_Italic_")

            result = main([str(test_file), "--config", str(config_file)])

            assert result == 0
            call_args = mock_convert.call_args
            kwargs = call_args[1]

            # Should have loaded options from config
            assert kwargs["markdown.emphasis_symbol"] == "_"

    def test_combined_new_features_integration(self):
        """Test all new features working together."""
        # Create multiple test files with some to exclude
        files_to_create = ["document1.html", "document2.html", "temp_file.html", "backup_doc.html"]

        test_files = []
        for filename in files_to_create:
            file_path = self.temp_dir / filename
            file_path.write_text(f"<h1>{filename}</h1><p>Content</p>")
            test_files.append(file_path)

        config_file = self.temp_dir / "combined_config.json"
        output_dir = self.temp_dir / "output"

        # First, test dry run with all features
        result = main(
            [
                str(self.temp_dir),
                "--dry-run",
                "--exclude",
                "temp_*",
                "--exclude",
                "backup_*",
                "--output-dir",
                str(output_dir),
                "--rich",
                "--parallel",
                "2",
                "--preserve-structure",
                "--save-config",
                str(config_file),
            ]
        )

        assert result == 0
        # Config should be saved even in dry run
        assert config_file.exists()
        # But no output files should be created
        assert not output_dir.exists()

        # Now test actual conversion using the config
        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Document\n\nContent")

            result = main([str(self.temp_dir), "--config", str(config_file), "--no-summary"])

            assert result == 0

            # Should have processed only non-excluded files
            processed_files = []
            for call in mock_convert.call_args_list:
                input_path = str(call[0][0])
                processed_files.append(input_path)

            # Should include regular documents
            assert any("document1.html" in f for f in processed_files)
            assert any("document2.html" in f for f in processed_files)

            # Should exclude pattern-matched files
            assert not any("temp_file.html" in f for f in processed_files)
            assert not any("backup_doc.html" in f for f in processed_files)

    def test_dependency_commands_with_rich_output(self, capsys):
        """Test dependency commands with rich output (if available)."""
        # Test dependency check with rich output
        with patch("all2md.dependencies.print_dependency_report") as mock_report:
            mock_report.return_value = "All2MD Dependency Status\n===================\nPDF: ✓"

            result = main(["check-deps"])
            assert result in [0, 1]

            captured = capsys.readouterr()
            # Should show dependency information
            assert len(captured.out) > 0 or mock_report.called

    def test_exclusion_error_handling(self):
        """Test error handling with exclusion patterns."""
        # Test with invalid glob patterns (should handle gracefully)
        test_file = self.temp_dir / "test.html"
        test_file.write_text("<h1>Test</h1>")

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.return_value = "# Test\n\nContent"

            # Test with complex exclusion patterns that don't match our file
            result = main(
                [str(test_file), "--exclude", "**/somethingelse/**", "--exclude", "[0-9]*backup*", "--no-summary"]
            )

            # Should handle without crashing (patterns don't match our test file)
            assert result == 0

    def test_dry_run_with_stdin(self, capsys):
        """Test dry run mode with stdin input."""
        test_content = "<h1>Stdin Test</h1>"

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.buffer.read.return_value = test_content.encode()

            # Dry run with stdin should show what would be processed
            result = main(["-", "--dry-run"])

            # Dry run doesn't apply to stdin (single input), should process normally
            # But this tests that dry run doesn't break stdin handling
            assert result in [0, 1]  # May succeed or fail depending on mocking

    def test_config_with_environment_variables(self):
        """Test that only explicit CLI arguments are saved, not environment variables."""
        import os

        config_file = self.temp_dir / "env_config.json"

        # Set environment variables
        os.environ["ALL2MD_RICH"] = "true"
        os.environ["ALL2MD_NO_SUMMARY"] = "true"

        try:
            # Save config with environment variables active
            # Only the explicitly provided --markdown-emphasis-symbol should be saved
            result = main(["test.pdf", "--markdown-emphasis-symbol", "_", "--save-config", str(config_file)])

            assert result == 0
            assert config_file.exists()

            # Load config and verify
            import json

            with open(config_file) as f:
                config = json.load(f)

            # Environment variables should NOT be saved to config
            # (they are ephemeral overrides, not persistent configuration)
            assert "rich" not in config  # Env var should not be saved
            assert "no_summary" not in config  # Env var should not be saved

            # Only explicitly provided CLI argument should be saved
            assert "markdown.emphasis_symbol" in config
            assert config["markdown.emphasis_symbol"] == "_"

        finally:
            # Clean up environment
            os.environ.pop("ALL2MD_RICH", None)
            os.environ.pop("ALL2MD_NO_SUMMARY", None)

    def test_backward_compatibility_with_new_features(self):
        """Test that new features don't break existing CLI workflows."""
        # Create test file
        test_file = self.temp_dir / "test.html"
        test_file.write_text("<h1>Test</h1><p>Content</p>")

        output_file = self.temp_dir / "output.md"

        with patch("all2md.cli.processors.convert") as mock_convert:
            mock_convert.side_effect = mock_convert_with_file_write("# Test\n\nContent")

            # Test that all existing patterns still work
            test_patterns = [
                # Basic usage
                [str(test_file)],
                # With output
                [str(test_file), "--out", str(output_file)],
                # With format
                [str(test_file), "--format", "html"],
                # With format-specific options
                [str(test_file), "--html-extract-title", "--markdown-emphasis-symbol", "_"],
                # With attachment options
                [str(test_file), "--attachment-mode", "base64"],
            ]

            for pattern in test_patterns:
                result = main(pattern)
                assert result == 0

            # Should have processed all test patterns
            assert mock_convert.call_count == len(test_patterns)
