#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Nested lists in the RST renderer read back as nested lists (#517).

The renderer used to write a nested list on the line after its parent item, six
columns in. docutils read the parent's text as a definition term and the list as
its definition, so the item came back with no paragraph and no list. A nested
list now sits a blank line below the item's text, at the item's text column, and
the item's other blocks (a literal block, a second paragraph) keep the blank
lines that separate them.
"""

from __future__ import annotations

import io

import pytest

from all2md import to_ast
from all2md.ast.nodes import CodeBlock, Document, List, ListItem, Node, Paragraph, Text
from all2md.renderers.rst import RestructuredTextRenderer


def _item(text: str, *blocks: Node) -> ListItem:
    return ListItem(children=[Paragraph(content=[Text(content=text)]), *blocks])


def _render(node: Node) -> str:
    return RestructuredTextRenderer().render_to_string(Document(children=[node]))


def _shape(node: Node) -> object:
    """The tree of block types and texts, which a round trip must keep."""
    if isinstance(node, Text):
        return node.content
    if isinstance(node, Paragraph):
        return ["Paragraph", *(_shape(child) for child in node.content)]
    if isinstance(node, CodeBlock):
        return ["CodeBlock", node.content]
    children = getattr(node, "items", None) or getattr(node, "children", None) or []
    return [type(node).__name__, *(_shape(child) for child in children)]


CASES = {
    "bullet-in-bullet": (
        List(ordered=False, items=[_item("parent", List(ordered=False, items=[_item("c1"), _item("c2")])), _item("2")]),
        "* parent\n\n  * c1\n  * c2\n\n* 2",
    ),
    "ordered-in-ordered": (
        List(ordered=True, items=[_item("parent", List(ordered=True, items=[_item("child")]))]),
        "1. parent\n\n   1. child",
    ),
    "three-levels": (
        List(
            ordered=False,
            items=[
                _item("a", List(ordered=True, items=[_item("b", List(ordered=False, items=[_item("c")]))])),
                _item("d"),
            ],
        ),
        "* a\n\n  1. b\n\n     * c\n\n* d",
    ),
    "wide-marker-then-paragraph": (
        List(
            ordered=True,
            start=9,
            items=[
                _item("nine"),
                _item("ten", List(ordered=False, items=[_item("x")]), Paragraph(content=[Text(content="after")])),
            ],
        ),
        "9. nine\n10. ten\n\n    * x\n\n    after",
    ),
    "literal-block-in-item": (
        List(ordered=False, items=[_item("p", CodeBlock(content="x = 1\n\ny = 2", language="python")), _item("q")]),
        "* p\n\n  .. code-block:: python\n\n     x = 1\n\n     y = 2\n\n* q",
    ),
}


@pytest.mark.unit
class TestNestedListsRoundTrip:
    @pytest.mark.parametrize("name", list(CASES))
    def test_rendered_text(self, name):
        node, expected = CASES[name]
        assert _render(node) == expected

    @pytest.mark.parametrize("name", list(CASES))
    def test_reads_back_with_the_same_shape(self, name):
        node, _ = CASES[name]
        back = to_ast(io.BytesIO(_render(node).encode("utf-8")), source_format="rst")
        assert [_shape(child) for child in back.children] == [_shape(node)]

    def test_flat_list_stays_compact(self):
        assert _render(List(ordered=False, items=[_item("a"), _item("b")])) == "* a\n* b"

    def test_no_trailing_spaces_on_blank_lines(self):
        node, _ = CASES["three-levels"]
        assert all(line == line.rstrip() for line in _render(node).split("\n"))
