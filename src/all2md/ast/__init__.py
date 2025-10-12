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

# Serialization
from all2md.ast.serialization import ast_to_dict, ast_to_json, dict_to_ast, json_to_ast

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
    merge_documents,
    transform_nodes,
)

# Utilities
from all2md.ast.utils import extract_text

# Document manipulation utilities
from all2md.ast.document_utils import (
    Section,
    add_section_after,
    add_section_before,
    count_sections,
    extract_section,
    find_heading,
    find_section_by_heading,
    find_sections,
    generate_toc,
    get_all_sections,
    get_preamble,
    get_section_by_index,
    insert_into_section,
    insert_toc,
    remove_section,
    replace_section,
    split_by_sections,
)

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
    "HeadingLevelTransformer",
    "LinkRewriter",
    "TextReplacer",
    # Utilities
    "extract_text",
    # Document manipulation
    "Section",
    "get_all_sections",
    "find_section_by_heading",
    "find_sections",
    "get_section_by_index",
    "add_section_after",
    "add_section_before",
    "remove_section",
    "replace_section",
    "insert_into_section",
    "split_by_sections",
    "extract_section",
    "generate_toc",
    "insert_toc",
    "get_preamble",
    "count_sections",
    "find_heading",
]
