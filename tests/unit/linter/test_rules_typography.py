"""Happy-path coverage for TYP001-TYP005."""

from __future__ import annotations

import pytest

from all2md.ast import Document, List, ListItem, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.typography import (
    DoubleHyphensRule,
    MixedListMarkersRule,
    MultipleSpacesRule,
    StraightQuotesRule,
    TrailingSpacesRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document) -> LintContext:
    return LintContext(document=doc)


class TestTypographyRules:
    def test_trailing_spaces_flags_text_ending_in_space(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello ")])])
        result = TrailingSpacesRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP001"

    def test_trailing_spaces_silent_when_not_last_child(self):
        """Text with trailing space that precedes another inline element is fine."""
        from all2md.ast import Emphasis

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Read the "),
                        Emphasis(content=[Text(content="docs")]),
                    ]
                )
            ]
        )
        assert TrailingSpacesRule().check(_ctx(doc)) == []

    def test_multiple_spaces_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello  world")])])
        result = MultipleSpacesRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP002"

    def test_straight_quotes_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content='A "quoted" phrase.')])])
        result = StraightQuotesRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP003"

    def test_double_hyphens_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content="foo -- bar")])])
        result = DoubleHyphensRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP004"

    def test_mixed_list_markers_flagged_on_adjacent_lists(self):
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[ListItem(children=[Paragraph(content=[Text(content="a")])])],
                ),
                List(
                    ordered=True,
                    items=[ListItem(children=[Paragraph(content=[Text(content="1")])])],
                ),
            ]
        )
        result = MixedListMarkersRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP005"

    def test_mixed_list_markers_silent_with_paragraph_between(self):
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[ListItem(children=[Paragraph(content=[Text(content="a")])])],
                ),
                Paragraph(content=[Text(content="divider")]),
                List(
                    ordered=True,
                    items=[ListItem(children=[Paragraph(content=[Text(content="1")])])],
                ),
            ]
        )
        assert MixedListMarkersRule().check(_ctx(doc)) == []
