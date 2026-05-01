"""End-to-end smoke tests for the `all2md lint` CLI handler."""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.cli.commands.lint import handle_lint_command

pytestmark = pytest.mark.unit

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "linter"


class TestLintCli:
    def test_clean_fixture_exits_success(self, capsys):
        exit_code = handle_lint_command([str(FIXTURE_DIR / "clean_document.md")])
        captured = capsys.readouterr()
        assert exit_code == EXIT_SUCCESS
        assert "Found 0 violations" in captured.out

    def test_issues_fixture_exits_validation_error(self, capsys):
        exit_code = handle_lint_command([str(FIXTURE_DIR / "all_issues.md")])
        captured = capsys.readouterr()
        assert exit_code == EXIT_VALIDATION_ERROR
        assert "STR003" in captured.out  # heading hierarchy error present
        assert "Found" in captured.out

    def test_severity_filter_changes_exit_code(self, capsys):
        exit_code = handle_lint_command(["--severity", "error", str(FIXTURE_DIR / "all_issues.md")])
        captured = capsys.readouterr()
        assert exit_code == EXIT_VALIDATION_ERROR
        # INFO-level violations should be filtered out of the display.
        assert "info:" not in captured.out
        # And at least one ERROR remains.
        assert "error:" in captured.out

    def test_disable_suppresses_rule(self, capsys):
        exit_code = handle_lint_command(
            [
                "--disable",
                "STR003",
                "--disable",
                "STR004",
                "--severity",
                "error",
                str(FIXTURE_DIR / "all_issues.md"),
            ]
        )
        captured = capsys.readouterr()
        # With the only two errors disabled and threshold=error, nothing remains.
        assert "STR003" not in captured.out
        assert "STR004" not in captured.out
        assert exit_code == EXIT_SUCCESS

    def test_json_format_emits_parseable_output(self, capsys):
        import json

        exit_code = handle_lint_command(["--format", "json", str(FIXTURE_DIR / "all_issues.md")])
        captured = capsys.readouterr()
        assert exit_code == EXIT_VALIDATION_ERROR
        payload = json.loads(captured.out)
        assert payload["summary"]["errors"] >= 1
        assert payload["results"][0]["violations"]


class TestLintCliFix:
    """Coverage for the --fix and --dry-run flags."""

    def _write_dirty(self, tmp_path: Path) -> Path:
        target = tmp_path / "dirty.md"
        target.write_text(
            "# Title\n\nThis sentence has a -- and an ellipsis... in it.\n",
            encoding="utf-8",
        )
        return target

    def test_fix_rewrites_file(self, tmp_path, capsys):
        path = self._write_dirty(tmp_path)
        before = path.read_text(encoding="utf-8")
        exit_code = handle_lint_command(["--fix", str(path)])
        captured = capsys.readouterr()
        after = path.read_text(encoding="utf-8")
        assert before != after
        assert "—" in after  # em-dash replaced --
        assert "…" in after  # ellipsis replaced ...
        assert "applied" in captured.out.lower()
        # Exit code: the fixture has STR006/STR007-class issues that don't fix,
        # so we don't pin to a specific code — just assert it didn't blow up.
        assert exit_code in (EXIT_SUCCESS, EXIT_VALIDATION_ERROR)

    def test_dry_run_does_not_write(self, tmp_path, capsys):
        path = self._write_dirty(tmp_path)
        before = path.read_text(encoding="utf-8")
        handle_lint_command(["--fix", "--dry-run", str(path)])
        after = path.read_text(encoding="utf-8")
        assert before == after, "--dry-run must not modify the file"

    def test_dry_run_without_fix_errors(self, tmp_path, capsys):
        path = self._write_dirty(tmp_path)
        exit_code = handle_lint_command(["--dry-run", str(path)])
        captured = capsys.readouterr()
        assert exit_code == EXIT_ERROR
        assert "--dry-run requires --fix" in captured.err

    def test_clean_file_not_rewritten(self, tmp_path, capsys):
        path = tmp_path / "clean.md"
        clean_source = (
            "# Title\n\nA clean paragraph with more than ten words to satisfy " "the short-section rule comfortably.\n"
        )
        path.write_text(clean_source, encoding="utf-8")
        before_mtime = path.stat().st_mtime_ns
        exit_code = handle_lint_command(["--fix", str(path)])
        after = path.read_text(encoding="utf-8")
        assert after == clean_source
        # mtime should be unchanged because the runner skips writing clean files.
        assert path.stat().st_mtime_ns == before_mtime
        assert exit_code == EXIT_SUCCESS

    def test_fix_idempotent_across_two_runs(self, tmp_path, capsys):
        path = self._write_dirty(tmp_path)
        handle_lint_command(["--fix", str(path)])
        first = path.read_text(encoding="utf-8")
        capsys.readouterr()  # discard first run output
        handle_lint_command(["--fix", str(path)])
        second = path.read_text(encoding="utf-8")
        assert first == second, "running --fix twice should be a no-op the second time"
