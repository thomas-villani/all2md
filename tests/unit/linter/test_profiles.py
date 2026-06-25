"""Unit tests for the lint profile bundles and their merge policy."""

from __future__ import annotations

import pytest

from all2md.linter import LintConfig, Severity, rule_registry
from all2md.linter.profiles import (
    LINT_PROFILES,
    available_profiles,
    describe_profiles,
    get_profile_config,
    merge_profile_dicts,
    profile_description,
)

pytestmark = pytest.mark.unit


class TestProfileCatalog:
    def test_available_profiles_sorted(self):
        names = available_profiles()
        assert names == sorted(names)
        assert set(names) == set(LINT_PROFILES)
        # The three profiles we ship.
        assert {"accessibility", "technical-docs", "prose"} <= set(names)

    def test_every_profile_references_real_rule_codes(self):
        """A profile must never name a rule code that isn't registered."""
        known = set(rule_registry.list_rules())
        for name in available_profiles():
            cfg = get_profile_config(name)
            referenced: set[str] = set()
            referenced.update(cfg.get("enable", []))
            referenced.update(cfg.get("disable", []))
            referenced.update(cfg.get("severity", {}).keys())
            referenced.update(cfg.get("rules", {}).keys())
            unknown = referenced - known
            assert not unknown, f"profile {name!r} references unknown rules: {sorted(unknown)}"

    def test_every_profile_loads_as_lintconfig(self):
        for name in available_profiles():
            config = LintConfig.from_dict(get_profile_config(name))
            assert isinstance(config, LintConfig)

    def test_profile_description_present(self):
        for name in available_profiles():
            assert profile_description(name).strip()

    def test_describe_profiles_lists_all(self):
        text = describe_profiles()
        for name in available_profiles():
            assert name in text

    def test_unknown_profile_raises(self):
        with pytest.raises(KeyError):
            get_profile_config("does-not-exist")

    def test_get_profile_config_returns_isolated_copy(self):
        first = get_profile_config("prose")
        first.setdefault("enable", []).append("ZZZ999")
        first.setdefault("severity", {})["ZZZ999"] = "error"
        second = get_profile_config("prose")
        assert "ZZZ999" not in second.get("enable", [])
        assert "ZZZ999" not in second.get("severity", {})


class TestProfileSemantics:
    def test_prose_elevates_typography_to_warning(self):
        config = LintConfig.from_dict(get_profile_config("prose"))
        assert config.severity_overrides["TYP003"] == Severity.WARNING
        # Whitelist mode: a rule outside the bundle is disabled.
        assert config.is_rule_enabled("TYP003")
        assert not config.is_rule_enabled("LST004")

    def test_accessibility_marks_alt_text_error(self):
        config = LintConfig.from_dict(get_profile_config("accessibility"))
        assert config.severity_overrides["IMG001"] == Severity.ERROR
        assert config.is_rule_enabled("IMG001")
        # Typography niceties are intentionally excluded from the a11y bundle.
        assert not config.is_rule_enabled("TYP003")

    def test_technical_docs_disables_prose_typography(self):
        config = LintConfig.from_dict(get_profile_config("technical-docs"))
        # Disable list (no whitelist), so unrelated rules stay enabled.
        assert not config.is_rule_enabled("TYP003")
        assert config.is_rule_enabled("STR001")


class TestMergePolicy:
    def test_disable_unions(self):
        merged = merge_profile_dicts({"disable": ["TYP003"]}, {"disable": ["TYP004"]})
        assert merged["disable"] == ["TYP003", "TYP004"]

    def test_disable_union_dedupes_and_preserves_order(self):
        merged = merge_profile_dicts({"disable": ["A", "B"]}, {"disable": ["B", "C"]})
        assert merged["disable"] == ["A", "B", "C"]

    def test_enable_replaces(self):
        merged = merge_profile_dicts({"enable": ["STR001", "STR002"]}, {"enable": ["TYP003"]})
        assert merged["enable"] == ["TYP003"]

    def test_severity_merges_override_wins(self):
        merged = merge_profile_dicts(
            {"severity": {"TYP003": "info", "STR001": "error"}},
            {"severity": {"TYP003": "warning"}},
        )
        assert merged["severity"] == {"TYP003": "warning", "STR001": "error"}

    def test_rules_options_merge_one_level_deep(self):
        merged = merge_profile_dicts(
            {"rules": {"HDG002": {"max_length": 80}}},
            {"rules": {"HDG002": {"foo": 1}, "STR006": {"min_words": 5}}},
        )
        assert merged["rules"]["HDG002"] == {"max_length": 80, "foo": 1}
        assert merged["rules"]["STR006"] == {"min_words": 5}

    def test_severity_threshold_replaces(self):
        merged = merge_profile_dicts({"severity_threshold": "info"}, {"severity_threshold": "warning"})
        assert merged["severity_threshold"] == "warning"

    def test_alias_keys_normalized(self):
        merged = merge_profile_dicts(
            {"enabled_rules": ["STR001"]},
            {"disabled_rules": ["TYP003"]},
        )
        assert merged["enable"] == ["STR001"]
        assert merged["disable"] == ["TYP003"]

    def test_inputs_not_mutated(self):
        base = {"disable": ["TYP003"]}
        override = {"disable": ["TYP004"]}
        merge_profile_dicts(base, override)
        assert base == {"disable": ["TYP003"]}
        assert override == {"disable": ["TYP004"]}

    def test_empty_override_is_identity(self):
        merged = merge_profile_dicts({"enable": ["STR001"], "disable": ["TYP003"]}, {})
        assert merged["enable"] == ["STR001"]
        assert merged["disable"] == ["TYP003"]
