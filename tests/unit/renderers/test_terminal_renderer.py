"""Tests for the terminal renderer.

The renderer walks the AST and builds rich renderables directly. The path it
replaces rendered Markdown text and let ``rich.markdown`` parse it again, which
showed footnotes, math, task lists, definition lists and admonitions as raw
source and ate the backslash in ``\\,`` inside math. Most tests read the plain
export (``color_system="none"``) at a fixed width.
"""

from __future__ import annotations

import re

import pytest
from document_strategies import (
    documents,
    documents_with_definition_lists,
    documents_with_footnotes,
    metacharacter_text,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md import from_ast, to_ast
from all2md.ast.nodes import (
    BlockQuote,
    Code,
    Comment,
    CommentInline,
    Document,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    Link,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.converter_registry import registry
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.terminal import HeadingPosition, TerminalRenderer, _iter_nodes

NL = chr(10)
BACKSLASH = chr(92)
ESC = chr(27)


def plain(doc: Document, **kwargs) -> str:
    """Render without escape codes, trailing spaces stripped from each line."""
    options = TerminalRendererOptions(**{"width": 60, "color_system": "none", **kwargs})
    output = TerminalRenderer(options).render_to_string(doc)
    return NL.join(line.rstrip() for line in output.split(NL))


def colored(doc: Document, **kwargs) -> str:
    options = TerminalRendererOptions(**{"width": 60, "color_system": "truecolor", **kwargs})
    return TerminalRenderer(options).render_to_string(doc)


def para(*inlines: Node) -> Paragraph:
    return Paragraph(content=list(inlines))


def markdown_doc(source: str) -> Document:
    return to_ast(source.encode(), source_format="markdown")


@pytest.mark.unit
class TestRegistration:
    def test_terminal_is_a_render_only_format(self):
        assert "terminal" in registry.list_formats()
        assert registry.get_renderer("terminal") is TerminalRenderer

    def test_from_ast(self):
        doc = Document(children=[para(Text(content="Hello"))])
        options = TerminalRendererOptions(color_system="none")
        assert from_ast(doc, "terminal", renderer_options=options) == "Hello"

    def test_width_must_be_positive(self):
        with pytest.raises(ValueError):
            TerminalRendererOptions(width=0)


@pytest.mark.unit
class TestWhatTheOldPathLost:
    """Each construct the rich.markdown path showed as raw source."""

    def test_display_math_keeps_its_backslashes(self):
        formula = BACKSLASH + "int_0^1 x" + BACKSLASH + ",dx"
        output = plain(Document(children=[MathBlock(content=formula)]))
        assert formula in output

    def test_inline_math_is_verbatim(self):
        output = plain(Document(children=[para(Text(content="So "), MathInline(content="E=mc^2"))]))
        assert output == "So E=mc^2"

    def test_task_list(self):
        output = plain(markdown_doc("- [x] done" + NL + "- [ ] todo" + NL))
        assert output.splitlines() == [" ☑ done", " ☐ todo"]

    def test_definition_list(self):
        output = plain(markdown_doc("Term" + NL + ": Definition here" + NL))
        assert output.splitlines() == ["Term", "    Definition here"]

    def test_github_alert_is_a_titled_panel(self):
        output = plain(markdown_doc("> [!WARNING]" + NL + "> Mind the gap." + NL))
        lines = output.splitlines()
        assert lines[0].startswith("╭─ Warning ─")
        assert "Mind the gap." in lines[1]
        assert "[!WARNING]" not in output

    def test_admonition_title_wins(self):
        quote = BlockQuote(
            children=[para(Text(content="Body"))],
            metadata={"admonition_type": "note", "admonition_title": "Heads up"},
        )
        assert plain(Document(children=[quote])).splitlines()[0].startswith("╭─ Heads up ─")

    def test_unknown_admonition_kind_still_renders(self):
        quote = BlockQuote(children=[para(Text(content="Body"))], metadata={"admonition_type": "custom"})
        assert plain(Document(children=[quote])).splitlines()[0].startswith("╭─ Custom ─")

    def test_footnotes_are_numbered_and_collected_at_the_end(self):
        doc = Document(
            children=[
                FootnoteDefinition(identifier="b", content=[para(Text(content="Second body."))]),
                para(
                    Text(content="One"),
                    FootnoteReference(identifier="b"),
                    Text(content=" two"),
                    FootnoteReference(identifier="a"),
                ),
                FootnoteDefinition(identifier="a", content=[para(Text(content="First body."))]),
                FootnoteDefinition(identifier="unused", content=[para(Text(content="Never cited."))]),
            ]
        )
        lines = plain(doc).splitlines()
        assert lines[0] == "One[1] two[2]"
        assert lines[-3:] == ["[1] Second body.", "[2] First body.", "[3] Never cited."]
        assert set(lines[-4]) == {"-"}

    def test_underline_is_styled(self):
        doc = markdown_doc("Some <u>under</u> text" + NL)
        assert ESC + "[4munder" in colored(doc)


@pytest.mark.unit
class TestInlines:
    def test_superscript_and_subscript_use_unicode(self):
        doc = Document(
            children=[
                para(
                    Text(content="H"),
                    Subscript(content=[Text(content="2")]),
                    Text(content="O x"),
                    Superscript(content=[Text(content="2")]),
                )
            ]
        )
        assert plain(doc) == "H₂O x²"

    def test_superscript_falls_back_to_a_caret(self):
        doc = Document(
            children=[
                para(
                    Text(content="x"),
                    Superscript(content=[Text(content="k")]),
                    Text(content=" y"),
                    Superscript(content=[Text(content="abc")]),
                )
            ]
        )
        assert plain(doc) == "x^k y^(abc)"

    def test_link_without_hyperlinks_shows_the_url(self):
        link = Link(url="https://example.com", content=[Text(content="site")])
        assert plain(Document(children=[para(link)]), hyperlinks=False) == "site (https://example.com)"

    def test_link_whose_text_is_the_url_is_not_repeated(self):
        link = Link(url="https://example.com", content=[Text(content="https://example.com")])
        assert plain(Document(children=[para(link)]), hyperlinks=False) == "https://example.com"

    def test_link_with_hyperlinks_is_osc8(self):
        link = Link(url="https://example.com", content=[Text(content="site")])
        output = colored(Document(children=[para(link)]))
        assert ESC + "]8;" in output
        assert "https://example.com" in output

    def test_image_placeholder(self):
        image = Image(url="cat.png", alt_text="A cat")
        assert plain(Document(children=[para(image)])) == "[image: A cat]"

    def test_inline_code(self):
        assert plain(Document(children=[para(Code(content="x = 1"))])) == "x = 1"

    def test_comments_visible_and_ignored(self):
        doc = Document(
            children=[
                Comment(content="Block note", metadata={"author": "Ann"}),
                para(Text(content="Body"), CommentInline(content="aside")),
            ]
        )
        assert plain(doc).splitlines() == ["Ann: Block note", "", "Body[aside]"]
        assert plain(doc, comment_mode="ignore") == "Body"


@pytest.mark.unit
class TestBlocks:
    def test_nested_list_indents(self):
        output = plain(markdown_doc("- outer" + NL + "  - inner" + NL + NL + "1. one" + NL + "2. two" + NL))
        assert output.splitlines() == [" • outer", "    • inner", "", " 1 one", " 2 two"]

    def test_ordered_list_start(self):
        output = plain(markdown_doc("7. seven" + NL + "8. eight" + NL))
        assert output.splitlines() == [" 7 seven", " 8 eight"]

    def test_block_quote_bar(self):
        output = plain(markdown_doc("> quoted" + NL))
        assert output == "▌ quoted"

    def test_merged_cell_content_sits_in_its_first_cell(self):
        table = Table(
            header=TableRow(
                cells=[TableCell(content=[Text(content=name)]) for name in ("A", "B", "C")], is_header=True
            ),
            rows=[
                TableRow(
                    cells=[TableCell(content=[Text(content="wide")], colspan=2), TableCell(content=[Text(content="c")])]
                ),
            ],
        )
        lines = [line for line in plain(Document(children=[table])).splitlines() if line.strip()]
        header, _, row = lines
        assert row.split() == ["wide", "c"]
        assert row.index("c") == header.index("C")

    def test_table_caption_and_alignment(self):
        doc = markdown_doc("| L | R |" + NL + "|:--|--:|" + NL + "| a | bbbbbb |" + NL)
        lines = [line for line in plain(doc).splitlines() if line.strip()]
        assert lines[-1].rstrip().endswith("bbbbbb")
        assert lines[0].rstrip().endswith("R")

    def test_width_is_respected(self):
        words = " ".join(["word"] * 40)
        output = plain(Document(children=[para(Text(content=words))]), width=30)
        assert max(len(line) for line in output.splitlines()) <= 30

    def test_heading_positions(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                para(Text(content="Body text")),
                Heading(level=2, content=[Text(content="Section")]),
            ]
        )
        renderer = TerminalRenderer(TerminalRendererOptions(width=40, color_system="none"))
        positions = renderer.heading_positions(doc)
        assert positions == [HeadingPosition(1, "Title", 0), HeadingPosition(2, "Section", 4)]
        lines = renderer.render_to_string(doc).splitlines()
        assert lines[4].strip() == "Section"


@pytest.mark.unit
class TestStyles:
    def test_rich_markdown_names_still_apply(self):
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output = colored(doc, styles={"h1": "bold red"})
        assert ESC + "[1;31m" in output

    def test_new_element_names_take_the_same_prefix(self):
        doc = Document(children=[para(MathInline(content="x"))])
        assert ESC + "[1;32mx" in colored(doc, styles={"math": "bold green"})

    def test_dotted_element_names_take_the_prefix_too(self):
        doc = markdown_doc("- item" + NL)
        assert ESC + "[1;31m" in colored(doc, styles={"item.bullet": "bold red"})

    def test_any_admonition_kind_can_be_styled(self):
        quote = BlockQuote(children=[para(Text(content="Body"))], metadata={"admonition_type": "custom"})
        output = colored(Document(children=[quote]), styles={"admonition.custom": "bold red"})
        assert ESC + "[1;31m" in output

    def test_an_invalid_style_is_skipped(self):
        doc = Document(children=[para(Text(content="ok"))])
        assert "ok" in colored(doc, styles={"h1": "not a style at all"})


# ---------------------------------------------------------------------------
# No-loss invariant
# ---------------------------------------------------------------------------


def _expected_fragments(doc: Document) -> list[str]:
    """Words of every Text, Code and math node, except where they are transformed by design.

    Superscript and subscript text may become Unicode digits, so those are left out.
    """
    transformed: set[int] = set()
    for node in _iter_nodes(doc):
        if isinstance(node, (Superscript, Subscript)):
            transformed.update(id(inner) for inner in _iter_nodes(node.content))
    fragments: list[str] = []
    for node in _iter_nodes(doc):
        if id(node) in transformed:
            continue
        if isinstance(node, (Text, Code)):
            fragments.extend(node.content.split())
        elif isinstance(node, (MathInline, MathBlock)):
            fragments.extend(node.content.split())
    return fragments


def _assert_no_loss(doc: Document) -> None:
    output = plain(doc, width=200)
    flat = re.sub(r"[ \t]+", " ", output)
    missing = [fragment for fragment in _expected_fragments(doc) if fragment not in flat]
    assert not missing, f"lost {missing!r} from:{NL}{output}"


@pytest.mark.unit
class TestNoLoss:
    """Every word of text, code and math reaches the terminal."""

    @settings(deadline=None, derandomize=True, max_examples=60, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=documents())
    def test_generated_documents(self, doc):
        _assert_no_loss(doc)

    @settings(deadline=None, derandomize=True, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=st.one_of(documents_with_footnotes(), documents_with_definition_lists()))
    def test_footnotes_and_definition_lists(self, doc):
        _assert_no_loss(doc)

    @settings(deadline=None, derandomize=True, max_examples=60)
    @given(formula=metacharacter_text())
    def test_math_is_never_escaped(self, formula):
        doc = Document(children=[para(MathInline(content=formula)), MathBlock(content=formula)])
        output = plain(doc, width=200)
        assert output.count(formula.strip()) >= 2
