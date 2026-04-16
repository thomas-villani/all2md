"""Tests for LintConfig."""

from __future__ import annotations

import pytest

from all2md.linter.config import LintConfig
from all2md.linter.rule import LintRule
from all2md.linter.violations import Severity

pytestmark = pytest.mark.unit


class _Dummy(LintRule):
    code = "DUMMY"
    name = "dummy"
    category = "test"
    description = "dummy rule"
    default_severity = Severity.WARNING

    def check(self, ctx):  # pragma: no cover - never called
        return []


class TestLintConfigFromDict:
    def test_empty_dict_returns_defaults(self):
        cfg = LintConfig.from_dict({})
        assert cfg.enabled_rules is None
        assert cfg.disabled_rules == frozenset()
        assert cfg.severity_threshold == Severity.INFO

    def test_none_returns_defaults(self):
        cfg = LintConfig.from_dict(None)
        assert cfg.enabled_rules is None

    def test_disable_list_is_parsed(self):
        cfg = LintConfig.from_dict({"disable": ["STR001", "TYP003"]})
        assert cfg.disabled_rules == frozenset({"STR001", "TYP003"})

    def test_enable_whitelist_is_parsed(self):
        cfg = LintConfig.from_dict({"enable": ["STR001"]})
        assert cfg.enabled_rules == frozenset({"STR001"})

    def test_severity_overrides_parse_strings(self):
        cfg = LintConfig.from_dict({"severity": {"STR005": "error", "LNK003": "warning"}})
        assert cfg.severity_overrides["STR005"] == Severity.ERROR
        assert cfg.severity_overrides["LNK003"] == Severity.WARNING

    def test_rule_options_parse_nested_tables(self):
        cfg = LintConfig.from_dict({"rules": {"HDG002": {"max_length": 100}}})
        assert cfg.rule_options["HDG002"] == {"max_length": 100}

    def test_rule_options_reject_non_table(self):
        with pytest.raises(ValueError):
            LintConfig.from_dict({"rules": {"HDG002": 100}})

    def test_severity_threshold_string(self):
        cfg = LintConfig.from_dict({"severity_threshold": "warning"})
        assert cfg.severity_threshold == Severity.WARNING


class TestLintConfigMethods:
    def test_is_rule_enabled_defaults_to_all(self):
        cfg = LintConfig()
        assert cfg.is_rule_enabled("STR001")

    def test_whitelist_excludes_others(self):
        cfg = LintConfig(enabled_rules=frozenset({"STR001"}))
        assert cfg.is_rule_enabled("STR001")
        assert not cfg.is_rule_enabled("STR002")

    def test_blacklist_wins_over_whitelist(self):
        cfg = LintConfig(
            enabled_rules=frozenset({"STR001"}),
            disabled_rules=frozenset({"STR001"}),
        )
        assert not cfg.is_rule_enabled("STR001")

    def test_get_severity_uses_override(self):
        cfg = LintConfig(severity_overrides={"DUMMY": Severity.ERROR})
        assert cfg.get_severity(_Dummy) == Severity.ERROR

    def test_get_severity_falls_back_to_default(self):
        cfg = LintConfig()
        assert cfg.get_severity(_Dummy) == Severity.WARNING

    def test_get_rule_options_returns_empty_when_missing(self):
        cfg = LintConfig()
        assert cfg.get_rule_options("DUMMY") == {}

    def test_frozen_create_updated(self):
        cfg = LintConfig()
        updated = cfg.create_updated(disabled_rules=frozenset({"STR001"}))
        assert cfg.disabled_rules == frozenset()
        assert updated.disabled_rules == frozenset({"STR001"})
