"""Tests for RuleRegistry."""

from __future__ import annotations

import pytest

from all2md.linter.registry import RuleRegistry
from all2md.linter.rule import LintRule
from all2md.linter.violations import Severity

pytestmark = pytest.mark.unit


class _RuleA(LintRule):
    code = "TEST001"
    name = "test-a"
    category = "test"
    description = "A"
    default_severity = Severity.INFO

    def check(self, ctx):
        return []


class _RuleB(LintRule):
    code = "TEST002"
    name = "test-b"
    category = "other"
    description = "B"
    default_severity = Severity.WARNING

    def check(self, ctx):
        return []


class TestRegistry:
    def test_singleton_identity(self):
        assert RuleRegistry() is RuleRegistry()

    def test_register_and_lookup(self):
        reg = RuleRegistry()
        reg.register(_RuleA)
        assert reg.has_rule("TEST001")
        assert reg.get_rule("TEST001") is _RuleA

    def test_unknown_rule_raises(self):
        reg = RuleRegistry()
        with pytest.raises(KeyError):
            reg.get_rule("NO_SUCH_RULE_XYZ")

    def test_list_rules_filters_by_category(self):
        reg = RuleRegistry()
        reg.register(_RuleA)
        reg.register(_RuleB)
        codes = reg.list_rules(category="test")
        assert "TEST001" in codes
        assert "TEST002" not in codes

    def test_unregister(self):
        reg = RuleRegistry()
        reg.register(_RuleA)
        assert reg.unregister("TEST001") is True
        assert reg.unregister("TEST001") is False

    def test_builtin_rules_auto_register(self):
        reg = RuleRegistry()
        codes = set(reg.list_rules())
        # All 20 MVP rules should be registered on first access.
        for code in ("STR001", "HDG001", "LNK001", "TYP001"):
            assert code in codes
