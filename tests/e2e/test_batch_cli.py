"""End-to-end tests for all2md CLI batch processing features.

This module tests batch processing features including --merge-from-list and
--batch-from-list as subprocesses, simulating real-world usage patterns.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestBatchCLI:
    """End-to-end tests for CLI batch processing functionality."""

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

    def _create_test_files(self) -> tuple[Path, Path, Path]:
        """Create test markdown files.

        Returns
        -------
        tuple[Path, Path, Path]
            Paths to three test files

        """
        file1 = self.temp_dir / "doc1.md"
        file1.write_text("# Document 1\n\nThis is the first document.\n", encoding="utf-8")

        file2 = self.temp_dir / "doc2.md"
        file2.write_text("# Document 2\n\nThis is the second document.\n", encoding="utf-8")

        file3 = self.temp_dir / "doc3.md"
        file3.write_text("# Document 3\n\nThis is the third document.\n", encoding="utf-8")

        return file1, file2, file3

    def test_merge_from_list_tsv(self):
        """Test merging documents from TSV list."""
        file1, file2, file3 = self._create_test_files()

        # Create TSV file with document list
        tsv_content = f"{file1}\tDocument One\n{file2}\tDocument Two\n{file3}\tDocument Three\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged.md"

        result = self._run_cli(["--merge-from-list", str(tsv_file), "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should contain content from all three documents
        assert "Document 1" in content
        assert "Document 2" in content
        assert "Document 3" in content
        assert "first document" in content
        assert "second document" in content
        assert "third document" in content

    def test_merge_from_list_custom_separator(self):
        """Test merging with custom list separator."""
        file1, file2, file3 = self._create_test_files()

        # Create file with custom separator (comma)
        csv_content = f"{file1},Document One\n{file2},Document Two\n{file3},Document Three\n"
        csv_file = self.temp_dir / "docs.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged.md"

        result = self._run_cli(["--merge-from-list", str(csv_file), "--list-separator", ",", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "Document 1" in content
        assert "Document 2" in content
        assert "Document 3" in content

    def test_merge_from_list_with_toc(self):
        """Test merging with table of contents generation."""
        file1, file2, file3 = self._create_test_files()

        tsv_content = f"{file1}\tChapter 1\n{file2}\tChapter 2\n{file3}\tChapter 3\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_toc.md"

        result = self._run_cli(["--merge-from-list", str(tsv_file), "--generate-toc", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should contain TOC
        toc_indicators = ["Table of Contents", "Contents", "Chapter 1", "Chapter 2", "Chapter 3"]
        has_toc = any(indicator in content for indicator in toc_indicators)
        assert has_toc, "Should generate table of contents"

    def test_merge_from_list_toc_title(self):
        """Test merging with custom TOC title."""
        file1, file2, _ = self._create_test_files()

        tsv_content = f"{file1}\tPart 1\n{file2}\tPart 2\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_custom_toc.md"

        result = self._run_cli(
            [
                "--merge-from-list",
                str(tsv_file),
                "--generate-toc",
                "--toc-title",
                "Book Contents",
                "--out",
                str(output_file),
            ]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        assert "Book Contents" in content

    def test_merge_from_list_toc_depth(self):
        """Test merging with TOC depth control."""
        file1, file2, _ = self._create_test_files()

        tsv_content = f"{file1}\tSection 1\n{file2}\tSection 2\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_toc_depth.md"

        result = self._run_cli(
            ["--merge-from-list", str(tsv_file), "--generate-toc", "--toc-depth", "2", "--out", str(output_file)]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

    def test_merge_from_list_toc_position(self):
        """Test merging with TOC position control."""
        file1, file2, _ = self._create_test_files()

        tsv_content = f"{file1}\tDoc 1\n{file2}\tDoc 2\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_toc_pos.md"

        result = self._run_cli(
            [
                "--merge-from-list",
                str(tsv_file),
                "--generate-toc",
                "--toc-position",
                "bottom",  # Use 'bottom' instead of 'end'
                "--out",
                str(output_file),
            ]
        )

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # TOC should be at the bottom
        lines = content.strip().split("\n")
        # Last sections should contain TOC indicators
        end_content = "\n".join(lines[-20:])
        has_toc_at_bottom = "Contents" in end_content or "Table" in end_content
        assert has_toc_at_bottom
        # Note: This test might need adjustment based on actual implementation

    def test_merge_from_list_no_section_titles(self):
        """Test merging without section titles."""
        file1, file2, _ = self._create_test_files()

        tsv_content = f"{file1}\tIgnore This\n{file2}\tIgnore That\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_no_titles.md"

        result = self._run_cli(["--merge-from-list", str(tsv_file), "--no-section-titles", "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"
        assert output_file.exists(), "Output file was not created"

        content = output_file.read_text(encoding="utf-8")
        # Should not add section titles from TSV
        # The original document titles should still be there
        assert "Document 1" in content or "Document 2" in content

    def test_batch_from_list(self):
        """Test batch processing from list."""
        file1, file2, file3 = self._create_test_files()

        # Create list file with just paths
        list_content = f"{file1}\n{file2}\n{file3}\n"
        list_file = self.temp_dir / "batch_list.txt"
        list_file.write_text(list_content, encoding="utf-8")

        output_dir = self.temp_dir / "batch_output"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(["--batch-from-list", str(list_file), "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should create output files for each input
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 3, f"Expected at least 3 output files, got {len(output_files)}"

    def test_merge_from_list_nonexistent_file(self):
        """Test error handling when list file doesn't exist."""
        nonexistent_list = self.temp_dir / "nonexistent.tsv"
        output_file = self.temp_dir / "output.md"

        result = self._run_cli(["--merge-from-list", str(nonexistent_list), "--out", str(output_file)])

        # Should fail with file error
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_merge_from_list_invalid_tsv(self):
        """Test error handling for invalid TSV content."""
        file1, _, _ = self._create_test_files()

        # Create TSV with invalid path
        tsv_content = f"{file1}\tValid File\n/nonexistent/file.md\tInvalid File\n"
        tsv_file = self.temp_dir / "invalid.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "output.md"

        result = self._run_cli(["--merge-from-list", str(tsv_file), "--out", str(output_file)])

        # May fail or skip invalid files depending on implementation
        # Error code 10 indicates invalid merge list
        # At minimum, should not crash
        assert result.returncode in [0, 3, 4, 10], "Should handle invalid files gracefully"

    def test_merge_from_list_empty_file(self):
        """Test error handling for empty list file."""
        empty_list = self.temp_dir / "empty.tsv"
        empty_list.write_text("", encoding="utf-8")

        output_file = self.temp_dir / "output.md"

        result = self._run_cli(["--merge-from-list", str(empty_list), "--out", str(output_file)])

        # Should handle empty list gracefully
        # Error code 10 indicates empty/invalid merge list
        assert result.returncode in [0, 3, 10], "Should handle empty list"

    def test_merge_from_list_to_stdout(self):
        """Test merging to stdout."""
        file1, file2, _ = self._create_test_files()

        tsv_content = f"{file1}\tFirst\n{file2}\tSecond\n"
        tsv_file = self.temp_dir / "docs.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        result = self._run_cli(["--merge-from-list", str(tsv_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should output merged content to stdout
        assert "Document 1" in result.stdout
        assert "Document 2" in result.stdout

    def test_merge_from_list_preserves_formatting(self):
        """Test that merging preserves markdown formatting."""
        # Create files with formatted content
        file1 = self.temp_dir / "formatted1.md"
        file1.write_text("# Title\n\n**Bold** text and *italic* text.\n", encoding="utf-8")

        file2 = self.temp_dir / "formatted2.md"
        file2.write_text("# Another\n\n- List item\n- Another item\n", encoding="utf-8")

        tsv_content = f"{file1}\tDoc 1\n{file2}\tDoc 2\n"
        tsv_file = self.temp_dir / "formatted.tsv"
        tsv_file.write_text(tsv_content, encoding="utf-8")

        output_file = self.temp_dir / "merged_formatted.md"

        result = self._run_cli(["--merge-from-list", str(tsv_file), "--out", str(output_file)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        content = output_file.read_text(encoding="utf-8")
        # Formatting should be preserved
        assert "**Bold**" in content
        assert "*italic*" in content
        # Bullets can be * or -
        assert "- List item" in content or "* List item" in content

    def test_batch_from_list_with_different_formats(self):
        """Test batch processing with different input formats."""
        # Create markdown file
        md_file = self.temp_dir / "test.md"
        md_file.write_text("# Markdown\n\nContent here.\n", encoding="utf-8")

        # Create HTML file
        html_file = self.temp_dir / "test.html"
        html_file.write_text("<h1>HTML</h1><p>Content here.</p>", encoding="utf-8")

        list_content = f"{md_file}\n{html_file}\n"
        list_file = self.temp_dir / "mixed_list.txt"
        list_file.write_text(list_content, encoding="utf-8")

        output_dir = self.temp_dir / "mixed_output"
        output_dir.mkdir(exist_ok=True)

        result = self._run_cli(["--batch-from-list", str(list_file), "--output-dir", str(output_dir)])

        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Should create output files (may be one combined or multiple separate)
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, "Should process file types"
        # Verify content was processed
        all_content = ""
        for f in output_files:
            all_content += f.read_text(encoding="utf-8")
        assert "Markdown" in all_content or "HTML" in all_content

    @pytest.mark.slow
    def test_merge_help(self):
        """Test that merge options are documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--merge-from-list" in result.stdout
        # Should mention related options
        assert "--generate-toc" in result.stdout or "toc" in result.stdout.lower()

    def test_batch_help(self):
        """Test that batch options are documented in help."""
        result = self._run_cli(["--help"])

        assert result.returncode == 0
        assert "--batch-from-list" in result.stdout
