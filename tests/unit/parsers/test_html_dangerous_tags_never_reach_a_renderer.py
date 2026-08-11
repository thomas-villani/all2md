#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The HTML parser, not the markdown renderer, is what makes `html -> markdown` safe.

#178 changed the markdown renderer's `html_passthrough_mode` default from "escape"
to "pass-through". That is only defensible because of the invariant asserted here:
the HTML parser maps tags to AST nodes and drops the executable ones outright, so
`<script>` and friends never become an `HTMLBlock`/`HTMLInline` for a renderer to
decide about. The renderer's default was never the thing standing between a scraped
page and a `<script>` in the output.

If a future change makes the HTML parser emit raw-HTML nodes for these tags, this
file fails - and the pass-through default has to be reconsidered along with it.
The two opt-ins that *do* produce `HTMLBlock` from HTML (`figures_parsing="html"`,
`details_parsing="html"`) are asked for explicitly and are not covered by this.
"""

from __future__ import annotations

import pytest

from all2md import from_ast, to_ast
from all2md.ast.nodes import HTMLBlock, HTMLInline, Node
from all2md.ast.transforms import NodeCollector

pytestmark = [pytest.mark.unit, pytest.mark.html]


def _raw_html_nodes(document: Node) -> list[Node]:
    collector = NodeCollector(lambda node: isinstance(node, (HTMLBlock, HTMLInline)))
    document.accept(collector)
    return collector.collected


_EXECUTABLE = {
    "script": b"<p>before</p><script>alert(1)</script><p>after</p>",
    "iframe": b"<p>before</p><iframe src='https://example.invalid'></iframe>",
    "form": b"<form action='/x'><input onclick='alert(1)'></form>",
    "svg-onload": b"<svg onload='alert(1)'><circle r='1'/></svg>",
    "object": b"<object data='x.swf'></object>",
    "embed": b"<embed src='x.swf'>",
}


@pytest.mark.parametrize("markup", _EXECUTABLE.values(), ids=list(_EXECUTABLE))
def test_the_html_parser_emits_no_raw_html_node_for_executable_markup(markup: bytes) -> None:
    document = to_ast(markup, source_format="html")
    assert _raw_html_nodes(document) == []


@pytest.mark.parametrize("markup", _EXECUTABLE.values(), ids=list(_EXECUTABLE))
def test_executable_markup_is_absent_from_the_rendered_markdown(markup: bytes) -> None:
    """The end-to-end claim, under the new default rather than a forced one."""
    rendered = from_ast(to_ast(markup, source_format="html"), target_format="markdown")
    lowered = rendered.lower()
    for tag in ("<script", "<iframe", "<object", "<embed", "onload=", "onclick="):
        assert tag not in lowered, f"{tag} survived into markdown:\n{rendered}"


def test_the_harness_can_actually_see_a_raw_html_node() -> None:
    """Guard the guard: a probe that never finds anything proves nothing.

    Markdown *does* hand raw HTML through to the AST - that is the whole reason
    #178 exists - so it makes the control the checks above need.
    """
    document = to_ast(b"# T\n\n<div align='center'>\n  <b>hi</b>\n</div>\n", source_format="markdown")
    assert len(_raw_html_nodes(document)) == 1


def test_ordinary_markup_still_survives_as_real_nodes() -> None:
    """Dropping the executable tags must not be dropping everything."""
    rendered = from_ast(
        to_ast(b"<h1>Title</h1><p>Body <strong>bold</strong></p>", source_format="html"),
        target_format="markdown",
    )
    assert "# Title" in rendered
    assert "**bold**" in rendered
