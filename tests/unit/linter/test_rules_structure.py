"""Happy-path coverage for STR001-STR008 plus auto-fix coverage for STR004."""

from __future__ import annotations

import pytest

from all2md.ast import BlockQuote, Document, Heading, Paragraph, Text
from all2md.linter.rule import LintContext
from all2md.linter.rules.structure import (
    EmptyDocumentRule,
    EmptyHeadingRule,
    ExcessiveNestingRule,
    HeadingHierarchyRule,
    MissingTitleRule,
    MultipleH1Rule,
    OrphanHeadingRule,
    ShortSectionRule,
)

from ._fix_helpers import assert_idempotent, lint_then_fix

pytestmark = pytest.mark.unit


def _ctx(doc: Document, options=None) -> LintContext:
    return LintContext(document=doc, config=options or {})


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

    def test_short_section_flags_thin_content(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[Text(content="Sparse")]),
                Paragraph(content=[Text(content="too few")]),
            ]
        )
        result = ShortSectionRule().check(_ctx(doc, {"min_words": 10}))
        # Both H1 and H2 sections are short; both should flag.
        assert len(result) == 2
        assert all(v.rule_code == "STR006" for v in result)

    def test_short_section_silent_for_long_section(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(
                    content=[
                        Text(
                            content=(
                                "This section has more than ten words by a " "comfortable margin to satisfy the rule."
                            )
                        )
                    ]
                ),
            ]
        )
        assert ShortSectionRule().check(_ctx(doc, {"min_words": 10})) == []

    def test_empty_document_flags_no_children(self):
        doc = Document(children=[])
        result = EmptyDocumentRule().check(_ctx(doc))
        assert len(result) == 1
        assert result[0].rule_code == "STR007"

    def test_empty_document_silent_with_content(self):
        doc = Document(children=[Paragraph(content=[Text(content="ok")])])
        assert EmptyDocumentRule().check(_ctx(doc)) == []

    def test_excessive_nesting_flags_deep_blockquotes(self):
        innermost = Paragraph(content=[Text(content="deep")])
        wrapped = innermost
        for _ in range(5):
            wrapped = BlockQuote(children=[wrapped])
        doc = Document(children=[wrapped])
        result = ExcessiveNestingRule().check(_ctx(doc, {"max_depth": 4}))
        assert result, "expected at least one STR008 violation"
        assert all(v.rule_code == "STR008" for v in result)


class TestStructureFixes:
    def test_str004_removes_empty_heading(self):
        kept = Heading(level=2, content=[Text(content="kept")])
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[]),  # empty — to be removed
                Paragraph(
                    content=[
                        Text(content=("Section content with at least ten words to " "avoid the short-section rule."))
                    ]
                ),
                kept,
                Paragraph(
                    content=[
                        Text(content=("Another long-enough paragraph that satisfies " "the short-section threshold."))
                    ]
                ),
            ]
        )
        lint_then_fix(doc, ["STR004"])
        # The empty heading should be gone, the kept heading remains.
        levels = [c.level for c in doc.children if isinstance(c, Heading)]
        assert levels == [1, 2]
        assert kept in doc.children

    def test_str004_idempotent(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[]),
            ]
        )
        assert_idempotent(doc, ["STR004"])
