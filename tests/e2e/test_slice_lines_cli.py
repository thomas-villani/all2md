"""End-to-end tests for all2md CLI paging/windowing flags.

Covers the quality-of-life selectors added alongside --extract:
- --slice X/Y       (semantic paging)
- --head / --tail   (output-line windows)
- --lines START:END (output-line range)
- multi --extract, ::N word limits, table:/figure: selectors
"""

import subprocess
import sys
from pathlib import Path

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestSliceLinesCLI:
    """End-to-end tests for --slice, --head, --tail, --lines, and rich --extract."""

    def setup_method(self):
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"

    def teardown_method(self):
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "all2md"] + args
        return subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
        )

    def _doc(self) -> Path:
        md = """# Introduction

Intro paragraph one with several words here for counting purposes today.

## Background

Background details go here with more words to push the count up nicely.

# Methods

We used a careful method.

| Name | Value |
| ---- | ----- |
| a    | 1     |
| b    | 2     |

![A figure](fig1.png)

# Results

Findings appear here.

| R1 | R2 |
| -- | -- |
| x  | y  |

# Conclusion

Final thoughts here.
"""
        path = self.temp_dir / "doc.md"
        path.write_text(md, encoding="utf-8")
        return path

    # --- --slice -----------------------------------------------------------

    def test_slice_returns_one_of_y(self):
        result = self._run_cli([str(self._doc()), "--slice", "1/3"])
        assert result.returncode == 0, result.stderr
        assert "# Introduction" in result.stdout
        # Footer hint points at the next slice and honors Y.
        assert "slice 1/3" in result.stdout
        assert "next: --slice 2/3" in result.stdout

    def test_slice_last_has_no_next_hint(self):
        result = self._run_cli([str(self._doc()), "--slice", "3/3"])
        assert result.returncode == 0, result.stderr
        assert "last slice" in result.stdout
        assert "next:" not in result.stdout

    def test_slice_out_of_range_errors(self):
        result = self._run_cli([str(self._doc()), "--slice", "99/99"])
        assert result.returncode != 0
        assert "only divides into" in result.stderr.lower() or "slice" in result.stderr.lower()

    def test_slice_invalid_spec_errors(self):
        result = self._run_cli([str(self._doc()), "--slice", "2"])
        assert result.returncode != 0

    # --- --head / --tail ---------------------------------------------------

    def test_head_default_and_n(self):
        result = self._run_cli([str(self._doc()), "--head", "3"])
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[0] == "# Introduction"
        # Only the first lines; later sections excluded.
        assert "# Conclusion" not in result.stdout

    def test_tail(self):
        result = self._run_cli([str(self._doc()), "--tail", "2"])
        assert result.returncode == 0, result.stderr
        assert "Final thoughts here." in result.stdout
        assert "# Introduction" not in result.stdout

    def test_lines_range(self):
        result = self._run_cli([str(self._doc()), "--lines", "5:8"])
        assert result.returncode == 0, result.stderr
        assert "## Background" in result.stdout
        assert "# Introduction" not in result.stdout

    def test_lines_with_line_numbers(self):
        result = self._run_cli([str(self._doc()), "--lines", "1:1", "--line-numbers"])
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().startswith("1: # Introduction")

    # --- rich --extract ----------------------------------------------------

    def test_extract_word_limit(self):
        result = self._run_cli([str(self._doc()), "--extract", "Introduction::6"])
        assert result.returncode == 0, result.stderr
        assert "# Introduction" in result.stdout
        # Background heading is past the word budget.
        assert "## Background" not in result.stdout

    def test_extract_table_selector(self):
        result = self._run_cli([str(self._doc()), "--extract", "table:2"])
        assert result.returncode == 0, result.stderr
        assert "R1" in result.stdout and "R2" in result.stdout
        assert "Name" not in result.stdout

    def test_extract_figure_selector(self):
        result = self._run_cli([str(self._doc()), "--extract", "figure:1"])
        assert result.returncode == 0, result.stderr
        assert "fig1.png" in result.stdout

    def test_multiple_extract_spec_order(self):
        result = self._run_cli([str(self._doc()), "--extract", "table:2", "--extract", "figure:1"])
        assert result.returncode == 0, result.stderr
        # Spec order: table first, figure second, separated by ---.
        table_pos = result.stdout.find("R1")
        fig_pos = result.stdout.find("fig1.png")
        sep_pos = result.stdout.find("---")
        assert table_pos != -1 and fig_pos != -1
        assert table_pos < sep_pos < fig_pos

    # --- mutual exclusion --------------------------------------------------

    def test_extract_and_head_conflict(self):
        result = self._run_cli([str(self._doc()), "--extract", "Methods", "--head", "3"])
        assert result.returncode != 0
        assert "cannot be combined" in result.stderr.lower()

    def test_slice_and_lines_conflict(self):
        result = self._run_cli([str(self._doc()), "--slice", "1/2", "--lines", "1:3"])
        assert result.returncode != 0
        assert "cannot be used together" in result.stderr.lower()
