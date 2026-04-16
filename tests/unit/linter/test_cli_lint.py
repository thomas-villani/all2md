"""End-to-end smoke tests for the `all2md lint` CLI handler."""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.cli.builder import EXIT_SUCCESS, EXIT_VALIDATION_ERROR
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
