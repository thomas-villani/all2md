#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Material for MkDocs / pymdownx markdown parsing.

Covers the targeted niche-flavor support added for mkdocs sites:

- definition lists (previously parsed by a handler that was never wired up),
- the inline mark family (``==``, ``^^``, ``^``, ``~``),
- admonitions (``!!!``) and their collapsible (``???`` / ``???+``) variants,

including option gating and round-trip rendering through the markdown renderer.
"""

from all2md.ast import (
    BlockQuote,
    DefinitionList,
    Mark,
    Subscript,
    Superscript,
    Text,
    Underline,
    transforms,
)
from all2md.options.markdown import MarkdownParserOptions, MarkdownRendererOptions
from all2md.parsers.markdown import MarkdownToAstConverter
from all2md.renderers.markdown import MarkdownRenderer


def _parse(markdown: str, **opts: object) -> object:
    return MarkdownToAstConverter(options=MarkdownParserOptions(**opts)).parse(markdown)


def _render(doc: object, flavor: str = "markdown_plus", **opts: object) -> str:
    return MarkdownRenderer(MarkdownRendererOptions(flavor=flavor, **opts)).render_to_string(doc)


class TestDefinitionLists:
    """Definition list parsing (reconnected dead handler)."""

    def test_definition_list_parsed(self) -> None:
        doc = _parse("Term\n: First definition\n: Second definition\n")
        dls = transforms.extract_nodes(doc, DefinitionList)
        assert len(dls) == 1
        term, descriptions = dls[0].items[0]
        assert len(descriptions) == 2

    def test_definition_list_disabled(self) -> None:
        doc = _parse("Term\n: Definition\n", parse_definition_lists=False)
        assert transforms.extract_nodes(doc, DefinitionList) == []

    def test_definition_list_round_trip(self) -> None:
        doc = _parse("Term\n: Definition\n")
        out = _render(doc)
        assert "Term" in out
        assert ": Definition" in out


class TestInlineMarks:
    """Highlight / insert / superscript / subscript inline syntax."""

    def test_highlight_to_mark(self) -> None:
        doc = _parse("a ==highlight== b")
        marks = transforms.extract_nodes(doc, Mark)
        assert len(marks) == 1

    def test_insert_to_underline(self) -> None:
        doc = _parse("a ^^inserted^^ b")
        assert len(transforms.extract_nodes(doc, Underline)) == 1

    def test_superscript(self) -> None:
        doc = _parse("10^th^")
        assert len(transforms.extract_nodes(doc, Superscript)) == 1

    def test_subscript(self) -> None:
        doc = _parse("H~2~O")
        assert len(transforms.extract_nodes(doc, Subscript)) == 1

    def test_marks_disabled(self) -> None:
        doc = _parse("==x== ^^y^^ a^b^ c~d~", parse_marks=False)
        assert transforms.extract_nodes(doc, Mark) == []
        assert transforms.extract_nodes(doc, Underline) == []
        assert transforms.extract_nodes(doc, Superscript) == []
        assert transforms.extract_nodes(doc, Subscript) == []

    def test_highlight_round_trip_markdown_plus(self) -> None:
        out = _render(_parse("a ==hi== b"), flavor="markdown_plus")
        assert "==hi==" in out

    def test_highlight_roundtrips_on_gfm_by_default(self) -> None:
        # GFM doesn't support ==highlight==, but the default emits Markdown (not a
        # raw <mark> that self-escapes on the next roundtrip). See #95.
        out = _render(_parse("a ==hi== b"), flavor="gfm")
        assert "==hi==" in out
        assert "<mark>" not in out

    def test_highlight_degrades_to_html_on_gfm_when_explicit(self) -> None:
        out = _render(_parse("a ==hi== b"), flavor="gfm", unsupported_inline_mode="html")
        assert "<mark>hi</mark>" in out

    def test_superscript_subscript_native_on_markdown_plus(self) -> None:
        # markdown_plus natively supports ^sup^ / ~sub~; the flavor drives it,
        # like ==highlight==, so it emits Markdown regardless of the *_mode option.
        assert "2^10^" in _render(_parse("2^10^"), flavor="markdown_plus", superscript_mode="html")
        assert "H~2~O" in _render(_parse("H~2~O"), flavor="markdown_plus", subscript_mode="html")

    def test_superscript_falls_back_to_mode_on_gfm(self) -> None:
        # GFM has no ^sup^ syntax, so the superscript_mode fallback applies:
        # default "markdown" (roundtrips), explicit "html" for display.
        assert "2^10^" in _render(_parse("2^10^"), flavor="gfm")
        assert "2<sup>10</sup>" in _render(_parse("2^10^"), flavor="gfm", superscript_mode="html")


class TestAdmonitions:
    """Material for MkDocs admonitions and collapsible variants."""

    def test_basic_admonition(self) -> None:
        doc = _parse('!!! note "Heads up"\n    Body text.\n')
        quotes = transforms.extract_nodes(doc, BlockQuote)
        assert len(quotes) == 1
        meta = quotes[0].metadata
        assert meta["source_format"] == "mkdocs"
        assert meta["admonition_type"] == "note"
        assert meta["admonition_title"] == "Heads up"
        assert meta["collapsible"] is False

    def test_admonition_default_type_when_titleless(self) -> None:
        doc = _parse("!!! warning\n    Careful.\n")
        meta = transforms.extract_nodes(doc, BlockQuote)[0].metadata
        assert meta["admonition_type"] == "warning"
        assert "admonition_title" not in meta

    def test_collapsible_collapsed(self) -> None:
        doc = _parse('??? note "T"\n    Hidden.\n')
        meta = transforms.extract_nodes(doc, BlockQuote)[0].metadata
        assert meta["collapsible"] is True
        assert meta["collapsed"] is True

    def test_collapsible_expanded(self) -> None:
        doc = _parse("???+ tip\n    Shown.\n")
        meta = transforms.extract_nodes(doc, BlockQuote)[0].metadata
        assert meta["collapsible"] is True
        assert meta["collapsed"] is False

    def test_multi_paragraph_body_and_separation(self) -> None:
        doc = _parse("!!! note\n    Para one.\n\n    Para two.\n\nOutside.\n")
        quote = transforms.extract_nodes(doc, BlockQuote)[0]
        # Two paragraphs inside, and the trailing paragraph stays outside.
        assert len(quote.children) == 2
        # "Outside." must live in a top-level paragraph, not inside the quote.
        outside_texts = [t.content for t in transforms.extract_nodes(doc, Text) if "Outside." in t.content]
        assert outside_texts
        quote_texts = [t.content for t in transforms.extract_nodes(quote, Text)]
        assert not any("Outside." in t for t in quote_texts)

    def test_admonitions_disabled(self) -> None:
        doc = _parse("!!! note\n    Body.\n", parse_admonitions=False)
        assert transforms.extract_nodes(doc, BlockQuote) == []

    def test_native_round_trip_markdown_plus(self) -> None:
        src = '!!! note "Heads up"\n    Body text.\n'
        out = _render(_parse(src), flavor="markdown_plus")
        assert '!!! note "Heads up"' in out
        assert "    Body text." in out

    def test_collapsible_markers_round_trip(self) -> None:
        out = _render(_parse('??? note "T"\n    Hidden.\n'), flavor="markdown_plus")
        assert '??? note "T"' in out
        out_plus = _render(_parse("???+ tip\n    Shown.\n"), flavor="markdown_plus")
        assert "???+ tip" in out_plus

    def test_degrades_to_labelled_quote_on_gfm(self) -> None:
        out = _render(_parse('!!! note "Heads up"\n    Body text.\n'), flavor="gfm")
        assert "> **Heads up:** Body text." in out

    def test_round_trip_is_idempotent(self) -> None:
        src = '!!! note "Heads up"\n    Para one.\n\n    Para two.\n\nOutside.\n'
        doc = _parse(src)
        first = _render(doc, flavor="markdown_plus")
        second = _render(_parse(first), flavor="markdown_plus")
        assert first == second
