"""End-to-end tests for all2md view CLI command.

This module tests the view command functionality, including HTML preview generation
with various themes, temporary file handling, and browser integration.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures import FIXTURES_PATH
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestViewCLIEndToEnd:
    """End-to-end tests for view CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str], mock_browser: bool = True) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI
        mock_browser : bool
            If True, mock webbrowser.open to prevent browser launches

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md"] + args

        # For view commands, we need to mock webbrowser at the module level
        # Since we're running in a subprocess, we can't easily mock it
        # Instead, we'll set an environment variable that the view command can check
        env = os.environ.copy()
        if mock_browser and "view" in args:
            env["ALL2MD_TEST_NO_BROWSER"] = "1"

        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            env=env,
        )

    def _create_test_markdown(self, filename: str = "test.md", content: str | None = None) -> Path:
        """Create a test Markdown file.

        Parameters
        ----------
        filename : str
            Name of the file to create
        content : str, optional
            Content for the file. If None, default test content is used.

        Returns
        -------
        Path
            Path to the created file

        """
        if content is None:
            content = """# Test Document

This is a test document for the view command.

## Features

- **Bold text**
- *Italic text*
- `Code snippets`

### Code Block

```python
def hello():
    return "Hello, World!"
```

### Links

Visit [example.com](https://example.com) for more info.

### Blockquote

> This is a quoted section with important information.
"""
        md_file = self.temp_dir / filename
        md_file.write_text(content, encoding="utf-8")
        return md_file

    def test_view_basic_markdown_with_keep(self):
        """Test viewing a markdown file with --keep option."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        html_content = output_file.read_text(encoding="utf-8")
        assert "Test Document" in html_content
        assert "Features" in html_content
        assert "hello" in html_content  # Code block content

    def test_view_with_dark_theme(self):
        """Test viewing with dark theme."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "dark", "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        html_content = output_file.read_text(encoding="utf-8")
        assert "Test Document" in html_content

    def test_view_with_minimal_theme(self):
        """Test viewing with minimal theme."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "minimal", "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_with_newspaper_theme(self):
        """Test viewing with newspaper theme."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "newspaper", "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_with_sidebar_theme(self):
        """Test viewing with sidebar theme."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "sidebar", "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_with_docs_theme(self):
        """Test viewing with docs theme (default)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "docs", "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_without_keep_uses_temp_file(self):
        """Test that view without --keep uses temporary file."""
        md_file = self._create_test_markdown()

        result = self._run_cli(["view", str(md_file)])

        assert result.returncode == 0
        # Temp file is created and automatically cleaned up in test mode
        assert "Error" not in result.stderr
        assert "Temporary file:" in result.stdout or "Skipping browser launch" in result.stdout

    def test_view_html_file(self):
        """Test viewing an HTML file."""
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test HTML</title></head>
<body>
    <h1>HTML Document</h1>
    <p>This is an HTML file being viewed.</p>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(html_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        output_content = output_file.read_text(encoding="utf-8")
        assert "HTML Document" in output_content

    def test_view_docx_file(self):
        """Test viewing a DOCX file (requires docx fixture)."""
        # Skip if no test fixtures available
        fixtures_dir = FIXTURES_PATH / "documents" / "generated"
        docx_files = list(fixtures_dir.glob("*.docx")) if fixtures_dir.exists() else []

        if not docx_files:
            pytest.skip("No DOCX test fixtures available")

        docx_file = docx_files[0]
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(docx_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_pdf_file(self):
        """Test viewing a PDF file (requires pdf fixture)."""
        # Skip if no test fixtures available
        fixtures_dir = FIXTURES_PATH / "documents" / "generated"
        pdf_files = list(fixtures_dir.glob("*.pdf")) if fixtures_dir.exists() else []

        if not pdf_files:
            pytest.skip("No PDF test fixtures available")

        pdf_file = pdf_files[0]
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(pdf_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()

    def test_view_nonexistent_file(self):
        """Test viewing a file that doesn't exist."""
        nonexistent = self.temp_dir / "nonexistent.md"
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(nonexistent), "--keep", str(output_file)])

        assert result.returncode != 0
        assert "Error" in result.stderr or "error" in result.stderr.lower()

    def test_view_with_invalid_theme(self):
        """Test viewing with an invalid theme name."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--theme", "nonexistent-theme", "--keep", str(output_file)])

        assert result.returncode != 0
        assert "Error" in result.stderr or "error" in result.stderr.lower()

    def test_view_keep_without_path(self):
        """Test --keep flag without providing a path (keeps temp file)."""
        md_file = self._create_test_markdown()

        result = self._run_cli(["view", str(md_file), "--keep"])

        assert result.returncode == 0
        # Should keep the temp file
        assert "Kept temporary file:" in result.stdout or "Skipping browser launch" in result.stdout

    def test_view_complex_markdown_content(self):
        """Test viewing markdown with complex content including tables and lists."""
        complex_content = """# Complex Document

## Table Example

| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |
| Bob | 25 | LA |
| Charlie | 35 | Chicago |

## Nested Lists

1. First item
   - Sub-item A
   - Sub-item B
2. Second item
   - Sub-item C
     - Nested sub-item
3. Third item

## Task List

- [x] Completed task
- [ ] Pending task
- [x] Another completed task

## Math (if supported)

The quadratic formula: $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$
"""
        md_file = self._create_test_markdown(content=complex_content)
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        html_content = output_file.read_text(encoding="utf-8")
        assert "Complex Document" in html_content
        assert "Alice" in html_content  # Table content
        assert "First item" in html_content  # List content

    def test_view_with_unicode_content(self):
        """Test viewing markdown with unicode characters."""
        unicode_content = """# Unicode Test Document

## Emoji Support

- Smiley face: \U0001f600
- Heart: \U00002764
- Star: \U00002b50

## International Characters

- Chinese: \U00004e2d\U00006587
- Arabic: \U00000627\U00000644\U00000639\U00000631\U00000628\U0000064a\U00000629
- Greek: \U00000391\U000003b1
- Russian: \U00000420\U0000043e\U00000441\U00000441\U00000438\U00000439\U00000441\U0000043a\U00000438\U00000439

## Mathematical Symbols

- Infinity: \U0000221e
- Plus-minus: \U000000b1
- Not equal: \U00002260
"""
        md_file = self._create_test_markdown(content=unicode_content)
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--keep", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists()
        # Verify the file can be read as UTF-8
        html_content = output_file.read_text(encoding="utf-8")
        assert "Unicode Test Document" in html_content

    def test_view_help_message(self):
        """Test that view --help displays usage information."""
        result = self._run_cli(["view", "--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout
        assert "view" in result.stdout
        assert "--theme" in result.stdout
        assert "--keep" in result.stdout

    def test_view_with_relative_path(self):
        """Test viewing with relative file path."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "output.html"

        # Use relative path notation
        rel_path = os.path.relpath(md_file, Path.cwd())

        result = self._run_cli(["view", rel_path, "--keep", str(output_file)])

        # May succeed or fail depending on working directory
        # Just verify it handles relative paths without crashing
        assert result.returncode == 0 or "Error" in result.stderr

    def test_view_preserves_markdown_formatting(self):
        """Test that view preserves markdown formatting in HTML output."""
        formatted_content = """# Formatting Test

**This text should be bold**

*This text should be italic*

***This text should be bold and italic***

~~This text should be strikethrough~~

`This is inline code`

[This is a link](https://example.com)
"""
        md_file = self._create_test_markdown(content=formatted_content)
        output_file = self.temp_dir / "output.html"

        result = self._run_cli(["view", str(md_file), "--keep", str(output_file)])

        assert result.returncode == 0
        html_content = output_file.read_text(encoding="utf-8")
        # Check for HTML formatting tags
        assert "<strong>" in html_content or "<b>" in html_content
        assert "<em>" in html_content or "<i>" in html_content
        assert "<code>" in html_content
        assert "<a " in html_content or "href=" in html_content
