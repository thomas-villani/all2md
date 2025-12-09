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
from typing import Any, cast

from all2md.ast.nodes import (
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
)


def _add_metadata_and_source(result: dict[str, Any], node: Node) -> None:
    """Add metadata and source_location to result dict.

    Parameters
    ----------
    result : dict
        Dictionary to add fields to
    node : Node
        Node containing metadata and source_location

    """
    result["metadata"] = node.metadata
    if node.source_location:
        result["source_location"] = ast_to_dict(node.source_location)


def _serialize_source_location(node: SourceLocation) -> dict[str, Any]:
    """Serialize a SourceLocation node.

    Parameters
    ----------
    node : SourceLocation
        SourceLocation to serialize

    Returns
    -------
    dict
        Serialized SourceLocation

    """
    result: dict[str, Any] = {"node_type": "SourceLocation", "format": node.format}
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


def _serialize_children_node(node: Node, node_type: str) -> dict[str, Any]:
    """Serialize nodes with a 'children' attribute.

    Parameters
    ----------
    node : Node
        Node with children attribute
    node_type : str
        Type name for the node

    Returns
    -------
    dict
        Serialized node

    """
    result: dict[str, Any] = {
        "node_type": node_type,
        "children": [ast_to_dict(child) for child in node.children],  # type: ignore
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_inline_content_node(node: Node, node_type: str) -> dict[str, Any]:
    """Serialize inline nodes with a 'content' attribute containing child nodes.

    Parameters
    ----------
    node : Node
        Node with content attribute
    node_type : str
        Type name for the node

    Returns
    -------
    dict
        Serialized node

    """
    result: dict[str, Any] = {
        "node_type": node_type,
        "content": [ast_to_dict(child) for child in node.content],  # type: ignore
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_text_content_node(node: Node, node_type: str) -> dict[str, Any]:
    """Serialize nodes with a 'content' attribute containing text.

    Parameters
    ----------
    node : Node
        Node with string content attribute
    node_type : str
        Type name for the node

    Returns
    -------
    dict
        Serialized node

    """
    result: dict[str, Any] = {"node_type": node_type, "content": node.content}  # type: ignore
    _add_metadata_and_source(result, node)
    return result


def _serialize_heading(node: Heading) -> dict[str, Any]:
    """Serialize a Heading node."""
    result: dict[str, Any] = {
        "node_type": "Heading",
        "level": node.level,
        "content": [ast_to_dict(child) for child in node.content],
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_code_block(node: CodeBlock) -> dict[str, Any]:
    """Serialize a CodeBlock node."""
    result: dict[str, Any] = {
        "node_type": "CodeBlock",
        "content": node.content,
        "fence_char": node.fence_char,
        "fence_length": node.fence_length,
    }
    if node.language:
        result["language"] = node.language
    _add_metadata_and_source(result, node)
    return result


def _serialize_list(node: List) -> dict[str, Any]:
    """Serialize a List node."""
    result: dict[str, Any] = {
        "node_type": "List",
        "ordered": node.ordered,
        "items": [ast_to_dict(item) for item in node.items],
        "start": node.start,
        "tight": node.tight,
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_list_item(node: ListItem) -> dict[str, Any]:
    """Serialize a ListItem node."""
    result: dict[str, Any] = {
        "node_type": "ListItem",
        "children": [ast_to_dict(child) for child in node.children],
    }
    if node.task_status:
        result["task_status"] = node.task_status
    _add_metadata_and_source(result, node)
    return result


def _serialize_definition_list(node: DefinitionList) -> dict[str, Any]:
    """Serialize a DefinitionList node."""
    result: dict[str, Any] = {
        "node_type": "DefinitionList",
        "items": [
            {
                "term": ast_to_dict(term),
                "descriptions": [ast_to_dict(d) for d in descriptions],
            }
            for (term, descriptions) in node.items
        ],
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_table(node: Table) -> dict[str, Any]:
    """Serialize a Table node."""
    result: dict[str, Any] = {
        "node_type": "Table",
        "rows": [ast_to_dict(row) for row in node.rows],
    }
    if node.header:
        result["header"] = ast_to_dict(node.header)
    if node.alignments:
        result["alignments"] = node.alignments
    if node.caption:
        result["caption"] = node.caption
    _add_metadata_and_source(result, node)
    return result


def _serialize_table_row(node: TableRow) -> dict[str, Any]:
    """Serialize a TableRow node."""
    result: dict[str, Any] = {
        "node_type": "TableRow",
        "cells": [ast_to_dict(cell) for cell in node.cells],
        "is_header": node.is_header,
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_table_cell(node: TableCell) -> dict[str, Any]:
    """Serialize a TableCell node."""
    result: dict[str, Any] = {
        "node_type": "TableCell",
        "content": [ast_to_dict(child) for child in node.content],
        "colspan": node.colspan,
        "rowspan": node.rowspan,
    }
    if node.alignment:
        result["alignment"] = node.alignment
    _add_metadata_and_source(result, node)
    return result


def _serialize_math_node(node: MathInline | MathBlock, node_type: str) -> dict[str, Any]:
    """Serialize MathInline or MathBlock nodes."""
    result: dict[str, Any] = {
        "node_type": node_type,
        "content": node.content,
        "notation": node.notation,
    }
    if node.representations:
        result["representations"] = node.representations
    _add_metadata_and_source(result, node)
    return result


def _serialize_link(node: Link) -> dict[str, Any]:
    """Serialize a Link node."""
    result: dict[str, Any] = {
        "node_type": "Link",
        "url": node.url,
        "content": [ast_to_dict(child) for child in node.content],
    }
    if node.title:
        result["title"] = node.title
    _add_metadata_and_source(result, node)
    return result


def _serialize_image(node: Image) -> dict[str, Any]:
    """Serialize an Image node."""
    result: dict[str, Any] = {
        "node_type": "Image",
        "url": node.url,
        "alt_text": node.alt_text,
    }
    if node.title:
        result["title"] = node.title
    if node.width:
        result["width"] = node.width
    if node.height:
        result["height"] = node.height
    _add_metadata_and_source(result, node)
    return result


def _serialize_line_break(node: LineBreak) -> dict[str, Any]:
    """Serialize a LineBreak node."""
    result: dict[str, Any] = {"node_type": "LineBreak", "soft": node.soft}
    _add_metadata_and_source(result, node)
    return result


def _serialize_footnote_reference(node: FootnoteReference) -> dict[str, Any]:
    """Serialize a FootnoteReference node."""
    result: dict[str, Any] = {"node_type": "FootnoteReference", "identifier": node.identifier}
    _add_metadata_and_source(result, node)
    return result


def _serialize_footnote_definition(node: FootnoteDefinition) -> dict[str, Any]:
    """Serialize a FootnoteDefinition node."""
    result: dict[str, Any] = {
        "node_type": "FootnoteDefinition",
        "identifier": node.identifier,
        "content": [ast_to_dict(child) for child in node.content],
    }
    _add_metadata_and_source(result, node)
    return result


def _serialize_thematic_break(node: ThematicBreak) -> dict[str, Any]:
    """Serialize a ThematicBreak node."""
    result: dict[str, Any] = {"node_type": "ThematicBreak"}
    _add_metadata_and_source(result, node)
    return result


# Dispatch table mapping node types to their serialization functions
_SERIALIZATION_DISPATCH: dict[type, Any] = {
    SourceLocation: _serialize_source_location,
    Document: lambda n: _serialize_children_node(n, "Document"),
    BlockQuote: lambda n: _serialize_children_node(n, "BlockQuote"),
    Heading: _serialize_heading,
    Paragraph: lambda n: _serialize_inline_content_node(n, "Paragraph"),
    CodeBlock: _serialize_code_block,
    List: _serialize_list,
    ListItem: _serialize_list_item,
    DefinitionList: _serialize_definition_list,
    DefinitionTerm: lambda n: _serialize_inline_content_node(n, "DefinitionTerm"),
    DefinitionDescription: lambda n: _serialize_inline_content_node(n, "DefinitionDescription"),
    Table: _serialize_table,
    TableRow: _serialize_table_row,
    TableCell: _serialize_table_cell,
    ThematicBreak: _serialize_thematic_break,
    HTMLBlock: lambda n: _serialize_text_content_node(n, "HTMLBlock"),
    Text: lambda n: _serialize_text_content_node(n, "Text"),
    Emphasis: lambda n: _serialize_inline_content_node(n, "Emphasis"),
    Strong: lambda n: _serialize_inline_content_node(n, "Strong"),
    Strikethrough: lambda n: _serialize_inline_content_node(n, "Strikethrough"),
    Underline: lambda n: _serialize_inline_content_node(n, "Underline"),
    Superscript: lambda n: _serialize_inline_content_node(n, "Superscript"),
    Subscript: lambda n: _serialize_inline_content_node(n, "Subscript"),
    MathInline: lambda n: _serialize_math_node(n, "MathInline"),
    MathBlock: lambda n: _serialize_math_node(n, "MathBlock"),
    Code: lambda n: _serialize_text_content_node(n, "Code"),
    Link: _serialize_link,
    Image: _serialize_image,
    LineBreak: _serialize_line_break,
    HTMLInline: lambda n: _serialize_text_content_node(n, "HTMLInline"),
    FootnoteReference: _serialize_footnote_reference,
    FootnoteDefinition: _serialize_footnote_definition,
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
    node_class = type(node)
    serializer = _SERIALIZATION_DISPATCH.get(node_class)
    if serializer:
        return serializer(node)

    raise ValueError(f"Unknown node type for serialization: {node_class.__name__}")


# Helper functions for deserialization
def _deserialize_children(children_data: list[dict[str, Any]]) -> list[Node]:
    """Recursively deserialize a list of child nodes.

    Parameters
    ----------
    children_data : list[dict]
        List of dictionaries representing child nodes

    Returns
    -------
    list[Node]
        List of deserialized nodes

    """
    return [cast(Node, dict_to_ast(child)) for child in children_data]


def _deserialize_source_location(loc_data: dict[str, Any] | None) -> SourceLocation | None:
    """Deserialize a source location if present.

    Parameters
    ----------
    loc_data : dict or None
        Dictionary representing source location

    Returns
    -------
    SourceLocation or None
        Deserialized source location or None

    """
    return dict_to_ast(loc_data) if loc_data else None  # type: ignore


# Individual deserializer functions for each node type
def _deserialize_source_location_node(data: dict[str, Any]) -> SourceLocation:
    """Deserialize SourceLocation."""
    return SourceLocation(
        format=data["format"],
        page=data.get("page"),
        line=data.get("line"),
        column=data.get("column"),
        element_id=data.get("element_id"),
        metadata=data.get("metadata", {}),
    )


def _deserialize_document(data: dict[str, Any]) -> Document:
    """Deserialize Document node."""
    return Document(
        children=_deserialize_children(data.get("children", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_heading(data: dict[str, Any]) -> Heading:
    """Deserialize Heading node."""
    return Heading(
        level=data["level"],
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_paragraph(data: dict[str, Any]) -> Paragraph:
    """Deserialize Paragraph node."""
    return Paragraph(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_code_block(data: dict[str, Any]) -> CodeBlock:
    """Deserialize CodeBlock node."""
    return CodeBlock(
        content=data["content"],
        language=data.get("language"),
        fence_char=data.get("fence_char", "`"),
        fence_length=data.get("fence_length", 3),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_block_quote(data: dict[str, Any]) -> BlockQuote:
    """Deserialize BlockQuote node."""
    return BlockQuote(
        children=_deserialize_children(data.get("children", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_list(data: dict[str, Any]) -> List:
    """Deserialize List node."""
    return List(
        ordered=data["ordered"],
        items=_deserialize_children(data.get("items", [])),  # type: ignore
        start=data.get("start", 1),
        tight=data.get("tight", True),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_list_item(data: dict[str, Any]) -> ListItem:
    """Deserialize ListItem node."""
    return ListItem(
        children=_deserialize_children(data.get("children", [])),
        task_status=data.get("task_status"),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_definition_list(data: dict[str, Any]) -> DefinitionList:
    """Deserialize DefinitionList node."""
    items = [
        (
            dict_to_ast(item["term"]),
            [dict_to_ast(d) for d in item["descriptions"]],
        )
        for item in data.get("items", [])
    ]
    return DefinitionList(
        items=items,  # type: ignore
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_definition_term(data: dict[str, Any]) -> DefinitionTerm:
    """Deserialize DefinitionTerm node."""
    return DefinitionTerm(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_definition_description(data: dict[str, Any]) -> DefinitionDescription:
    """Deserialize DefinitionDescription node."""
    return DefinitionDescription(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_table(data: dict[str, Any]) -> Table:
    """Deserialize Table node."""
    return Table(
        rows=_deserialize_children(data.get("rows", [])),  # type: ignore
        header=dict_to_ast(data["header"]) if data.get("header") else None,  # type: ignore
        alignments=data.get("alignments", []),
        caption=data.get("caption"),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_table_row(data: dict[str, Any]) -> TableRow:
    """Deserialize TableRow node."""
    return TableRow(
        cells=_deserialize_children(data.get("cells", [])),  # type: ignore
        is_header=data.get("is_header", False),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_table_cell(data: dict[str, Any]) -> TableCell:
    """Deserialize TableCell node."""
    return TableCell(
        content=_deserialize_children(data.get("content", [])),
        colspan=data.get("colspan", 1),
        rowspan=data.get("rowspan", 1),
        alignment=data.get("alignment"),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_thematic_break(data: dict[str, Any]) -> ThematicBreak:
    """Deserialize ThematicBreak node."""
    return ThematicBreak(
        metadata=data.get("metadata", {}), source_location=_deserialize_source_location(data.get("source_location"))
    )


def _deserialize_html_block(data: dict[str, Any]) -> HTMLBlock:
    """Deserialize HTMLBlock node."""
    return HTMLBlock(
        content=data["content"],
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_text(data: dict[str, Any]) -> Text:
    """Deserialize Text node."""
    return Text(
        content=data["content"],
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_emphasis(data: dict[str, Any]) -> Emphasis:
    """Deserialize Emphasis node."""
    return Emphasis(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_strong(data: dict[str, Any]) -> Strong:
    """Deserialize Strong node."""
    return Strong(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_strikethrough(data: dict[str, Any]) -> Strikethrough:
    """Deserialize Strikethrough node."""
    return Strikethrough(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_underline(data: dict[str, Any]) -> Underline:
    """Deserialize Underline node."""
    return Underline(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_superscript(data: dict[str, Any]) -> Superscript:
    """Deserialize Superscript node."""
    return Superscript(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_subscript(data: dict[str, Any]) -> Subscript:
    """Deserialize Subscript node."""
    return Subscript(
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_code(data: dict[str, Any]) -> Code:
    """Deserialize Code node."""
    return Code(
        content=data["content"],
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_link(data: dict[str, Any]) -> Link:
    """Deserialize Link node."""
    return Link(
        url=data["url"],
        content=_deserialize_children(data.get("content", [])),
        title=data.get("title"),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_image(data: dict[str, Any]) -> Image:
    """Deserialize Image node."""
    return Image(
        url=data["url"],
        alt_text=data.get("alt_text", ""),
        title=data.get("title"),
        width=data.get("width"),
        height=data.get("height"),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_line_break(data: dict[str, Any]) -> LineBreak:
    """Deserialize LineBreak node."""
    return LineBreak(
        soft=data.get("soft", False),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_html_inline(data: dict[str, Any]) -> HTMLInline:
    """Deserialize HTMLInline node."""
    return HTMLInline(
        content=data["content"],
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_math_inline(data: dict[str, Any]) -> MathInline:
    """Deserialize MathInline node."""
    return MathInline(
        content=data.get("content", ""),
        notation=data.get("notation", "latex"),
        representations=data.get("representations", {}).copy(),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_math_block(data: dict[str, Any]) -> MathBlock:
    """Deserialize MathBlock node."""
    return MathBlock(
        content=data.get("content", ""),
        notation=data.get("notation", "latex"),
        representations=data.get("representations", {}).copy(),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_footnote_reference(data: dict[str, Any]) -> FootnoteReference:
    """Deserialize FootnoteReference node."""
    return FootnoteReference(
        identifier=data["identifier"],
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


def _deserialize_footnote_definition(data: dict[str, Any]) -> FootnoteDefinition:
    """Deserialize FootnoteDefinition node."""
    return FootnoteDefinition(
        identifier=data["identifier"],
        content=_deserialize_children(data.get("content", [])),
        metadata=data.get("metadata", {}),
        source_location=_deserialize_source_location(data.get("source_location")),
    )


# Dispatch table mapping node type strings to deserializer functions
_DESERIALIZATION_DISPATCH: dict[str, Any] = {
    "SourceLocation": _deserialize_source_location_node,
    "Document": _deserialize_document,
    "Heading": _deserialize_heading,
    "Paragraph": _deserialize_paragraph,
    "CodeBlock": _deserialize_code_block,
    "BlockQuote": _deserialize_block_quote,
    "List": _deserialize_list,
    "ListItem": _deserialize_list_item,
    "DefinitionList": _deserialize_definition_list,
    "DefinitionTerm": _deserialize_definition_term,
    "DefinitionDescription": _deserialize_definition_description,
    "Table": _deserialize_table,
    "TableRow": _deserialize_table_row,
    "TableCell": _deserialize_table_cell,
    "ThematicBreak": _deserialize_thematic_break,
    "HTMLBlock": _deserialize_html_block,
    "Text": _deserialize_text,
    "Emphasis": _deserialize_emphasis,
    "Strong": _deserialize_strong,
    "Strikethrough": _deserialize_strikethrough,
    "Underline": _deserialize_underline,
    "Superscript": _deserialize_superscript,
    "Subscript": _deserialize_subscript,
    "Code": _deserialize_code,
    "Link": _deserialize_link,
    "Image": _deserialize_image,
    "LineBreak": _deserialize_line_break,
    "HTMLInline": _deserialize_html_inline,
    "MathInline": _deserialize_math_inline,
    "MathBlock": _deserialize_math_block,
    "FootnoteReference": _deserialize_footnote_reference,
    "FootnoteDefinition": _deserialize_footnote_definition,
}


def dict_to_ast(data: dict[str, Any], strict_mode: bool = True) -> Node | SourceLocation:
    """Convert a dictionary representation back to an AST node.

    Parameters
    ----------
    data : dict
        Dictionary representation of a node
    strict_mode : bool, default True
        If True, raise ValueError on unknown node types.
        If False, skip unknown nodes (useful for forward compatibility).

    Returns
    -------
    Node or SourceLocation
        Reconstructed AST node

    Raises
    ------
    ValueError
        If the dictionary contains an unknown node type and strict_mode is True

    Examples
    --------
    >>> data = {'node_type': 'Text', 'content': 'Hello', 'metadata': {}, 'source_location': None}
    >>> node = dict_to_ast(data)
    >>> print(node.content)
    Hello

    """
    import logging

    logger = logging.getLogger(__name__)

    node_type = data.get("node_type")
    if not node_type:
        if strict_mode:
            raise ValueError("Dictionary must contain 'node_type' field")
        else:
            logger.warning("Dictionary missing 'node_type' field, skipping")
            # Return a placeholder Text node for robustness
            from all2md.ast import Text

            return Text(content="")

    deserializer = _DESERIALIZATION_DISPATCH.get(node_type)
    if not deserializer:
        if strict_mode:
            raise ValueError(f"Unknown node type: {node_type}")
        else:
            logger.warning(f"Unknown node type '{node_type}', skipping")
            # Return a placeholder Text node for robustness
            from all2md.ast import Text

            return Text(content=f"[Unknown node type: {node_type}]")

    return deserializer(data)


def ast_to_json(node: Node, indent: int | None = None) -> str:
    """Serialize an AST node to JSON string with schema versioning.

    The serialized JSON includes a schema_version field to enable migration
    paths for future AST evolution. Unicode characters are preserved without
    escape sequences for improved readability.

    Parameters
    ----------
    node : Node
        The AST node to serialize
    indent : int or None, default = None
        Number of spaces for indentation (None for compact format)

    Returns
    -------
    str
        JSON string representation with schema version

    Notes
    -----
    The output format includes a schema_version field:
        {"schema_version": 1, "node_type": "...", ...}

    Examples
    --------
    >>> from all2md.ast import Document, Paragraph, Text
    >>> doc = Document(children=[
    ...     Paragraph(content=[Text(content="Hello")])
    ... ])
    >>> json_str = ast_to_json(doc, indent=2)
    >>> print(json_str)

    """
    node_dict = ast_to_dict(node)
    # Add schema version at the root level for future migration support
    versioned_dict = {"schema_version": 1, **node_dict}
    # Use ensure_ascii=False to preserve Unicode characters
    return json.dumps(versioned_dict, indent=indent, ensure_ascii=False)


def json_to_ast(json_str: str, validate_schema: bool = True, strict_mode: bool = True) -> Node:
    """Deserialize a JSON string to an AST node.

    This function handles schema versioning to support future AST evolution.
    If no schema_version is present in the JSON (for backward compatibility),
    it assumes version 1.

    Parameters
    ----------
    json_str : str
        JSON string representation
    validate_schema : bool, default True
        If True, validate schema version and raise errors on unsupported versions.
        If False, skip schema validation (useful for forward compatibility).
    strict_mode : bool, default True
        If True, raise ValueError on unknown node types or attributes.
        If False, log warnings and skip unknown elements (useful for forward compatibility).

    Returns
    -------
    Node
        Reconstructed AST node

    Raises
    ------
    ValueError
        If JSON is invalid, contains unknown node types, or has an
        unsupported schema version (when validate_schema=True or strict_mode=True)
    json.JSONDecodeError
        If JSON string is malformed

    Notes
    -----
    Backward compatibility is maintained for JSON without schema_version field.

    Examples
    --------
    >>> json_str = '{"schema_version": 1, "node_type": "Text", "content": "Hello"}'
    >>> node = json_to_ast(json_str)
    >>> print(node.content)
    Hello

    Optional validation allows forward compatibility:

    >>> # With validation disabled, can load newer schema versions
    >>> node = json_to_ast(future_json, validate_schema=False, strict_mode=False)

    """
    import logging

    logger = logging.getLogger(__name__)

    data = json.loads(json_str)

    # Extract and validate schema version
    schema_version = data.pop("schema_version", None)

    if validate_schema:
        if schema_version is None:
            # Backward compatibility: if no version specified, assume version 1
            schema_version = 1
        if not isinstance(schema_version, int):
            raise ValueError(f"Schema version must be an integer, got {type(schema_version).__name__}")
        elif schema_version != 1:
            raise ValueError(
                f"Unsupported schema version: {schema_version}. "
                f"This version of all2md supports schema version 1 only."
            )
    else:
        # Schema validation disabled - just log a warning if version differs
        if schema_version is not None and schema_version != 1:
            logger.warning(
                f"Schema version {schema_version} differs from supported version 1. "
                f"Attempting to parse anyway (schema validation disabled)."
            )

    return dict_to_ast(data, strict_mode=strict_mode)  # type: ignore


__all__ = [
    "ast_to_dict",
    "dict_to_ast",
    "ast_to_json",
    "json_to_ast",
]
