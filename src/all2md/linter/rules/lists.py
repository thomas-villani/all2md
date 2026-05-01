"""List rules (LST001-LST006).

Lists are the most common non-heading structure in converted documents
and are frequently mangled by format conversion. These rules check for
single-item lists, empty items, ordered-list numbering issues, excessive
nesting, and inconsistent punctuation/capitalization across siblings.
"""

from __future__ import annotations

from typing import Any

from all2md.ast import Document, List, ListItem, Node, NodeCollector, extract_text
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_DEFAULT_MAX_LIST_DEPTH = 4


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _line(node: Node) -> int | None:
    return node.source_location.line if node.source_location else None


def _column(node: Node) -> int | None:
    return node.source_location.column if node.source_location else None


def _collect_lists(doc: Document) -> list[List]:
    collector = NodeCollector(lambda n: isinstance(n, List))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, List)]


def _item_text(item: ListItem) -> str:
    """Return the item's plain text with whitespace collapsed."""
    raw = extract_text(item, joiner=" ")
    return " ".join(raw.split())


class SingleItemListRule(LintRule):
    """LST001: Flag lists that contain a single item."""

    code = "LST001"
    name = "single-item-list"
    category = "lists"
    description = "A list with only one item should usually be a paragraph."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each list whose ``items`` has length one."""
        violations: list[Violation] = []
        for lst in _collect_lists(ctx.document):
            if len(lst.items) == 1:
                violations.append(
                    self.build_violation(
                        message="List has only one item",
                        line=_line(lst),
                        column=_column(lst),
                        node_type="List",
                        suggestion="Convert to a paragraph or expand the list",
                    )
                )
        return violations


class EmptyListItemRule(LintRule):
    """LST002: Flag list items that contain no rendered text."""

    code = "LST002"
    name = "empty-list-item"
    category = "lists"
    description = "List items must have content."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each list item whose text content is empty."""
        violations: list[Violation] = []
        for lst in _collect_lists(ctx.document):
            for item in lst.items:
                if not _item_text(item):
                    violations.append(
                        self.build_violation(
                            message="List item has no content",
                            line=_line(item),
                            column=_column(item),
                            node_type="ListItem",
                            suggestion="Add content to the item or remove it",
                        )
                    )
        return violations


class OrderedListNumberingRule(LintRule):
    """LST003: Flag ordered lists that don't start at 1.

    The AST tracks only the list's ``start`` attribute (the number the
    first item renders as), so this rule cannot detect mid-list numbering
    gaps from the AST alone — it flags non-1 starts. Markdown renderers
    re-number anyway, so the practical risk this catches is "the source
    intentionally started at 5, was that meant?"
    """

    code = "LST003"
    name = "ordered-list-numbering"
    category = "lists"
    description = "Ordered lists should typically start at 1."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each ordered list whose ``start`` is not 1."""
        violations: list[Violation] = []
        for lst in _collect_lists(ctx.document):
            if not lst.ordered:
                continue
            if lst.start != 1:
                violations.append(
                    self.build_violation(
                        message=f"Ordered list starts at {lst.start} (expected 1)",
                        line=_line(lst),
                        column=_column(lst),
                        node_type="List",
                        suggestion="Renumber the list to start at 1",
                    )
                )
        return violations


class ListDepthExcessiveRule(LintRule):
    """LST004: Flag lists nested deeper than ``max_depth`` levels.

    Depth is counted in nested :class:`List` nodes (``max_depth`` defaults
    to 4). Override via ``[tool.all2md.lint.rules]`` ``LST004.max_depth``.
    """

    code = "LST004"
    name = "list-depth-excessive"
    category = "lists"
    description = "Lists should not be nested too deeply."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each list whose nesting depth exceeds the threshold."""
        max_depth = _coerce_positive_int(
            ctx.config.get("max_depth", _DEFAULT_MAX_LIST_DEPTH),
            default=_DEFAULT_MAX_LIST_DEPTH,
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
        from all2md.ast import get_node_children

        new_depth = depth + 1 if isinstance(node, List) else depth
        if isinstance(node, List) and new_depth > max_depth and id(node) not in seen:
            seen.add(id(node))
            violations.append(
                self.build_violation(
                    message=f"List is nested {new_depth} levels deep (max {max_depth})",
                    line=_line(node),
                    column=_column(node),
                    node_type="List",
                    suggestion="Flatten the nesting or split into separate lists",
                )
            )
        for child in get_node_children(node):
            self._walk(child, depth=new_depth, max_depth=max_depth, violations=violations, seen=seen)


class ListPunctuationInconsistentRule(LintRule):
    """LST005: Flag lists where some items end with a period and others don't.

    Lists with fewer than two non-empty items are exempt — the comparison
    is meaningless. Items that end in any non-letter punctuation other
    than ``.``/``!``/``?`` are treated as "no terminal punctuation" for
    the purpose of this rule.
    """

    code = "LST005"
    name = "list-punctuation-inconsistent"
    category = "lists"
    description = "List items should be consistent about ending with a period."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each minority-style item in a mixed-style list."""
        violations: list[Violation] = []
        for lst in _collect_lists(ctx.document):
            entries = [(item, _item_text(item)) for item in lst.items]
            entries = [(item, text) for item, text in entries if text]
            if len(entries) < 2:
                continue
            ending = [(item, text, text[-1] in ".!?") for item, text in entries]
            with_period = sum(1 for _, _, has in ending if has)
            without_period = len(ending) - with_period
            if with_period == 0 or without_period == 0:
                continue
            majority_has_period = with_period >= without_period
            for item, text, has_period in ending:
                if has_period == majority_has_period:
                    continue
                violations.append(
                    self.build_violation(
                        message=(
                            "List item differs from sibling punctuation style "
                            f"({'no period' if not has_period else 'period'})"
                        ),
                        line=_line(item),
                        column=_column(item),
                        node_type="ListItem",
                        suggestion="Match the punctuation style of the other items in this list",
                        context=text[:80],
                    )
                )
        return violations


class ListCapitalizationInconsistentRule(LintRule):
    """LST006: Flag lists where some items start with an uppercase letter and others don't."""

    code = "LST006"
    name = "list-capitalization-inconsistent"
    category = "lists"
    description = "List items should consistently start with the same case."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each minority-case item in a mixed-case list."""
        violations: list[Violation] = []
        for lst in _collect_lists(ctx.document):
            entries: list[tuple[ListItem, str, bool]] = []
            for item in lst.items:
                text = _item_text(item)
                if not text:
                    continue
                first = text[0]
                if not first.isalpha():
                    continue
                entries.append((item, text, first.isupper()))
            if len(entries) < 2:
                continue
            with_upper = sum(1 for _, _, up in entries if up)
            with_lower = len(entries) - with_upper
            if with_upper == 0 or with_lower == 0:
                continue
            majority_upper = with_upper >= with_lower
            for item, text, is_upper in entries:
                if is_upper == majority_upper:
                    continue
                violations.append(
                    self.build_violation(
                        message=(
                            "List item differs from sibling capitalization "
                            f"({'lowercase' if not is_upper else 'uppercase'} start)"
                        ),
                        line=_line(item),
                        column=_column(item),
                        node_type="ListItem",
                        suggestion="Match the capitalization of the other items in this list",
                        context=text[:80],
                    )
                )
        return violations


for _rule_cls in (
    SingleItemListRule,
    EmptyListItemRule,
    OrderedListNumberingRule,
    ListDepthExcessiveRule,
    ListPunctuationInconsistentRule,
    ListCapitalizationInconsistentRule,
):
    rule_registry.register(_rule_cls)
