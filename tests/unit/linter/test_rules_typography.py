"""Happy-path coverage for TYP001-TYP008 plus their auto-fixes."""

from __future__ import annotations

import pytest

from all2md.ast import Document, List, ListItem, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.typography import (
    ConsecutivePunctuationRule,
    DoubleHyphensRule,
    EllipsisCharacterRule,
    MixedListMarkersRule,
    MultipleSpacesRule,
    SpaceBeforePunctuationRule,
    StraightQuotesRule,
    TrailingSpacesRule,
)

from ._fix_helpers import assert_idempotent, lint_then_fix

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

    def test_ellipsis_character_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content="wait...")])])
        result = EllipsisCharacterRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP006"

    def test_ellipsis_silent_for_four_dots(self):
        # Four dots is a sentence-ending ellipsis pattern that the rule deliberately ignores.
        doc = Document(children=[Paragraph(content=[Text(content="wait....")])])
        assert EllipsisCharacterRule().check(_ctx(doc)) == []

    def test_space_before_punctuation_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello , world ?")])])
        result = SpaceBeforePunctuationRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP007"

    def test_consecutive_punctuation_flagged(self):
        doc = Document(children=[Paragraph(content=[Text(content="really??")])])
        result = ConsecutivePunctuationRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "TYP008"

    def test_consecutive_punctuation_silent_for_dots_and_excl(self):
        # ?! is treated as intentional and should not fire (different chars).
        doc = Document(children=[Paragraph(content=[Text(content="really?!")])])
        assert ConsecutivePunctuationRule().check(_ctx(doc)) == []


class TestTypographyFixes:
    def test_typ001_strips_trailing_space(self):
        text = Text(content="hello   ")
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP001"])
        assert text.content == "hello"

    def test_typ001_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello   ")])])
        assert_idempotent(doc, ["TYP001"])

    def test_typ002_collapses_runs(self):
        text = Text(content="hello   world")
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP002"])
        assert text.content == "hello world"

    def test_typ002_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello   world")])])
        assert_idempotent(doc, ["TYP002"])

    def test_typ003_curls_double_quotes(self):
        text = Text(content='He said "hello" today.')
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP003"])
        assert "“" in text.content
        assert "”" in text.content
        assert '"' not in text.content

    def test_typ003_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content='He said "hello".')])])
        assert_idempotent(doc, ["TYP003"])

    def test_typ004_replaces_double_hyphen_with_em_dash(self):
        text = Text(content="alpha -- beta")
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP004"])
        assert text.content == "alpha — beta"

    def test_typ004_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content="alpha -- beta")])])
        assert_idempotent(doc, ["TYP004"])

    def test_typ006_replaces_dots_with_ellipsis(self):
        text = Text(content="wait...")
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP006"])
        assert text.content == "wait…"

    def test_typ006_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content="wait...")])])
        assert_idempotent(doc, ["TYP006"])

    def test_typ007_strips_space_before_punctuation(self):
        text = Text(content="hello , world ?")
        doc = Document(children=[Paragraph(content=[text])])
        lint_then_fix(doc, ["TYP007"])
        assert text.content == "hello, world?"

    def test_typ007_idempotent(self):
        doc = Document(children=[Paragraph(content=[Text(content="hello , world ?")])])
        assert_idempotent(doc, ["TYP007"])
