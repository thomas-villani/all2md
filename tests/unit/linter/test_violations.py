"""Tests for Severity and Violation."""

from __future__ import annotations

import pytest

from all2md.linter.violations import Severity, Violation

pytestmark = pytest.mark.unit


class TestSeverity:
    def test_ordering(self):
        assert Severity.INFO < Severity.WARNING < Severity.ERROR

    def test_from_name_case_insensitive(self):
        assert Severity.from_name("error") is Severity.ERROR
        assert Severity.from_name("WARNING") is Severity.WARNING
        assert Severity.from_name("Info") is Severity.INFO

    def test_from_name_rejects_unknown(self):
        with pytest.raises(ValueError):
            Severity.from_name("catastrophic")

    def test_label_lowercase(self):
        assert Severity.ERROR.label == "error"


class TestViolation:
    def test_to_dict_roundtrip(self):
        v = Violation(
            rule_code="STR001",
            rule_name="missing-title",
            message="No H1",
            severity=Severity.ERROR,
            line=3,
            column=1,
            node_type="Document",
            suggestion="Add a # Title",
            context="example",
        )
        d = v.to_dict()
        assert d["rule_code"] == "STR001"
        assert d["severity"] == "error"
        assert d["line"] == 3
        assert d["context"] == "example"
        assert d["fixable"] is False

    def test_frozen(self):
        v = Violation(rule_code="X", rule_name="x", message="m", severity=Severity.INFO)
        with pytest.raises(Exception):  # FrozenInstanceError
            v.severity = Severity.ERROR  # type: ignore[misc]
