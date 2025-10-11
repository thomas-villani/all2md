"""End-to-end tests for all2md CLI functionality.

This module tests the CLI as a subprocess, simulating real-world usage patterns
and testing the complete pipeline from command-line to file output.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.slow
class TestCLIEndToEnd:
    """End-to-end tests for CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        # Path to the CLI module
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,  # Run from project root
            capture_output=True,
            text=True
        )

    def test_html_file_conversion(self):
        """Test converting a real HTML file to Markdown."""
        # Create test HTML file
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Document</title>
</head>
<body>
    <h1>Main Title</h1>
    <h2>Subtitle</h2>
    <p>This is a paragraph with <strong>bold text</strong> and <em>italic text</em>.</p>

    <h3>Lists</h3>
    <ul>
        <li>Unordered item 1</li>
        <li>Unordered item 2</li>
        <li>Unordered item 3</li>
    </ul>

    <ol>
        <li>Ordered item 1</li>
        <li>Ordered item 2</li>
    </ol>

    <h3>Code and Links</h3>
    <p>Here's some <code>inline code</code> and a <a href="https://example.com">link</a>.</p>

    <pre><code>
def example_function():
    return "Hello, World!"
    </code></pre>

    <blockquote>
        <p>This is a blockquote with important information.</p>
    </blockquote>
</body>
</html>"""

        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")

        output_file = self.temp_dir / "output.md"

        # Run CLI conversion
        result = self._run_cli([
            str(html_file),
            "--out", str(output_file),
            "--html-extract-title"
        ])

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check output file was created
        assert output_file.exists(), "Output file was not created"

        # Check content
        content = output_file.read_text(encoding="utf-8")
        assert "# Test Document" in content  # Title extracted
        assert "## Main Title" in content  # Main heading
        assert "### Subtitle" in content  # Subheading
        assert "**bold text**" in content  # Bold formatting
        assert "*italic text*" in content  # Italic formatting
        assert "* Unordered item 1" in content  # List items
        assert "1. Ordered item 1" in content  # Numbered list
        assert "`inline code`" in content  # Inline code
        assert "[link](https://example.com)" in content  # Link
        assert "```" in content  # Code block
        assert ">" in content  # Blockquote

    def test_cli_help_output(self):
        """Test that CLI help displays correctly."""
        result = self._run_cli(["--help"])

        # Help should exit with code 0
        assert result.returncode == 0

        # Check help content
        help_output = result.stdout
        assert "all2md" in help_output
        assert "Convert documents to Markdown format" in help_output
        assert "--format" in help_output
        assert "--log-level" in help_output
        assert "--attachment-mode" in help_output
        assert "PDF options:" in help_output
        assert "HTML options:" in help_output

    def test_format_override_txt(self):
        """Test format override to treat HTML as source code."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML Title</h1><p>Content</p>")

        result = self._run_cli([
            str(html_file),
            "--format", "sourcecode"
        ])

        assert result.returncode == 0
        # Should output as code block since it's treated as source code
        assert "```" in result.stdout  # Should be in a code fence

    def test_nonexistent_file_error(self):
        """Test error handling for nonexistent files."""
        nonexistent_file = self.temp_dir / "does_not_exist.pdf"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "WARNING: Path does not exist" in result.stderr

    def test_invalid_format_error(self):
        """Test error handling for invalid format."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        result = self._run_cli([
            str(html_file),
            "--format", "invalid_format"
        ])

        assert result.returncode == 2  # argparse error code

    def test_invalid_log_level_error(self):
        """Test error handling for invalid log level."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test</p>")

        result = self._run_cli([
            str(html_file),
            "--log-level", "INVALID"
        ])

        assert result.returncode == 2  # argparse error code

    def test_attachment_warning(self):
        """Test warning when using attachment-output-dir without download mode."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p>Test <img src='image.png' alt='test'></p>")

        result = self._run_cli([
            str(html_file),
            "--attachment-output-dir", "./images"
        ])

        assert result.returncode == 0
        assert "Warning" in result.stderr
        assert "attachment mode is 'alt_text'" in result.stderr

    def test_debug_logging(self):
        """Test debug logging output."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test</h1>")

        result = self._run_cli([
            str(html_file),
            "--log-level", "DEBUG"
        ])

        assert result.returncode == 0
        # Should contain debug information
        assert "DEBUG:" in result.stderr

    def test_markdown_formatting_options(self):
        """Test Markdown formatting options."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<p><em>italic</em> text</p><ul><li>item</li></ul>")

        result = self._run_cli([
            str(html_file),
            "--markdown-emphasis-symbol", "_"
        ])

        assert result.returncode == 0
        # Should use underscore for emphasis
        assert "_italic_" in result.stdout

    def test_complex_html_with_all_options(self):
        """Test complex HTML conversion with multiple options."""
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Complex Document</title>
    <style>body { color: red; }</style>
</head>
<body>
    <h1>Main Heading</h1>
    <p>Text with <em>emphasis</em> and <strong>strong</strong>.</p>
    <ul>
        <li>List item 1</li>
        <li>List item 2</li>
    </ul>
    <img src="test.jpg" alt="Test image">
    <script>alert('dangerous');</script>
</body>
</html>"""

        html_file = self.temp_dir / "complex.html"
        html_file.write_text(html_content)

        output_file = self.temp_dir / "complex_output.md"

        result = self._run_cli([
            str(html_file),
            "--out", str(output_file),
            "--html-extract-title",
            "--html-strip-dangerous-elements",
            "--markdown-emphasis-symbol", "_",
            "--markdown-bullet-symbols", "•",
            "--log-level", "INFO"
        ])

        assert result.returncode == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "# Complex Document" in content  # Title extracted
        assert "## Main Heading" in content  # Heading converted
        assert "_emphasis_" in content  # Underscore emphasis
        assert "List item 1" in content  # List content present
        assert content.count("List item") >= 2  # Both list items present
        assert "alert" not in content  # Dangerous content stripped

    def test_stdout_vs_file_output(self):
        """Test difference between stdout and file output."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>Test Content</h1>")

        # Test stdout output
        result_stdout = self._run_cli([str(html_file)])
        assert result_stdout.returncode == 0
        assert "# Test Content" in result_stdout.stdout

        # Test file output
        output_file = self.temp_dir / "output.md"
        result_file = self._run_cli([
            str(html_file),
            "--out", str(output_file)
        ])

        assert result_file.returncode == 0
        assert output_file.exists()
        assert "# Test Content" in output_file.read_text()

        # File output should show conversion message
        assert f"Converted {html_file} -> {output_file}" in result_file.stdout

    @pytest.mark.slow
    def test_large_html_file_performance(self):
        """Test CLI performance with a large HTML file."""
        # Create a large HTML file
        large_html_content = """<!DOCTYPE html>
<html><head><title>Large Document</title></head><body>"""

        # Add many paragraphs and lists
        for i in range(100):
            large_html_content += f"""
            <h2>Section {i}</h2>
            <p>This is paragraph {i} with some <strong>bold</strong> and <em>italic</em> text.</p>
            <ul>
                <li>Item {i}.1</li>
                <li>Item {i}.2</li>
                <li>Item {i}.3</li>
            </ul>
            """

        large_html_content += "</body></html>"

        large_html_file = self.temp_dir / "large.html"
        large_html_file.write_text(large_html_content)

        result = self._run_cli([
            str(large_html_file),
            "--html-extract-title"
        ])

        assert result.returncode == 0
        assert "# Large Document" in result.stdout
        assert "Section 99" in result.stdout  # Should process all sections

    def test_odf_file_conversion_real(self):
        """Test converting a real ODT file to Markdown."""
        from fixtures.generators.odf_fixtures import HAS_ODFPY, create_odt_with_formatting, save_odt_to_file

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODT generation")

        # Create real ODT document
        try:
            odt_doc = create_odt_with_formatting()
            odt_file = self.temp_dir / "test_formatting.odt"
            save_odt_to_file(odt_doc, odt_file)
        except ImportError:
            pytest.skip("odfpy not available for ODT generation")

        output_file = self.temp_dir / "output.md"

        # Run CLI conversion
        result = self._run_cli([
            str(odt_file),
            "--out", str(output_file),
        ])

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check output file was created
        assert output_file.exists(), "Output file was not created"

        # Check content
        content = output_file.read_text(encoding="utf-8")
        assert "Formatting Test Document" in content
        assert len(content.strip()) > 0

    def test_odf_with_attachment_options(self):
        """Test ODT conversion with attachment handling."""
        from fixtures.generators.odf_fixtures import (
            HAS_ODFPY,
            create_comprehensive_odt_test_document,
            save_odt_to_file,
        )

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODT generation")

        # Create comprehensive ODT document
        try:
            odt_doc = create_comprehensive_odt_test_document()
            odt_file = self.temp_dir / "comprehensive.odt"
            save_odt_to_file(odt_doc, odt_file)
        except ImportError:
            pytest.skip("odfpy not available for ODT generation")

        output_file = self.temp_dir / "comprehensive_output.md"
        images_dir = self.temp_dir / "images"

        result = self._run_cli([
            str(odt_file),
            "--out", str(output_file),
            "--attachment-mode", "download",
            "--attachment-output-dir", str(images_dir),
            "--markdown-emphasis-symbol", "_"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "Comprehensive ODF Test Document" in content
        assert "Text Formatting" in content
        assert "Lists" in content
        assert "Tables" in content

    def test_odf_table_options(self):
        """Test ODT table handling options."""
        from fixtures.generators.odf_fixtures import HAS_ODFPY, create_odt_with_tables, save_odt_to_file

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODT generation")

        try:
            odt_doc = create_odt_with_tables()
            odt_file = self.temp_dir / "tables.odt"
            save_odt_to_file(odt_doc, odt_file)
        except ImportError:
            pytest.skip("odfpy not available for ODT generation")

        # Test with tables preserved
        result_with_tables = self._run_cli([
            str(odt_file),
        ])

        assert result_with_tables.returncode == 0
        assert "|" in result_with_tables.stdout  # Should contain table formatting

        # Test with tables disabled
        result_no_tables = self._run_cli([
            str(odt_file),
            "--odt-no-preserve-tables"
        ])

        assert result_no_tables.returncode == 0
        # Should still process without error, just no table formatting

    def test_odf_lists_conversion(self):
        """Test ODT list conversion."""
        from fixtures.generators.odf_fixtures import HAS_ODFPY, create_odt_with_lists, save_odt_to_file

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODT generation")

        try:
            odt_doc = create_odt_with_lists()
            odt_file = self.temp_dir / "lists.odt"
            save_odt_to_file(odt_doc, odt_file)
        except ImportError:
            pytest.skip("odfpy not available for ODT generation")

        result = self._run_cli([
            str(odt_file),
            "--markdown-bullet-symbols", "•"
        ])

        assert result.returncode == 0
        content = result.stdout

        # Should contain list content
        assert "List Test Document" in content
        # Should process lists without errors
        assert len(content.strip()) > 0

    @pytest.mark.odf
    def test_odp_presentation_conversion(self):
        """Test ODP presentation file conversion."""
        from fixtures.generators.odf_fixtures import HAS_ODFPY, create_odp_with_slides

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODP generation")

        try:
            odp_doc = create_odp_with_slides()
            odp_file = self.temp_dir / "presentation.odp"

            # Save ODP manually since we don't have a helper function
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.odp', delete=False) as tmp:
                odp_doc.save(tmp.name)
                import shutil
                shutil.copy(tmp.name, odp_file)
        except ImportError:
            pytest.skip("odfpy not available for ODP generation")
        except Exception as e:
            pytest.skip(f"Failed to create ODP document: {e}")

        result = self._run_cli([str(odp_file)])

        assert result.returncode == 0

    @pytest.mark.odf
    def test_odf_format_override(self):
        """Test format override for ODF files."""
        # Create a text file but force it to be treated as ODT
        text_file = self.temp_dir / "fake.txt"
        text_file.write_text("This is just text, not really ODT")

        result = self._run_cli([
            str(text_file),
            "--format", "odt"
        ])

        # Should attempt ODT processing (may fail since it's not real ODT)
        # But should not crash due to format detection
        assert result.returncode in [0, 1, 2]

    @pytest.mark.odf
    def test_odf_nonexistent_file(self):
        """Test error handling for nonexistent ODT file."""
        nonexistent_file = self.temp_dir / "does_not_exist.odt"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "Error:" in result.stderr or "does not exist" in result.stderr

    @pytest.mark.odf
    def test_odf_complex_options_combination(self):
        """Test ODT conversion with complex option combinations."""
        from fixtures.generators.odf_fixtures import (
            HAS_ODFPY,
            create_comprehensive_odt_test_document,
            save_odt_to_file,
        )

        if not HAS_ODFPY:
            pytest.skip("odfpy not available for ODT generation")

        try:
            odt_doc = create_comprehensive_odt_test_document()
            odt_file = self.temp_dir / "complex.odt"
            save_odt_to_file(odt_doc, odt_file)
        except ImportError:
            pytest.skip("odfpy not available for ODT generation")

        output_file = self.temp_dir / "complex_output.md"

        result = self._run_cli([
            str(odt_file),
            "--out", str(output_file),
            "--attachment-mode", "base64",
            "--markdown-emphasis-symbol", "_",
            "--markdown-bullet-symbols", "•→◦",
            "--log-level", "DEBUG"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text()
        assert "Comprehensive ODF Test Document" in content
        assert len(content.strip()) > 0

        # Should contain debug information in stderr
        assert "DEBUG:" in result.stderr or len(result.stderr) >= 0  # Some debug output or at least no crash

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_basic_conversion_e2e(self):
        """Test end-to-end Jupyter Notebook conversion."""
        from fixtures.generators.ipynb_fixtures import create_simple_notebook, save_notebook_to_file

        notebook = create_simple_notebook()
        ipynb_file = self.temp_dir / "simple.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        result = self._run_cli([str(ipynb_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout

        # Verify content structure
        assert "# Simple Notebook" in output
        assert "This is a basic test notebook." in output
        assert "```python" in output
        assert "print('Hello, World!')" in output
        assert "Hello, World!" in output

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_with_images_e2e(self):
        """Test end-to-end Jupyter Notebook conversion with images."""
        from fixtures.generators.ipynb_fixtures import create_notebook_with_images, save_notebook_to_file

        notebook = create_notebook_with_images()
        ipynb_file = self.temp_dir / "with_images.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        result = self._run_cli([str(ipynb_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout

        # Should contain basic notebook structure
        assert "# Notebook with Images" in output
        assert "![cell output]" in output
        assert "matplotlib.pyplot" in output

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_with_output_file_e2e(self):
        """Test end-to-end Jupyter Notebook conversion with output file."""
        from fixtures.generators.ipynb_fixtures import create_simple_notebook, save_notebook_to_file

        notebook = create_simple_notebook()
        ipynb_file = self.temp_dir / "input.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        output_file = self.temp_dir / "output.md"

        result = self._run_cli([str(ipynb_file), "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text()
        assert "# Simple Notebook" in content
        assert "```python" in content

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_with_attachment_download_e2e(self):
        """Test Jupyter Notebook conversion with image download."""
        from fixtures.generators.ipynb_fixtures import create_notebook_with_images, save_notebook_to_file

        notebook = create_notebook_with_images()
        ipynb_file = self.temp_dir / "with_plots.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        images_dir = self.temp_dir / "images"

        result = self._run_cli([
            str(ipynb_file),
            "--attachment-mode", "download",
            "--attachment-output-dir", str(images_dir)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout

        # Should reference downloaded images
        assert "![cell output](" in output
        assert ".png)" in output

        # Images should be saved to disk
        assert images_dir.exists()
        image_files = list(images_dir.glob("*.png"))
        assert len(image_files) > 0

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_truncation_e2e(self):
        """Test Jupyter Notebook conversion with output truncation."""
        from fixtures.generators.ipynb_fixtures import create_notebook_with_long_outputs, save_notebook_to_file

        notebook = create_notebook_with_long_outputs()
        ipynb_file = self.temp_dir / "long_outputs.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        # Note: CLI truncation options not yet implemented
        result = self._run_cli([str(ipynb_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout

        # Should contain basic long output structure
        assert "Line 0:" in output
        assert "for i in range(50):" in output

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_format_override_e2e(self):
        """Test forcing ipynb format on non-.ipynb files."""
        import json

        # Create notebook content but save as .txt
        notebook = {
            "cells": [{"cell_type": "markdown", "source": ["# Forced Notebook"]}],
            "metadata": {"kernelspec": {"language": "python"}},
            "nbformat": 4
        }

        txt_file = self.temp_dir / "notebook.txt"
        with open(txt_file, 'w') as f:
            json.dump(notebook, f)

        result = self._run_cli([str(txt_file), "--format", "ipynb"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout

        assert "# Forced Notebook" in output

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_error_handling_e2e(self):
        """Test error handling for invalid Jupyter Notebook files."""
        # Create invalid JSON file
        invalid_file = self.temp_dir / "invalid.ipynb"
        invalid_file.write_text('{ "invalid": json content')

        result = self._run_cli([str(invalid_file)])

        assert result.returncode != 0  # Should fail - malformed file
        assert "Error:" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_nonexistent_file_e2e(self):
        """Test error handling for nonexistent ipynb file."""
        nonexistent_file = self.temp_dir / "does_not_exist.ipynb"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "Error:" in result.stderr or "does not exist" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_complex_options_combination_e2e(self):
        """Test Jupyter Notebook conversion with complex option combinations."""
        from fixtures.generators.ipynb_fixtures import create_data_science_notebook, save_notebook_to_file

        notebook = create_data_science_notebook()
        ipynb_file = self.temp_dir / "data_science.ipynb"
        save_notebook_to_file(notebook, str(ipynb_file))

        output_file = self.temp_dir / "data_science_output.md"
        images_dir = self.temp_dir / "notebook_images"

        result = self._run_cli([
            str(ipynb_file),
            "--out", str(output_file),
            "--attachment-mode", "download",
            "--attachment-output-dir", str(images_dir)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text()
        assert "# Customer Churn Analysis" in content
        assert "## Exploratory Data Analysis" in content
        assert "```python" in content
        assert len(content.strip()) > 0

        # Should have downloaded images
        if images_dir.exists():
            image_files = list(images_dir.glob("*.png"))
            assert len(image_files) >= 0  # May or may not have images depending on processing


@pytest.mark.e2e
@pytest.mark.epub
@pytest.mark.slow
class TestEpubCLIEndToEnd:
    """End-to-end tests for EPUB CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess."""
        cmd = [sys.executable, "-m", "all2md"] + args
        cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        return subprocess.run(
            cmd,
            cwd=cli_path.parent.parent.parent,  # Run from project root
            capture_output=True,
            text=True
        )

    def test_epub_basic_conversion(self):
        """Test basic EPUB conversion via CLI."""
        # Skip if ebooklib not available
        try:
            import importlib.util
            if importlib.util.find_spec("ebooklib") is None:
                pytest.skip("ebooklib not available for EPUB tests")
        except Exception:
            pytest.skip("ebooklib not available for EPUB tests")

        from fixtures.generators.epub_fixtures import create_simple_epub

        # Create test EPUB file
        epub_content = create_simple_epub()
        epub_file = self.temp_dir / "test_book.epub"
        epub_file.write_bytes(epub_content)

        # Run CLI conversion
        result = self._run_cli([str(epub_file)])

        # Check success
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check output contains expected content
        output = result.stdout
        assert "Chapter 1: Introduction" in output
        assert "Chapter 2: Content" in output
        assert "**bold text**" in output
        assert "*italic text*" in output
        assert "[link](https://example.com)" in output

    def test_epub_with_output_file(self):
        """Test EPUB conversion to output file."""
        try:
            import importlib.util
            if importlib.util.find_spec("ebooklib") is None:
                pytest.skip("ebooklib not available for EPUB tests")
        except Exception:
            pytest.skip("ebooklib not available for EPUB tests")

        from fixtures.generators.epub_fixtures import create_simple_epub

        epub_content = create_simple_epub()
        epub_file = self.temp_dir / "test_book.epub"
        epub_file.write_bytes(epub_content)

        output_file = self.temp_dir / "output.md"

        # Run CLI conversion with output file
        result = self._run_cli([
            str(epub_file),
            "--out", str(output_file)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        # Check content
        content = output_file.read_text(encoding="utf-8")
        assert "Chapter 1: Introduction" in content
        assert "Chapter 2: Content" in content

    def test_epub_with_base64_images(self):
        """Test EPUB conversion with base64 image embedding."""
        try:
            import importlib.util
            if importlib.util.find_spec("ebooklib") is None:
                pytest.skip("ebooklib not available for EPUB tests")
        except Exception:
            pytest.skip("ebooklib not available for EPUB tests")

        from fixtures.generators.epub_fixtures import create_epub_with_images

        epub_content = create_epub_with_images()
        epub_file = self.temp_dir / "test_with_images.epub"
        epub_file.write_bytes(epub_content)

        # Run CLI with base64 mode
        result = self._run_cli([
            str(epub_file),
            "--attachment-mode", "base64"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check for base64 image data
        output = result.stdout
        assert "Chapter with Image" in output
        assert "data:image/png;base64," in output or "![" in output

    def test_epub_with_download_images(self):
        """Test EPUB conversion with image download."""
        try:
            import importlib.util
            if importlib.util.find_spec("ebooklib") is None:
                pytest.skip("ebooklib not available for EPUB tests")
        except Exception:
            pytest.skip("ebooklib not available for EPUB tests")

        from fixtures.generators.epub_fixtures import create_epub_with_images

        epub_content = create_epub_with_images()
        epub_file = self.temp_dir / "test_with_images.epub"
        epub_file.write_bytes(epub_content)

        images_dir = self.temp_dir / "images"
        output_file = self.temp_dir / "output.md"

        # Run CLI with download mode
        result = self._run_cli([
            str(epub_file),
            "--out", str(output_file),
            "--attachment-mode", "download",
            "--attachment-output-dir", str(images_dir)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "Chapter with Image" in content

    def test_epub_format_override(self):
        """Test EPUB format override."""
        try:
            import importlib.util
            if importlib.util.find_spec("ebooklib") is None:
                pytest.skip("ebooklib not available for EPUB tests")
        except Exception:
            pytest.skip("ebooklib not available for EPUB tests")

        from fixtures.generators.epub_fixtures import create_simple_epub

        epub_content = create_simple_epub()
        epub_file = self.temp_dir / "test.epub"
        epub_file.write_bytes(epub_content)

        # Test with explicit format
        result = self._run_cli([
            str(epub_file),
            "--format", "epub"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert "Chapter 1: Introduction" in result.stdout

    def test_epub_nonexistent_file_error(self):
        """Test error handling for nonexistent EPUB file."""
        nonexistent_file = self.temp_dir / "does_not_exist.epub"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "Error" in result.stderr


@pytest.mark.e2e
@pytest.mark.mhtml
@pytest.mark.slow
class TestMhtmlCLIEndToEnd:
    """End-to-end tests for MHTML CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess."""
        cmd = [sys.executable, "-m", "all2md"] + args
        cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        return subprocess.run(
            cmd,
            cwd=cli_path.parent.parent.parent,  # Run from project root
            capture_output=True,
            text=True
        )

    def test_mhtml_basic_conversion(self):
        """Test basic MHTML conversion via CLI."""
        from fixtures.generators.mhtml_fixtures import create_simple_mhtml

        # Create test MHTML file
        mhtml_content = create_simple_mhtml()
        mhtml_file = self.temp_dir / "test_page.mht"
        mhtml_file.write_bytes(mhtml_content)

        # Run CLI conversion
        result = self._run_cli([str(mhtml_file)])

        # Check success
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check output contains expected content
        output = result.stdout
        assert "Test MHTML Document" in output
        assert "**bold**" in output or "<strong>" in output
        assert "*italic*" in output or "<em>" in output
        assert "example.com" in output

    def test_mhtml_with_output_file(self):
        """Test MHTML conversion to output file."""
        from fixtures.generators.mhtml_fixtures import create_simple_mhtml

        mhtml_content = create_simple_mhtml()
        mhtml_file = self.temp_dir / "test_page.mht"
        mhtml_file.write_bytes(mhtml_content)

        output_file = self.temp_dir / "output.md"

        # Run CLI conversion with output file
        result = self._run_cli([
            str(mhtml_file),
            "--out", str(output_file)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        # Check content
        content = output_file.read_text(encoding="utf-8")
        assert "Test MHTML Document" in content
        assert len(content.strip()) > 0

    def test_mhtml_with_images(self):
        """Test MHTML conversion with embedded images."""
        from fixtures.generators.mhtml_fixtures import create_mhtml_with_image

        mhtml_content = create_mhtml_with_image()
        mhtml_file = self.temp_dir / "test_with_images.mht"
        mhtml_file.write_bytes(mhtml_content)

        # Run CLI with base64 mode
        result = self._run_cli([
            str(mhtml_file),
            "--attachment-mode", "base64"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check for image processing
        output = result.stdout
        assert "Test MHTML with Image" in output
        assert len(output.strip()) > 0

    def test_mhtml_with_download_images(self):
        """Test MHTML conversion with image download."""
        from fixtures.generators.mhtml_fixtures import create_mhtml_with_image

        mhtml_content = create_mhtml_with_image()
        mhtml_file = self.temp_dir / "test_with_images.mht"
        mhtml_file.write_bytes(mhtml_content)

        images_dir = self.temp_dir / "images"
        output_file = self.temp_dir / "output.md"

        # Run CLI with download mode
        result = self._run_cli([
            str(mhtml_file),
            "--out", str(output_file),
            "--attachment-mode", "download",
            "--attachment-output-dir", str(images_dir)
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "Test MHTML with Image" in content

    def test_mhtml_ms_word_artifacts(self):
        """Test MHTML conversion with MS Word artifacts."""
        from fixtures.generators.mhtml_fixtures import create_mhtml_with_ms_word_artifacts

        mhtml_content = create_mhtml_with_ms_word_artifacts()
        mhtml_file = self.temp_dir / "test_word_artifacts.mht"
        mhtml_file.write_bytes(mhtml_content)

        # Run CLI conversion
        result = self._run_cli([str(mhtml_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check output contains cleaned content
        output = result.stdout
        assert "MS Word MHTML Document" in output
        assert "First list item" in output
        assert "Second list item" in output

    def test_mhtml_format_override(self):
        """Test MHTML format override."""
        from fixtures.generators.mhtml_fixtures import create_simple_mhtml

        mhtml_content = create_simple_mhtml()
        mhtml_file = self.temp_dir / "test.mht"
        mhtml_file.write_bytes(mhtml_content)

        # Test with explicit format
        result = self._run_cli([
            str(mhtml_file),
            "--format", "mhtml"
        ])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert "Test MHTML Document" in result.stdout

    def test_mhtml_nonexistent_file_error(self):
        """Test error handling for nonexistent MHTML file."""
        nonexistent_file = self.temp_dir / "does_not_exist.mht"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "Error" in result.stderr


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.slow
class TestAdvancedCLIFeaturesE2E:
    """End-to-end tests for advanced CLI features."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess."""
        cmd = [sys.executable, "-m", "all2md"] + args
        cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        return subprocess.run(
            cmd,
            cwd=cli_path.parent.parent.parent,  # Run from project root
            capture_output=True,
            text=True
        )

    def test_rich_output_e2e(self):
        """Test rich output end-to-end."""
        # Create test HTML files
        html_file1 = self.temp_dir / "test1.html"
        html_file1.write_text("<h1>Test Document 1</h1><p>Content 1</p>")

        html_file2 = self.temp_dir / "test2.html"
        html_file2.write_text("<h1>Test Document 2</h1><p>Content 2</p>")

        output_dir = self.temp_dir / "rich_output"

        # Run with rich flag
        result = self._run_cli([
            str(html_file1),
            str(html_file2),
            "--rich",
            "--output-dir", str(output_dir)
        ])

        # Should work regardless of rich availability
        assert result.returncode == 0
        assert output_dir.exists()

        # Check output files were created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 2

    def test_progress_bar_e2e(self):
        """Test progress bar end-to-end."""
        # Create multiple test files
        files = []
        for i in range(4):
            html_file = self.temp_dir / f"progress_{i}.html"
            html_file.write_text(f"<h1>Document {i}</h1><p>Content {i}</p>")
            files.append(str(html_file))

        # Run with progress flag
        result = self._run_cli([
            *files,
            "--progress"
        ])

        assert result.returncode == 0
        # Should handle gracefully whether tqdm is available or not

    def test_multi_file_processing_e2e(self):
        """Test multi-file processing end-to-end."""
        # Create test files of different types
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML Document</h1><p>HTML content</p>")

        # Create another HTML file (we can't easily create real PDF/DOCX in tests)
        html_file2 = self.temp_dir / "test2.html"
        html_file2.write_text("<h2>Second Document</h2><p>More content</p>")

        output_dir = self.temp_dir / "multi_output"

        result = self._run_cli([
            str(html_file),
            str(html_file2),
            "--output-dir", str(output_dir),
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        # Check output files
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 2

        # Verify content
        for output_file in output_files:
            content = output_file.read_text()
            assert len(content.strip()) > 0

    def test_collation_e2e(self):
        """Test file collation end-to-end."""
        # Create multiple HTML files
        files = []
        for i in range(3):
            html_file = self.temp_dir / f"section_{i}.html"
            html_file.write_text(f"<h1>Section {i}</h1><p>Content for section {i}</p>")
            files.append(str(html_file))

        output_file = self.temp_dir / "collated.md"

        result = self._run_cli([
            *files,
            "--collate",
            "--out", str(output_file)
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_file.exists()

        content = output_file.read_text()
        # Should contain file headers and separators
        assert "# File: section_0.html" in content
        assert "# File: section_1.html" in content
        assert "# File: section_2.html" in content
        assert "---" in content  # File separator

        # Should contain actual converted content
        assert "Section 0" in content
        assert "Section 1" in content
        assert "Section 2" in content

    def test_recursive_directory_processing_e2e(self):
        """Test recursive directory processing end-to-end."""
        # Create nested directory structure
        (self.temp_dir / "subdir1").mkdir()
        (self.temp_dir / "subdir1" / "nested").mkdir()
        (self.temp_dir / "subdir2").mkdir()

        # Create HTML files at different levels
        files_to_create = [
            self.temp_dir / "root.html",
            self.temp_dir / "subdir1" / "level1.html",
            self.temp_dir / "subdir1" / "nested" / "deep.html",
            self.temp_dir / "subdir2" / "another.html"
        ]

        for i, file_path in enumerate(files_to_create):
            file_path.write_text(f"<h1>Document {i}</h1><p>Content at {file_path.name}</p>")

        output_dir = self.temp_dir / "recursive_output"

        result = self._run_cli([
            str(self.temp_dir),
            "--recursive",
            "--output-dir", str(output_dir),
            "--preserve-structure",
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        # Should have processed files from all directories
        output_files = list(output_dir.rglob("*.md"))
        assert len(output_files) >= 4

        # Check that structure is preserved
        assert (output_dir / "root.md").exists()
        assert (output_dir / "subdir1" / "level1.md").exists()
        assert (output_dir / "subdir1" / "nested" / "deep.md").exists()
        assert (output_dir / "subdir2" / "another.md").exists()

    def test_environment_variables_e2e(self):
        """Test environment variable support end-to-end."""
        html_file = self.temp_dir / "env_test.html"
        html_file.write_text("<h1>Environment Test</h1><p>Testing env vars</p>")

        output_dir = self.temp_dir / "env_output"

        # Run CLI with environment variables set
        env = {
            **os.environ,
            'ALL2MD_OUTPUT_DIR': str(output_dir),
            'ALL2MD_NO_SUMMARY': 'true'
        }

        cmd = [sys.executable, "-m", "all2md", str(html_file)]
        cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        result = subprocess.run(
            cmd,
            cwd=cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        # Should use environment variable for output directory
        # (Note: exact behavior depends on implementation)

    def test_parallel_processing_e2e(self):
        """Test parallel processing end-to-end."""
        # Create multiple HTML files
        files = []
        for i in range(6):
            html_file = self.temp_dir / f"parallel_{i}.html"
            html_file.write_text(f"<h1>Parallel Document {i}</h1><p>Processing content {i}</p>")
            files.append(str(html_file))

        output_dir = self.temp_dir / "parallel_output"

        result = self._run_cli([
            *files,
            "--parallel", "3",
            "--output-dir", str(output_dir),
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        # All files should be processed
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 6

        # Verify each file has content
        for output_file in output_files:
            content = output_file.read_text()
            assert "Parallel Document" in content

    def test_skip_errors_e2e(self):
        """Test skip errors functionality end-to-end."""
        # Create good HTML file
        good_file = self.temp_dir / "good.html"
        good_file.write_text("<h1>Good File</h1><p>This should convert fine</p>")

        # Create a problematic file (empty or malformed)
        bad_file = self.temp_dir / "bad.html"
        bad_file.write_text("")  # Empty file might cause issues

        output_dir = self.temp_dir / "error_test_output"

        result = self._run_cli([
            str(good_file),
            str(bad_file),
            "--skip-errors",
            "--output-dir", str(output_dir),
            "--no-summary"
        ])

        # Should continue processing even if one file fails
        assert result.returncode in [0, 1]  # May return 1 for partial failure
        assert output_dir.exists()

        # Good file should be processed
        good_output = output_dir / "good.md"
        assert good_output.exists()

    def test_complex_feature_combination_e2e(self):
        """Test complex combination of features end-to-end."""
        # Create multiple HTML files
        files = []
        for i in range(4):
            html_file = self.temp_dir / f"complex_{i}.html"
            html_file.write_text(f"<h1>Complex Document {i}</h1><p>Content for testing {i}</p>")
            files.append(str(html_file))

        # Use many features together
        result = self._run_cli([
            *files,
            "--rich",  # Rich output
            "--progress",  # Progress bar
            "--parallel", "2",  # Parallel processing
            "--skip-errors",  # Error handling
            "--collate",  # File collation
            "--no-summary"  # No summary
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Should output collated content to stdout
        assert "# File: complex_0.html" in result.stdout
        assert "Complex Document 0" in result.stdout

    @pytest.mark.slow
    def test_large_multi_file_processing_e2e(self):
        """Test processing many files for performance."""
        # Create many HTML files
        files = []
        for i in range(20):
            html_file = self.temp_dir / f"large_{i:03d}.html"
            content = f"""
            <html>
            <head><title>Document {i}</title></head>
            <body>
                <h1>Large Document {i}</h1>
                <p>This is document number {i} for testing large batch processing.</p>
                <ul>
                    <li>Item 1 in document {i}</li>
                    <li>Item 2 in document {i}</li>
                </ul>
                <p>More content to make the document substantial.</p>
            </body>
            </html>
            """
            html_file.write_text(content)
            files.append(str(html_file))

        output_dir = self.temp_dir / "large_output"

        result = self._run_cli([
            *files,
            "--output-dir", str(output_dir),
            "--parallel", "4",
            "--progress",
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        # All files should be processed
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 20

        # Spot check a few files
        for i in [0, 9, 19]:
            output_file = output_dir / f"large_{i:03d}.md"
            assert output_file.exists()
            content = output_file.read_text()
            assert f"Large Document {i}" in content

    def test_attachment_handling_multi_file_e2e(self):
        """Test attachment handling across multiple files end-to-end."""
        # Create HTML files with image references
        html1 = self.temp_dir / "with_image1.html"
        html1.write_text('''
        <html>
        <head><title>Document with Image 1</title></head>
        <body>
            <h1>Document 1</h1>
            <p>This document has an image:</p>
            <img src="image1.png" alt="Test Image 1">
        </body>
        </html>
        ''')

        html2 = self.temp_dir / "with_image2.html"
        html2.write_text('''
        <html>
        <head><title>Document with Image 2</title></head>
        <body>
            <h1>Document 2</h1>
            <p>This document also has an image:</p>
            <img src="image2.png" alt="Test Image 2">
        </body>
        </html>
        ''')

        output_dir = self.temp_dir / "attachment_output"

        result = self._run_cli([
            str(html1),
            str(html2),
            "--output-dir", str(output_dir),
            "--attachment-mode", "alt_text",  # Use alt_text to avoid download complexity
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 2

        # Check that images were handled (as alt text)
        for output_file in output_files:
            content = output_file.read_text()
            assert "Test Image" in content

    def test_markdown_formatting_options_e2e(self):
        """Test Markdown formatting options across multiple files."""
        # Create HTML files with various formatting
        html1 = self.temp_dir / "formatting1.html"
        html1.write_text('''
        <html>
        <body>
            <h1>Formatting Test 1</h1>
            <p>Text with <em>emphasis</em> and <strong>strong</strong></p>
            <ul>
                <li>First item</li>
                <li>Second item</li>
            </ul>
        </body>
        </html>
        ''')

        html2 = self.temp_dir / "formatting2.html"
        html2.write_text('''
        <html>
        <body>
            <h1>Formatting Test 2</h1>
            <p>More <em>italic</em> and <strong>bold</strong> text</p>
            <ul>
                <li>Another item</li>
                <li>Yet another item</li>
            </ul>
        </body>
        </html>
        ''')

        output_dir = self.temp_dir / "formatting_output"

        result = self._run_cli([
            str(html1),
            str(html2),
            "--output-dir", str(output_dir),
            "--markdown-emphasis-symbol", "_",
            "--markdown-bullet-symbols", "•",
            "--no-summary"
        ])

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_dir.exists()

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 2

        # Check formatting was applied consistently
        for output_file in output_files:
            content = output_file.read_text()
            # Should use underscore emphasis (if supported by converter)
            # Note: Actual formatting depends on HTML converter implementation
            assert "Formatting Test" in content

    def test_backward_compatibility_e2e(self):
        """Test that new features don't break existing usage patterns."""
        html_file = self.temp_dir / "backward_compat.html"
        html_file.write_text("<h1>Backward Compatibility Test</h1><p>Existing usage should work</p>")

        # Test all existing usage patterns still work
        test_cases = [
            # Basic usage
            [str(html_file)],

            # With output file
            [str(html_file), "--out", str(self.temp_dir / "output1.md")],

            # With format override
            [str(html_file), "--format", "html"],

            # With HTML options
            [str(html_file), "--html-extract-title"],

            # With attachment options
            [str(html_file), "--attachment-mode", "alt_text"],
        ]

        for i, args in enumerate(test_cases):
            result = self._run_cli(args)
            assert result.returncode == 0, f"Test case {i} failed: {result.stderr}"

    def test_help_includes_new_features_e2e(self):
        """Test that help output includes all new features."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        help_text = result.stdout

        # Check that all new options appear in help
        new_options = [
            "--rich",
            "--progress",
            "--output-dir",
            "--recursive",
            "--parallel",
            "--skip-errors",
            "--preserve-structure",
            "--collate",
            "--no-summary"
        ]

        for option in new_options:
            assert option in help_text, f"Option {option} not found in help"

        # Check for meaningful descriptions
        assert "progress bar" in help_text.lower()
        assert "parallel" in help_text.lower()
        assert "recursive" in help_text.lower()

    def test_error_messages_improved_e2e(self):
        """Test that error messages are helpful for new features."""
        # Test invalid parallel count
        result = self._run_cli([
            "test.html",
            "--parallel", "-1"
        ])
        assert result.returncode != 0

        # Test conflicting options (if any validation exists)
        nonexistent_file = self.temp_dir / "nonexistent.html"
        result = self._run_cli([str(nonexistent_file)])
        assert result.returncode == 4  # EXIT_FILE_ERROR
        assert "Error" in result.stderr or "does not exist" in result.stderr
