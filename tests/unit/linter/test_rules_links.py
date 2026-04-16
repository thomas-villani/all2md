"""Happy-path coverage for LNK001-LNK005."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Link, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.links import (
    BareUrlRule,
    DuplicateUrlsRule,
    EmptyLinkTextRule,
    LinkTextQualityRule,
    MissingUrlRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document) -> LintContext:
    return LintContext(document=doc)


def _para_with_link(link: Link) -> Paragraph:
    return Paragraph(content=[link])


class TestLinkRules:
    def test_empty_link_text_flags_missing_content(self):
        doc = Document(children=[_para_with_link(Link(url="https://example.com", content=[]))])
        result = EmptyLinkTextRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LNK001"

    def test_empty_link_text_silent_with_content(self):
        doc = Document(children=[_para_with_link(Link(url="https://example.com", content=[Text(content="docs")]))])
        assert EmptyLinkTextRule().check(_ctx(doc)) == []

    def test_missing_url_flags_blank(self):
        doc = Document(children=[_para_with_link(Link(url="", content=[Text(content="text")]))])
        result = MissingUrlRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LNK002"

    def test_duplicate_urls_reports_extras(self):
        doc = Document(
            children=[
                _para_with_link(Link(url="https://example.com", content=[Text(content="a")])),
                _para_with_link(Link(url="https://example.com", content=[Text(content="b")])),
                _para_with_link(Link(url="https://example.com", content=[Text(content="c")])),
            ]
        )
        result = DuplicateUrlsRule().check(_ctx(doc))
        assert len(result) == 2
        assert all(v.rule_code == "LNK003" for v in result)

    def test_bare_url_detected_in_paragraph_text(self):
        doc = Document(
            children=[
                Paragraph(content=[Text(content="See https://example.com for more info.")]),
            ]
        )
        result = BareUrlRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LNK004"

    def test_bare_url_silent_inside_link(self):
        doc = Document(
            children=[_para_with_link(Link(url="https://example.com", content=[Text(content="https://example.com")]))]
        )
        assert BareUrlRule().check(_ctx(doc)) == []

    def test_link_text_quality_flags_click_here(self):
        doc = Document(
            children=[_para_with_link(Link(url="https://example.com", content=[Text(content="click here")]))]
        )
        result = LinkTextQualityRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "LNK005"
