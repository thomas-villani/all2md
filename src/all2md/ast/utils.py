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

from all2md.ast.nodes import Text, get_node_children

if TYPE_CHECKING:
    from all2md.ast.nodes import Node


def extract_text(node_or_nodes: Union[Node, list[Node]], joiner: str = " ") -> str:
    r"""Extract plain text from a node or list of nodes.

    This function recursively traverses the AST and concatenates all Text node
    content, joining text parts with the specified joiner string. It uses
    get_node_children() to properly handle all node types including List, Table,
    and other complex structures.

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

    Notes
    -----
    **Spacing Behavior**:
        The joiner is applied at each level of the AST hierarchy when combining
        child nodes. This can result in extra spaces when Text nodes already
        contain whitespace at their boundaries. For example:

            >>> para = Paragraph(content=[
            ...     Text(content="This is "),  # trailing space
            ...     Strong(content=[Text(content="bold")]),
            ...     Text(content=" text.")     # leading space
            ... ])
            >>> extract_text(para)
            'This is  bold  text.'  # Note the double spaces

        This occurs because:
        1. Text content is preserved exactly (including trailing/leading spaces)
        2. The joiner adds spacing between nodes at each nesting level
        3. These can combine to create multiple consecutive spaces

        **Workarounds**:
        - Use `joiner=""` and rely on spaces within Text nodes: `extract_text(node, joiner="")`
        - Post-process with regex: `re.sub(r'\\s+', ' ', extract_text(node)).strip()`
        - Normalize Text nodes before extraction to trim whitespace

        This behavior is intentional to preserve the exact text content and
        provide consistent separation at structural boundaries.

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
        'This is  bold  text.'  # Note: double spaces preserved

    Extract text with no joiner (preserves only Text content):

        >>> from all2md.ast import Heading, Text
        >>> heading = Heading(level=2, content=[Text(content="My Heading")])
        >>> extract_text(heading.content, joiner="")
        'My Heading'

    Extract text from a list of nodes:

        >>> from all2md.ast import Text, Emphasis
        >>> nodes = [Text(content="Hello"), Emphasis(content=[Text(content="world")])]
        >>> extract_text(nodes)
        'Hello world'

    Extract text from complex structures (List, Table):

        >>> from all2md.ast import List, ListItem, Text, Paragraph
        >>> lst = List(ordered=False, items=[
        ...     ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
        ...     ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
        ... ])
        >>> extract_text(lst)
        'Item 1 Item 2'

    Normalize whitespace in extracted text:

        >>> import re
        >>> result = extract_text(para)
        >>> normalized = re.sub(r'\\s+', ' ', result).strip()
        >>> normalized
        'This is bold text.'

    """
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

    # Recursively extract text from all child nodes using get_node_children
    # This handles all node types (List.items, Table.rows, etc.)
    for child in get_node_children(node):
        extracted = extract_text(child, joiner=joiner)
        if extracted:
            text_parts.append(extracted)

    return joiner.join(text_parts)


__all__ = [
    "extract_text",
]
