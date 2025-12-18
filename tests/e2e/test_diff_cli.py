"""End-to-end tests for all2md diff CLI command.

This module tests the diff command as a subprocess, simulating real-world usage
patterns and testing the complete pipeline from command-line to output.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir

pytest.importorskip("mistune", reason="mistune not installed, skipping diff CLI tests")


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.slow
class TestDiffCLI:
    """End-to-end tests for diff CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

        # Create two test markdown files with differences
        self.file1 = self.temp_dir / "doc1.md"
        self.file1.write_text(
            """# Document Title

## Introduction
This is the original introduction.

## Methods
We used traditional approaches.

## Results
The results were good.
""",
            encoding="utf-8",
        )

        self.file2 = self.temp_dir / "doc2.md"
        self.file2.write_text(
            """# Document Title

## Introduction
This is the updated introduction with new content.

## Methodology
We used modern approaches with AI.

## Results
The results exceeded expectations.

## Conclusion
We achieved our goals.
""",
            encoding="utf-8",
        )

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_diff(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run diff command as a subprocess.

        Parameters
        ----------
        args : list[str]
            Arguments to pass to diff command

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md", "diff"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def test_basic_diff(self):
        """Test basic diff between two files."""
        result = self._run_diff([str(self.file1), str(self.file2)])

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert result.stdout, "No output generated"
        # Check that it's unified diff by default
        assert "---" in result.stdout
        assert "+++" in result.stdout
        assert "@@" in result.stdout

    def test_diff_html_format(self):
        """Test diff with HTML format."""
        result = self._run_diff([str(self.file1), str(self.file2), "--format", "html"])

        assert result.returncode == 0
        assert result.stdout, "No output generated"
        # Should contain HTML
        assert "<!DOCTYPE html>" in result.stdout
        assert "Document Diff" in result.stdout
        assert "diff-summary" in result.stdout

    def test_diff_json_format(self):
        """Test diff with JSON format."""
        result = self._run_diff([str(self.file1), str(self.file2), "--format", "json"])

        assert result.returncode == 0
        assert result.stdout, "No output generated"

        # Validate JSON structure
        data = json.loads(result.stdout)
        assert "type" in data
        assert data["type"] == "unified_diff"
        assert "statistics" in data
        assert "hunks" in data
        assert "old_file" in data
        assert "new_file" in data
        assert data["granularity"] == "block"

    def test_diff_unified_format(self):
        """Test diff with unified format."""
        result = self._run_diff([str(self.file1), str(self.file2), "--format", "unified"])

        assert result.returncode == 0
        assert result.stdout, "No output generated"
        # Check for unified diff markers
        assert "---" in result.stdout
        assert "+++" in result.stdout
        assert "@@" in result.stdout

    def test_diff_with_output_file(self):
        """Test diff with file output."""
        output_file = self.temp_dir / "diff.html"
        result = self._run_diff([str(self.file1), str(self.file2), "--format", "html", "--output", str(output_file)])

        assert result.returncode == 0
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Document Diff" in content

    def test_diff_with_ignore_whitespace(self):
        """Test diff with ignore-whitespace option."""
        result = self._run_diff([str(self.file1), str(self.file2), "--ignore-whitespace"])

        assert result.returncode == 0
        # Should still produce diff output
        assert "---" in result.stdout
        assert "+++" in result.stdout

    def test_diff_with_context_lines(self):
        """Test diff with custom context lines."""
        result = self._run_diff([str(self.file1), str(self.file2), "--context", "5"])

        assert result.returncode == 0
        # Should still produce valid unified diff
        assert "---" in result.stdout
        assert "+++" in result.stdout
        assert "@@" in result.stdout

    def test_diff_identical_files(self):
        """Test diff with identical files."""
        # Create identical file
        file3 = self.temp_dir / "doc3.md"
        file3.write_text(self.file1.read_text(), encoding="utf-8")

        result = self._run_diff([str(self.file1), str(file3)])

        assert result.returncode == 0
        # Stderr should indicate no differences
        assert "No differences found" in result.stderr

    def test_diff_missing_file(self):
        """Test diff with missing file."""
        missing_file = self.temp_dir / "nonexistent.md"
        result = self._run_diff([str(self.file1), str(missing_file)])

        assert result.returncode != 0, "Should fail with missing file"
        assert "not found" in result.stderr.lower()

    def test_diff_help(self):
        """Test diff help output."""
        result = self._run_diff(["--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "original" in result.stdout.lower()
        assert "modified" in result.stdout.lower()
        assert "--format" in result.stdout

    def test_diff_cross_format(self):
        """Test diff between different formats."""
        # Create an HTML file
        html_file = self.temp_dir / "doc.html"
        html_file.write_text(
            """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<h1>Document Title</h1>
<h2>Introduction</h2>
<p>This is content.</p>
</body>
</html>""",
            encoding="utf-8",
        )

        # Compare HTML with Markdown
        result = self._run_diff([str(html_file), str(self.file1), "--format", "json"])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "statistics" in data

    def test_diff_context_lines(self):
        """Test diff with custom context lines."""
        for context in [1, 5, 10]:
            result = self._run_diff(
                [str(self.file1), str(self.file2), "--format", "unified", "--context", str(context)]
            )

            assert result.returncode == 0, f"Context lines {context} failed"

    def test_diff_sentence_granularity(self):
        """Test diff with sentence granularity."""
        result = self._run_diff([str(self.file1), str(self.file2), "--granularity", "sentence", "--format", "unified"])

        assert result.returncode == 0
        # Sentence granularity should surface the changed heading separately
        assert "-## Methods" in result.stdout or "-## Methodology" in result.stdout

    def test_diff_word_granularity(self):
        """Test diff with word granularity."""
        result = self._run_diff([str(self.file1), str(self.file2), "--granularity", "word", "--format", "unified"])

        assert result.returncode == 0
        # Word granularity should show individual tokens
        assert any(line.startswith("+") and "updated" in line.lower() for line in result.stdout.splitlines())

    def test_diff_color_flag(self):
        """Test diff with color options."""
        # Test --color never (should work without errors)
        result = self._run_diff([str(self.file1), str(self.file2), "--color", "never"])
        assert result.returncode == 0

        # Test --color always (should work without errors)
        result = self._run_diff([str(self.file1), str(self.file2), "--color", "always"])
        assert result.returncode == 0

        # Test --color auto (default, should work)
        result = self._run_diff([str(self.file1), str(self.file2), "--color", "auto"])
        assert result.returncode == 0
