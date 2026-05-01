"""Coverage for TBL001-TBL006."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Paragraph, Table, TableCell, TableRow, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.tables import (
    TableCaptionMissingRule,
    TableEmptyCellsRule,
    TableHeaderMissingRule,
    TableSingleColumnRule,
    TableSingleRowRule,
    TableWidthExcessiveRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document, options=None) -> LintContext:
    return LintContext(document=doc, config=options or {})


def _cell(text: str) -> TableCell:
    return TableCell(content=[Text(content=text)] if text else [])


def _row(*texts: str, header: bool = False) -> TableRow:
    return TableRow(cells=[_cell(t) for t in texts], is_header=header)


class TestTableHeaderMissing:
    def test_flags_table_without_header(self):
        doc = Document(children=[Table(rows=[_row("a"), _row("b")])])
        result = TableHeaderMissingRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TBL001"

    def test_silent_when_header_present(self):
        doc = Document(children=[Table(header=_row("Col", header=True), rows=[_row("a"), _row("b")])])
        assert TableHeaderMissingRule().check(_ctx(doc)) == []


class TestTableEmptyCells:
    def test_flags_empty_cells(self):
        doc = Document(
            children=[
                Table(
                    header=_row("A", "B", header=True),
                    rows=[_row("x", ""), _row("y", "z")],
                )
            ]
        )
        result = TableEmptyCellsRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TBL002"


class TestTableSingleColumn:
    def test_flags_single_column(self):
        doc = Document(children=[Table(header=_row("Only", header=True), rows=[_row("a"), _row("b")])])
        result = TableSingleColumnRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TBL003"


class TestTableSingleRow:
    def test_flags_single_body_row(self):
        doc = Document(children=[Table(header=_row("A", "B", header=True), rows=[_row("x", "y")])])
        result = TableSingleRowRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TBL004"

    def test_silent_for_two_rows(self):
        doc = Document(children=[Table(header=_row("A", "B", header=True), rows=[_row("x", "y"), _row("p", "q")])])
        assert TableSingleRowRule().check(_ctx(doc)) == []


class TestTableCaptionMissing:
    def test_flags_table_without_caption_or_preceding_paragraph(self):
        doc = Document(children=[Table(header=_row("A", header=True), rows=[_row("x"), _row("y")])])
        result = TableCaptionMissingRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TBL005"

    def test_silent_when_preceded_by_paragraph(self):
        doc = Document(
            children=[
                Paragraph(content=[Text(content="The next table shows…")]),
                Table(header=_row("A", header=True), rows=[_row("x"), _row("y")]),
            ]
        )
        assert TableCaptionMissingRule().check(_ctx(doc)) == []


class TestTableWidthExcessive:
    def test_flags_wide_tables(self):
        doc = Document(
            children=[
                Table(
                    header=_row("a", "b", "c", "d", "e", header=True),
                    rows=[_row("1", "2", "3", "4", "5")],
                )
            ]
        )
        result = TableWidthExcessiveRule().check(_ctx(doc, {"max_columns": 3}))
        assert len(result) == 1
        assert result[0].rule_code == "TBL006"
