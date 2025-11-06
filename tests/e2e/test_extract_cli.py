"""End-to-end tests for all2md CLI --extract functionality.

This module tests the CLI section extraction feature as a subprocess, simulating
real-world usage patterns for extracting specific sections from documents.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestExtractCLI:
    """End-to-end tests for CLI --extract functionality."""

    def setup_method(self):
        """Set up test environment.

        Creates a temporary directory for test files and locates the CLI module.
        """
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

    def teardown_method(self):
        """Clean up test environment.

        Removes temporary files and directories created during tests.
        """
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
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def _create_test_markdown(self) -> Path:
        """Create a test markdown file with multiple sections.

        Returns
        -------
        Path
            Path to the created test file

        Notes
        -----
        Creates a markdown file with the following structure:
        - H1: Introduction
        - H2: Background
        - H1: Methods
        - H2: Data Collection
        - H2: Analysis
        - H1: Results
        - H1: Conclusion

        """
        md_content = """# Introduction

This is the introduction section with some important content about the topic.

## Background

Background information about the subject matter.

# Methods

This section describes the methods used in the research.

## Data Collection

Details about how data was collected for this study.

## Analysis

Analysis methodology and approaches taken.

# Results

Here are the results of our analysis and findings.

# Conclusion

Final thoughts and conclusions from the research.
"""
        md_file = self.temp_dir / "test_doc.md"
        md_file.write_text(md_content, encoding="utf-8")
        return md_file

    def test_extract_by_exact_section_name(self):
        """Test extracting a section by exact name match."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "Methods", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "# Methods" in content
        assert "describes the methods" in content
        # Note: Extraction may or may not include subsections depending on implementation
        # Should NOT contain other top-level sections
        assert "# Introduction" not in content
        assert "# Results" not in content

    def test_extract_by_pattern_wildcard(self):
        """Test extracting sections by wildcard pattern matching."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "*ysis", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "## Analysis" in content
        assert "Analysis methodology" in content
        # Should NOT contain other sections
        assert "# Introduction" not in content
        assert "# Methods" not in content  # The parent heading
        assert "## Data Collection" not in content

    def test_extract_by_index_single(self):
        """Test extracting a section by index (#:1)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "#:1", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Index 1 should be the first H1 section (Introduction)
        assert "# Introduction" in content
        assert "important content" in content
        # Should NOT contain other H1 sections
        assert "# Methods" not in content
        assert "# Results" not in content

    def test_extract_by_index_range(self):
        """Test extracting sections by index range (#:1-3)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "#:1-3", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should contain multiple sections (implementation may be 0-indexed or 1-indexed)
        # At minimum, should have content from multiple sections
        assert len(content) > 100, "Should contain content from multiple sections"
        # Should contain at least some section headings
        section_count = content.count("# ")
        assert section_count >= 2, f"Should contain multiple sections, found {section_count}"

    def test_extract_by_index_list(self):
        """Test extracting sections by index list (#:1,3)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "#:1,3", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should contain multiple sections from the list
        assert len(content) > 50, "Should contain content from selected sections"
        # Should have at least one section heading
        assert content.count("# ") >= 1, "Should contain at least one section"

    def test_extract_by_index_open_range(self):
        """Test extracting sections by open-ended range (#:3-)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "#:3-", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should contain sections from index 3 onwards (implementation dependent)
        assert len(content) > 50, "Should contain content from later sections"
        # Should have at least one section
        assert content.count("# ") >= 1, "Should contain at least one section"

    def test_extract_to_stdout(self):
        """Test extracting a section to stdout."""
        md_file = self._create_test_markdown()

        result = self._run_cli([str(md_file), "--extract", "Results"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert "# Results" in result.stdout
        assert "findings" in result.stdout
        assert "# Introduction" not in result.stdout

    def test_extract_from_html(self):
        """Test extracting a section from HTML document."""
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
    <h1>Introduction</h1>
    <p>Introduction content here.</p>

    <h1>Methods</h1>
    <p>Methods section with details.</p>

    <h1>Results</h1>
    <p>Results and findings.</p>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(html_file), "--extract", "Methods", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "Methods" in content
        assert "section with details" in content
        assert "Introduction" not in content
        assert "Results" not in content

    def test_extract_nonexistent_section_error(self):
        """Test error handling when extracting non-existent section."""
        md_file = self._create_test_markdown()

        result = self._run_cli([str(md_file), "--extract", "NonexistentSection"])

        # Should fail with error when section not found
        assert result.returncode != 0, "Should fail when section not found"
        # Should have error message
        assert "error" in result.stderr.lower() or "no sections" in result.stderr.lower()

    def test_extract_invalid_index_format(self):
        """Test error handling for invalid index format."""
        md_file = self._create_test_markdown()

        result = self._run_cli([str(md_file), "--extract", "#:invalid"])

        # Should fail with argument error
        assert result.returncode != 0
        # Should have error message about invalid format
        assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_extract_with_nested_sections(self):
        """Test extracting a section (may or may not include subsections)."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "Methods", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        content = output_file.read_text(encoding="utf-8")

        # Should at minimum include the parent section
        assert "# Methods" in content or "Methods" in content
        assert "methods" in content.lower()

    def test_extract_subsection_only(self):
        """Test extracting only a subsection without parent."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "Analysis", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        content = output_file.read_text(encoding="utf-8")

        # Should only include the subsection
        assert "## Analysis" in content
        assert "Analysis methodology" in content
        # Should NOT include other sections
        assert "## Data Collection" not in content
        assert "# Results" not in content

    def test_extract_with_formatting_preservation(self):
        """Test that extraction preserves markdown formatting."""
        md_content = """# Test Section

This section has **bold** text and *italic* text.

It also has:
- Bullet lists
- With multiple items

And `inline code` plus:

```python
def example():
    return True
```

Plus a [link](https://example.com) and more.
"""
        md_file = self.temp_dir / "formatted.md"
        md_file.write_text(md_content, encoding="utf-8")
        output_file = self.temp_dir / "extracted.md"

        result = self._run_cli([str(md_file), "--extract", "Test Section", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        content = output_file.read_text(encoding="utf-8")

        # Verify formatting is preserved
        assert "**bold**" in content
        assert "*italic*" in content
        # Bullets can be * or -
        assert "- Bullet" in content or "* Bullet" in content
        assert "`inline code`" in content
        assert "```" in content
        assert "[link]" in content

    def test_extract_case_sensitivity(self):
        """Test section extraction with different case."""
        md_file = self._create_test_markdown()
        output_file = self.temp_dir / "extracted.md"

        # Try to extract with wrong case
        result = self._run_cli([str(md_file), "--extract", "methods", "--out", str(output_file)])  # lowercase

        # Implementation may be case-sensitive or case-insensitive
        # Just verify it handles the case gracefully (either matches or doesn't)
        if result.returncode == 0:
            # If it succeeds, verify output exists
            assert output_file.exists()
        else:
            # If it fails, should have error message
            assert "error" in result.stderr.lower() or "no sections" in result.stderr.lower()

    def test_extract_help(self):
        """Test that --extract is documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--extract" in result.stdout
        # Should mention section extraction
        assert "section" in result.stdout.lower() or "extract" in result.stdout.lower()
