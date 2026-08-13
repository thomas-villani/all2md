#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Figures carry their caption on the node, and it survives a round trip (#338).

``Image`` had ``url``, ``alt_text``, ``title``, ``width`` and ``height`` -- and no
caption. Two parsers had independently worked around that by writing the caption
into ``alt_text``, which conflates two different things: alt text stands in for an
image nobody can see, a caption is text printed beside one everybody can. A figure
that had both had to choose.

``Image.caption`` ends the choice. On the way out, formats with a native spelling
use it (AsciiDoc's block title, reST's ``figure`` directive, HTML's ``<figure>``);
Markdown, which has none, borrows the two-part device #237 built for table
captions -- a visible italic line plus a marker comment naming it a caption. The
difference from tables is placement, because the typographic convention differs: a
table's caption is set above it, a figure's below.
"""

from __future__ import annotations

import pytest

from all2md import to_ast
from all2md.ast.nodes import Document, Image, Paragraph, Text
from all2md.ast.serialization import ast_to_dict, dict_to_ast
from all2md.constants import MARKDOWN_IMAGE_CAPTION_MARKER
from all2md.options import MarkdownRendererOptions
from all2md.renderers.markdown import MarkdownRenderer

pytestmark = [pytest.mark.unit, pytest.mark.image]

CAPTION = "Figure 1. Growth over time."


def _figure(caption: str | None = CAPTION, alt: str = "a plot") -> Paragraph:
    return Paragraph(content=[Image(url="fig1.png", alt_text=alt, caption=caption)])


def _render(document: Document, **options: object) -> str:
    return MarkdownRenderer(MarkdownRendererOptions(**options)).render_to_string(document)  # type: ignore[arg-type]


def _images(document: Document) -> list[Image]:
    return [
        node
        for child in document.children
        if isinstance(child, Paragraph)
        for node in child.content
        if isinstance(node, Image)
    ]


class TestMarkdownRoundTrip:
    def test_caption_survives_and_adds_no_node(self) -> None:
        parsed = to_ast(_render(Document(children=[_figure()])).encode(), source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Paragraph"]
        assert _images(parsed)[0].caption == CAPTION

    def test_the_caption_does_not_displace_the_alt_text(self) -> None:
        """The whole point of the field: a figure can have both, and keeps both."""
        parsed = to_ast(_render(Document(children=[_figure()])).encode(), source_format="markdown")

        image = _images(parsed)[0]
        assert image.caption == CAPTION
        assert image.alt_text == "a plot"

    def test_the_caption_is_still_visible_to_a_reader(self) -> None:
        assert f"*{CAPTION}*" in _render(Document(children=[_figure()]))

    def test_rendering_is_idempotent(self) -> None:
        once = _render(Document(children=[_figure()]))
        twice = _render(to_ast(once.encode(), source_format="markdown"))
        assert once == twice

    def test_editing_the_visible_line_edits_the_caption(self) -> None:
        """The marker deliberately carries no copy of the text."""
        rendered = _render(Document(children=[_figure()])).replace(CAPTION, "Figure 1. Revised.")
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert _images(parsed)[0].caption == "Figure 1. Revised."

    def test_an_uncaptioned_image_gains_neither_marker_nor_paragraph(self) -> None:
        rendered = _render(Document(children=[_figure(caption=None)]))

        assert MARKDOWN_IMAGE_CAPTION_MARKER not in rendered
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph"]
        assert _images(parsed)[0].caption is None

    def test_a_following_block_is_not_absorbed(self) -> None:
        document = Document(children=[_figure(), Paragraph(content=[Text(content="Body prose.")])])
        parsed = to_ast(_render(document).encode(), source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph"]
        assert _images(parsed)[0].caption == CAPTION


class TestItIsConservative:
    """Each of these is more likely someone's real content than a caption to rewrite."""

    def test_an_italic_paragraph_after_an_image_is_left_alone(self) -> None:
        """The control that matters: without the marker, nothing is swallowed."""
        parsed = to_ast(b"![a](f.png)\n\n*Just some emphasis.*\n", source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph"]
        assert _images(parsed)[0].caption is None

    def test_a_marker_with_no_image_before_it_is_left_alone(self) -> None:
        source = f"Some prose.\n\n*Cap*\n\n<!-- {MARKDOWN_IMAGE_CAPTION_MARKER} -->\n".encode()
        parsed = to_ast(source, source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph", "Comment"]

    def test_an_image_sharing_its_paragraph_is_not_captioned(self) -> None:
        """A caption has no unambiguous owner when the paragraph holds other content."""
        source = f"see ![a](f.png)\n\n*Cap*\n\n<!-- {MARKDOWN_IMAGE_CAPTION_MARKER} -->\n".encode()
        parsed = to_ast(source, source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph", "Comment"]
        assert _images(parsed)[0].caption is None

    def test_a_mixed_paragraph_is_not_treated_as_a_caption(self) -> None:
        source = f"![a](f.png)\n\nLead in *Cap*\n\n<!-- {MARKDOWN_IMAGE_CAPTION_MARKER} -->\n".encode()
        parsed = to_ast(source, source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph", "Comment"]


class TestCommentMode:
    def test_ignore_suppresses_the_marker_and_says_so_by_losing_the_caption(self) -> None:
        """``comment_mode="ignore"`` asks for no comments; the caption degrades to prose."""
        rendered = _render(Document(children=[_figure()]), comment_mode="ignore")

        assert MARKDOWN_IMAGE_CAPTION_MARKER not in rendered
        assert f"*{CAPTION}*" in rendered

        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Paragraph"]
        assert _images(parsed)[0].caption is None

    @pytest.mark.parametrize("mode", ["html", "blockquote"])
    def test_every_other_comment_mode_keeps_the_round_trip(self, mode: str) -> None:
        parsed = to_ast(_render(Document(children=[_figure()]), comment_mode=mode).encode(), source_format="markdown")
        assert _images(parsed)[0].caption == CAPTION


class TestOtherFormats:
    """Formats with a native caption spelling should use it rather than drop it."""

    def test_asciidoc_round_trips_through_the_block_title(self) -> None:
        from all2md.parsers.asciidoc import AsciiDocParser
        from all2md.renderers.asciidoc import AsciiDocRenderer

        document = Document(children=[_figure()])
        rendered = AsciiDocRenderer().render_to_string(document)

        assert rendered.startswith(f".{CAPTION}\n")
        assert AsciiDocParser().parse(rendered).children == document.children

    def test_a_period_leading_paragraph_is_still_a_paragraph(self) -> None:
        """The AsciiDoc control: a block title is only a block title above a block."""
        from all2md.parsers.asciidoc import AsciiDocParser

        parsed = AsciiDocParser().parse(".Just a sentence. And another.\n")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph"]
        assert not _images(parsed)

    def test_rst_promotes_the_image_directive_to_a_figure(self) -> None:
        from all2md.renderers.rst import RestructuredTextRenderer

        rendered = RestructuredTextRenderer().render_to_string(Document(children=[_figure()]))

        assert ".. figure:: fig1.png" in rendered
        assert f"\n\n   {CAPTION}" in rendered, "the caption must be a blank line below the options, and indented"

    def test_rst_stays_an_image_directive_without_a_caption(self) -> None:
        from all2md.renderers.rst import RestructuredTextRenderer

        rendered = RestructuredTextRenderer().render_to_string(Document(children=[_figure(caption=None)]))
        assert ".. image:: fig1.png" in rendered
        assert "figure" not in rendered

    def test_html_emits_a_figure_and_reads_it_back(self) -> None:
        from all2md.options.html import HtmlOptions
        from all2md.parsers.html import HtmlToAstConverter
        from all2md.renderers.html import HtmlRenderer

        rendered = HtmlRenderer().render_to_string(Document(children=[_figure()]))
        assert "<figure" in rendered and f"<figcaption>{CAPTION}</figcaption>" in rendered

        parsed = HtmlToAstConverter(HtmlOptions(figures_parsing="image_with_caption")).parse(rendered)
        image = _images(parsed)[0]
        assert image.caption == CAPTION
        assert image.alt_text == "a plot"

    def test_an_uncaptioned_image_is_not_wrapped_in_a_figure(self) -> None:
        from all2md.renderers.html import HtmlRenderer

        rendered = HtmlRenderer().render_to_string(Document(children=[_figure(caption=None)]))
        assert "<figure" not in rendered
        assert "<img" in rendered


class TestSerialization:
    def test_the_caption_survives_a_dict_round_trip(self) -> None:
        """A field the serializer does not know about is a field that silently vanishes."""
        restored = dict_to_ast(ast_to_dict(Document(children=[_figure()])))
        assert _images(restored)[0].caption == CAPTION

    def test_an_absent_caption_is_not_serialized(self) -> None:
        payload = ast_to_dict(Document(children=[_figure(caption=None)]))
        assert "caption" not in payload["children"][0]["content"][0]
