#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Table captions survive a Markdown round trip (#237).

Markdown has no caption syntax, so there is no lossless single answer. Emitting
only an italic paragraph is what we did before: readable, but on the way back in
it is indistinguishable from prose, so the round trip lost the caption *and*
gained a Paragraph node - a structural change, not a missing attribute. Emitting
only an HTML comment would round-trip cleanly and hide the caption from anyone
reading the file.

So the renderer emits both, and the parser folds the triple back into
``Table.caption``. The marker carries no text: the visible line is the caption,
which means editing the file edits the caption rather than desynchronising it
from a hidden copy.
"""

from __future__ import annotations

import pytest

from all2md import to_ast
from all2md.ast.nodes import Document, Paragraph, Table, TableCell, TableRow, Text
from all2md.constants import MARKDOWN_TABLE_CAPTION_MARKER
from all2md.options import MarkdownRendererOptions
from all2md.renderers.markdown import MarkdownRenderer

pytestmark = [pytest.mark.unit, pytest.mark.table]


def _cell(text: str) -> TableCell:
    return TableCell(content=[Text(content=text)])


def _table(caption: str | None = "Table 1. Results") -> Table:
    return Table(
        header=TableRow(
            is_header=True,
            cells=[_cell("A"), _cell("B")],
        ),
        rows=[TableRow(cells=[_cell("1"), _cell("2")])],
        caption=caption,
    )


def _render(document: Document, **options: object) -> str:
    return MarkdownRenderer(MarkdownRendererOptions(**options)).render_to_string(document)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_caption_survives_and_adds_no_node(self) -> None:
        rendered = _render(Document(children=[_table()]))
        parsed = to_ast(rendered.encode(), source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Table"]
        assert parsed.children[0].caption == "Table 1. Results"

    def test_the_caption_is_still_visible_to_a_reader(self) -> None:
        """The reason we do not just use a comment."""
        rendered = _render(Document(children=[_table()]))
        assert "*Table 1. Results*" in rendered

    def test_rendering_is_idempotent(self) -> None:
        once = _render(Document(children=[_table()]))
        twice = _render(to_ast(once.encode(), source_format="markdown"))
        assert once == twice

    def test_editing_the_visible_line_edits_the_caption(self) -> None:
        """The marker deliberately carries no copy of the text."""
        rendered = _render(Document(children=[_table()])).replace("Table 1. Results", "Table 1. Revised")
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert parsed.children[0].caption == "Table 1. Revised"

    def test_a_table_without_a_caption_gains_neither_marker_nor_paragraph(self) -> None:
        rendered = _render(Document(children=[_table(caption=None)]))
        assert MARKDOWN_TABLE_CAPTION_MARKER not in rendered
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Table"]
        assert parsed.children[0].caption is None

    def test_a_caption_inside_a_list_item_folds_too(self) -> None:
        """Tables nest, so the triple can be nested; the fold recurses."""
        from all2md.ast.nodes import List, ListItem

        document = Document(children=[List(ordered=False, items=[ListItem(children=[_table()])])])
        parsed = to_ast(_render(document).encode(), source_format="markdown")

        tables = [n for n in parsed.children[0].items[0].children if isinstance(n, Table)]
        assert len(tables) == 1
        assert tables[0].caption == "Table 1. Results"


class TestItIsConservative:
    """Each of these is more likely someone's real content than a caption to rewrite."""

    def test_an_italic_paragraph_before_a_table_is_left_alone(self) -> None:
        """The control that matters: without the marker, nothing is swallowed."""
        source = b"*Just some emphasis.*\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        parsed = to_ast(source, source_format="markdown")

        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Table"]
        assert parsed.children[1].caption is None

    def test_a_marker_with_no_table_after_it_is_left_alone(self) -> None:
        source = f"*Cap*\n\n<!-- {MARKDOWN_TABLE_CAPTION_MARKER} -->\n\nJust a paragraph.\n".encode()
        parsed = to_ast(source, source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Comment", "Paragraph"]

    def test_a_bare_marker_before_a_table_is_left_alone(self) -> None:
        source = f"<!-- {MARKDOWN_TABLE_CAPTION_MARKER} -->\n\n| A |\n|---|\n| 1 |\n".encode()
        parsed = to_ast(source, source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Comment", "Table"]
        assert parsed.children[1].caption is None

    def test_a_mixed_paragraph_is_not_treated_as_a_caption(self) -> None:
        """Only a paragraph that is *entirely* one emphasis span reads as a caption."""
        source = f"Lead in *Cap*\n\n<!-- {MARKDOWN_TABLE_CAPTION_MARKER} -->\n\n| A |\n|---|\n| 1 |\n".encode()
        parsed = to_ast(source, source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Comment", "Table"]


class TestCommentMode:
    def test_ignore_suppresses_the_marker_and_says_so_by_losing_the_caption(self) -> None:
        """``comment_mode="ignore"`` asks for no comments; the caption degrades as it used to."""
        rendered = _render(Document(children=[_table()]), comment_mode="ignore")

        assert MARKDOWN_TABLE_CAPTION_MARKER not in rendered
        assert "*Table 1. Results*" in rendered

        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert [type(node).__name__ for node in parsed.children] == ["Paragraph", "Table"]
        assert parsed.children[1].caption is None

    @pytest.mark.parametrize("mode", ["html", "blockquote"])
    def test_every_other_comment_mode_keeps_the_round_trip(self, mode: str) -> None:
        rendered = _render(Document(children=[_table()]), comment_mode=mode)
        parsed = to_ast(rendered.encode(), source_format="markdown")
        assert isinstance(parsed.children[0], Table)
        assert parsed.children[0].caption == "Table 1. Results"


def test_the_probe_can_see_a_lost_caption() -> None:
    """Guard the guard: prove an un-marked caption really does fail to round trip.

    Otherwise every assertion above could be passing for some unrelated reason.
    """
    source = b"*Table 1. Results*\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    parsed = to_ast(source, source_format="markdown")

    assert any(isinstance(node, Paragraph) for node in parsed.children)
    table = next(node for node in parsed.children if isinstance(node, Table))
    assert table.caption is None
