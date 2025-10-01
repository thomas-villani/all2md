#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/__init__.py
"""Abstract Syntax Tree (AST) module for document representation.

This module provides a complete Abstract Syntax Tree representation for markdown
documents, enabling separation of document parsing from markdown rendering. The
AST approach allows for:

1. Multiple markdown flavor support (CommonMark, GFM, etc.)
2. Document structure validation and manipulation
3. Improved testability and maintainability
4. Bidirectional conversion support

The module consists of several components:

- nodes: AST node classes representing document structure
- visitors: Visitor pattern implementation for AST traversal
- renderer: Markdown rendering from AST
- flavors: Different markdown dialect support
- builder: Helper classes for constructing complex AST structures

Examples
--------
Basic usage:

    >>> from all2md.ast import Document, Heading, Paragraph, Text
    >>> from all2md.ast import MarkdownRenderer
    >>>
    >>> # Create AST
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")]),
    ...     Paragraph(content=[Text(content="Hello world")])
    ... ])
    >>>
    >>> # Render to markdown
    >>> renderer = MarkdownRenderer()
    >>> markdown = renderer.render(doc)

"""

from __future__ import annotations

# Builder helpers
from all2md.ast.builder import DocumentBuilder, ListBuilder, TableBuilder
from all2md.ast.flavors import (
    CommonMarkFlavor,
    GFMFlavor,
    MarkdownFlavor,
    MarkdownPlusFlavor,
)

# Core node types
from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    SourceLocation,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)

# Renderer and flavors
from all2md.ast.renderer import MarkdownRenderer, RenderOptions

# Visitor pattern base
from all2md.ast.visitors import NodeVisitor, ValidationVisitor

__all__ = [
    # Nodes
    "Node",
    "SourceLocation",
    "Document",
    "Heading",
    "Paragraph",
    "CodeBlock",
    "BlockQuote",
    "List",
    "ListItem",
    "Table",
    "TableRow",
    "TableCell",
    "ThematicBreak",
    "HTMLBlock",
    "Text",
    "Emphasis",
    "Strong",
    "Code",
    "Link",
    "Image",
    "LineBreak",
    "Strikethrough",
    "Underline",
    "Superscript",
    "Subscript",
    "HTMLInline",
    # Visitors
    "NodeVisitor",
    "ValidationVisitor",
    # Renderer
    "MarkdownRenderer",
    "RenderOptions",
    # Flavors
    "MarkdownFlavor",
    "GFMFlavor",
    "CommonMarkFlavor",
    "MarkdownPlusFlavor",
    # Builders
    "ListBuilder",
    "TableBuilder",
    "DocumentBuilder",
]
