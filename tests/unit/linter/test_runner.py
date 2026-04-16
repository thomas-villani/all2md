"""Tests for LintRunner."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.linter.config import LintConfig
from all2md.linter.registry import RuleRegistry
from all2md.linter.rule import LintRule
from all2md.linter.runner import LintRunner
from all2md.linter.violations import Severity, Violation

pytestmark = pytest.mark.unit


class _FakeRegistry:
    """Minimal registry that returns a fixed list of rule classes."""

    def __init__(self, rule_classes):
        self._classes = rule_classes

    def iter_rules(self):
        return iter(self._classes)


class _TwoViolations(LintRule):
    code = "FAKE001"
    name = "fake-two"
    category = "test"
    description = "emits two violations"
    default_severity = Severity.WARNING

    def check(self, ctx):
        return [
            Violation(
                rule_code=self.code,
                rule_name=self.name,
                message="first",
                severity=self.default_severity,
                line=5,
                column=2,
            ),
            Violation(
                rule_code=self.code,
                rule_name=self.name,
                message="second",
                severity=self.default_severity,
                line=2,
                column=1,
            ),
        ]


class _InfoRule(LintRule):
    code = "FAKE002"
    name = "fake-info"
    category = "test"
    description = "emits an info"
    default_severity = Severity.INFO

    def check(self, ctx):
        return [
            Violation(
                rule_code=self.code,
                rule_name=self.name,
                message="info-level",
                severity=self.default_severity,
            )
        ]


class _Crashing(LintRule):
    code = "FAKE003"
    name = "fake-crash"
    category = "test"
    description = "always crashes"
    default_severity = Severity.ERROR

    def check(self, ctx):
        raise RuntimeError("boom")


def _doc() -> Document:
    return Document(children=[Paragraph(content=[Text(content="hello")])])


class TestLintRunner:
    def test_sort_by_line_then_column(self):
        runner = LintRunner(config=LintConfig(), registry=_FakeRegistry([_TwoViolations]))
        result = runner.lint_document(_doc(), file_path="f.md")
        assert [v.line for v in result.violations] == [2, 5]
        assert result.rules_checked == 1

    def test_severity_threshold_drops_below(self):
        cfg = LintConfig(severity_threshold=Severity.WARNING)
        runner = LintRunner(config=cfg, registry=_FakeRegistry([_InfoRule, _TwoViolations]))
        result = runner.lint_document(_doc())
        codes = {v.rule_code for v in result.violations}
        assert "FAKE002" not in codes
        assert "FAKE001" in codes

    def test_crashing_rule_produces_internal_error(self):
        runner = LintRunner(config=LintConfig(), registry=_FakeRegistry([_Crashing]))
        result = runner.lint_document(_doc())
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.rule_code == "INTERNAL-ERROR"
        assert v.severity == Severity.ERROR
        assert "FAKE003" in v.message

    def test_severity_override_applied(self):
        cfg = LintConfig(severity_overrides={"FAKE001": Severity.ERROR})
        runner = LintRunner(config=cfg, registry=_FakeRegistry([_TwoViolations]))
        result = runner.lint_document(_doc())
        assert all(v.severity == Severity.ERROR for v in result.violations)
        assert result.error_count == 2

    def test_disabled_rule_is_skipped(self):
        cfg = LintConfig(disabled_rules=frozenset({"FAKE001"}))
        runner = LintRunner(config=cfg, registry=_FakeRegistry([_TwoViolations]))
        result = runner.lint_document(_doc())
        assert result.violations == []
        assert result.rules_checked == 0

    def test_real_registry_against_clean_heading(self):
        """A minimal but valid document should produce no ERROR-level violations."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="hello world")]),
            ]
        )
        runner = LintRunner(config=LintConfig(), registry=RuleRegistry())
        result = runner.lint_document(doc, file_path="inline.md")
        assert result.error_count == 0
