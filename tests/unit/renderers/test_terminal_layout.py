"""Tests for the terminal renderer's layout map.

``TerminalRenderer.layout`` lays a document out once and reports where every
heading, link and footnote definition landed, so a viewer can draw an outline,
jump between links and follow footnotes without laying the document out again.
Headings and links are found by a meta tag on their rich style, which must not
change a byte of the printed output.
"""

from __future__ import annotations

import re

import pytest
from document_strategies import documents, documents_with_footnotes
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rich.cells import cell_len

from all2md import to_ast
from all2md.ast.nodes import (
    BlockQuote,
    Document,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.terminal import HeadingPosition, LinkPosition, TerminalRenderer

NL = chr(10)
ESC = chr(27)


def renderer(**kwargs) -> TerminalRenderer:
    return TerminalRenderer(TerminalRendererOptions(**{"width": 40, "color_system": "none", **kwargs}))


def para(*inlines: Node) -> Paragraph:
    return Paragraph(content=list(inlines))


def link(label: str, url: str) -> Link:
    return Link(url=url, content=[Text(content=label)])


def cells(line: str, start: int, end: int) -> str:
    """The characters of ``line`` occupying terminal cells ``start`` to ``end``."""
    out = []
    column = 0
    for char in line:
        width = cell_len(char)
        if start <= column and column + width <= end:
            out.append(char)
        column += width
    return "".join(out)


def shown(layout, position: LinkPosition) -> str:
    return cells(layout.text.split(NL)[position.line], position.start, position.end)


@pytest.mark.unit
class TestText:
    @pytest.mark.parametrize("color_system", ["none", "truecolor"])
    @pytest.mark.parametrize("hyperlinks", [False, True])
    def test_text_is_render_to_string(self, color_system, hyperlinks):
        doc = to_ast(
            "# Title\n\nSee [the docs](https://example.com) and a note[^1].\n\n"
            "> ## Quoted\n> [inner](#title)\n\n[^1]: The note.\n".encode(),
            source_format="markdown",
        )
        r = renderer(color_system=color_system, hyperlinks=hyperlinks)
        layout = r.layout(doc)
        again = r.render_to_string(doc)
        if hyperlinks and color_system != "none":
            # OSC 8 link ids are random on every render; compare with them blanked.
            blank = re.compile("id=[0-9-]+;")
            layout_text, again = blank.sub("", layout.text), blank.sub("", again)
        else:
            layout_text = layout.text
        assert layout_text == again

    @settings(deadline=None, derandomize=True, max_examples=40, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=st.one_of(documents(), documents_with_footnotes()), width=st.integers(min_value=20, max_value=100))
    def test_line_count_and_width(self, doc, width):
        layout = renderer(width=width).layout(doc)
        assert layout.width == width
        assert layout.line_count == len(layout.text.split(NL)) if layout.text else layout.line_count == 0

    def test_tags_do_not_split_styled_runs(self):
        """A centered heading prints as one styled run, padding included, as it did untagged."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output = renderer(color_system="truecolor").layout(doc).text
        assert output.count(ESC + "[0m") == 1


@pytest.mark.unit
class TestHeadings:
    def test_nested_headings_are_found(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Top")]),
                BlockQuote(children=[Heading(level=2, content=[Text(content="Quoted")])]),
                List(ordered=False, items=[ListItem(children=[Heading(level=3, content=[Text(content="Listed")])])]),
            ]
        )
        layout = renderer().layout(doc)
        lines = layout.text.split(NL)
        assert [(h.level, h.text) for h in layout.headings] == [(1, "Top"), (2, "Quoted"), (3, "Listed")]
        for heading in layout.headings:
            assert heading.text in lines[heading.line]

    def test_wrapped_heading_starts_on_its_first_line(self):
        words = "word " * 20
        doc = Document(children=[para(Text(content="intro")), Heading(level=2, content=[Text(content=words)])])
        layout = renderer(width=30).layout(doc)
        assert layout.headings == (HeadingPosition(2, words, 2),)

    def test_heading_without_text_has_no_position(self):
        doc = Document(children=[Heading(level=2, content=[]), Heading(level=2, content=[Text(content="Real")])])
        assert [h.text for h in renderer().layout(doc).headings] == ["Real"]

    def test_heading_that_is_a_link_is_both(self):
        doc = Document(children=[Heading(level=2, content=[link("Home", "https://example.com")])])
        layout = renderer().layout(doc)
        assert [h.text for h in layout.headings] == ["Home"]
        assert [shown(layout, p) for p in layout.links] == ["Home"]

    def test_heading_positions_matches_layout(self):
        doc = to_ast("# A\n\ntext\n\n> ## B\n".encode(), source_format="markdown")
        r = renderer()
        assert r.heading_positions(doc) == list(r.layout(doc).headings)


@pytest.mark.unit
class TestLinks:
    def test_position_covers_the_link_text(self):
        doc = Document(
            children=[para(Text(content="See "), link("the docs", "https://example.com"), Text(content="."))]
        )
        layout = renderer().layout(doc)
        assert layout.links == (LinkPosition(0, 4, 12, "https://example.com", 0),)

    def test_shown_url_is_not_part_of_the_link(self):
        doc = Document(children=[para(link("docs", "https://example.com"))])
        layout = renderer(hyperlinks=False).layout(doc)
        assert "(https://example.com)" in layout.text
        assert [shown(layout, p) for p in layout.links] == ["docs"]

    def test_styled_parts_make_one_position(self):
        content = [Text(content="plain "), Strong(content=[Text(content="bold")]), Text(content=" tail")]
        doc = Document(children=[para(Link(url="https://example.com", content=content))])
        layout = renderer().layout(doc)
        assert [shown(layout, p) for p in layout.links] == ["plain bold tail"]

    def test_wrapped_link_has_a_position_per_line(self):
        label = "a rather long link label that wraps"
        doc = Document(children=[para(Text(content="Start "), link(label, "#target"))])
        layout = renderer(width=20).layout(doc)
        assert len(layout.links) > 1
        assert {p.index for p in layout.links} == {0}
        assert [p.line for p in layout.links] == sorted({p.line for p in layout.links})
        assert " ".join(shown(layout, p).strip() for p in layout.links) == label

    def test_links_are_numbered_in_document_order(self):
        doc = Document(children=[para(link("one", "#a"), Text(content=" and "), link("two", "#b"))])
        layout = renderer().layout(doc)
        assert [(p.index, p.target) for p in layout.links] == [(0, "#a"), (1, "#b")]

    def test_columns_count_the_prefixes_of_quotes_lists_and_tables(self):
        doc = Document(
            children=[
                BlockQuote(children=[para(link("quoted", "#q"))]),
                List(ordered=False, items=[ListItem(children=[para(link("listed", "#l"))])]),
                Table(
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="x")]), TableCell(content=[link("cell", "#c")])]
                        )
                    ]
                ),
            ]
        )
        layout = renderer().layout(doc)
        assert [shown(layout, p) for p in layout.links] == ["quoted", "listed", "cell"]
        assert all(p.start > 0 for p in layout.links)

    def test_columns_are_terminal_cells(self):
        doc = Document(children=[para(Text(content="漢字 "), link("リンク", "#wide"))])
        layout = renderer().layout(doc)
        (position,) = layout.links
        assert (position.start, position.end) == (5, 11)
        assert shown(layout, position) == "リンク"

    def test_link_without_a_target_is_not_listed(self):
        doc = Document(children=[para(link("nowhere", ""))])
        assert renderer().layout(doc).links == ()

    def test_target_has_no_control_characters(self):
        doc = Document(children=[para(link("bad", "https://example.com/" + ESC + "]0;x"))])
        (position,) = renderer().layout(doc).links
        assert ESC not in position.target


@pytest.mark.unit
class TestFootnotes:
    def test_reference_is_a_link_to_its_definition(self):
        doc = Document(
            children=[
                para(Text(content="Claim"), FootnoteReference(identifier="src")),
                FootnoteDefinition(identifier="src", content=[para(Text(content="The source."))]),
            ]
        )
        layout = renderer().layout(doc)
        lines = layout.text.split(NL)
        (reference,) = layout.links
        assert reference.footnote and reference.target == "src"
        assert shown(layout, reference) == "[1]"
        assert lines[layout.footnotes["src"]].startswith("[1] The source.")

    def test_reference_without_a_definition_is_not_a_link(self):
        doc = Document(children=[para(Text(content="Claim"), FootnoteReference(identifier="missing"))])
        layout = renderer().layout(doc)
        assert layout.links == ()
        assert layout.footnotes == {}

    @settings(deadline=None, derandomize=True, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=documents_with_footnotes())
    def test_every_footnote_link_resolves(self, doc):
        layout = renderer(width=60).layout(doc)
        for position in layout.links:
            if position.footnote:
                assert position.target in layout.footnotes
