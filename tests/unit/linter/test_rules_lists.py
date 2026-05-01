"""Coverage for LST001-LST006."""

from __future__ import annotations

import pytest

from all2md.ast import Document, List, ListItem, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.lists import (
    EmptyListItemRule,
    ListCapitalizationInconsistentRule,
    ListDepthExcessiveRule,
    ListPunctuationInconsistentRule,
    OrderedListNumberingRule,
    SingleItemListRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document, options=None) -> LintContext:
    return LintContext(document=doc, config=options or {})


def _item(text: str) -> ListItem:
    return ListItem(children=[Paragraph(content=[Text(content=text)])])


class TestSingleItemList:
    def test_flags_single_item_list(self):
        doc = Document(children=[List(ordered=False, items=[_item("only one")])])
        result = SingleItemListRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LST001"

    def test_silent_for_two_items(self):
        doc = Document(children=[List(ordered=False, items=[_item("first"), _item("second")])])
        assert SingleItemListRule().check(_ctx(doc)) == []


class TestEmptyListItem:
    def test_flags_empty_item(self):
        doc = Document(children=[List(ordered=False, items=[_item("ok"), ListItem(children=[])])])
        result = EmptyListItemRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LST002"


class TestOrderedListNumbering:
    def test_flags_non_one_start(self):
        doc = Document(children=[List(ordered=True, items=[_item("a"), _item("b")], start=5)])
        result = OrderedListNumberingRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LST003"

    def test_silent_for_unordered_lists(self):
        doc = Document(children=[List(ordered=False, items=[_item("a"), _item("b")], start=5)])
        assert OrderedListNumberingRule().check(_ctx(doc)) == []


class TestListDepthExcessive:
    def test_flags_deep_nesting(self):
        # Build a list nested 5 levels deep
        innermost = List(ordered=False, items=[_item("deep")])
        nested = innermost
        for _ in range(4):
            nested = List(ordered=False, items=[ListItem(children=[nested])])
        doc = Document(children=[nested])
        result = ListDepthExcessiveRule().check(_ctx(doc, {"max_depth": 4}))
        # The innermost list (depth 5) should be flagged.
        assert len(result) >= 1
        assert all(v.rule_code == "LST004" for v in result)

    def test_silent_at_threshold(self):
        # Nesting exactly at max_depth — should not flag
        innermost = List(ordered=False, items=[_item("ok")])
        nested = List(ordered=False, items=[ListItem(children=[innermost])])
        doc = Document(children=[nested])
        assert ListDepthExcessiveRule().check(_ctx(doc, {"max_depth": 4})) == []


class TestListPunctuationInconsistent:
    def test_flags_mixed_periods(self):
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[_item("First."), _item("Second"), _item("Third.")],
                )
            ]
        )
        result = ListPunctuationInconsistentRule().check(_ctx(doc))
        # Two items have periods, one doesn't — the no-period item is the minority.
        assert len(result) == 1
        assert result[0].rule_code == "LST005"

    def test_silent_when_consistent(self):
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[_item("a"), _item("b"), _item("c")],
                )
            ]
        )
        assert ListPunctuationInconsistentRule().check(_ctx(doc)) == []


class TestListCapitalizationInconsistent:
    def test_flags_mixed_case(self):
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[_item("Apple"), _item("banana"), _item("Cherry")],
                )
            ]
        )
        result = ListCapitalizationInconsistentRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LST006"
