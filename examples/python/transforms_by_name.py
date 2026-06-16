#!/usr/bin/env python3
"""Compose built-in transforms by name, mix in a custom transform, and use hooks.

all2md ships a registry of built-in transforms you can apply *by string name* --
the same names the CLI exposes via ``--transform`` (run ``all2md list-transforms``
to see them). This is the quickest way to clean up a document on the way to
Markdown, with no transform classes to import.

This example shows three layers, from simplest to most flexible:

1. Built-in transforms by name      -> to_markdown(src, transforms=["remove-images", ...])
2. Built-ins + a custom transform   -> mix names and NodeTransformer instances in one list
3. Hooks                            -> observe/modify specific node types during rendering

Usage:
    python transforms_by_name.py <document>
    python transforms_by_name.py ../../tests/fixtures/documents/basic.docx
"""

from __future__ import annotations

import sys

from all2md import to_markdown
from all2md.ast import Text
from all2md.ast.transforms import NodeTransformer


class UpperToLowerHeadingsTransform(NodeTransformer):
    """A tiny custom transform: l-case any ALL-CAPS text (e.g. shouty headings)."""

    def visit_text(self, node: Text) -> Text:
        content = node.content
        if content.isupper() and any(c.isalpha() for c in content):
            return Text(content=content.capitalize(), metadata=node.metadata.copy())
        return node


def main() -> int:
    """Run the three-layer transform demo against a document."""
    if len(sys.argv) < 2:
        print("Usage: python transforms_by_name.py <document>")
        return 1

    source = sys.argv[1]

    # ------------------------------------------------------------------
    # 1. Built-in transforms, applied by name and in order.
    #    Equivalent CLI: all2md doc --transform remove-images \
    #                              --transform heading-offset --heading-offset 1
    # ------------------------------------------------------------------
    print("=" * 70)
    print("1. Built-in transforms by name")
    print("=" * 70)
    md = to_markdown(
        source,
        transforms=["remove-images", "remove-boilerplate", "word-count"],
    )
    print(md[:600])
    print("...\n")

    # ------------------------------------------------------------------
    # 2. Mix built-in names with a custom NodeTransformer instance.
    #    The list is applied left-to-right; names and instances interleave freely.
    # ------------------------------------------------------------------
    print("=" * 70)
    print("2. Built-ins + a custom transform")
    print("=" * 70)
    md = to_markdown(
        source,
        transforms=["remove-images", UpperToLowerHeadingsTransform()],
    )
    print(md[:600])
    print("...\n")

    # ------------------------------------------------------------------
    # 3. Hooks: run a callback for every node of a given type during rendering.
    #    Hooks are keyed by node type ("image", "link", "heading", ...) or by a
    #    pipeline point ("pre_render", "post_render", ...). Each callback receives
    #    (node, HookContext) and returns the (possibly modified) node.
    # ------------------------------------------------------------------
    print("=" * 70)
    print("3. Hooks (observe links and headings without modifying them)")
    print("=" * 70)
    seen = {"link": 0, "heading": 0}

    def count_links(node, context):
        seen["link"] += 1
        return node  # return the node unchanged

    def count_headings(node, context):
        seen["heading"] += 1
        return node

    to_markdown(
        source,
        hooks={"link": [count_links], "heading": [count_headings]},
    )
    print(f"Document contains {seen['heading']} heading(s) and {seen['link']} link(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
