"""Table rules (TBL001-TBL006).

Tables are critical to all2md (PDF table detection is a headline feature)
and converted tables frequently have structural issues. These rules
check for missing headers, empty cells, single-column or single-row
tables, missing captions, and excessive width.
"""

from __future__ import annotations

from typing import Any

from all2md.ast import (
    Document,
    Node,
    NodeCollector,
    Paragraph,
    Table,
    TableCell,
    extract_text,
)
from all2md.linter.registry import rule_registry
from all2md.linter.rule import LintContext, LintRule
from all2md.linter.violations import Severity, Violation

_DEFAULT_MAX_TABLE_COLUMNS = 12


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


def _collect_tables(doc: Document) -> list[Table]:
    collector = NodeCollector(lambda n: isinstance(n, Table))
    doc.accept(collector)
    return [n for n in collector.collected if isinstance(n, Table)]


def _cell_text(cell: TableCell) -> str:
    raw = extract_text(cell, joiner=" ")
    return " ".join(raw.split())


class TableHeaderMissingRule(LintRule):
    """TBL001: Flag tables that have no header row."""

    code = "TBL001"
    name = "table-header-missing"
    category = "tables"
    description = "Tables should have a header row to label their columns."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each table without a header."""
        violations: list[Violation] = []
        for table in _collect_tables(ctx.document):
            if table.header is None:
                violations.append(
                    self.build_violation(
                        message="Table has no header row",
                        line=_line(table),
                        column=_column(table),
                        node_type="Table",
                        suggestion="Add a header row that names each column",
                    )
                )
        return violations


class TableEmptyCellsRule(LintRule):
    """TBL002: Flag tables with cells that have no rendered text content.

    Reports one violation per empty cell. Cells whose content is solely
    whitespace are treated as empty.
    """

    code = "TBL002"
    name = "table-empty-cells"
    category = "tables"
    description = "Cells should have content."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each empty cell in any table."""
        violations: list[Violation] = []
        for table in _collect_tables(ctx.document):
            cells: list[TableCell] = []
            if table.header:
                cells.extend(table.header.cells)
            for row in table.rows:
                cells.extend(row.cells)
            for cell in cells:
                if not _cell_text(cell):
                    violations.append(
                        self.build_violation(
                            message="Table cell is empty",
                            line=_line(cell),
                            column=_column(cell),
                            node_type="TableCell",
                            suggestion="Add content to the cell or use a placeholder like '—'",
                        )
                    )
        return violations


class TableSingleColumnRule(LintRule):
    """TBL003: Flag tables that contain only one column."""

    code = "TBL003"
    name = "table-single-column"
    category = "tables"
    description = "Single-column tables should usually be a list."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each table whose widest row has only one cell."""
        violations: list[Violation] = []
        for table in _collect_tables(ctx.document):
            widest = 0
            if table.header:
                widest = max(widest, len(table.header.cells))
            for row in table.rows:
                widest = max(widest, len(row.cells))
            if widest == 1:
                violations.append(
                    self.build_violation(
                        message="Table has only one column",
                        line=_line(table),
                        column=_column(table),
                        node_type="Table",
                        suggestion="Convert to a bulleted list",
                    )
                )
        return violations


class TableSingleRowRule(LintRule):
    """TBL004: Flag tables with only one body row (excluding header)."""

    code = "TBL004"
    name = "table-single-row"
    category = "tables"
    description = "Single-row tables often don't need to be tables."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each table whose ``rows`` list has length one."""
        violations: list[Violation] = []
        for table in _collect_tables(ctx.document):
            if len(table.rows) == 1:
                violations.append(
                    self.build_violation(
                        message="Table has only one body row",
                        line=_line(table),
                        column=_column(table),
                        node_type="Table",
                        suggestion="Consider rewriting as a paragraph or definition list",
                    )
                )
        return violations


class TableCaptionMissingRule(LintRule):
    """TBL005: Flag tables that have neither a caption nor a preceding paragraph.

    A "preceding paragraph" is the last sibling immediately before the
    table; if it's a :class:`Paragraph`, we treat the table as captioned
    in prose. This is intentionally lenient — an explicit ``caption`` on
    the AST is preferred but not required.
    """

    code = "TBL005"
    name = "table-caption-missing"
    category = "tables"
    description = "Tables should be introduced by a caption or preceding paragraph."
    default_severity = Severity.INFO

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each table that is neither captioned nor preceded by a paragraph."""
        violations: list[Violation] = []
        self._walk(ctx.document, violations)
        return violations

    def _walk(self, parent: Node, violations: list[Violation]) -> None:
        from all2md.ast import get_node_children

        children = get_node_children(parent)
        for idx, child in enumerate(children):
            if isinstance(child, Table):
                if child.caption:
                    pass
                else:
                    prev = children[idx - 1] if idx > 0 else None
                    if not isinstance(prev, Paragraph):
                        violations.append(
                            self.build_violation(
                                message="Table has no caption or preceding paragraph",
                                line=_line(child),
                                column=_column(child),
                                node_type="Table",
                                suggestion="Add a caption or a sentence introducing the table",
                            )
                        )
            self._walk(child, violations)


class TableWidthExcessiveRule(LintRule):
    """TBL006: Flag tables whose header has more than ``max_columns`` columns (default 12)."""

    code = "TBL006"
    name = "table-width-excessive"
    category = "tables"
    description = "Wide tables are hard to read and don't fit on most displays."
    default_severity = Severity.WARNING

    def check(self, ctx: LintContext) -> list[Violation]:
        """Return a violation for each table whose widest row exceeds ``max_columns``."""
        max_columns = _coerce_positive_int(
            ctx.config.get("max_columns", _DEFAULT_MAX_TABLE_COLUMNS),
            default=_DEFAULT_MAX_TABLE_COLUMNS,
        )
        violations: list[Violation] = []
        for table in _collect_tables(ctx.document):
            widest = 0
            if table.header:
                widest = max(widest, len(table.header.cells))
            for row in table.rows:
                widest = max(widest, len(row.cells))
            if widest > max_columns:
                violations.append(
                    self.build_violation(
                        message=f"Table has {widest} columns (max {max_columns})",
                        line=_line(table),
                        column=_column(table),
                        node_type="Table",
                        suggestion="Split the table or transpose rows and columns",
                    )
                )
        return violations


for _rule_cls in (
    TableHeaderMissingRule,
    TableEmptyCellsRule,
    TableSingleColumnRule,
    TableSingleRowRule,
    TableCaptionMissingRule,
    TableWidthExcessiveRule,
):
    rule_registry.register(_rule_cls)
