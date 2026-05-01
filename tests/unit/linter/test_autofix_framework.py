"""Framework-level tests for the auto-fix machinery.

Per-rule fix behaviour is exercised by the existing test files
(``test_rules_typography.py``, ``test_rules_structure.py``); these tests
cover the framework itself: conflict detection, MANUAL pass-through,
crash handling, and ``FixContext`` edge cases.
"""

from __future__ import annotations

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.linter.fixes import (
    FixContext,
    FixSafety,
    LintFix,
    apply_fixes,
)
from all2md.linter.rule import LintRule
from all2md.linter.runner import LintRunner
from all2md.linter.violations import Severity, Violation

pytestmark = pytest.mark.unit


def _make_violation(target, *, safety=FixSafety.SAFE, raises=False, mutate=None) -> Violation:
    """Build a Violation with a synthetic LintFix for testing."""

    def apply_fn(_fctx, t=target, m=mutate):
        if raises:
            raise RuntimeError("synthetic failure")
        if m is not None:
            m(t)

    return Violation(
        rule_code="SYN001",
        rule_name="synthetic",
        message="synthetic violation",
        severity=Severity.INFO,
        fix=LintFix(target=target, apply=apply_fn, safety=safety, description="synthetic fix"),
    )


class TestApplyFixes:
    def test_max_safety_filters_out_higher_safety_levels(self):
        """SUGGESTED fixes are skipped when max_safety=SAFE."""
        node = Text(content="hi")
        doc = Document(children=[Paragraph(content=[node])])
        v = _make_violation(node, safety=FixSafety.SUGGESTED, mutate=lambda n: setattr(n, "content", "X"))
        applied, skipped = apply_fixes(doc, [v], FixSafety.SAFE)
        assert applied == []
        assert skipped == []
        assert node.content == "hi"

    def test_max_safety_includes_equal_or_lower(self):
        """SAFE fixes run when max_safety=SAFE, and SUGGESTED runs when max_safety=SUGGESTED."""
        node1 = Text(content="a")
        node2 = Text(content="b")
        doc = Document(children=[Paragraph(content=[node1, node2])])
        v_safe = _make_violation(node1, safety=FixSafety.SAFE, mutate=lambda n: setattr(n, "content", "A"))
        v_sugg = _make_violation(node2, safety=FixSafety.SUGGESTED, mutate=lambda n: setattr(n, "content", "B"))
        applied, _ = apply_fixes(doc, [v_safe, v_sugg], FixSafety.SUGGESTED)
        assert len(applied) == 2
        assert node1.content == "A"
        assert node2.content == "B"

    def test_conflicting_fixes_first_wins_second_skipped(self):
        """Two fixes targeting the same node — first wins, second goes to skipped."""
        node = Text(content="original")
        doc = Document(children=[Paragraph(content=[node])])
        v1 = _make_violation(node, mutate=lambda n: setattr(n, "content", "first"))
        v2 = _make_violation(node, mutate=lambda n: setattr(n, "content", "second"))
        applied, skipped = apply_fixes(doc, [v1, v2], FixSafety.SAFE)
        assert len(applied) == 1
        assert len(skipped) == 1
        assert node.content == "first"

    def test_violations_without_fixes_are_ignored(self):
        node = Text(content="hi")
        doc = Document(children=[Paragraph(content=[node])])
        v = Violation(
            rule_code="MAN001",
            rule_name="manual-only",
            message="no fix attached",
            severity=Severity.WARNING,
        )
        applied, skipped = apply_fixes(doc, [v], FixSafety.SUGGESTED)
        assert applied == []
        assert skipped == []

    def test_fix_that_raises_is_logged_and_skipped(self):
        node = Text(content="hi")
        doc = Document(children=[Paragraph(content=[node])])
        v = _make_violation(node, raises=True)
        applied, skipped = apply_fixes(doc, [v], FixSafety.SAFE)
        # The fix raised, so it neither lands in 'applied' nor is the node mutated.
        assert applied == []
        assert node.content == "hi"


class TestFixContext:
    def test_parent_of_root_is_none(self):
        doc = Document(children=[])
        fctx = FixContext(doc)
        assert fctx.parent_of(doc) is None

    def test_parent_of_known_descendant(self):
        text = Text(content="x")
        para = Paragraph(content=[text])
        doc = Document(children=[para])
        fctx = FixContext(doc)
        assert fctx.parent_of(text) is para
        assert fctx.parent_of(para) is doc

    def test_remove_detaches_from_parent(self):
        h = Heading(level=2, content=[])
        para = Paragraph(content=[Text(content="kept")])
        doc = Document(children=[h, para])
        fctx = FixContext(doc)
        assert fctx.remove(h) is True
        assert h not in doc.children
        assert para in doc.children

    def test_remove_returns_false_for_orphan(self):
        text = Text(content="x")
        # text is not in the document tree we'll search
        doc = Document(children=[Paragraph(content=[Text(content="other")])])
        fctx = FixContext(doc)
        assert fctx.remove(text) is False


class TestLintAndFixDocument:
    def test_returns_pre_and_post_fix_results(self):
        text = Text(content="hello   world")
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[text]),
            ]
        )
        runner = LintRunner()
        result = runner.lint_and_fix_document(doc)
        # Pre-fix should report TYP002 (multiple-spaces); post-fix should not.
        assert any(v.rule_code == "TYP002" for v in result.initial.violations)
        assert not any(v.rule_code == "TYP002" for v in result.final.violations)
        assert text.content == "hello world"
        assert result.rewritten is True

    def test_clean_document_does_not_rewrite(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(
                    content=[
                        Text(
                            content=(
                                "A clean paragraph with enough words to " "satisfy the short-section rule for sure."
                            )
                        )
                    ]
                ),
            ]
        )
        runner = LintRunner()
        result = runner.lint_and_fix_document(doc)
        assert result.rewritten is False
        assert result.applied == []

    def test_max_passes_caps_runaway_loops(self):
        """A non-idempotent fix shouldn't loop forever — max_passes caps it."""
        node = Text(content="abc")
        doc = Document(children=[Paragraph(content=[node])])

        # Build a synthetic rule that always fires and always toggles content.
        class ToggleRule(LintRule):
            code = "TGL001"
            name = "toggle"
            category = "test"
            description = "test"
            default_severity = Severity.INFO

            def check(self, ctx):
                from all2md.ast import NodeCollector

                collector = NodeCollector(lambda n: isinstance(n, Text))
                ctx.document.accept(collector)
                texts = [n for n in collector.collected if isinstance(n, Text)]
                vs = []
                for t in texts:
                    vs.append(
                        self.build_violation(
                            message="toggle",
                            fix=LintFix(
                                target=t,
                                apply=lambda _f, n=t: setattr(n, "content", "abc" if n.content != "abc" else "def"),
                                safety=FixSafety.SAFE,
                                description="toggle",
                            ),
                        )
                    )
                return vs

        from all2md.linter import LintConfig

        class _FakeRegistry:
            """Duck-typed stand-in — only ``iter_rules`` is consumed by the runner.

            Bypassing the real :class:`RuleRegistry` is critical because
            :class:`RuleRegistry` is a process-wide singleton; mutating it
            from a test would clobber the built-in rule registrations and
            break every other test in the suite.
            """

            def __init__(self, rules):
                self._rules = list(rules)

            def iter_rules(self):
                return iter(self._rules)

        runner = LintRunner(config=LintConfig(), registry=_FakeRegistry([ToggleRule]))
        result = runner.lint_and_fix_document(doc, max_passes=3)
        # Should have applied 3 fixes (capped) and still report a violation.
        assert len(result.applied) == 3
        assert any(v.rule_code == "TGL001" for v in result.final.violations)
