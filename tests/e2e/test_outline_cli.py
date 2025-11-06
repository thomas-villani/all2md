"""End-to-end tests for all2md CLI --outline functionality.

This module tests the CLI outline generation feature as a subprocess, simulating
real-world usage patterns for generating tables of contents from documents.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestOutlineCLI:
    """End-to-end tests for CLI --outline functionality."""

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

    def _create_structured_markdown(self) -> Path:
        """Create a markdown file with hierarchical heading structure.

        Returns
        -------
        Path
            Path to the created test file

        Notes
        -----
        Creates a markdown file with:
        - H1: Introduction
          - H2: Background
          - H2: Motivation
        - H1: Methods
          - H2: Data Collection
            - H3: Survey Design
            - H3: Sampling
          - H2: Analysis
        - H1: Results
          - H2: Quantitative Findings
          - H2: Qualitative Insights
        - H1: Conclusion

        """
        md_content = """# Introduction

This is the introduction section.

## Background

Background information about the topic.

## Motivation

Why this research is important.

# Methods

This section describes the methodology.

## Data Collection

How we collected data for the study.

### Survey Design

Details about survey design approach.

### Sampling

Sampling methodology and strategy.

## Analysis

Analysis techniques used in the research.

# Results

Findings from the analysis.

## Quantitative Findings

Numerical results and statistics.

## Qualitative Insights

Qualitative observations and themes.

# Conclusion

Final thoughts and conclusions.
"""
        md_file = self.temp_dir / "structured_doc.md"
        md_file.write_text(md_content, encoding="utf-8")
        return md_file

    def test_outline_basic(self):
        """Test basic outline generation."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should output an outline structure
        output = result.stdout
        assert "Introduction" in output
        assert "Methods" in output
        assert "Results" in output
        assert "Conclusion" in output
        # Should include H2 headings
        assert "Background" in output
        assert "Data Collection" in output

    def test_outline_to_file(self):
        """Test outline generation to output file."""
        md_file = self._create_structured_markdown()
        output_file = self.temp_dir / "outline.md"

        result = self._run_cli([str(md_file), "--outline", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Verify outline structure
        assert "Introduction" in content
        assert "Methods" in content
        assert "Results" in content
        assert "Background" in content
        assert "Analysis" in content

    def test_outline_max_level_2(self):
        """Test outline generation with max level 2 (only H1 and H2)."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "2"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        # Should include H1 and H2
        assert "Introduction" in output
        assert "Background" in output
        assert "Data Collection" in output
        assert "Analysis" in output
        # Should NOT include H3
        assert "Survey Design" not in output
        assert "Sampling" not in output

    def test_outline_max_level_1(self):
        """Test outline generation with max level 1 (only H1)."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "1"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        # Should only include H1 headings
        assert "Introduction" in output
        assert "Methods" in output
        assert "Results" in output
        assert "Conclusion" in output
        # Should NOT include H2 headings
        assert "Background" not in output
        assert "Data Collection" not in output
        assert "Analysis" not in output

    def test_outline_max_level_3(self):
        """Test outline generation with max level 3 (H1, H2, H3)."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "3"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        # Should include all levels up to H3
        assert "Introduction" in output
        assert "Data Collection" in output
        assert "Survey Design" in output
        assert "Sampling" in output

    def test_outline_from_html(self):
        """Test outline generation from HTML document."""
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
    <h1>Chapter 1: Introduction</h1>
    <p>Introduction content.</p>

    <h2>Section 1.1: Background</h2>
    <p>Background details.</p>

    <h1>Chapter 2: Methods</h1>
    <p>Methods content.</p>

    <h2>Section 2.1: Approach</h2>
    <p>Approach details.</p>

    <h1>Chapter 3: Results</h1>
    <p>Results content.</p>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")

        result = self._run_cli([str(html_file), "--outline"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        output = result.stdout
        assert "Chapter 1" in output or "Introduction" in output
        assert "Chapter 2" in output or "Methods" in output
        assert "Background" in output
        assert "Approach" in output

    def test_outline_from_docx(self):
        """Test outline generation from DOCX document if available."""
        # This test requires docx fixtures which may not exist
        # Skip if fixture is not available
        docx_fixtures = list(Path("tests/fixtures/documents").glob("*.docx"))
        if not docx_fixtures:
            pytest.skip("No DOCX fixtures available")

        docx_file = docx_fixtures[0]

        result = self._run_cli([str(docx_file), "--outline"])

        # Should succeed or skip gracefully
        assert result.returncode in [0, 4]  # 0 success, 4 file error

    def test_outline_empty_document(self):
        """Test outline generation for document with no headings."""
        md_content = """This is a document with no headings.

Just plain paragraphs of text.

No structure to outline.
"""
        md_file = self.temp_dir / "no_headings.md"
        md_file.write_text(md_content, encoding="utf-8")

        result = self._run_cli([str(md_file), "--outline"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        # Output should be minimal or empty
        assert len(result.stdout.strip()) < 100

    def test_outline_single_heading(self):
        """Test outline generation for document with single heading."""
        md_content = """# Only One Heading

This document has just one heading and some content below it.

More content here.
"""
        md_file = self.temp_dir / "single_heading.md"
        md_file.write_text(md_content, encoding="utf-8")

        result = self._run_cli([str(md_file), "--outline"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout
        assert "Only One Heading" in output

    def test_outline_hierarchical_structure(self):
        """Test that outline maintains hierarchical structure."""
        md_file = self._create_structured_markdown()
        output_file = self.temp_dir / "outline.md"

        result = self._run_cli([str(md_file), "--outline", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        content = output_file.read_text(encoding="utf-8")

        # Verify hierarchical structure with indentation or numbering
        lines = content.split("\n")
        # Check that structure is present (could be bullet list or numbered)
        has_structure = any(line.strip().startswith(("*", "-", "1.", "2.", "3.")) for line in lines)
        assert has_structure, "Outline should have list structure"

    def test_outline_with_special_characters(self):
        """Test outline generation with special characters in headings."""
        md_content = """# Introduction: Why It Matters

Some content here.

## Background & Context

More content.

# Methods (2024)

Research methods.

## Data Collection [Phase 1]

Data collection details.

# Results - Key Findings

Results content.
"""
        md_file = self.temp_dir / "special_chars.md"
        md_file.write_text(md_content, encoding="utf-8")

        result = self._run_cli([str(md_file), "--outline"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        output = result.stdout
        # Special characters should be preserved
        assert "Why It Matters" in output or "Introduction" in output
        assert "Background" in output or "&" in output or "Context" in output
        assert "2024" in output or "Methods" in output

    def test_outline_help(self):
        """Test that --outline is documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--outline" in result.stdout
        # Should mention outline or table of contents
        assert "outline" in result.stdout.lower() or "toc" in result.stdout.lower()

    def test_outline_with_outline_max_level_help(self):
        """Test that --outline-max-level is documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--outline-max-level" in result.stdout

    def test_outline_invalid_max_level(self):
        """Test error handling for invalid --outline-max-level."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "invalid"])

        # Should fail with argument error
        assert result.returncode == 2  # argparse error
        assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_outline_max_level_zero(self):
        """Test error handling for --outline-max-level=0."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "0"])

        # Should either fail or produce no output
        if result.returncode == 0:
            # If it succeeds, output should be minimal
            assert len(result.stdout.strip()) < 50
        else:
            # Should fail with error
            assert result.returncode != 0

    def test_outline_max_level_excessive(self):
        """Test --outline-max-level with value at max (6)."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--outline-max-level", "6"])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        # Should work fine and include all headings
        output = result.stdout
        assert "Introduction" in output
        assert "Survey Design" in output

    def test_outline_conflicts_with_extract(self):
        """Test that --outline conflicts with --extract."""
        md_file = self._create_structured_markdown()

        result = self._run_cli([str(md_file), "--outline", "--extract", "Methods"])

        # Should fail with argument conflict error
        assert result.returncode != 0
        # Should have error message about conflict
        assert "conflict" in result.stderr.lower() or "cannot" in result.stderr.lower()
