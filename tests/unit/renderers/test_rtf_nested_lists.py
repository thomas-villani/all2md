#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_rtf_nested_lists.py
"""Unit tests for nested list handling in the RTF renderer.

pyth writes one ``\\ilvl`` level prefix per paragraph inside a list entry, so an
entry whose content is a nested list gets the outer level's prefix and the inner
level's prefix on the same output paragraph. Its reader charges those controls to
the preceding paragraph and reads the result as a level decrease with no matching
increase, which either pops the document off its own stack (#209) or strands the
content of a list it never re-attaches.

The renderer therefore flattens nested lists before handing them to pyth. Nesting
depth is the only thing given up, and the RTF parser does not reconstruct it in
any case - a plain two-item list already round-trips back as two paragraphs.

"""

import io

import pytest

from all2md import from_ast
from all2md.ast.nodes import Document, List, ListItem, Paragraph, Text
from all2md.parsers.rtf import RtfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.formatting]


def _p(text: str) -> Paragraph:
    return Paragraph(content=[Text(content=text)])


def _ul(*items: ListItem) -> List:
    return List(ordered=False, tight=False, items=list(items))


def _texts(node: object) -> list[str]:
    """Collect every non-blank Text payload under a node."""
    found: list[str] = []

    def walk(current: object) -> None:
        if isinstance(current, Text):
            found.append(current.content)
            return
        for attr in ("children", "items", "content"):
            for child in getattr(current, attr, None) or []:
                walk(child)

    walk(node)
    return [text for text in found if text.strip()]


def _round_trip(doc: Document) -> Document:
    rtf = from_ast(doc, "rtf")
    return RtfToAstConverter().parse(io.BytesIO(rtf.encode("utf-8")))


#: An empty list item nested one level down, alongside an empty sibling. Shrunk
#: by Hypothesis from a generated counterexample (#209).
NESTED_EMPTY_ITEM = Document(
    children=[
        _p("0"),
        _ul(ListItem(children=[_ul(ListItem(children=[]))]), ListItem(children=[])),
    ]
)

#: The same shape carrying a task status, which took a different path (#210).
NESTED_TASK_ITEM = Document(
    children=[
        _ul(
            ListItem(
                task_status="checked",
                children=[_ul(ListItem(children=[], task_status="checked"))],
            )
        )
    ]
)


class TestNestedListsDoNotCrash:
    """The shapes the fuzzer shrank out must render and parse back."""

    def test_nested_empty_item_round_trips(self) -> None:
        """#209: the reader used to pop the document off its own list stack."""
        assert _round_trip(NESTED_EMPTY_ITEM) is not None

    def test_nested_task_item_renders(self) -> None:
        """#210: a marker run reached pyth's paragraph dispatch as a bare str."""
        assert from_ast(NESTED_TASK_ITEM, "rtf")


class TestNestedListsKeepTheirContent:
    """Flattening gives up depth, not text."""

    def test_two_level_list_keeps_every_item(self) -> None:
        doc = Document(
            children=[_ul(ListItem(children=[_p("outer")]), ListItem(children=[_ul(ListItem(children=[_p("inner")]))]))]
        )

        assert _texts(_round_trip(doc)) == ["outer", "inner"]

    def test_three_level_list_keeps_the_deepest_item(self) -> None:
        """The depth that used to be dropped outright rather than flattened.

        Before the fix this lost ``L3``: pyth's reader pushed a list for the
        level increase and never popped it, so its content never reached the
        document. That was a live data-loss bug the fuzzer had not reached.
        """
        doc = Document(
            children=[
                _ul(
                    ListItem(children=[_p("L1")]),
                    ListItem(
                        children=[
                            _ul(ListItem(children=[_p("L2")]), ListItem(children=[_ul(ListItem(children=[_p("L3")]))]))
                        ]
                    ),
                )
            ]
        )

        assert _texts(_round_trip(doc)) == ["L1", "L2", "L3"]

    def test_item_with_text_and_a_sub_list_keeps_both(self) -> None:
        doc = Document(children=[_ul(ListItem(children=[_p("head"), _ul(ListItem(children=[_p("sub")]))]))])

        assert _texts(_round_trip(doc)) == ["head", "sub"]


class TestTaskMarkers:
    """A task marker survives whether or not the item has text of its own."""

    def test_marker_is_written_for_a_plain_task_item(self) -> None:
        doc = Document(children=[_ul(ListItem(children=[_p("todo")], task_status="unchecked"))])

        assert "[ ] " in from_ast(doc, "rtf")

    def test_marker_gets_its_own_paragraph_when_the_item_is_only_a_sub_list(self) -> None:
        """The marker cannot be inserted into a List, so it needs a paragraph.

        pyth's ``List`` subclasses ``Paragraph``, which is what let the run be
        inserted into the sub-list's content in the first place.
        """
        assert "[x] " in from_ast(NESTED_TASK_ITEM, "rtf")


class TestEmittedRtfIsWellFormed:
    """The level prefixes pyth writes must stay balanced."""

    def test_no_paragraph_declares_two_list_levels(self) -> None:
        """Two ``\\ilvl`` controls on one paragraph is the shape that broke the reader."""
        doc = Document(
            children=[_ul(ListItem(children=[_p("outer")]), ListItem(children=[_ul(ListItem(children=[_p("inner")]))]))]
        )

        for line in from_ast(doc, "rtf").splitlines():
            if "\\par" in line:
                assert line.count("\\ilvl") <= 1, f"paragraph declares two list levels: {line}"
