"""Document linter for the all2md AST.

The linter inspects a ``Document`` (regardless of the source format it was
parsed from) and reports structural, heading, link, and typography issues
via a rule-based engine.

Typical use::

    from all2md import to_ast
    from all2md.linter import lint_document, LintConfig

    doc = to_ast("whitepaper.pdf")
    result = lint_document(doc)
    for violation in result.violations:
        print(violation)

The CLI entry point is exposed as ``all2md lint``.
"""

from __future__ import annotations

from all2md.linter.config import LintConfig
from all2md.linter.fixes import AppliedFix, FixContext, FixSafety, LintFix, apply_fixes
from all2md.linter.profiles import (
    LINT_PROFILES,
    available_profiles,
    describe_profiles,
    get_profile_config,
    merge_profile_dicts,
    profile_description,
)
from all2md.linter.registry import RuleRegistry, rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.runner import (
    LintFixResult,
    LintResult,
    LintRunner,
    lint_and_fix_document,
    lint_and_fix_file,
    lint_document,
    lint_file,
)
from all2md.linter.violations import Severity, Violation

__all__ = [
    "LINT_PROFILES",
    "AppliedFix",
    "FixContext",
    "FixSafety",
    "LintConfig",
    "LintContext",
    "LintFix",
    "LintFixResult",
    "LintResult",
    "LintRule",
    "LintRunner",
    "RuleRegistry",
    "Severity",
    "Violation",
    "apply_fixes",
    "available_profiles",
    "describe_profiles",
    "get_profile_config",
    "lint_and_fix_document",
    "lint_and_fix_file",
    "lint_document",
    "lint_file",
    "merge_profile_dicts",
    "profile_description",
    "rule_registry",
]
