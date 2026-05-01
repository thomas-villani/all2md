"""Lint runner — orchestrates rules against an all2md AST ``Document``.

The runner owns three responsibilities:

1. Instantiate the rules allowed by the config and run each one against
   the document.
2. Catch any exception a rule raises so a single broken rule cannot kill
   the whole run. Such failures surface as an ``INTERNAL-ERROR`` violation.
3. Apply the severity threshold and sort the resulting violations into a
   stable, reportable order.

When ``--fix`` is requested, :meth:`LintRunner.lint_and_fix_document`
runs the lint pass, applies attached fixes via
:func:`all2md.linter.fixes.apply_fixes`, and re-lints the mutated AST so
reporters can show "fixed N, M remaining". :meth:`lint_and_fix_file`
additionally serialises the mutated AST back to disk via the markdown
renderer.

Top-level convenience wrappers ``lint_document`` and ``lint_file`` are
exposed via the ``all2md.linter`` package.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from all2md.linter.config import LintConfig
from all2md.linter.fixes import AppliedFix, FixSafety, apply_fixes
from all2md.linter.registry import RuleRegistry, rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

if TYPE_CHECKING:
    from all2md.ast import Document

logger = logging.getLogger(__name__)


@dataclass
class LintResult:
    """Result of linting a single document."""

    file_path: Optional[str]
    violations: list[Violation] = field(default_factory=list)
    rules_checked: int = 0

    @property
    def error_count(self) -> int:
        """Return the number of ERROR-severity violations."""
        return sum(1 for v in self.violations if v.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Return the number of WARNING-severity violations."""
        return sum(1 for v in self.violations if v.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        """Return the number of INFO-severity violations."""
        return sum(1 for v in self.violations if v.severity == Severity.INFO)

    @property
    def total(self) -> int:
        """Return the total number of violations in this result."""
        return len(self.violations)


@dataclass
class LintFixResult:
    """Result of running ``lint --fix`` against a single document.

    Carries both the pre-fix and post-fix lint results so reporters can
    show "applied N fixes, M remaining" without recomputing.
    """

    file_path: Optional[str]
    initial: LintResult
    final: LintResult
    applied: list[AppliedFix] = field(default_factory=list)
    skipped_conflicts: list[AppliedFix] = field(default_factory=list)
    rewritten: bool = False

    @property
    def violations(self) -> list[Violation]:
        """Post-fix violations — the ones the user still needs to address."""
        return self.final.violations

    @property
    def rules_checked(self) -> int:
        """Forward to the post-fix lint result."""
        return self.final.rules_checked

    @property
    def error_count(self) -> int:
        """Forward to the post-fix lint result."""
        return self.final.error_count

    @property
    def warning_count(self) -> int:
        """Forward to the post-fix lint result."""
        return self.final.warning_count

    @property
    def info_count(self) -> int:
        """Forward to the post-fix lint result."""
        return self.final.info_count

    @property
    def total(self) -> int:
        """Forward to the post-fix lint result."""
        return self.final.total


class LintRunner:
    """Run a ``LintConfig`` over one or more documents."""

    def __init__(self, config: Optional[LintConfig] = None, registry: Optional[RuleRegistry] = None) -> None:
        """Initialise the runner with a config and a registry.

        Either argument can be omitted; defaults are a blank ``LintConfig``
        and the global ``rule_registry``.
        """
        self.config = config or LintConfig()
        self.registry = registry or rule_registry

    def _collect_rules(self) -> list[LintRule]:
        """Instantiate every rule that's both registered and enabled."""
        instances: list[LintRule] = []
        for rule_cls in self.registry.iter_rules():
            if not self.config.is_rule_enabled(rule_cls.code):
                continue
            instances.append(rule_cls())
        return instances

    def _apply_severity_override(self, violation: Violation, rule_cls: type[LintRule]) -> Violation:
        """Replace a violation's severity with the configured override, if any."""
        effective = self.config.get_severity(rule_cls)
        if effective == violation.severity:
            return violation
        return Violation(
            rule_code=violation.rule_code,
            rule_name=violation.rule_name,
            message=violation.message,
            severity=effective,
            line=violation.line,
            column=violation.column,
            node_type=violation.node_type,
            suggestion=violation.suggestion,
            context=violation.context,
            fix=violation.fix,
        )

    def lint_document(self, doc: "Document", file_path: Optional[str] = None) -> LintResult:
        """Run all enabled rules against ``doc`` and return a ``LintResult``."""
        rules = self._collect_rules()
        all_violations: list[Violation] = []

        for rule in rules:
            ctx = LintContext(
                document=doc,
                file_path=file_path,
                config=self.config.get_rule_options(rule.code),
            )
            try:
                produced = rule.check(ctx)
            except Exception as exc:
                logger.exception("Lint rule %s raised an exception", rule.code)
                all_violations.append(
                    Violation(
                        rule_code="INTERNAL-ERROR",
                        rule_name="rule-crash",
                        message=f"Rule {rule.code} crashed: {exc!r}",
                        severity=Severity.ERROR,
                    )
                )
                continue

            rule_cls = type(rule)
            for violation in produced:
                all_violations.append(self._apply_severity_override(violation, rule_cls))

        threshold = self.config.severity_threshold
        filtered = [v for v in all_violations if v.severity >= threshold]
        filtered.sort(
            key=lambda v: (
                v.line if v.line is not None else 0,
                v.column if v.column is not None else 0,
                -int(v.severity),
                v.rule_code,
            )
        )
        return LintResult(file_path=file_path, violations=filtered, rules_checked=len(rules))

    def lint_file(self, file_path: Union[str, Path]) -> LintResult:
        """Parse ``file_path`` to an AST and lint it."""
        from all2md.api import to_ast

        path_str = str(file_path)
        doc = to_ast(file_path)
        return self.lint_document(doc, file_path=path_str)

    def lint_files(self, file_paths: list[Union[str, Path]]) -> list[LintResult]:
        """Run ``lint_file()`` against every path in the list."""
        return [self.lint_file(p) for p in file_paths]

    def lint_and_fix_document(
        self,
        doc: "Document",
        *,
        file_path: Optional[str] = None,
        max_safety: FixSafety = FixSafety.SAFE,
        max_passes: int = 5,
    ) -> LintFixResult:
        """Lint ``doc``, apply attached fixes (in place) to fixpoint, re-lint.

        When two fixes target the same node, :func:`apply_fixes` skips the
        later one — so a single pass may leave correctable violations
        untouched. The runner re-runs the lint+fix cycle until no fixes
        apply (or ``max_passes`` is reached), which converts the per-call
        "first-wins" policy into "run to fixpoint" at the user level.

        ``max_passes`` is a safety cap that surfaces non-idempotent fixes
        (the loop would otherwise oscillate forever). Five passes is
        plenty for the v2.0 SAFE fixes — the deepest natural cascade is
        TYP001 → TYP002 on the same node, which converges in two.

        The document is mutated in place. Callers that need to write the
        result back to disk should serialise via the markdown renderer
        when ``LintFixResult.rewritten`` is true.
        """
        initial = self.lint_document(doc, file_path=file_path)
        all_applied: list[AppliedFix] = []
        all_skipped: list[AppliedFix] = []
        current = initial
        for _ in range(max_passes):
            applied, skipped = apply_fixes(doc, current.violations, max_safety)
            all_applied.extend(applied)
            if not applied:
                all_skipped = skipped
                break
            current = self.lint_document(doc, file_path=file_path)
            all_skipped = skipped
        final = current
        return LintFixResult(
            file_path=file_path,
            initial=initial,
            final=final,
            applied=all_applied,
            skipped_conflicts=all_skipped,
            rewritten=bool(all_applied),
        )

    def lint_and_fix_file(
        self,
        file_path: Union[str, Path],
        *,
        max_safety: FixSafety = FixSafety.SAFE,
        write: bool = True,
    ) -> LintFixResult:
        """Parse ``file_path``, lint+fix, and (optionally) rewrite the file.

        When ``write=True`` (the default) and at least one fix was
        applied, the mutated AST is serialised back to ``file_path`` via
        :class:`all2md.renderers.markdown.MarkdownRenderer`. A clean file
        (no fixes applied) is never rewritten, sidestepping spurious
        renderer-canonicalisation drift.
        """
        from all2md.api import to_ast
        from all2md.renderers.markdown import MarkdownRenderer

        path_str = str(file_path)
        doc = to_ast(file_path)
        result = self.lint_and_fix_document(doc, file_path=path_str, max_safety=max_safety)
        if write and result.rewritten:
            renderer = MarkdownRenderer()
            rendered = renderer.render_to_string(doc)
            Path(path_str).write_text(rendered, encoding="utf-8")
        return result


def lint_document(
    doc: "Document",
    config: Optional[LintConfig] = None,
    file_path: Optional[str] = None,
) -> LintResult:
    """Lint an already-parsed ``Document``."""
    runner = LintRunner(config=config)
    return runner.lint_document(doc, file_path=file_path)


def lint_file(file_path: Union[str, Path], config: Optional[LintConfig] = None) -> LintResult:
    """Parse ``file_path`` into an AST and lint it with ``config``."""
    runner = LintRunner(config=config)
    return runner.lint_file(file_path)


def lint_and_fix_document(
    doc: "Document",
    config: Optional[LintConfig] = None,
    *,
    file_path: Optional[str] = None,
    max_safety: FixSafety = FixSafety.SAFE,
) -> LintFixResult:
    """Lint and fix ``doc`` in place; re-lint and return the combined result."""
    runner = LintRunner(config=config)
    return runner.lint_and_fix_document(doc, file_path=file_path, max_safety=max_safety)


def lint_and_fix_file(
    file_path: Union[str, Path],
    config: Optional[LintConfig] = None,
    *,
    max_safety: FixSafety = FixSafety.SAFE,
    write: bool = True,
) -> LintFixResult:
    """Parse, lint+fix, and rewrite ``file_path``."""
    runner = LintRunner(config=config)
    return runner.lint_and_fix_file(file_path, max_safety=max_safety, write=write)
