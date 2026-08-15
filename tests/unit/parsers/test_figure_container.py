#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The Figure container holds blocks and a caption, and survives a round trip (#338).

``Image.caption`` covered the single-raster case, but a figure is not always one
image: multi-panel journal figures embed one raster per panel, LaTeXML wraps
every arXiv table in ``<figure>``, and a vector-drawn PDF figure has a caption
and no raster at all -- a caption with no ``Image`` to carry it. ``Figure`` is
the general container for all of those: block children plus an optional caption.

Markdown has no figure syntax, so the container borrows the #237 marker device,
extended to an extent: an opening marker comment, the child blocks rendered
normally, and a closing marker -- the caption marker (preceded by the visible
italic caption line) when there is a caption, the end marker otherwise. HTML
maps directly onto ``<figure>``/``<figcaption>`` in both directions.
"""

from __future__ import annotations

import pytest

from all2md import to_ast
from all2md.ast.extraction import collect_figures
from all2md.ast.nodes import (
    BlockQuote,
    Document,
    Figure,
    Image,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast.serialization import ast_to_dict, dict_to_ast
from all2md.ast.visitors import ValidationVisitor
from all2md.constants import (
    MARKDOWN_FIGURE_CAPTION_MARKER,
    MARKDOWN_FIGURE_END_MARKER,
    MARKDOWN_FIGURE_MARKER,
)
from all2md.options import MarkdownRendererOptions
from all2md.options.html import HtmlOptions
from all2md.renderers.html import HtmlRenderer
from all2md.renderers.markdown import MarkdownRenderer

pytestmark = [pytest.mark.unit]

CAPTION = "Figure 1. Two panels and a table."


def _paragraph(text: str) -> Paragraph:
    return Paragraph(content=[Text(content=text)])


def _table() -> Table:
    return Table(
        header=TableRow(is_header=True, cells=[TableCell(content=[Text(content="h")])]),
        rows=[TableRow(cells=[TableCell(content=[Text(content="v")])])],
    )


def _figure(caption: str | None = CAPTION) -> Figure:
    return Figure(
        children=[Paragraph(content=[Image(url="fig1.png", alt_text="panel A")]), _table()],
        caption=caption,
    )


def _render(document: Document, **options: object) -> str:
    return MarkdownRenderer(MarkdownRendererOptions(**options)).render_to_string(document)  # type: ignore[arg-type]


def _figures(document: Document) -> list[Figure]:
    return [node for node in document.children if isinstance(node, Figure)]


class TestMarkdownRoundTrip:
    def test_container_and_caption_survive(self) -> None:
        parsed = to_ast(_render(Document(children=[_figure()])).encode(), source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Figure"]
        figure = _figures(parsed)[0]
        assert figure.caption == CAPTION
        assert [type(child).__name__ for child in figure.children] == ["Paragraph", "Table"]

    def test_uncaptioned_figure_survives(self) -> None:
        rendered = _render(Document(children=[_figure(caption=None)]))
        assert MARKDOWN_FIGURE_END_MARKER in rendered
        assert MARKDOWN_FIGURE_CAPTION_MARKER not in rendered

        figure = _figures(to_ast(rendered.encode(), source_format="markdown"))[0]
        assert figure.caption is None
        assert len(figure.children) == 2

    def test_empty_figure_keeps_its_caption(self) -> None:
        """The vector-drawn case must not collapse to nothing.

        No extractable content, and the caption is the only record the figure
        existed.
        """
        vector = Document(children=[Figure(children=[], caption="Figure 2. Vector only.")])
        parsed = to_ast(_render(vector).encode(), source_format="markdown")

        figure = _figures(parsed)[0]
        assert figure.caption == "Figure 2. Vector only."
        assert figure.children == []

    def test_rendering_is_idempotent(self) -> None:
        document = Document(children=[_paragraph("before"), _figure(), _paragraph("after")])
        once = _render(document)
        twice = _render(to_ast(once.encode(), source_format="markdown"))
        assert once == twice

    def test_the_caption_is_still_visible_to_a_reader(self) -> None:
        assert f"*{CAPTION}*" in _render(Document(children=[_figure()]))

    def test_editing_the_visible_line_edits_the_caption(self) -> None:
        """The marker deliberately carries no copy of the text."""
        rendered = _render(Document(children=[_figure()])).replace(CAPTION, "Figure 1. Revised.")
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert _figures(parsed)[0].caption == "Figure 1. Revised."

    def test_an_unterminated_marker_folds_nothing(self) -> None:
        """Conservative like the caption triples.

        An opening marker with no closing marker is more likely someone's real
        comment than our output.
        """
        text = f"<!-- {MARKDOWN_FIGURE_MARKER} -->\n\nJust a paragraph.\n"
        parsed = to_ast(text.encode(), source_format="markdown")
        assert _figures(parsed) == []

    def test_nested_figures_fold_inside_out(self) -> None:
        inner = Figure(children=[_paragraph("inner content")], caption="Inner caption")
        outer = Figure(children=[_paragraph("outer content"), inner], caption="Outer caption")
        parsed = to_ast(_render(Document(children=[outer])).encode(), source_format="markdown")

        figure = _figures(parsed)[0]
        assert figure.caption == "Outer caption"
        nested = [child for child in figure.children if isinstance(child, Figure)]
        assert len(nested) == 1
        assert nested[0].caption == "Inner caption"

    def test_figure_inside_a_blockquote_folds(self) -> None:
        document = Document(children=[BlockQuote(children=[_figure()])])
        parsed = to_ast(_render(document).encode(), source_format="markdown")

        quote = parsed.children[0]
        assert isinstance(quote, BlockQuote)
        inner = [child for child in quote.children if isinstance(child, Figure)]
        assert len(inner) == 1
        assert inner[0].caption == CAPTION

    def test_comment_mode_ignore_degrades_to_visible_content(self) -> None:
        """No markers means no round trip, but nothing invisible is lost.

        The children and the caption line are all still on the page.
        """
        rendered = _render(Document(children=[_figure()]), comment_mode="ignore")
        assert MARKDOWN_FIGURE_MARKER not in rendered
        assert f"*{CAPTION}*" in rendered
        assert "![panel A](fig1.png)" in rendered


class TestHtml:
    def test_renderer_emits_figure_and_figcaption(self) -> None:
        html = HtmlRenderer().render_to_string(Document(children=[_figure()]))
        assert "<figure>" in html
        assert f"<figcaption>{CAPTION}</figcaption>" in html
        assert "</figure>" in html

    def test_figure_mode_reads_the_container_back(self) -> None:
        html = (
            b"<figure><img src='x.png' alt='a'><table><tr><th>h</th></tr></table>"
            b"<figcaption>Cap</figcaption></figure>"
        )
        parsed = to_ast(html, source_format="html", parser_options=HtmlOptions(figures_parsing="figure"))

        figure = _figures(parsed)[0]
        assert figure.caption == "Cap"
        assert any(isinstance(child, Table) for child in figure.children)

    def test_figure_mode_keeps_a_captionless_empty_figure_out(self) -> None:
        parsed = to_ast(
            b"<figure></figure>", source_format="html", parser_options=HtmlOptions(figures_parsing="figure")
        )
        assert _figures(parsed) == []

    def test_default_mode_is_unchanged(self) -> None:
        """Flipping the default is a separate, deliberate change."""
        parsed = to_ast(b"<figure><p>x</p><figcaption>Cap</figcaption></figure>", source_format="html")
        assert _figures(parsed) == []
        assert isinstance(parsed.children[0], BlockQuote)


class TestNodeContract:
    def test_serialization_round_trips(self) -> None:
        figure = _figure()
        assert dict_to_ast(ast_to_dict(figure)) == figure

    def test_validation_accepts_block_children(self) -> None:
        Document(children=[_figure()]).accept(ValidationVisitor(strict=True))

    def test_validation_rejects_inline_children(self) -> None:
        bad = Document(children=[Figure(children=[Text(content="bare inline")])])
        with pytest.raises(ValueError, match="Figure can only contain block nodes"):
            bad.accept(ValidationVisitor(strict=True))

    def test_collect_figures_counts_containers_not_panels(self) -> None:
        """A Figure with three panel images is one figure.

        A bare image outside any container is still one of its own.
        """
        panels = Figure(
            children=[Paragraph(content=[Image(url=f"p{i}.png", alt_text=str(i))]) for i in range(3)],
            caption=CAPTION,
        )
        loose = Paragraph(content=[Image(url="loose.png", alt_text="loose")])
        collected = collect_figures(Document(children=[panels, loose]))

        assert [type(node).__name__ for node in collected] == ["Figure", "Image"]
