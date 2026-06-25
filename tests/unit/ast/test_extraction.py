#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for typed --extract selectors (sections, tables, figures, word limits)."""

import pytest

from all2md.ast.extraction import (
    build_extracted_document,
    collect_figures,
    collect_tables,
    parse_extract_selector,
)
from all2md.ast.nodes import (
    Document,
    Heading,
    Image,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.ast.utils import extract_text


def _cell(text: str) -> TableCell:
    return TableCell(content=[Text(content=text)])


def _table(tag: str) -> Table:
    return Table(
        header=TableRow(cells=[_cell(f"{tag}-h1"), _cell(f"{tag}-h2")]),
        rows=[TableRow(cells=[_cell(f"{tag}-a"), _cell(f"{tag}-b")])],
    )


@pytest.fixture
def doc():
    """A document with two sections, two tables, and one figure."""
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="one two three four five six seven eight")]),
            _table("T1"),
            Heading(level=1, content=[Text(content="Methods")]),
            Paragraph(content=[Text(content="alpha beta gamma")]),
            Paragraph(content=[Image(url="fig1.png", alt_text="Figure one")]),
            _table("T2"),
        ]
    )


@pytest.mark.unit
class TestParseExtractSelector:
    def test_section_name(self):
        sel = parse_extract_selector("Introduction")
        assert (sel.kind, sel.spec, sel.word_limit) == ("section", "Introduction", None)

    def test_section_index(self):
        sel = parse_extract_selector("#:1-3")
        assert sel.kind == "section"
        assert sel.spec == "#:1-3"

    def test_word_limit_suffix(self):
        sel = parse_extract_selector("Introduction::500")
        assert sel.kind == "section"
        assert sel.spec == "Introduction"
        assert sel.word_limit == 500

    def test_table_selector(self):
        sel = parse_extract_selector("table:2")
        assert (sel.kind, sel.spec) == ("table", "2")

    def test_figure_and_image_alias(self):
        assert parse_extract_selector("figure:1").kind == "figure"
        assert parse_extract_selector("image:1").kind == "figure"

    def test_table_with_word_limit(self):
        sel = parse_extract_selector("table:1::20")
        assert (sel.kind, sel.spec, sel.word_limit) == ("table", "1", 20)

    def test_invalid_word_limit_raises(self):
        with pytest.raises(ValueError, match="word limit"):
            parse_extract_selector("Intro::0")
        with pytest.raises(ValueError, match="word limit"):
            parse_extract_selector("Intro::abc")

    def test_empty_selector_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            parse_extract_selector("::500")


@pytest.mark.unit
class TestCollectors:
    def test_collect_tables_in_order(self, doc):
        tables = collect_tables(doc)
        assert len(tables) == 2
        assert extract_text(tables[0]).startswith("T1")
        assert extract_text(tables[1]).startswith("T2")

    def test_collect_figures(self, doc):
        figures = collect_figures(doc)
        assert len(figures) == 1
        assert figures[0].url == "fig1.png"


@pytest.mark.unit
class TestBuildExtractedDocument:
    def test_single_section(self, doc):
        out = build_extracted_document(doc, ["Introduction"])
        assert isinstance(out.children[0], Heading)
        assert extract_text(out.children[0]) == "Introduction"
        # Introduction's table is part of the section content.
        assert any(isinstance(n, Table) for n in out.children)
        # Methods must not appear.
        assert "Methods" not in extract_text(out.children)

    def test_table_selector(self, doc):
        out = build_extracted_document(doc, ["table:2"])
        tables = [n for n in out.children if isinstance(n, Table)]
        assert len(tables) == 1
        assert extract_text(tables[0]).startswith("T2")

    def test_figure_wrapped_in_paragraph(self, doc):
        out = build_extracted_document(doc, ["figure:1"])
        assert len(out.children) == 1
        assert isinstance(out.children[0], Paragraph)
        assert isinstance(out.children[0].content[0], Image)

    def test_multiple_specs_in_spec_order_separated(self, doc):
        # table:2 first, then figure:1 -- order follows the spec list, not the doc.
        out = build_extracted_document(doc, ["table:2", "figure:1"])
        kinds = [type(n).__name__ for n in out.children]
        assert kinds == ["Table", "ThematicBreak", "Paragraph"]
        assert isinstance(out.children[1], ThematicBreak)

    def test_word_limit_truncates_at_node_boundary(self, doc):
        # Heading (1 word) + first paragraph (8 words) = 9; the table that follows
        # should be dropped once the 5-word budget is exceeded.
        out = build_extracted_document(doc, ["Introduction::5"])
        assert isinstance(out.children[0], Heading)
        assert isinstance(out.children[1], Paragraph)
        assert not any(isinstance(n, Table) for n in out.children)

    def test_word_limit_keeps_at_least_first_node(self, doc):
        out = build_extracted_document(doc, ["Introduction::1"])
        assert len(out.children) >= 1
        assert isinstance(out.children[0], Heading)

    def test_no_match_raises(self, doc):
        with pytest.raises(ValueError):
            build_extracted_document(doc, ["table:99"])

    def test_no_tables_raises(self):
        bare = Document(children=[Heading(level=1, content=[Text(content="x")])])
        with pytest.raises(ValueError, match="no table"):
            build_extracted_document(bare, ["table:1"])
