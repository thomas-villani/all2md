"""Tests for the text and JSON reporters."""

from __future__ import annotations

import json

import pytest

from all2md.linter.reporters import get_reporter
from all2md.linter.reporters.json_reporter import JsonReporter
from all2md.linter.reporters.text import TextReporter
from all2md.linter.runner import LintResult
from all2md.linter.violations import Severity, Violation

pytestmark = pytest.mark.unit


def _make_result() -> LintResult:
    return LintResult(
        file_path="example.md",
        violations=[
            Violation(
                rule_code="STR001",
                rule_name="missing-title",
                message="No title",
                severity=Severity.ERROR,
                line=1,
                column=1,
            ),
            Violation(
                rule_code="TYP001",
                rule_name="trailing-spaces",
                message="Trailing space",
                severity=Severity.INFO,
                line=3,
            ),
        ],
        rules_checked=5,
    )


class TestGetReporter:
    def test_returns_text(self):
        assert isinstance(get_reporter("text"), TextReporter)

    def test_returns_json(self):
        assert isinstance(get_reporter("json"), JsonReporter)

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_reporter("xml")


class TestTextReporter:
    def test_contains_violation_lines(self):
        rendered = TextReporter().render([_make_result()])
        assert "example.md:1:1: STR001 error: No title" in rendered
        assert "example.md:3:-: TYP001 info: Trailing space" in rendered
        assert "Found 2 violations" in rendered

    def test_empty_results_summary(self):
        rendered = TextReporter().render([LintResult(file_path="clean.md", violations=[], rules_checked=20)])
        assert "Found 0 violations" in rendered


class TestJsonReporter:
    def test_valid_json_with_summary(self):
        rendered = JsonReporter().render([_make_result()])
        payload = json.loads(rendered)
        assert payload["summary"]["violations"] == 2
        assert payload["summary"]["errors"] == 1
        assert payload["results"][0]["violations"][0]["rule_code"] == "STR001"
        assert payload["results"][0]["violations"][0]["severity"] == "error"
