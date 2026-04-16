"""Happy-path coverage for STR001-STR005 on a fixture document."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Heading, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.structure import (
    EmptyHeadingRule,
    HeadingHierarchyRule,
    MissingTitleRule,
    MultipleH1Rule,
    OrphanHeadingRule,
)

pytestmark = pytest.mark.unit


def _ctx(doc: Document) -> LintContext:
    return LintContext(document=doc)


class TestStructureRules:
    def test_missing_title_flags_document_without_h1(self):
        doc = Document(children=[Paragraph(content=[Text(content="no title")])])
        result = MissingTitleRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "STR001"

    def test_missing_title_silent_with_h1(self):
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        assert MissingTitleRule().check(_ctx(doc)) == []

    def test_multiple_h1_flags_extras(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="First")]),
                Heading(level=1, content=[Text(content="Second")]),
                Heading(level=1, content=[Text(content="Third")]),
            ]
        )
        result = MultipleH1Rule().check(_ctx(doc))
        assert len(result) == 2
        assert all(v.rule_code == "STR002" for v in result)

    def test_heading_hierarchy_flags_skipped_level(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=3, content=[Text(content="Skipped")]),
            ]
        )
        result = HeadingHierarchyRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "STR003"
        assert "level 3 follows level 1" in result[0].message

    def test_heading_hierarchy_quiet_when_sequential(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[Text(content="Section")]),
                Heading(level=3, content=[Text(content="Sub")]),
            ]
        )
        assert HeadingHierarchyRule().check(_ctx(doc)) == []

    def test_empty_heading_flags_blank_content(self):
        doc = Document(children=[Heading(level=2, content=[])])
        result = EmptyHeadingRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "STR004"

    def test_orphan_heading_flags_trailing_heading(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="body")]),
                Heading(level=2, content=[Text(content="Trailing")]),
            ]
        )
        result = OrphanHeadingRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "STR005"

    def test_orphan_heading_silent_when_content_follows(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[Text(content="Section")]),
                Paragraph(content=[Text(content="body")]),
            ]
        )
        assert OrphanHeadingRule().check(_ctx(doc)) == []
