"""Structural document rules (STR001-STR008).

These check high-level document shape: does it have a title, are heading
levels consistent, are headings empty or orphaned, are sections too short,
is the document empty, is block-level nesting excessive?
"""

from __future__ import annotations

from typing import Any, Callable

from all2md.ast import (
    BlockQuote,
    Document,
    Heading,
    ListItem,
    Node,
    NodeCollector,
    extract_text,
    get_node_children,
)
from all2md.linter.fixes import FixContext, FixSafety, LintFix
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_DEFAULT_SHORT_SECTION_WORDS = 10
_DEFAULT_MAX_NESTING_DEPTH = 4


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


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


def _remove_empty_heading(heading: Heading) -> Callable[[FixContext], None]:
    """Build a fix-apply callback that removes ``heading`` from its parent.

    Closes over ``heading`` via a default argument to avoid the late-binding
    closure pitfall when this is called inside a loop.
    """

    def _apply(fctx: FixContext, h: Heading = heading) -> None:
        fctx.remove(h)

    return _apply


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
                        fix=LintFix(
                            target=heading,
                            apply=_remove_empty_heading(heading),
                            safety=FixSafety.SAFE,
                            description="Remove empty heading",
                        ),
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


class ShortSectionRule(LintRule):
    """STR006: Flag headings whose section contains fewer than N words of content.

    A "section" is the run of top-level children between this heading and the
    next heading at the same-or-higher level (matching how readers perceive a
    section). The default threshold is 10 words; override via
    ``[tool.all2md.lint.rules]`` ``STR006.min_words``.
    """

    code = "STR006"
    name = "short-section"
    category = "structure"
    description = "Sections should have enough content to justify their heading."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each heading whose section is too short."""
        min_words = _coerce_positive_int(
            ctx.config.get("min_words", _DEFAULT_SHORT_SECTION_WORDS),
            default=_DEFAULT_SHORT_SECTION_WORDS,
        )
        violations: list[Violation] = []
        children = ctx.document.children
        n = len(children)
        for idx, child in enumerate(children):
            if not isinstance(child, Heading):
                continue
            # Collect siblings until the next same-or-higher-level heading.
            section_nodes: list[Node] = []
            for j in range(idx + 1, n):
                follow = children[j]
                if isinstance(follow, Heading) and follow.level <= child.level:
                    break
                section_nodes.append(follow)
            words = sum(len(extract_text(n, joiner=" ").split()) for n in section_nodes)
            if words < min_words:
                text = _heading_text(child)
                violations.append(
                    self.build_violation(
                        message=f"Section under {text!r} has only {words} words (min {min_words})",
                        line=_heading_line(child),
                        column=_heading_column(child),
                        node_type="Heading",
                        suggestion="Expand the section or merge it into an adjacent one",
                        context=text[:80] or None,
                    )
                )
        return violations


class EmptyDocumentRule(LintRule):
    """STR007: Flag documents whose children list is empty."""

    code = "STR007"
    name = "empty-document"
    category = "structure"
    description = "A document should contain at least one block."
    default_severity = Severity.ERROR

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a single violation if ``ctx.document.children`` is empty."""
        if ctx.document.children:
            return []
        return [
            self.build_violation(
                message="Document is empty (no children)",
                suggestion="Add content to the document",
            )
        ]


class ExcessiveNestingRule(LintRule):
    """STR008: Flag block-level nesting deeper than N levels.

    "Block-level nesting" counts only :class:`BlockQuote` and :class:`ListItem`
    on the path from the document root to the deepest descendant. Default
    threshold is 4; override via ``STR008.max_depth``.
    """

    code = "STR008"
    name = "excessive-nesting"
    category = "structure"
    description = "Block-level nesting (blockquotes, list items) should not be excessively deep."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation per nested container exceeding ``max_depth``."""
        max_depth = _coerce_positive_int(
            ctx.config.get("max_depth", _DEFAULT_MAX_NESTING_DEPTH),
            default=_DEFAULT_MAX_NESTING_DEPTH,
        )
        violations: list[Violation] = []
        seen: set[int] = set()
        self._walk(ctx.document, depth=0, max_depth=max_depth, violations=violations, seen=seen)
        return violations

    def _walk(
        self,
        node: Node,
        *,
        depth: int,
        max_depth: int,
        violations: list[Violation],
        seen: set[int],
    ) -> None:
        new_depth = depth + 1 if isinstance(node, (BlockQuote, ListItem)) else depth
        if new_depth > max_depth and id(node) not in seen and isinstance(node, (BlockQuote, ListItem)):
            seen.add(id(node))
            violations.append(
                self.build_violation(
                    message=f"{type(node).__name__} is nested {new_depth} levels deep (max {max_depth})",
                    line=node.source_location.line if node.source_location else None,
                    column=node.source_location.column if node.source_location else None,
                    node_type=type(node).__name__,
                    suggestion="Flatten the nesting or split into separate top-level blocks",
                )
            )
        for child in get_node_children(node):
            self._walk(child, depth=new_depth, max_depth=max_depth, violations=violations, seen=seen)


for _rule_cls in (
    MissingTitleRule,
    MultipleH1Rule,
    HeadingHierarchyRule,
    EmptyHeadingRule,
    OrphanHeadingRule,
    ShortSectionRule,
    EmptyDocumentRule,
    ExcessiveNestingRule,
):
    rule_registry.register(_rule_cls)
