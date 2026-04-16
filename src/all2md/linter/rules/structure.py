"""Structural document rules (STR001-STR005).

These check high-level document shape: does it have a title, are heading
levels consistent, are headings empty or orphaned?
"""

from __future__ import annotations

from all2md.ast import Document, Heading, NodeCollector, extract_text
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation


def _heading_line(heading: Heading) -> int | None:
    return heading.source_location.line if heading.source_location else None


def _heading_column(heading: Heading) -> int | None:
    return heading.source_location.column if heading.source_location else None


def _collect_headings(doc: Document) -> list[Heading]:
    collector = NodeCollector(lambda n: isinstance(n, Heading))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Heading)]


def _heading_text(heading: Heading) -> str:
    """Return the heading's plain text with whitespace collapsed."""
    raw = extract_text(heading, joiner="")
    return " ".join(raw.split())


class MissingTitleRule(LintRule):
    """STR001: Flag documents that lack a top-level (H1) heading."""

    code = "STR001"
    name = "missing-title"
    category = "structure"
    description = "Every document should have a top-level (H1) heading."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a single violation if the document has no H1 heading."""
        headings = _collect_headings(ctx.document)
        if any(h.level == 1 for h in headings):
            return []
        return [
            self.build_violation(
                message="Document has no top-level heading (H1)",
                suggestion="Add a '# Title' heading at the top of the document",
            )
        ]


class MultipleH1Rule(LintRule):
    """STR002: Flag documents that contain more than one H1 heading."""

    code = "STR002"
    name = "multiple-h1"
    category = "structure"
    description = "A document should have exactly one H1 heading."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation per extra H1 (skipping the first one)."""
        h1s = [h for h in _collect_headings(ctx.document) if h.level == 1]
        if len(h1s) <= 1:
            return []
        violations: list[Violation] = []
        for extra in h1s[1:]:
            text = _heading_text(extra)
            violations.append(
                self.build_violation(
                    message=f"Additional H1 heading found: {text!r}",
                    line=_heading_line(extra),
                    column=_heading_column(extra),
                    node_type="Heading",
                    suggestion="Demote this heading or merge it with the primary H1",
                    context=text[:80] or None,
                )
            )
        return violations


class HeadingHierarchyRule(LintRule):
    """STR003: Flag heading-level skips (for example, H1 followed directly by H3)."""

    code = "STR003"
    name = "heading-hierarchy"
    category = "structure"
    description = "Heading levels must not skip (e.g., H1 followed by H3)."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for every heading that skips a level."""
        violations: list[Violation] = []
        prev_level = 0
        for heading in _collect_headings(ctx.document):
            if prev_level > 0 and heading.level > prev_level + 1:
                text = _heading_text(heading)
                violations.append(
                    self.build_violation(
                        message=f"Heading level {heading.level} follows level {prev_level}",
                        line=_heading_line(heading),
                        column=_heading_column(heading),
                        node_type="Heading",
                        suggestion=f"Use heading level {prev_level + 1} instead",
                        context=text[:80] or None,
                    )
                )
            prev_level = heading.level
        return violations


class EmptyHeadingRule(LintRule):
    """STR004: Flag headings that contain no text."""

    code = "STR004"
    name = "empty-heading"
    category = "structure"
    description = "Headings must contain text."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each empty heading."""
        violations: list[Violation] = []
        for heading in _collect_headings(ctx.document):
            if not _heading_text(heading):
                violations.append(
                    self.build_violation(
                        message=f"Empty H{heading.level} heading",
                        line=_heading_line(heading),
                        column=_heading_column(heading),
                        node_type="Heading",
                        suggestion="Add text to the heading or remove it",
                    )
                )
        return violations


class OrphanHeadingRule(LintRule):
    """STR005: Flag a heading that ends the document with no content after it."""

    code = "STR005"
    name = "orphan-heading"
    category = "structure"
    description = "A heading at the end of the document with no content after it is likely a mistake."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation if the last child of the document is a heading."""
        children = ctx.document.children
        if not children:
            return []
        last = children[-1]
        if not isinstance(last, Heading):
            return []
        text = _heading_text(last)
        return [
            self.build_violation(
                message=f"Heading {text!r} has no content after it",
                line=_heading_line(last),
                column=_heading_column(last),
                node_type="Heading",
                suggestion="Add content beneath the heading or remove it",
                context=text[:80] or None,
            )
        ]


for _rule_cls in (
    MissingTitleRule,
    MultipleH1Rule,
    HeadingHierarchyRule,
    EmptyHeadingRule,
    OrphanHeadingRule,
):
    rule_registry.register(_rule_cls)
