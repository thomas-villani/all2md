#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/utils.py
"""Utility functions for working with AST nodes.

This module provides helper functions for common operations on AST nodes,
including text extraction, node traversal, and node manipulation.

Functions
---------
extract_text : Extract plain text from a node or list of nodes

Examples
--------
Extract text from a heading:

    >>> from all2md.ast import Heading, Text, Emphasis
    >>> from all2md.ast.utils import extract_text
    >>>
    >>> heading = Heading(level=1, content=[
    ...     Text(content="Hello "),
    ...     Emphasis(content=[Text(content="world")])
    ... ])
    >>> extract_text(heading)
    'Hello world'

Extract text without spaces (for ID generation):

    >>> extract_text(heading, joiner="")
    'Helloworld'

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from all2md.ast.nodes import Node


def extract_text(node_or_nodes: Union[Node, list[Node]], joiner: str = " ") -> str:
    """Extract plain text from a node or list of nodes.

    This function recursively traverses the AST and concatenates all Text node
    content, joining text parts with the specified joiner string.

    Parameters
    ----------
    node_or_nodes : Node or list of Node
        A single node or list of nodes to extract text from
    joiner : str, default = " "
        String to use for joining text parts. Use "" for no separation
        (useful for ID generation) or " " for natural text with spaces
        (useful for word counting).

    Returns
    -------
    str
        Concatenated text content from all Text nodes

    Examples
    --------
    Extract text with space joiner (default):

        >>> from all2md.ast import Paragraph, Text, Strong
        >>> para = Paragraph(content=[
        ...     Text(content="This is "),
        ...     Strong(content=[Text(content="bold")]),
        ...     Text(content=" text.")
        ... ])
        >>> extract_text(para)
        'This is bold text.'

    Extract text with no joiner (for slugification):

        >>> from all2md.ast import Heading, Text
        >>> heading = Heading(level=2, content=[Text(content="My Heading")])
        >>> extract_text(heading.content, joiner="")
        'MyHeading'

    Extract text from a list of nodes:

        >>> from all2md.ast import Text, Emphasis
        >>> nodes = [Text(content="Hello"), Emphasis(content=[Text(content="world")])]
        >>> extract_text(nodes)
        'Hello world'

    """
    # Import here to avoid circular imports
    from all2md.ast.nodes import Text

    # Handle list of nodes
    if isinstance(node_or_nodes, list):
        text_parts = []
        for node in node_or_nodes:
            extracted = extract_text(node, joiner=joiner)
            if extracted:
                text_parts.append(extracted)
        return joiner.join(text_parts)

    # Handle single node
    node = node_or_nodes
    text_parts = []

    # If node is Text, return its content directly
    if isinstance(node, Text):
        return node.content

    # If node has children list (block nodes), recurse
    if hasattr(node, 'children') and isinstance(node.children, list):
        for child in node.children:
            extracted = extract_text(child, joiner=joiner)
            if extracted:
                text_parts.append(extracted)

    # If node has content list (inline nodes), recurse
    if hasattr(node, 'content') and isinstance(node.content, list):
        for child in node.content:
            extracted = extract_text(child, joiner=joiner)
            if extracted:
                text_parts.append(extracted)

    return joiner.join(text_parts)


__all__ = [
    "extract_text",
]
