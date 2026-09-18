#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_rst_adjacent_lists.py
"""Two adjacent lists of the same kind stay two lists through RST (#496).

A blank line does not end a reStructuredText list. Two bullet lists written back to back
came back from docutils as one list, and two enumerated lists came back as one whenever
the second continued the first's numbering -- the very shape a restarted DOCX list or a
pair of HTML ``<ol>`` elements arrives in -- taking the second list's ``start`` with it.

docutils does end a list where the marker changes, so the renderer now switches marker
for a list that directly follows one of its own kind: ``-`` after ``*``, ``3)`` after
``2.``, and back again for a third. That is the Markdown renderer's rule from #495; RST
needs no separator fallback because both switches are always available.
"""

from __future__ import annotations

import io

import pytest

from all2md import to_ast
from all2md.ast.nodes import BlockQuote, Document, List, ListItem, Paragraph, Text
from all2md.renderers.rst import RestructuredTextRenderer

pytestmark = [pytest.mark.unit]


def _item(text: str, *blocks) -> ListItem:
    return ListItem(children=[Paragraph(content=[Text(content=text)]), *blocks])


def _bullets(*texts: str) -> List:
    return List(ordered=False, items=[_item(t) for t in texts])


def _numbered(*texts: str, start: int = 1) -> List:
    return List(ordered=True, start=start, items=[_item(t) for t in texts])


def _render(*children) -> str:
    return RestructuredTextRenderer().render_to_string(Document(children=list(children)))


def _reparse(rendered: str) -> list[tuple[bool, int, int]]:
    """Each top-level list as ``(ordered, item count, start)`` after docutils reads it back."""
    doc = to_ast(io.BytesIO(rendered.encode("utf-8")), source_format="rst")
    return [(node.ordered, len(node.items), node.start) for node in doc.children if isinstance(node, List)]


class TestAdjacentListsSwitchMarker:
    def test_a_second_bullet_list_takes_the_other_bullet(self):
        rendered = _render(_bullets("a"), _bullets("b"))

        assert rendered == "* a\n\n- b"
        assert _reparse(rendered) == [(False, 1, 1), (False, 1, 1)]

    def test_a_continuing_ordered_list_keeps_its_start(self):
        # The hard shape: without the switch this read as one list of three, start 1.
        rendered = _render(_numbered("a", "b"), _numbered("c", start=3))

        assert rendered == "1. a\n2. b\n\n3) c"
        assert _reparse(rendered) == [(True, 2, 1), (True, 1, 3)]

    def test_a_third_list_switches_back(self):
        rendered = _render(_bullets("a"), _bullets("b"), _bullets("c"))

        assert rendered == "* a\n\n- b\n\n* c"
        assert _reparse(rendered) == [(False, 1, 1)] * 3

    def test_lists_of_different_kinds_need_no_switch(self):
        rendered = _render(_bullets("a"), _numbered("b"))

        assert rendered == "* a\n\n1. b"
        assert _reparse(rendered) == [(False, 1, 1), (True, 1, 1)]

    def test_a_list_after_a_paragraph_uses_the_default_marker(self):
        rendered = _render(_bullets("a"), Paragraph(content=[Text(content="between")]), _bullets("b"))

        assert rendered == "* a\n\nbetween\n\n* b"


class TestTheSwitchIsLocalToTheSiblingRun:
    def test_a_nested_list_starts_from_the_default_marker(self):
        # The flag is consumed by the list it was set for; its children are not affected.
        outer = List(ordered=False, items=[_item("b", _bullets("nested"))])
        rendered = _render(_bullets("a"), outer)

        assert rendered == "* a\n\n- b\n      * nested"

    def test_adjacent_lists_inside_an_item_switch_too(self):
        outer = List(ordered=False, items=[_item("parent", _numbered("x"), _numbered("y", start=2))])

        rendered = _render(outer)

        # Only the rendering is asserted: a nested list is written without a blank line
        # before it and six columns in, which docutils reads back as a definition list.
        # That is a pre-existing nesting defect of this renderer, separate from #496;
        # written with a blank line and two columns in, the same text reparses as two
        # lists with starts 1 and 2.
        assert rendered == "* parent\n      1. x\n      2) y"

    def test_a_list_inside_a_block_quote_after_a_list_outside_it_is_not_adjacent(self):
        rendered = _render(_bullets("a"), BlockQuote(children=[_bullets("quoted")]))

        assert "   * quoted" in rendered
