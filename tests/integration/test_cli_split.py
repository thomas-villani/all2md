#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for document splitting CLI feature."""

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

from all2md.ast.document_splitter import DocumentSplitter, parse_split_spec
from all2md.ast.nodes import Document, Heading, Paragraph, Text
from all2md.cli.validation import collect_argument_problems


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_markdown_doc():
    """Create a sample document with multiple sections."""
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="This is the introduction section with some content.")]),
            Heading(level=1, content=[Text(content="Methods")]),
            Paragraph(content=[Text(content="This section describes the methods used in the study.")]),
            Heading(level=1, content=[Text(content="Results")]),
            Paragraph(content=[Text(content="Here are the results of our analysis.")]),
            Heading(level=1, content=[Text(content="Conclusion")]),
            Paragraph(content=[Text(content="Final thoughts and conclusions.")]),
        ]
    )


class TestCLISplitting:
    """Integration tests for CLI document splitting."""

    def test_split_by_h1(self, sample_markdown_doc, temp_output_dir):
        """Test splitting a document by H1 headings."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(sample_markdown_doc, level=1)

        assert len(splits) == 4
        assert splits[0].title == "Introduction"
        assert splits[1].title == "Methods"
        assert splits[2].title == "Results"
        assert splits[3].title == "Conclusion"

    def test_split_by_parts(self, sample_markdown_doc):
        """Test splitting a document into equal parts."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_parts(sample_markdown_doc, num_parts=2)

        assert len(splits) >= 2

        total_words = sum(split.word_count for split in splits)
        assert total_words > 0

    def test_split_with_title_slugs(self, sample_markdown_doc):
        """Test slug generation from section titles."""
        splitter = DocumentSplitter()
        splits = splitter.split_by_heading_level(sample_markdown_doc, level=1)

        assert len(splits) == 4

        for split in splits:
            if split.title and split.title != "Preamble":
                slug = split.get_filename_slug()
                assert slug
                assert slug.islower()
                assert " " not in slug

    def test_split_validation_requires_output(self):
        """Test that splitting requires output location."""
        args = argparse.Namespace(
            split_by="h1",
            out=None,
            output_dir=None,
            collate=False,
            extract=None,
            outline=False,
        )

        problems = collect_argument_problems(args)

        assert len(problems) > 0
        assert any("output" in str(problem).lower() for problem in problems)

    def test_split_conflicts_with_collate(self):
        """Test that splitting conflicts with collate."""
        args = argparse.Namespace(
            split_by="h1",
            out="output.md",
            output_dir=None,
            collate=True,
            extract=None,
            outline=False,
        )

        problems = collect_argument_problems(args)

        assert len(problems) > 0
        assert any("collate" in str(problem).lower() for problem in problems)

    def test_split_by_auto(self, sample_markdown_doc):
        """Test auto-detection splitting strategy."""
        splitter = DocumentSplitter()
        splits = splitter.split_auto(sample_markdown_doc)

        assert len(splits) >= 1

        for split in splits:
            assert split.document is not None
            assert split.word_count >= 0
            assert "strategy" in split.metadata

    def test_parse_split_spec_integration(self):
        """Test parsing various split specifications."""
        strategy, param = parse_split_spec("h1")
        assert strategy == "heading"
        assert param == 1

        strategy, param = parse_split_spec("length=500")
        assert strategy == "length"
        assert param == 500

        strategy, param = parse_split_spec("parts=3")
        assert strategy == "parts"
        assert param == 3

        strategy, param = parse_split_spec("auto")
        assert strategy == "auto"
        assert param is None


@pytest.mark.e2e
@pytest.mark.cli
class TestSplitCLIE2E:
    """End-to-end tests for CLI --split-by functionality using subprocess."""

    def setup_method(self):
        """Set up test environment.

        Creates a temporary directory for test files and locates the CLI module.
        """
        # Get the project root (3 levels up from this test file: tests/integration/test_cli_split.py)
        project_root = Path(__file__).parent.parent.parent
        self.temp_dir = project_root / "tmp_split_e2e"
        self.temp_dir.mkdir(exist_ok=True)
        self.cli_path = project_root / "src" / "all2md" / "cli" / "__init__.py"

    def teardown_method(self):
        """Clean up test environment.

        Removes temporary files and directories created during tests.
        """
        if self.temp_dir.exists():
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

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
        # Get project root (3 parents up from src/all2md/cli/__init__.py)
        project_root = self.cli_path.parent.parent.parent
        cmd = [sys.executable, "-m", "all2md"] + args
        return subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

    def _create_test_markdown(self) -> Path:
        """Create a test markdown file with multiple H1 sections.

        Returns
        -------
        Path
            Path to the created test file

        """
        md_content = """# Introduction

This is the introduction section with some content and details.

## Background

Some background information about the topic.

# Methods

This section describes the methods used in the research.

## Experimental Design

Details about the experimental design.

## Data Collection

Information about data collection procedures.

# Results

Here are the results of our analysis and findings.

## Key Findings

The main findings from the study.

# Discussion

Discussion of the results and their implications.

# Conclusion

Final thoughts and conclusions from the research.
"""
        md_file = self.temp_dir / "test_doc.md"
        md_file.write_text(md_content, encoding="utf-8")
        return md_file

    def test_split_by_h1(self):
        """Test splitting a document by H1 headings."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_h1"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "h1", "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check that multiple files were created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 4, f"Expected at least 4 files, got {len(output_files)}"

        # Verify content in split files
        all_content = ""
        for file in output_files:
            all_content += file.read_text(encoding="utf-8")

        assert "Introduction" in all_content
        assert "Methods" in all_content
        assert "Results" in all_content
        assert "Conclusion" in all_content

    def test_split_by_h2(self):
        """Test splitting a document by H2 headings."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_h2"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "h2", "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check that files were created (should be more than h1 split)
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, f"Expected at least 1 file, got {len(output_files)}"

    def test_split_by_parts(self):
        """Test splitting a document into equal parts."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_parts"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "parts=3", "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should create approximately 3 files
        output_files = list(output_dir.glob("*.md"))
        assert 2 <= len(output_files) <= 4, f"Expected 2-4 files for parts=3, got {len(output_files)}"

    def test_split_by_length(self):
        """Test splitting a document by character length."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_length"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(
            [
                str(md_file),
                "--split-by",
                "length=200",  # Use smaller length to ensure multiple files
                "--output-dir",
                str(output_dir),
            ]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check that files were created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, f"Expected at least 1 file, got {len(output_files)}"

        # Verify that files are reasonably sized
        for file in output_files:
            content = file.read_text(encoding="utf-8")
            # Files should be reasonably sized (implementation may vary)
            assert len(content) > 0, f"File {file.name} is empty"

    def test_split_by_auto(self):
        """Test auto-detection splitting strategy."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_auto"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "auto", "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check that files were created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, f"Expected at least 1 file, got {len(output_files)}"

    def test_split_naming_numeric(self):
        """Test splitting with numeric naming."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_numeric"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(
            [str(md_file), "--split-by", "h1", "--split-by-naming", "numeric", "--output-dir", str(output_dir)]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check for numeric filenames
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1

        # At least some files should have numeric names
        numeric_files = [f for f in output_files if any(char.isdigit() for char in f.stem)]
        assert len(numeric_files) >= 1, "Expected numeric filenames"

    def test_split_naming_title(self):
        """Test splitting with title-based naming."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_title"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(
            [str(md_file), "--split-by", "h1", "--split-by-naming", "title", "--output-dir", str(output_dir)]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check for title-based filenames
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1

        # Filenames should contain section titles (lowercased/slugified)
        filenames = [f.stem.lower() for f in output_files]
        title_based = any(
            "introduction" in f or "methods" in f or "results" in f or "conclusion" in f for f in filenames
        )
        assert title_based, "Expected title-based filenames"

    def test_split_digits_padding(self):
        """Test splitting with digit padding."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_digits"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(
            [
                str(md_file),
                "--split-by",
                "h1",
                "--split-by-naming",
                "numeric",
                "--split-by-digits",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check for zero-padded numeric filenames
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1

        # Check if any filenames have zero-padded numbers
        padded_files = [f for f in output_files if "001" in f.name or "002" in f.name or "000" in f.name]
        assert len(padded_files) >= 1, "Expected zero-padded numeric filenames"

    def test_split_without_output_dir_error(self):
        """Test that splitting without output directory fails."""
        md_file = self._create_test_markdown()

        result = self._run_cli([str(md_file), "--split-by", "h1"])

        # Should fail because no output location specified
        assert result.returncode != 0
        assert "output" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_split_with_collate_conflict(self):
        """Test that splitting conflicts with --collate."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_collate"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "h1", "--collate", "--output-dir", str(output_dir)])

        # Should fail due to conflict
        assert result.returncode != 0
        assert "collate" in result.stderr.lower() or "conflict" in result.stderr.lower()

    def test_split_invalid_strategy(self):
        """Test error handling for invalid split strategy."""
        md_file = self._create_test_markdown()
        output_dir = self.temp_dir / "split_invalid"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(md_file), "--split-by", "invalid_strategy", "--output-dir", str(output_dir)])

        # Should fail with invalid strategy error
        assert result.returncode != 0
        assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_split_from_html(self):
        """Test splitting an HTML document."""
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test Document</title></head>
<body>
    <h1>Chapter 1</h1>
    <p>Content for chapter 1.</p>

    <h1>Chapter 2</h1>
    <p>Content for chapter 2.</p>

    <h1>Chapter 3</h1>
    <p>Content for chapter 3.</p>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")
        output_dir = self.temp_dir / "split_html"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli([str(html_file), "--split-by", "h1", "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Check that files were created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 3, f"Expected at least 3 files, got {len(output_files)}"

    def test_split_help(self):
        """Test that --split-by is documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--split-by" in result.stdout
        # Should mention splitting strategies
        assert "split" in result.stdout.lower() or "h1" in result.stdout.lower()
