"""Linter configuration.

:class:`LintConfig` is the single frozen dataclass that controls which rules
run, at what severity, and with what rule-specific options. It is normally
populated from the ``[tool.all2md.lint]`` section of ``pyproject.toml`` (or
the equivalent ``[lint]`` section of ``.all2md.toml``), but can also be
built programmatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from all2md.linter.rule import LintRule
from all2md.linter.violations import Severity
from all2md.options.base import CloneFrozenMixin


@dataclass(frozen=True)
class LintConfig(CloneFrozenMixin):
    """Frozen configuration for a lint run.

    Parameters
    ----------
    enabled_rules : frozenset[str] or None
        When set, only rules whose code appears in this whitelist run.
        ``None`` (the default) means "every registered rule is enabled".
    disabled_rules : frozenset[str]
        Rules to skip. Applied after ``enabled_rules``.
    severity_overrides : dict[str, Severity]
        Map of rule code to severity, overriding the rule's ``default_severity``.
    rule_options : dict[str, dict[str, Any]]
        Per-rule option dictionaries, keyed by rule code. Forwarded to rules
        via :class:`all2md.linter.rule.LintContext.config`.
    severity_threshold : Severity
        Minimum severity to report. Violations below this level are dropped
        by the runner before results are returned. Defaults to ``INFO``
        (everything is reported).

    """

    enabled_rules: Optional[frozenset[str]] = None
    disabled_rules: frozenset[str] = field(default_factory=frozenset)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    rule_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    severity_threshold: Severity = Severity.INFO

    def is_rule_enabled(self, code: str) -> bool:
        """Return True if the rule with ``code`` should run under this config."""
        if self.enabled_rules is not None and code not in self.enabled_rules:
            return False
        if code in self.disabled_rules:
            return False
        return True

    def get_severity(self, rule_cls: type[LintRule]) -> Severity:
        """Return the effective severity for ``rule_cls``, honouring overrides."""
        override = self.severity_overrides.get(rule_cls.code)
        if override is not None:
            return override
        return rule_cls.default_severity

    def get_rule_options(self, code: str) -> dict[str, Any]:
        """Return the option dict for ``code`` (empty dict if none configured)."""
        return self.rule_options.get(code, {})

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LintConfig":
        """Build a ``LintConfig`` from a plain dict (as produced by the TOML loader).

        Recognised keys:

        - ``enable`` / ``enabled_rules``  : list of rule codes (whitelist)
        - ``disable`` / ``disabled_rules`` : list of rule codes (blacklist)
        - ``severity``                    : dict of rule code -> severity name
        - ``rules``                       : dict of rule code -> per-rule options dict
        - ``severity_threshold``          : severity name (info/warning/error)

        Unknown keys are silently ignored so config files can evolve without
        breaking older installs.
        """
        if not data:
            return cls()

        enabled_raw = data.get("enable", data.get("enabled_rules"))
        if enabled_raw is None:
            enabled: Optional[frozenset[str]] = None
        else:
            enabled = frozenset(str(code) for code in enabled_raw)

        disabled_raw = data.get("disable", data.get("disabled_rules", []))
        disabled = frozenset(str(code) for code in disabled_raw)

        severity_raw = data.get("severity", {}) or {}
        severity_overrides: dict[str, Severity] = {}
        for code, level in severity_raw.items():
            if isinstance(level, Severity):
                severity_overrides[str(code)] = level
            else:
                severity_overrides[str(code)] = Severity.from_name(str(level))

        rule_options_raw = data.get("rules", {}) or {}
        rule_options: dict[str, dict[str, Any]] = {}
        for code, options in rule_options_raw.items():
            if not isinstance(options, dict):
                raise ValueError(f"rule options for {code!r} must be a table, got {type(options).__name__}")
            rule_options[str(code)] = dict(options)

        threshold_raw = data.get("severity_threshold")
        if threshold_raw is None:
            threshold = Severity.INFO
        elif isinstance(threshold_raw, Severity):
            threshold = threshold_raw
        else:
            threshold = Severity.from_name(str(threshold_raw))

        return cls(
            enabled_rules=enabled,
            disabled_rules=disabled,
            severity_overrides=severity_overrides,
            rule_options=rule_options,
            severity_threshold=threshold,
        )
