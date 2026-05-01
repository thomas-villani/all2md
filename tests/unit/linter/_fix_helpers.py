"""Test-only helpers for auto-fix tests.

Not part of the public surface. Provides ergonomic ``lint_then_fix`` and
``assert_idempotent`` so per-rule fix tests stay one-liners.
"""

from __future__ import annotations

from typing import Iterable, Optional

from all2md.ast import Document
from all2md.linter import FixSafety, LintConfig, LintFixResult, LintRunner


def lint_then_fix(
    doc: Document,
    rule_codes: Optional[Iterable[str]] = None,
    *,
    max_safety: FixSafety = FixSafety.SAFE,
) -> LintFixResult:
    """Run lint+fix on ``doc``. Returns the LintFixResult; ``doc`` is mutated.

    When ``rule_codes`` is given, only those rules run — useful when a
    test wants to focus on a single rule without ambient violations from
    others polluting the assertion.
    """
    if rule_codes is not None:
        config = LintConfig(enabled_rules=frozenset(rule_codes))
    else:
        config = LintConfig()
    runner = LintRunner(config=config)
    return runner.lint_and_fix_document(doc, max_safety=max_safety)


def assert_idempotent(doc: Document, rule_codes: Iterable[str]) -> None:
    """Run --fix twice and assert the second pass applies zero fixes.

    Also asserts that the post-fix document has none of ``rule_codes``
    among its remaining violations — i.e. the fixes actually resolved
    the rules they target. Idempotency on its own is necessary but not
    sufficient (a no-op fix is trivially idempotent).
    """
    codes = list(rule_codes)
    first = lint_then_fix(doc, codes)
    assert first.applied, f"first pass should have applied at least one fix for {codes}"
    second = lint_then_fix(doc, codes)
    assert not second.applied, f"second pass should be a no-op; applied={[a.rule_code for a in second.applied]}"
    remaining = [v.rule_code for v in second.final.violations if v.rule_code in codes]
    assert not remaining, f"rules {codes} still firing after fix: {remaining}"
