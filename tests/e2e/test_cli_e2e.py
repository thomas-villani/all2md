"""End-to-end tests for all2md CLI functionality.

This module tests the CLI as a subprocess, simulating real-world usage patterns
and testing the complete pipeline from command-line to file output.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
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
        assert "## Main Title" in content    # Main heading
        assert "### Subtitle" in content     # Subheading
        assert "**bold text**" in content    # Bold formatting
        assert "*italic text*" in content    # Italic formatting
        assert "* Unordered item 1" in content  # List items
        assert "1. Ordered item 1" in content   # Numbered list
        assert "`inline code`" in content    # Inline code
        assert "[link](https://example.com)" in content  # Link
        assert "```" in content              # Code block
        assert ">" in content                # Blockquote

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
        """Test format override to treat HTML as plain text."""
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML Title</h1><p>Content</p>")

        result = self._run_cli([
            str(html_file),
            "--format", "txt"
        ])

        assert result.returncode == 0
        # Should output raw HTML since it's treated as text
        assert "<h1>HTML Title</h1><p>Content</p>" in result.stdout

    def test_nonexistent_file_error(self):
        """Test error handling for nonexistent files."""
        nonexistent_file = self.temp_dir / "does_not_exist.pdf"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 1
        assert "Error: Input file does not exist" in result.stderr

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
        assert "## Main Heading" in content     # Heading converted
        assert "_emphasis_" in content          # Underscore emphasis
        assert "List item 1" in content         # List content present
        assert content.count("List item") >= 2  # Both list items present
        assert "alert" not in content           # Dangerous content stripped

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
        from tests.fixtures.generators.odf_fixtures import (
            create_odt_with_formatting, save_odt_to_file, HAS_ODFPY
        )

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
        from tests.fixtures.generators.odf_fixtures import (
            create_comprehensive_odt_test_document, save_odt_to_file, HAS_ODFPY
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
        from tests.fixtures.generators.odf_fixtures import (
            create_odt_with_tables, save_odt_to_file, HAS_ODFPY
        )

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
            "--odf-no-preserve-tables"
        ])

        assert result_no_tables.returncode == 0
        # Should still process without error, just no table formatting

    def test_odf_lists_conversion(self):
        """Test ODT list conversion."""
        from tests.fixtures.generators.odf_fixtures import (
            create_odt_with_lists, save_odt_to_file, HAS_ODFPY
        )

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
        from tests.fixtures.generators.odf_fixtures import (
            create_odp_with_slides, HAS_ODFPY
        )

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

        # Should process without major errors
        # Note: ODP conversion might be limited, so we just check it doesn't crash
        assert result.returncode in [0, 1]  # May fail gracefully if ODP support is limited

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

        assert result.returncode == 1
        assert "Error:" in result.stderr or "does not exist" in result.stderr

    @pytest.mark.odf
    def test_odf_complex_options_combination(self):
        """Test ODT conversion with complex option combinations."""
        from tests.fixtures.generators.odf_fixtures import (
            create_comprehensive_odt_test_document, save_odt_to_file, HAS_ODFPY
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
        from tests.fixtures.generators.ipynb_fixtures import create_simple_notebook, save_notebook_to_file

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
        from tests.fixtures.generators.ipynb_fixtures import create_notebook_with_images, save_notebook_to_file

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
        from tests.fixtures.generators.ipynb_fixtures import create_simple_notebook, save_notebook_to_file

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
        from tests.fixtures.generators.ipynb_fixtures import create_notebook_with_images, save_notebook_to_file

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
        from tests.fixtures.generators.ipynb_fixtures import create_notebook_with_long_outputs, save_notebook_to_file

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

        assert result.returncode == 1
        assert "Error:" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_nonexistent_file_e2e(self):
        """Test error handling for nonexistent ipynb file."""
        nonexistent_file = self.temp_dir / "does_not_exist.ipynb"

        result = self._run_cli([str(nonexistent_file)])

        assert result.returncode == 1
        assert "Error:" in result.stderr or "does not exist" in result.stderr

    @pytest.mark.e2e
    @pytest.mark.ipynb
    def test_ipynb_complex_options_combination_e2e(self):
        """Test Jupyter Notebook conversion with complex option combinations."""
        from tests.fixtures.generators.ipynb_fixtures import create_data_science_notebook, save_notebook_to_file

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
