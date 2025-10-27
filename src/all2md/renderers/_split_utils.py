#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/_split_utils.py
"""Shared utilities for splitting AST documents into chunks.

This module provides reusable functions for splitting AST documents
into logical units (chapters, slides, sections) based on various
strategies. Used by EPUB and PPTX renderers.
"""

from __future__ import annotations

from all2md.ast.nodes import Document, Heading, Node, Text, ThematicBreak


def split_ast_by_separator(doc: Document) -> list[list[Node]]:
    """Split AST document into chunks based on ThematicBreak nodes.

    This splitting strategy mirrors how parsers use ThematicBreak to
    separate logical units (chapters in EPUB, slides in PPTX).

    Parameters
    ----------
    doc : Document
        AST document to split

    Returns
    -------
    list of list of Node
        List of node chunks, where each chunk represents content
        between separators. Empty chunks are excluded.

    Examples
    --------
    >>> from all2md.ast import Document, Paragraph, Text, ThematicBreak
    >>> doc = Document(children=[
    ...     Paragraph(content=[Text(content="Chapter 1")]),
    ...     ThematicBreak(),
    ...     Paragraph(content=[Text(content="Chapter 2")]),
    ... ])
    >>> chunks = split_ast_by_separator(doc)
    >>> len(chunks)
    2

    Notes
    -----
    ThematicBreak nodes are consumed during splitting and not included
    in the output chunks.

    """
    chunks: list[list[Node]] = []
    current_chunk: list[Node] = []

    for node in doc.children:
        if isinstance(node, ThematicBreak):
            # Separator found - finalize current chunk
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
        else:
            current_chunk.append(node)

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def split_ast_by_heading(doc: Document, heading_level: int = 1) -> list[tuple[Heading | None, list[Node]]]:
    """Split AST document into chunks based on heading level.

    This strategy splits the document when encountering a heading at
    the specified level, treating it as a chapter/slide boundary.

    Parameters
    ----------
    doc : Document
        AST document to split
    heading_level : int, default 1
        Heading level to use as split boundary (1 = H1, 2 = H2, etc.)

    Returns
    -------
    list of tuple[Heading or None, list of Node]
        List of (heading, content_nodes) tuples, where heading is the
        boundary heading (or None for content before first heading)
        and content_nodes are the nodes following that heading.

    Examples
    --------
    >>> from all2md.ast import Document, Heading, Paragraph, Text
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Chapter 1")]),
    ...     Paragraph(content=[Text(content="Content 1")]),
    ...     Heading(level=1, content=[Text(content="Chapter 2")]),
    ...     Paragraph(content=[Text(content="Content 2")]),
    ... ])
    >>> chunks = split_ast_by_heading(doc, heading_level=1)
    >>> len(chunks)
    2
    >>> chunks[0][0].content[0].content
    'Chapter 1'

    Notes
    -----
    The heading itself is included in the returned tuple but NOT in
    the content_nodes list. This allows renderers to use the heading
    for titles while rendering content separately.

    """
    chunks: list[tuple[Heading | None, list[Node]]] = []
    current_heading: Heading | None = None
    current_chunk: list[Node] = []

    for node in doc.children:
        if isinstance(node, Heading) and node.level == heading_level:
            # Heading boundary found - finalize current chunk
            if current_heading is not None or current_chunk:
                chunks.append((current_heading, current_chunk))

            # Start new chunk with this heading
            current_heading = node
            current_chunk = []
        else:
            current_chunk.append(node)

    # Don't forget the last chunk
    if current_heading is not None or current_chunk:
        chunks.append((current_heading, current_chunk))

    return chunks


def auto_split_ast(doc: Document, heading_level: int = 1) -> list[tuple[Heading | None, list[Node]]]:
    """Automatically determine best splitting strategy for AST.

    This function tries separator-based splitting first (ThematicBreak).
    If no separators are found, it falls back to heading-based splitting.

    Parameters
    ----------
    doc : Document
        AST document to split
    heading_level : int, default 1
        Heading level to use for fallback splitting

    Returns
    -------
    list of tuple[Heading or None, list of Node]
        List of (heading, content_nodes) tuples. If separator-based
        splitting was used, heading will be None for all chunks.

    Examples
    --------
    Document with separators uses separator splitting:

        >>> from all2md.ast import Document, Paragraph, Text, ThematicBreak
        >>> doc = Document(children=[
        ...     Paragraph(content=[Text(content="Part 1")]),
        ...     ThematicBreak(),
        ...     Paragraph(content=[Text(content="Part 2")]),
        ... ])
        >>> chunks = auto_split_ast(doc)
        >>> chunks[0][0] is None  # No heading (separator-based)
        True

    Document without separators uses heading splitting:

        >>> from all2md.ast import Document, Heading, Paragraph, Text
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Chapter 1")]),
        ...     Paragraph(content=[Text(content="Content")]),
        ... ])
        >>> chunks = auto_split_ast(doc, heading_level=1)
        >>> chunks[0][0].level  # Has heading (heading-based)
        1

    Notes
    -----
    The return format is always (Heading | None, list[Node]) tuples
    for consistency, even when using separator-based splitting.

    """
    # Check if document contains any ThematicBreak nodes
    has_separators = any(isinstance(node, ThematicBreak) for node in doc.children)

    if has_separators:
        # Use separator-based splitting
        separator_chunks = split_ast_by_separator(doc)
        # Convert to (None, nodes) format for consistency
        return [(None, chunk) for chunk in separator_chunks]
    else:
        # Fall back to heading-based splitting
        return split_ast_by_heading(doc, heading_level)


def extract_heading_text(heading: Heading | None) -> str:
    """Extract plain text from a heading node.

    Parameters
    ----------
    heading : Heading or None
        Heading node to extract text from

    Returns
    -------
    str
        Plain text content of the heading, or empty string if None

    Examples
    --------
    >>> from all2md.ast import Heading, Text, Strong
    >>> heading = Heading(level=1, content=[
    ...     Text(content="Chapter "),
    ...     Strong(content=[Text(content="One")])
    ... ])
    >>> extract_heading_text(heading)
    'Chapter One'

    """
    if heading is None:
        return ""

    text_parts: list[str] = []

    def collect_text(nodes: list) -> None:
        """Recursively collect text from nodes."""
        for node in nodes:
            if isinstance(node, Text):
                text_parts.append(node.content)
            elif hasattr(node, "content") and isinstance(node.content, list):
                collect_text(node.content)

    collect_text(heading.content)
    return "".join(text_parts)
