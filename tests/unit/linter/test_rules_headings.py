"""Happy-path coverage for HDG001-HDG005."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Heading, Strong, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.headings import (
    DuplicateHeadingsRule,
    HeadingCapitalizationRule,
    HeadingEmphasisRule,
    HeadingLengthRule,
    HeadingTrailingPunctuationRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document, options=None) -> LintContext:
    return LintContext(document=doc, config=options or {})


class TestHeadingRules:
    def test_trailing_punctuation_flags_period(self):
        doc = Document(children=[Heading(level=2, content=[Text(content="Overview.")])])
        result = HeadingTrailingPunctuationRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "HDG001"

    def test_trailing_punctuation_silent_on_question(self):
        doc = Document(children=[Heading(level=2, content=[Text(content="Why?")])])
        assert HeadingTrailingPunctuationRule().check(_ctx(doc)) == []

    def test_length_uses_default_limit(self):
        long_text = "x" * 100
        doc = Document(children=[Heading(level=2, content=[Text(content=long_text)])])
        result = HeadingLengthRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "HDG002"

    def test_length_honours_rule_options(self):
        doc = Document(children=[Heading(level=2, content=[Text(content="x" * 40)])])
        result = HeadingLengthRule().check(_ctx(doc, options={"max_length": 30}))
        assert len(result) == 1

    def test_duplicate_headings_flag_second_occurrence(self):
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Setup")]),
                Heading(level=2, content=[Text(content="Setup")]),
            ]
        )
        result = DuplicateHeadingsRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "HDG003"

    def test_capitalization_flags_outlier_in_group(self):
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Getting Started Guide")]),
                Heading(level=2, content=[Text(content="Installing The Package")]),
                Heading(level=2, content=[Text(content="Configuring with yaml files")]),
            ]
        )
        result = HeadingCapitalizationRule().check(_ctx(doc))
        codes = {v.rule_code for v in result}
        assert "HDG004" in codes

    def test_heading_emphasis_flags_wrapped_strong(self):
        doc = Document(
            children=[
                Heading(level=2, content=[Strong(content=[Text(content="Bold Title")])]),
            ]
        )
        result = HeadingEmphasisRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "HDG005"

    def test_heading_emphasis_silent_on_partial(self):
        doc = Document(
            children=[
                Heading(
                    level=2,
                    content=[
                        Text(content="Intro to "),
                        Strong(content=[Text(content="bold")]),
                    ],
                )
            ]
        )
        assert HeadingEmphasisRule().check(_ctx(doc)) == []
