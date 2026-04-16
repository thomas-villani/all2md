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
from all2md.linter.registry import RuleRegistry, rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.runner import LintResult, LintRunner, lint_document, lint_file
from all2md.linter.violations import Severity, Violation

__all__ = [
    "LintConfig",
    "LintContext",
    "LintResult",
    "LintRule",
    "LintRunner",
    "RuleRegistry",
    "Severity",
    "Violation",
    "lint_document",
    "lint_file",
    "rule_registry",
]
