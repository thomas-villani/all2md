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
- serialization: JSON serialization and deserialization of AST structures
- transforms: AST transformation utilities (cloning, filtering, rewriting)
- builder: Helper classes for constructing complex AST structures

Examples
--------
Basic usage:

    >>> from all2md.ast import Document, Heading, Paragraph, Text
    >>> from all2md.renderers.markdown import MarkdownRenderer
    >>>
    >>> # Create AST
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")]),
    ...     Paragraph(content=[Text(content="Hello world")])
    ... ])
    >>>
    >>> # Render to markdown
    >>> renderer = MarkdownRenderer()
    >>> markdown = renderer.render_to_string(doc)

"""

from __future__ import annotations

# Builder helpers
from all2md.ast.builder import DocumentBuilder, ListBuilder, TableBuilder

# Core node types
from all2md.ast.nodes import (
    Alignment,
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
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
    get_node_children,
    replace_node_children,
)

# Section operations (extraction, TOC)
# Section primitives and querying
from all2md.ast.sections import (
    Section,
    count_sections,
    extract_sections,
    find_heading,
    generate_toc,
    get_all_sections,
    get_preamble,
    insert_toc,
    parse_section_ranges,
    query_sections,
)

# Serialization
from all2md.ast.serialization import ast_to_dict, ast_to_json, dict_to_ast, json_to_ast

# Document splitting strategies
from all2md.ast.splitting import DocumentSplitter, SplitResult, parse_split_spec

# Transforms
from all2md.ast.transforms import (
    HeadingLevelTransformer,
    LinkRewriter,
    NodeCollector,
    NodeTransformer,
    TextReplacer,
    clone_node,
    extract_nodes,
    filter_nodes,
    first_write_wins_merger,
    last_write_wins_merger,
    merge_documents,
    merge_lists_merger,
    transform_nodes,
)

# Utilities
from all2md.ast.utils import extract_text

# Visitor pattern base
from all2md.ast.visitors import NodeVisitor, ValidationVisitor

__all__ = [
    # Nodes
    "Node",
    "SourceLocation",
    "Alignment",
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
    "Comment",
    "CommentInline",
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
    "FootnoteReference",
    "FootnoteDefinition",
    "MathInline",
    "MathBlock",
    "DefinitionList",
    "DefinitionTerm",
    "DefinitionDescription",
    # Node helpers
    "get_node_children",
    "replace_node_children",
    # Visitors
    "NodeVisitor",
    "ValidationVisitor",
    # Builders
    "ListBuilder",
    "TableBuilder",
    "DocumentBuilder",
    # Serialization
    "ast_to_dict",
    "dict_to_ast",
    "ast_to_json",
    "json_to_ast",
    # Transforms
    "NodeTransformer",
    "NodeCollector",
    "clone_node",
    "extract_nodes",
    "filter_nodes",
    "transform_nodes",
    "merge_documents",
    "last_write_wins_merger",
    "first_write_wins_merger",
    "merge_lists_merger",
    "HeadingLevelTransformer",
    "LinkRewriter",
    "TextReplacer",
    # Utilities
    "extract_text",
    # Section primitives and querying
    "Section",
    "get_all_sections",
    "get_preamble",
    "parse_section_ranges",
    "query_sections",
    "count_sections",
    "find_heading",
    # Section operations
    "extract_sections",
    "generate_toc",
    "insert_toc",
    # Document splitting
    "DocumentSplitter",
    "SplitResult",
    "parse_split_spec",
]
