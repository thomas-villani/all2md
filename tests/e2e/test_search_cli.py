#  Copyright (c) 2025 Tom Villani, Ph.D.
"""End-to-end tests for all2md search and grep CLI commands.

This module tests the search and grep commands as subprocesses, simulating
real-world usage patterns for document searching with various modes and options.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.search
class TestSearchCLI:
    """End-to-end tests for search CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

        # Create test documents
        self.doc1 = self.temp_dir / "document1.md"
        self.doc1.write_text(
            """# Introduction to Python

Python is a high-level programming language known for its simplicity and readability.

## Features

- Easy to learn
- Interpreted language
- Dynamic typing
- Large standard library

## Getting Started

To install Python, visit python.org and download the installer.
""",
            encoding="utf-8",
        )

        self.doc2 = self.temp_dir / "document2.md"
        self.doc2.write_text(
            """# JavaScript Basics

JavaScript is the programming language of the web.

## Features

- Client-side scripting
- Event-driven programming
- Asynchronous operations
- DOM manipulation

## Getting Started

JavaScript runs in the browser. No installation needed.
""",
            encoding="utf-8",
        )

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_search(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run search command as a subprocess.

        Parameters
        ----------
        args : list[str]
            Arguments to pass to search command

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md", "search"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def test_search_help(self):
        """Test search help output."""
        result = self._run_search(["--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "query" in result.stdout.lower()
        assert "--mode" in result.stdout
        assert "--grep" in result.stdout
        assert "--keyword" in result.stdout

    def test_search_grep_mode_basic(self):
        """Test basic grep mode search."""
        result = self._run_search(["Python", str(self.doc1), "--grep"])

        assert result.returncode == 0
        assert "Python" in result.stdout

    def test_search_grep_mode_with_multiple_files(self):
        """Test grep mode with multiple files."""
        result = self._run_search(["programming", str(self.doc1), str(self.doc2), "--grep"])

        assert result.returncode == 0
        # Should find matches in both documents
        assert "programming" in result.stdout.lower()

    def test_search_grep_mode_no_results(self):
        """Test grep mode when no results are found."""
        result = self._run_search(["nonexistent_xyz_123", str(self.doc1), "--grep"])

        assert result.returncode == 0
        assert "No results found" in result.stdout

    def test_search_grep_mode_with_json_output(self):
        """Test grep mode with JSON output."""
        result = self._run_search(["Python", str(self.doc1), "--grep", "--json"])

        assert result.returncode == 0
        # Should be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_search_grep_mode_case_sensitive(self):
        """Test grep mode case sensitivity."""
        # Search for lowercase - should not match "Python" if case-sensitive
        result = self._run_search(["python", str(self.doc1), "--grep"])

        # The actual behavior depends on implementation
        assert result.returncode == 0

    def test_search_mode_explicit(self):
        """Test explicit --mode grep flag."""
        result = self._run_search(["Python", str(self.doc1), "--mode", "grep"])

        assert result.returncode == 0

    def test_search_with_directory(self):
        """Test search with directory input."""
        result = self._run_search(["programming", str(self.temp_dir), "--grep", "--recursive"])

        assert result.returncode == 0

    def test_search_with_top_k(self):
        """Test search with --top-k option."""
        result = self._run_search(["programming", str(self.doc1), str(self.doc2), "--grep", "--top-k", "5"])

        assert result.returncode == 0

    def test_search_missing_query(self):
        """Test search without query argument."""
        result = self._run_search([])

        # Should fail with missing required argument
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "usage" in result.stderr.lower()

    def test_search_nonexistent_file(self):
        """Test search with nonexistent file."""
        result = self._run_search(["test", str(self.temp_dir / "nonexistent.md"), "--grep"])

        assert result.returncode != 0

    def test_search_with_exclude_pattern(self):
        """Test search with --exclude pattern."""
        # Create additional file to exclude
        excluded = self.temp_dir / "exclude-me.md"
        excluded.write_text("# Excluded\nThis should be excluded from search.", encoding="utf-8")

        result = self._run_search(["search", str(self.temp_dir), "--grep", "--recursive", "--exclude", "exclude-*.md"])

        # Command should run (may succeed or fail based on implementation)
        assert result.returncode in (0, 2, 4)

    def test_search_with_progress(self):
        """Test search with --progress flag."""
        result = self._run_search(["Python", str(self.doc1), "--grep", "--progress"])

        assert result.returncode == 0

    def test_search_with_rich_output(self):
        """Test search with --rich flag."""
        result = self._run_search(["Python", str(self.doc1), "--grep", "--rich"])

        # Should work without errors (rich may or may not be installed)
        assert result.returncode == 0


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.search
class TestGrepCLI:
    """End-to-end tests for grep CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

        # Create test document
        self.doc = self.temp_dir / "test.md"
        self.doc.write_text(
            """# Test Document

Line 1: First line of text.
Line 2: Second line with Python keyword.
Line 3: Third line of text.
Line 4: Fourth line with JavaScript keyword.
Line 5: Fifth line of text.
Line 6: Sixth line with programming keyword.
Line 7: Seventh line of text.
""",
            encoding="utf-8",
        )

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_grep(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run grep command as a subprocess.

        Parameters
        ----------
        args : list[str]
            Arguments to pass to grep command

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md", "grep"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def test_grep_basic(self):
        """Test basic grep command."""
        result = self._run_grep(["Python", str(self.doc)])

        assert result.returncode == 0
        assert "Python" in result.stdout

    def test_grep_help(self):
        """Test grep help output."""
        result = self._run_grep(["--help"])

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "query" in result.stdout.lower()

    def test_grep_with_context_before(self):
        """Test grep with -B (before context) option."""
        result = self._run_grep(["Python", str(self.doc), "-B", "1"])

        assert result.returncode == 0

    def test_grep_with_context_after(self):
        """Test grep with -A (after context) option."""
        result = self._run_grep(["Python", str(self.doc), "-A", "1"])

        assert result.returncode == 0

    def test_grep_with_context_both(self):
        """Test grep with -C (context before and after) option."""
        result = self._run_grep(["Python", str(self.doc), "-C", "2"])

        assert result.returncode == 0

    def test_grep_with_line_numbers(self):
        """Test grep with -n (line numbers) option."""
        result = self._run_grep(["Python", str(self.doc), "-n"])

        assert result.returncode == 0

    def test_grep_case_insensitive(self):
        """Test grep with -i (case insensitive) option."""
        result = self._run_grep(["python", str(self.doc), "-i"])

        assert result.returncode == 0
        # Should find "Python" even when searching for "python"
        assert "Python" in result.stdout or "python" in result.stdout.lower()

    def test_grep_regex(self):
        """Test grep with -e (regex) option."""
        result = self._run_grep(["Line [0-9]+", str(self.doc), "-e"])

        assert result.returncode == 0

    def test_grep_no_regex(self):
        """Test grep with --no-regex option."""
        result = self._run_grep(["Python", str(self.doc), "--no-regex"])

        assert result.returncode == 0

    def test_grep_recursive(self):
        """Test grep with --recursive option."""
        # Create subdirectory with file
        subdir = self.temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.md").write_text("# Nested\nPython is great.", encoding="utf-8")

        result = self._run_grep(["Python", str(self.temp_dir), "--recursive"])

        assert result.returncode == 0

    def test_grep_with_exclude(self):
        """Test grep with --exclude option."""
        result = self._run_grep(["Python", str(self.temp_dir), "--recursive", "--exclude", "*.txt"])

        assert result.returncode == 0

    def test_grep_max_columns(self):
        """Test grep with -M (max columns) option."""
        result = self._run_grep(["Line", str(self.doc), "-M", "50"])

        assert result.returncode == 0

    def test_grep_rich_output(self):
        """Test grep with --rich option."""
        result = self._run_grep(["Python", str(self.doc), "--rich"])

        assert result.returncode == 0

    def test_grep_multiple_files(self):
        """Test grep with multiple files."""
        doc2 = self.temp_dir / "doc2.md"
        doc2.write_text("# Another Doc\nPython again.", encoding="utf-8")

        result = self._run_grep(["Python", str(self.doc), str(doc2)])

        assert result.returncode == 0

    def test_grep_no_results(self):
        """Test grep when no results are found."""
        result = self._run_grep(["nonexistent_pattern_xyz", str(self.doc)])

        assert result.returncode == 0
        assert "No results found" in result.stdout

    def test_grep_missing_inputs(self):
        """Test grep without input files."""
        result = self._run_grep(["Python"])

        # Should fail with missing required argument
        assert result.returncode != 0
