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
        cmd = [sys.executable, "-m", "all2md.cli"] + args
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