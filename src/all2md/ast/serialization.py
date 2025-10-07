#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/serialization.py
"""JSON serialization and deserialization for AST nodes.

This module provides utilities for converting AST structures to and from JSON format,
enabling persistence, transmission, and interoperability with other tools.

The JSON format preserves:
- All node types and their attributes
- Metadata and source location information
- Document structure and nesting
- Round-trip compatibility (AST → JSON → AST produces identical structure)

Examples
--------
Serialize AST to JSON:

    >>> from all2md.ast import Document, Heading, Text
    >>> from all2md.ast.serialization import ast_to_json
    >>>
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")])
    ... ])
    >>> json_str = ast_to_json(doc, indent=2)
    >>> print(json_str)

Deserialize JSON back to AST:

    >>> from all2md.ast.serialization import json_to_ast
    >>> doc = json_to_ast(json_str)
    >>> print(doc.children[0].level)
    1

"""

from __future__ import annotations

import json
from typing import Any

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
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
)

# Mapping from node class names to classes for deserialization
_NODE_TYPE_MAP = {
    "Document": Document,
    "Heading": Heading,
    "Paragraph": Paragraph,
    "CodeBlock": CodeBlock,
    "BlockQuote": BlockQuote,
    "List": List,
    "ListItem": ListItem,
    "DefinitionList": DefinitionList,
    "DefinitionTerm": DefinitionTerm,
    "DefinitionDescription": DefinitionDescription,
    "Table": Table,
    "TableRow": TableRow,
    "TableCell": TableCell,
    "ThematicBreak": ThematicBreak,
    "HTMLBlock": HTMLBlock,
    "Text": Text,
    "Emphasis": Emphasis,
    "Strong": Strong,
    "Code": Code,
    "Link": Link,
    "Image": Image,
    "LineBreak": LineBreak,
    "Strikethrough": Strikethrough,
    "Underline": Underline,
    "Superscript": Superscript,
    "Subscript": Subscript,
    "HTMLInline": HTMLInline,
    "MathInline": MathInline,
    "MathBlock": MathBlock,
    "SourceLocation": SourceLocation,
}


def ast_to_dict(node: Node | SourceLocation) -> dict[str, Any]:
    """Convert an AST node to a dictionary representation.

    Parameters
    ----------
    node : Node or SourceLocation
        The AST node to convert

    Returns
    -------
    dict
        Dictionary representation of the node

    Examples
    --------
    >>> from all2md.ast import Text
    >>> text = Text(content="Hello")
    >>> ast_to_dict(text)
    {'node_type': 'Text', 'content': 'Hello', 'metadata': {}, 'source_location': None}

    """
    node_type = type(node).__name__
    result: dict[str, Any] = {"node_type": node_type}

    # Handle SourceLocation specially
    if isinstance(node, SourceLocation):
        result["format"] = node.format
        if node.page is not None:
            result["page"] = node.page
        if node.line is not None:
            result["line"] = node.line
        if node.column is not None:
            result["column"] = node.column
        if node.element_id is not None:
            result["element_id"] = node.element_id
        if node.metadata:
            result["metadata"] = node.metadata
        return result

    # Convert node attributes to dict
    if isinstance(node, Document):
        result["children"] = [ast_to_dict(child) for child in node.children]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Heading):
        result["level"] = node.level
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Paragraph):
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, CodeBlock):
        result["content"] = node.content
        if node.language:
            result["language"] = node.language
        result["fence_char"] = node.fence_char
        result["fence_length"] = node.fence_length
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, BlockQuote):
        result["children"] = [ast_to_dict(child) for child in node.children]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, List):
        result["ordered"] = node.ordered
        result["items"] = [ast_to_dict(item) for item in node.items]
        result["start"] = node.start
        result["tight"] = node.tight
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, ListItem):
        result["children"] = [ast_to_dict(child) for child in node.children]
        if node.task_status:
            result["task_status"] = node.task_status
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, DefinitionList):
        result["items"] = [
            {
                "term": ast_to_dict(term),
                "descriptions": [ast_to_dict(d) for d in descriptions],
            }
            for (term, descriptions) in node.items
        ]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, DefinitionTerm):
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, DefinitionDescription):
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Table):
        result["rows"] = [ast_to_dict(row) for row in node.rows]
        if node.header:
            result["header"] = ast_to_dict(node.header)
        if node.alignments:
            result["alignments"] = node.alignments
        if node.caption:
            result["caption"] = node.caption
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, TableRow):
        result["cells"] = [ast_to_dict(cell) for cell in node.cells]
        result["is_header"] = node.is_header
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, TableCell):
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["colspan"] = node.colspan
        result["rowspan"] = node.rowspan
        if node.alignment:
            result["alignment"] = node.alignment
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, (ThematicBreak, HTMLBlock)):
        if isinstance(node, HTMLBlock):
            result["content"] = node.content
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Text):
        result["content"] = node.content
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, (Emphasis, Strong, Strikethrough, Underline, Superscript, Subscript)):
        result["content"] = [ast_to_dict(child) for child in node.content]
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, MathInline):
        result["content"] = node.content
        result["notation"] = node.notation
        if node.representations:
            result["representations"] = node.representations
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, MathBlock):
        result["content"] = node.content
        result["notation"] = node.notation
        if node.representations:
            result["representations"] = node.representations
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Code):
        result["content"] = node.content
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Link):
        result["url"] = node.url
        result["content"] = [ast_to_dict(child) for child in node.content]
        if node.title:
            result["title"] = node.title
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, Image):
        result["url"] = node.url
        result["alt_text"] = node.alt_text
        if node.title:
            result["title"] = node.title
        if node.width:
            result["width"] = node.width
        if node.height:
            result["height"] = node.height
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, LineBreak):
        result["soft"] = node.soft
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    elif isinstance(node, HTMLInline):
        result["content"] = node.content
        result["metadata"] = node.metadata
        if node.source_location:
            result["source_location"] = ast_to_dict(node.source_location)

    return result


def dict_to_ast(data: dict[str, Any]) -> Node | SourceLocation:
    """Convert a dictionary representation back to an AST node.

    Parameters
    ----------
    data : dict
        Dictionary representation of a node

    Returns
    -------
    Node or SourceLocation
        Reconstructed AST node

    Raises
    ------
    ValueError
        If the dictionary contains an unknown node type

    Examples
    --------
    >>> data = {'node_type': 'Text', 'content': 'Hello', 'metadata': {}, 'source_location': None}
    >>> node = dict_to_ast(data)
    >>> print(node.content)
    Hello

    """
    node_type = data.get("node_type")
    if not node_type:
        raise ValueError("Dictionary must contain 'node_type' field")

    node_class = _NODE_TYPE_MAP.get(node_type)
    if not node_class:
        raise ValueError(f"Unknown node type: {node_type}")

    # Handle SourceLocation
    if node_type == "SourceLocation":
        return SourceLocation(
            format=data["format"],
            page=data.get("page"),
            line=data.get("line"),
            column=data.get("column"),
            element_id=data.get("element_id"),
            metadata=data.get("metadata", {}),
        )

    # Helper to recursively deserialize
    def deserialize_children(children_data: list[dict[str, Any]]) -> list[Node]:
        return [dict_to_ast(child) for child in children_data]

    def deserialize_source_location(loc_data: dict[str, Any] | None) -> SourceLocation | None:
        return dict_to_ast(loc_data) if loc_data else None  # type: ignore

    # Reconstruct node based on type
    metadata = data.get("metadata", {})
    source_location = deserialize_source_location(data.get("source_location"))

    if node_type == "Document":
        return Document(
            children=deserialize_children(data.get("children", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "Heading":
        return Heading(
            level=data["level"],
            content=deserialize_children(data.get("content", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "Paragraph":
        return Paragraph(
            content=deserialize_children(data.get("content", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "CodeBlock":
        return CodeBlock(
            content=data["content"],
            language=data.get("language"),
            fence_char=data.get("fence_char", "`"),
            fence_length=data.get("fence_length", 3),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "BlockQuote":
        return BlockQuote(
            children=deserialize_children(data.get("children", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "List":
        return List(
            ordered=data["ordered"],
            items=deserialize_children(data.get("items", [])),  # type: ignore
            start=data.get("start", 1),
            tight=data.get("tight", True),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "ListItem":
        return ListItem(
            children=deserialize_children(data.get("children", [])),
            task_status=data.get("task_status"),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "DefinitionList":
        items = [
            (
                dict_to_ast(item["term"]),
                [dict_to_ast(d) for d in item["descriptions"]],
            )
            for item in data.get("items", [])
        ]
        return DefinitionList(
            items=items,  # type: ignore
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "DefinitionTerm":
        return DefinitionTerm(
            content=deserialize_children(data.get("content", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "DefinitionDescription":
        return DefinitionDescription(
            content=deserialize_children(data.get("content", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "Table":
        return Table(
            rows=deserialize_children(data.get("rows", [])),  # type: ignore
            header=dict_to_ast(data["header"]) if data.get("header") else None,  # type: ignore
            alignments=data.get("alignments", []),
            caption=data.get("caption"),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "TableRow":
        return TableRow(
            cells=deserialize_children(data.get("cells", [])),  # type: ignore
            is_header=data.get("is_header", False),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "TableCell":
        return TableCell(
            content=deserialize_children(data.get("content", [])),
            colspan=data.get("colspan", 1),
            rowspan=data.get("rowspan", 1),
            alignment=data.get("alignment"),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "ThematicBreak":
        return ThematicBreak(metadata=metadata, source_location=source_location)

    elif node_type == "HTMLBlock":
        return HTMLBlock(content=data["content"], metadata=metadata, source_location=source_location)

    elif node_type == "Text":
        return Text(content=data["content"], metadata=metadata, source_location=source_location)

    elif node_type in ("Emphasis", "Strong", "Strikethrough", "Underline", "Superscript", "Subscript"):
        return node_class(  # type: ignore
            content=deserialize_children(data.get("content", [])),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "Code":
        return Code(content=data["content"], metadata=metadata, source_location=source_location)

    elif node_type == "Link":
        return Link(
            url=data["url"],
            content=deserialize_children(data.get("content", [])),
            title=data.get("title"),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "Image":
        return Image(
            url=data["url"],
            alt_text=data.get("alt_text", ""),
            title=data.get("title"),
            width=data.get("width"),
            height=data.get("height"),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "LineBreak":
        return LineBreak(soft=data.get("soft", False), metadata=metadata, source_location=source_location)

    elif node_type == "HTMLInline":
        return HTMLInline(content=data["content"], metadata=metadata, source_location=source_location)

    elif node_type == "MathInline":
        return MathInline(
            content=data.get("content", ""),
            notation=data.get("notation", "latex"),
            representations=data.get("representations", {}).copy(),
            metadata=metadata,
            source_location=source_location,
        )

    elif node_type == "MathBlock":
        return MathBlock(
            content=data.get("content", ""),
            notation=data.get("notation", "latex"),
            representations=data.get("representations", {}).copy(),
            metadata=metadata,
            source_location=source_location,
        )

    raise ValueError(f"Unhandled node type in deserialization: {node_type}")


def ast_to_json(node: Node, indent: int | None = None) -> str:
    """Serialize an AST node to JSON string.

    Parameters
    ----------
    node : Node
        The AST node to serialize
    indent : int or None, default = None
        Number of spaces for indentation (None for compact format)

    Returns
    -------
    str
        JSON string representation

    Examples
    --------
    >>> from all2md.ast import Document, Paragraph, Text
    >>> doc = Document(children=[
    ...     Paragraph(content=[Text(content="Hello")])
    ... ])
    >>> json_str = ast_to_json(doc, indent=2)
    >>> print(json_str)

    """
    return json.dumps(ast_to_dict(node), indent=indent)


def json_to_ast(json_str: str) -> Node:
    """Deserialize a JSON string to an AST node.

    Parameters
    ----------
    json_str : str
        JSON string representation

    Returns
    -------
    Node
        Reconstructed AST node

    Raises
    ------
    ValueError
        If JSON is invalid or contains unknown node types
    json.JSONDecodeError
        If JSON string is malformed

    Examples
    --------
    >>> json_str = '{"node_type": "Text", "content": "Hello", "metadata": {}, "source_location": null}'
    >>> node = json_to_ast(json_str)
    >>> print(node.content)
    Hello

    """
    data = json.loads(json_str)
    return dict_to_ast(data)  # type: ignore


__all__ = [
    "ast_to_dict",
    "dict_to_ast",
    "ast_to_json",
    "json_to_ast",
]
