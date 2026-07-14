"""Tests that HTML content survives the containers it is wrapped in.

Two failures, both silent, both found on the same real document (an arXiv paper rendered
by LaTeXML, which wraps every table in ``<figure class="ltx_table">`` and scaled tables in
``<span class="ltx_transformed_inner">``). Between them, every table in that paper was lost
-- 13 tables, 150 rows, 661 cells parsed to nothing -- while the captions survived, so the
output still looked plausible.

1. ``<figure>`` was special-cased to images: the parser looked for a ``<figcaption>`` and an
   ``<img>`` and built its result from those two alone. Any other child -- a table, a
   ``<pre>``, a ``<video>`` -- was never visited.

2. A block element inside an *inline* element was dropped outright. An inline context has
   nowhere to put a block, so ``_process_children_to_inline`` skipped it with a debug log.
   That is unreachable in valid HTML, but real renderers emit inline layout wrappers around
   block content, and a ``<table>`` inside a ``<span>`` vanished, figure or no figure.

The two are independent: fixing the figure alone still lost every table in the paper.
"""

import pytest

from all2md import to_ast
from all2md.ast.nodes import BlockQuote, Image, Paragraph, Table, get_node_children
from all2md.options.html import HtmlOptions

TABLE = (
    "<table><tbody>"
    "<tr><th>H1</th><th>H2</th></tr>"
    "<tr><td>a</td><td>b</td></tr>"
    "<tr><td>c</td><td>d</td></tr>"
    "</tbody></table>"
)


def _walk(node):
    yield node
    for child in get_node_children(node):
        yield from _walk(child)


def _tables(html: str, **options):
    doc = to_ast(html.encode(), source_format="html", parser_options=HtmlOptions(**options) if options else None)
    return [n for n in _walk(doc) if isinstance(n, Table)]


def _census(html: str, **options) -> tuple[int, int, int]:
    """(tables, rows, cells) -- counting the header row, which Table keeps separately."""
    tables = _tables(html, **options)
    rows = sum(len(t.rows) + (1 if t.header else 0) for t in tables)
    cells = sum(sum(len(r.cells) for r in t.rows) + (len(t.header.cells) if t.header else 0) for t in tables)
    return len(tables), rows, cells


@pytest.mark.unit
@pytest.mark.html
class TestTableInFigure:
    """A <table> in a <figure> is the HTML5-recommended way to caption a table."""

    def test_bare_table(self):
        assert _census(TABLE) == (1, 3, 6)

    def test_table_in_div(self):
        assert _census(f"<div>{TABLE}</div>") == (1, 3, 6)

    def test_table_in_figure(self):
        """Used to return no Table node at all."""
        assert _census(f"<figure>{TABLE}</figure>") == (1, 3, 6)

    def test_table_in_figure_with_caption(self):
        """Used to return a BlockQuote holding only the caption -- the table vanished."""
        html = f"<figure>{TABLE}<figcaption>Table 1: results</figcaption></figure>"
        assert _census(html) == (1, 3, 6)

    def test_caption_survives_alongside_the_table(self):
        html = f"<figure>{TABLE}<figcaption>Table 1: results</figcaption></figure>"
        doc = to_ast(html.encode(), source_format="html")
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "Table 1: results" in text

    def test_non_image_non_table_content_survives(self):
        """A figure is a container: a <pre> listing must survive it too."""
        doc = to_ast(
            b"<figure><pre><code>print(1)</code></pre><figcaption>Listing 1</figcaption></figure>",
            source_format="html",
        )
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "print(1)" in text
        assert "Listing 1" in text

    def test_image_in_figure_still_works(self):
        """The case the old code did handle must not regress."""
        doc = to_ast(
            b"<figure><img src='x.png' alt='pic'><figcaption>Cap</figcaption></figure>",
            source_format="html",
        )
        images = [n for n in _walk(doc) if isinstance(n, Image)]
        assert len(images) == 1
        assert images[0].url == "x.png"

    def test_nested_figure_keeps_its_own_caption(self):
        """A recursive figcaption search would let the outer figure steal the inner caption."""
        html = "<figure><figure><img src='x.png'><figcaption>Inner</figcaption></figure><figcaption>Outer</figcaption></figure>"
        doc = to_ast(html.encode(), source_format="html")
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "Inner" in text
        assert "Outer" in text


@pytest.mark.unit
@pytest.mark.html
class TestBlockInsideInlineWrapper:
    """A block element inside an inline layout wrapper must not be discarded.

    LaTeXML scales oversized tables by wrapping them in
    ``<span class="ltx_transformed_inner" style="transform:scale(0.7)">``.
    """

    def test_table_in_span(self):
        assert _census(f"<span>{TABLE}</span>") == (1, 3, 6)

    def test_table_in_div_in_span(self):
        assert _census(f"<div><span>{TABLE}</span></div>") == (1, 3, 6)

    def test_arxiv_shape(self):
        """The exact nesting LaTeXML emits: figure > figcaption + div > span > table."""
        html = f"<figure><figcaption>Table 1</figcaption><div><span>{TABLE}</span></div></figure>"
        assert _census(html) == (1, 3, 6)

    def test_surrounding_inline_text_is_preserved(self):
        """Promoting the wrapper to a block must not lose the text around the block."""
        doc = to_ast(f"<div>before<span>{TABLE}</span>after</div>".encode(), source_format="html")
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "before" in text
        assert "after" in text

    def test_ordinary_inline_span_is_still_inline(self):
        """A span with no block content must not be promoted to a block container."""
        doc = to_ast(b"<p>hello <span>inline</span> world</p>", source_format="html")
        paragraphs = [n for n in _walk(doc) if isinstance(n, Paragraph)]
        assert len(paragraphs) == 1
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "inline" in text

    def test_block_dropped_from_a_true_inline_context_is_recorded(self):
        """<a> cannot hold a block, so the block is lost -- but it must not be lost silently."""
        doc = to_ast(b'<a href="#"><div>block inside a link</div></a>', source_format="html")
        events = doc.metadata["confidence"]["degraded_events"]
        assert any(e["kind"] == "block_in_inline_context_dropped" for e in events)


@pytest.mark.unit
@pytest.mark.html
class TestFiguresParsingModes:
    """All six documented modes.

    Four of them were never implemented: skip did not skip, paragraph returned a
    blockquote, and caption_only kept the image.
    """

    FIGURE = (
        b"<figure><img src='x.png'>"
        b"<table><tbody><tr><th>H</th></tr><tr><td>a</td></tr></tbody></table>"
        b"<figcaption>Cap</figcaption></figure>"
    )

    def _parse(self, mode):
        return to_ast(self.FIGURE, source_format="html", parser_options=HtmlOptions(figures_parsing=mode))

    def test_blockquote_wraps_content_and_caption(self):
        doc = self._parse("blockquote")
        quotes = [n for n in _walk(doc) if isinstance(n, BlockQuote)]
        assert len(quotes) == 1
        assert any(isinstance(n, Table) for n in _walk(quotes[0]))
        assert any(isinstance(n, Image) for n in _walk(quotes[0]))

    def test_paragraph_emits_blocks_without_a_blockquote(self):
        doc = self._parse("paragraph")
        assert not [n for n in _walk(doc) if isinstance(n, BlockQuote)]
        assert [n for n in _walk(doc) if isinstance(n, Table)]
        assert [n for n in _walk(doc) if isinstance(n, Image)]

    def test_caption_only_keeps_just_the_caption(self):
        doc = self._parse("caption_only")
        assert not [n for n in _walk(doc) if isinstance(n, Image)]
        assert not [n for n in _walk(doc) if isinstance(n, Table)]
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "Cap" in text

    def test_skip_drops_the_figure(self):
        doc = self._parse("skip")
        assert not list(get_node_children(doc))

    def test_html_preserves_the_source(self):
        doc = self._parse("html")
        html_blocks = [n for n in _walk(doc) if type(n).__name__ == "HTMLBlock"]
        assert len(html_blocks) == 1
        assert "<table" in html_blocks[0].content

    def test_image_with_caption_folds_caption_into_alt_text(self):
        doc = self._parse("image_with_caption")
        images = [n for n in _walk(doc) if isinstance(n, Image)]
        assert images[0].alt_text == "Cap"
        # ...and the table is still not dropped
        assert [n for n in _walk(doc) if isinstance(n, Table)]

    def test_image_with_caption_keeps_a_caption_it_cannot_absorb(self):
        """If the image already has alt text, the caption has nowhere to go -- emit it."""
        doc = to_ast(
            b"<figure><img src='x.png' alt='real alt'><figcaption>Cap</figcaption></figure>",
            source_format="html",
            parser_options=HtmlOptions(figures_parsing="image_with_caption"),
        )
        images = [n for n in _walk(doc) if isinstance(n, Image)]
        assert images[0].alt_text == "real alt"
        text = " ".join(n.content for n in _walk(doc) if hasattr(n, "content") and isinstance(n.content, str))
        assert "Cap" in text, "caption was dropped instead of being emitted as a paragraph"
