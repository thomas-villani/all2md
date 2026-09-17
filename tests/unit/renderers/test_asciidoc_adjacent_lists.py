#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_asciidoc_adjacent_lists.py
"""Two adjacent lists of the same kind stay two lists through AsciiDoc (#497).

A blank line does not end an AsciiDoc list. Two bullet lists written back to back came
back as one list of two, and two ordered lists as one list of three -- so a restarted
DOCX list, or a pair of HTML ``<ol>`` elements, continued the numbering of the list
before it. Only a second list with a ``start`` other than 1 survived, and only because
its ``[start=N]`` attribute line happened to break the list.

AsciiDoc's documented way to force adjacent lists apart is a line comment between them,
conventionally ``//-``. The renderer now writes one before a list that directly follows
one of its own kind, at the document and block-quote level. The parser ends the first
list at the comment and keeps it as a ``Comment`` node, exactly as the Markdown parser
keeps the ``<!-- -->`` the Markdown renderer writes for the same boundary (#495).
"""

from __future__ import annotations

import io

import pytest

from all2md import to_ast
from all2md.ast.nodes import BlockQuote, Comment, Document, List, ListItem, Paragraph, Text
from all2md.renderers.asciidoc import AsciiDocRenderer

pytestmark = [pytest.mark.unit]


def _item(text: str, *blocks) -> ListItem:
    return ListItem(children=[Paragraph(content=[Text(content=text)]), *blocks])


def _bullets(*texts: str) -> List:
    return List(ordered=False, items=[_item(t) for t in texts])


def _numbered(*texts: str, start: int = 1) -> List:
    return List(ordered=True, start=start, items=[_item(t) for t in texts])


def _render(*children) -> str:
    # The renderer ends its output with a newline; dropped so the assertions read cleanly.
    return AsciiDocRenderer().render_to_string(Document(children=list(children))).rstrip("\n")


def _shapes(nodes) -> list[str]:
    """Each block as ``List(ordered, count, start)`` or ``Comment``, so the boundary shows."""
    out = []
    for node in nodes:
        if isinstance(node, List):
            out.append(f"List({node.ordered}, {len(node.items)}, {node.start})")
        elif isinstance(node, Comment):
            out.append("Comment")
        else:
            out.append(type(node).__name__)
    return out


def _reparse(rendered: str) -> list[str]:
    return _shapes(to_ast(io.BytesIO(rendered.encode("utf-8")), source_format="asciidoc").children)


class TestAdjacentListsGetACommentBetweenThem:
    def test_two_bullet_lists_stay_two(self):
        rendered = _render(_bullets("a"), _bullets("b"))

        assert rendered == "* a\n\n//-\n* b"
        assert _reparse(rendered) == ["List(False, 1, 1)", "Comment", "List(False, 1, 1)"]

    def test_a_restarted_ordered_list_no_longer_continues_the_first(self):
        # The shape from the issue: read back as one list of three before.
        rendered = _render(_numbered("a", "b"), _numbered("c"))

        assert rendered == ". a\n. b\n\n//-\n. c"
        assert _reparse(rendered) == ["List(True, 2, 1)", "Comment", "List(True, 1, 1)"]

    def test_the_comment_sits_before_the_start_attribute(self):
        rendered = _render(_numbered("a", "b"), _numbered("c", start=3))

        assert rendered == ". a\n. b\n\n//-\n[start=3]\n. c"
        assert _reparse(rendered) == ["List(True, 2, 1)", "Comment", "List(True, 1, 3)"]

    def test_every_boundary_in_a_run_of_three_is_marked(self):
        rendered = _render(_bullets("a"), _bullets("b"), _bullets("c"))

        assert rendered == "* a\n\n//-\n* b\n\n//-\n* c"
        assert _reparse(rendered) == ["List(False, 1, 1)", "Comment"] * 2 + ["List(False, 1, 1)"]

    def test_lists_of_different_kinds_need_no_comment(self):
        rendered = _render(_bullets("a"), _numbered("b"))

        assert rendered == "* a\n\n. b"
        assert _reparse(rendered) == ["List(False, 1, 1)", "List(True, 1, 1)"]

    def test_a_paragraph_between_two_lists_is_boundary_enough(self):
        rendered = _render(_bullets("a"), Paragraph(content=[Text(content="between")]), _bullets("b"))

        assert rendered == "* a\n\nbetween\n\n* b"

    def test_adjacent_lists_inside_a_block_quote_are_kept_apart_too(self):
        rendered = _render(BlockQuote(children=[_bullets("a"), _bullets("b")]))

        assert rendered == "____\n* a\n\n//-\n* b\n____"
        (quote,) = to_ast(io.BytesIO(rendered.encode("utf-8")), source_format="asciidoc").children
        assert isinstance(quote, BlockQuote)
        assert _shapes(quote.children) == ["List(False, 1, 1)", "Comment", "List(False, 1, 1)"]


class TestNestedListsAreLeftAlone:
    def test_two_nested_lists_under_one_item_get_no_comment(self):
        # A comment line inside a nested list ends the outer list and orphans the
        # nested marker after it, which the parser rejects. The nested pair still
        # merges on reparse; that is the documented residue of #497.
        outer = List(ordered=False, items=[_item("parent", _bullets("x"), _bullets("y"))])

        rendered = _render(outer)

        assert "//-" not in rendered
        (parsed,) = to_ast(io.BytesIO(rendered.encode("utf-8")), source_format="asciidoc").children
        assert isinstance(parsed, List)
