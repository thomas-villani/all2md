#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/transforms.py
"""AST transformation and manipulation utilities.

This module provides visitors and utilities for transforming and manipulating AST structures.
It enables filtering nodes, applying transformations, cloning trees, and performing common
document processing tasks.

Examples
--------
Extract all headings from a document:

    >>> from all2md.ast import transforms
    >>> headings = transforms.extract_nodes(doc, Heading)
    >>> for heading in headings:
    ...     print(f"Level {heading.level}: {heading.content}")

Remove all images from a document:

    >>> filtered_doc = transforms.filter_nodes(doc, lambda n: not isinstance(n, Image))

Change heading levels:

    >>> transformer = transforms.HeadingLevelTransformer(offset=1)
    >>> new_doc = transforms.transform_nodes(doc, transformer)

"""

from __future__ import annotations

import copy
import re
from typing import Any, Callable, Pattern, Type

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
from all2md.ast.visitors import NodeVisitor
from all2md.constants import SAFE_LINK_SCHEMES


def _validate_url_scheme(url: str, context: str = "URL") -> None:
    """Validate URL scheme for security.

    This function checks URLs for dangerous schemes (javascript:, vbscript:, etc.)
    and validates that URLs with schemes use recognized safe schemes.

    Parameters
    ----------
    url : str
        URL to validate
    context : str, default = "URL"
        Context description for error messages (e.g., "Link", "Image")

    Raises
    ------
    ValueError
        If URL uses a dangerous scheme or unrecognized scheme

    Examples
    --------
    >>> _validate_url_scheme("https://example.com")  # Safe
    >>> _validate_url_scheme("javascript:alert(1)")  # Raises ValueError

    """
    from all2md.utils.security import is_relative_url, is_url_scheme_dangerous

    if not url:
        return

    url_lower = url.lower()

    # Check for dangerous schemes using consolidated utility
    if is_url_scheme_dangerous(url):
        # Extract scheme for error message
        scheme = url_lower.split(":", 1)[0] if ":" in url_lower else "unknown"
        raise ValueError(
            f"{context} URL uses dangerous scheme '{scheme}': {url[:50]}"
        )

    # Check if URL has a scheme with ://
    if "://" in url:
        # Extract scheme
        scheme = url.split("://", 1)[0].lower()

        # Check if scheme is in safe list (strict allowlist validation)
        if scheme not in SAFE_LINK_SCHEMES:
            raise ValueError(
                f"{context} URL has unrecognized scheme '{scheme}': {url[:50]}"
            )
    else:
        # Check for scheme-like patterns without ://
        # This catches things like "javascript:alert(1)" which don't have ://
        if ":" in url and not is_relative_url(url):
            potential_scheme = url.split(":", 1)[0].lower()
            # If it looks like a scheme but isn't dangerous, check if it's recognized
            # (already checked for dangerous schemes above)
            if potential_scheme not in SAFE_LINK_SCHEMES:
                raise ValueError(
                    f"{context} URL uses unrecognized scheme '{potential_scheme}': {url[:50]}"
                )


class NodeTransformer(NodeVisitor):
    """Base class for transforming AST nodes.

    Subclasses should implement visit_* methods that return modified nodes
    or None to remove nodes. The transformer creates a new AST with the
    transformations applied.

    Examples
    --------
    >>> class UppercaseTransformer(NodeTransformer):
    ...     def visit_text(self, node):
    ...         return Text(content=node.content.upper())
    >>>
    >>> transformer = UppercaseTransformer()
    >>> new_doc = transformer.transform(doc)

    """

    def transform(self, node: Node) -> Node | None:
        """Transform an AST node.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node or None
            Transformed node or None to remove

        """
        return node.accept(self)

    def _transform_children(self, children: list[Node]) -> list[Node]:
        """Transform a list of child nodes.

        Parameters
        ----------
        children : list of Node
            Children to transform

        Returns
        -------
        list of Node
            Transformed children (filtered for None values)

        """
        result = []
        for child in children:
            transformed = self.transform(child)
            if transformed is not None:
                result.append(transformed)
        return result

    def _generic_transform(self, node: Node) -> Node:
        """Transform nodes generically using traversal helpers.

        This method provides a generic way to transform nodes by automatically
        handling child traversal and reconstruction. Individual visit_* methods
        can use this for simple transformations or override it for complex cases.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node
            Transformed node with children replaced

        Notes
        -----
        This method uses get_node_children and replace_node_children helpers
        to minimize boilerplate in visitor implementations.

        """
        from all2md.ast.nodes import get_node_children, replace_node_children

        children = get_node_children(node)
        if not children:
            # Leaf node - return a copy
            from dataclasses import replace
            return replace(node)  # type: ignore[type-var]

        # Transform children and rebuild node
        transformed_children = self._transform_children(children)
        return replace_node_children(node, transformed_children)

    def visit_document(self, node: Document) -> Document:
        """Transform a Document node."""
        return Document(
            children=self._transform_children(node.children),
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_heading(self, node: Heading) -> Heading:
        """Transform a Heading node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_paragraph(self, node: Paragraph) -> Paragraph:
        """Transform a Paragraph node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_code_block(self, node: CodeBlock) -> CodeBlock:
        """Transform a CodeBlock node."""
        return CodeBlock(
            content=node.content,
            language=node.language,
            fence_char=node.fence_char,
            fence_length=node.fence_length,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_block_quote(self, node: BlockQuote) -> BlockQuote:
        """Transform a BlockQuote node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_list(self, node: List) -> List:
        """Transform a List node."""
        return List(
            ordered=node.ordered,
            items=self._transform_children(node.items),  # type: ignore
            start=node.start,
            tight=node.tight,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_list_item(self, node: ListItem) -> ListItem:
        """Transform a ListItem node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_table(self, node: Table) -> Table:
        """Transform a Table node."""
        return Table(
            rows=self._transform_children(node.rows),  # type: ignore
            header=self.transform(node.header) if node.header else None,  # type: ignore
            alignments=node.alignments.copy(),
            caption=node.caption,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_table_row(self, node: TableRow) -> TableRow:
        """Transform a TableRow node."""
        return TableRow(
            cells=self._transform_children(node.cells),  # type: ignore
            is_header=node.is_header,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_table_cell(self, node: TableCell) -> TableCell:
        """Transform a TableCell node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_thematic_break(self, node: ThematicBreak) -> ThematicBreak:
        """Transform a ThematicBreak node."""
        return ThematicBreak(metadata=node.metadata.copy(), source_location=node.source_location)

    def visit_html_block(self, node: HTMLBlock) -> HTMLBlock:
        """Transform an HTMLBlock node."""
        return HTMLBlock(
            content=node.content, metadata=node.metadata.copy(), source_location=node.source_location
        )

    def visit_text(self, node: Text) -> Text:
        """Transform a Text node."""
        return Text(content=node.content, metadata=node.metadata.copy(), source_location=node.source_location)

    def visit_emphasis(self, node: Emphasis) -> Emphasis:
        """Transform an Emphasis node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_strong(self, node: Strong) -> Strong:
        """Transform a Strong node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_code(self, node: Code) -> Code:
        """Transform a Code node."""
        return Code(content=node.content, metadata=node.metadata.copy(), source_location=node.source_location)

    def visit_link(self, node: Link) -> Link:
        """Transform a Link node."""
        return Link(
            url=node.url,
            content=self._transform_children(node.content),
            title=node.title,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_image(self, node: Image) -> Image:
        """Transform an Image node."""
        return Image(
            url=node.url,
            alt_text=node.alt_text,
            title=node.title,
            width=node.width,
            height=node.height,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_line_break(self, node: LineBreak) -> LineBreak:
        """Transform a LineBreak node."""
        return LineBreak(soft=node.soft, metadata=node.metadata.copy(), source_location=node.source_location)

    def visit_strikethrough(self, node: Strikethrough) -> Strikethrough:
        """Transform a Strikethrough node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_underline(self, node: Underline) -> Underline:
        """Transform an Underline node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_superscript(self, node: Superscript) -> Superscript:
        """Transform a Superscript node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_subscript(self, node: Subscript) -> Subscript:
        """Transform a Subscript node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_html_inline(self, node: HTMLInline) -> HTMLInline:
        """Transform an HTMLInline node."""
        return HTMLInline(
            content=node.content, metadata=node.metadata.copy(), source_location=node.source_location
        )

    def visit_footnote_reference(self, node: "FootnoteReference") -> "FootnoteReference":
        """Transform a FootnoteReference node."""
        return FootnoteReference(
            identifier=node.identifier,
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )

    def visit_math_inline(self, node: "MathInline") -> "MathInline":
        """Transform a MathInline node."""
        return MathInline(
            content=node.content,
            notation=node.notation,
            representations=node.representations.copy(),
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )

    def visit_footnote_definition(self, node: "FootnoteDefinition") -> "FootnoteDefinition":
        """Transform a FootnoteDefinition node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_definition_list(self, node: "DefinitionList") -> "DefinitionList":
        """Transform a DefinitionList node."""
        transformed_items = []
        for term, descriptions in node.items:
            t_term = self.transform(term)
            if t_term is None:
                continue
            t_descs = [d for d in (self.transform(desc) for desc in descriptions) if d is not None]
            if not t_descs:
                continue
            transformed_items.append((t_term, t_descs))
        return DefinitionList(
            items=transformed_items,  # type: ignore
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )

    def visit_definition_term(self, node: "DefinitionTerm") -> "DefinitionTerm":
        """Transform a DefinitionTerm node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_definition_description(self, node: "DefinitionDescription") -> "DefinitionDescription":
        """Transform a DefinitionDescription node."""
        return self._generic_transform(node)  # type: ignore[return-value]

    def visit_math_block(self, node: "MathBlock") -> "MathBlock":
        """Transform a MathBlock node."""
        return MathBlock(
            content=node.content,
            notation=node.notation,
            representations=node.representations.copy(),
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )


class NodeCollector(NodeVisitor):
    """Visitor that collects nodes matching a condition.

    Parameters
    ----------
    predicate : callable or None, default = None
        Function that takes a node and returns True to collect it

    """

    def __init__(self, predicate: Callable[[Node], bool] | None = None):
        """Initialize the collector with an optional predicate function."""
        self.predicate = predicate or (lambda n: True)
        self.collected: list[Node] = []

    def _collect_if_match(self, node: Node) -> None:
        """Collect node if it matches the predicate."""
        if self.predicate(node):
            self.collected.append(node)

    def _visit_children(self, children: list[Node]) -> None:
        """Visit all children nodes."""
        for child in children:
            child.accept(self)

    def _generic_visit(self, node: Node) -> None:
        """Collect nodes generically using traversal helpers.

        This method provides a generic way to collect nodes by automatically
        handling child traversal. Individual visit_* methods can use this
        to reduce boilerplate.

        Parameters
        ----------
        node : Node
            Node to visit

        Notes
        -----
        This method uses get_node_children helper to minimize boilerplate
        in visitor implementations.

        """
        from all2md.ast.nodes import get_node_children

        self._collect_if_match(node)
        children = get_node_children(node)
        self._visit_children(children)

    def visit_document(self, node: Document) -> None:
        """Visit a Document node."""
        self._collect_if_match(node)
        self._visit_children(node.children)

    def visit_heading(self, node: Heading) -> None:
        """Visit a Heading node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_paragraph(self, node: Paragraph) -> None:
        """Visit a Paragraph node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Visit a CodeBlock node."""
        self._collect_if_match(node)

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Visit a BlockQuote node."""
        self._collect_if_match(node)
        self._visit_children(node.children)

    def visit_list(self, node: List) -> None:
        """Visit a List node."""
        self._collect_if_match(node)
        self._visit_children(node.items)  # type: ignore

    def visit_list_item(self, node: ListItem) -> None:
        """Visit a ListItem node."""
        self._collect_if_match(node)
        self._visit_children(node.children)

    def visit_table(self, node: Table) -> None:
        """Visit a Table node."""
        self._collect_if_match(node)
        if node.header:
            node.header.accept(self)
        self._visit_children(node.rows)  # type: ignore

    def visit_table_row(self, node: TableRow) -> None:
        """Visit a TableRow node."""
        self._collect_if_match(node)
        self._visit_children(node.cells)  # type: ignore

    def visit_table_cell(self, node: TableCell) -> None:
        """Visit a TableCell node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Visit a ThematicBreak node."""
        self._collect_if_match(node)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Visit an HTMLBlock node."""
        self._collect_if_match(node)

    def visit_text(self, node: Text) -> None:
        """Visit a Text node."""
        self._collect_if_match(node)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Visit an Emphasis node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_strong(self, node: Strong) -> None:
        """Visit a Strong node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_code(self, node: Code) -> None:
        """Visit a Code node."""
        self._collect_if_match(node)

    def visit_link(self, node: Link) -> None:
        """Visit a Link node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_image(self, node: Image) -> None:
        """Visit an Image node."""
        self._collect_if_match(node)

    def visit_line_break(self, node: LineBreak) -> None:
        """Visit a LineBreak node."""
        self._collect_if_match(node)

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Visit a Strikethrough node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_underline(self, node: Underline) -> None:
        """Visit an Underline node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_superscript(self, node: Superscript) -> None:
        """Visit a Superscript node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_subscript(self, node: Subscript) -> None:
        """Visit a Subscript node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Visit an HTMLInline node."""
        self._collect_if_match(node)

    def visit_footnote_reference(self, node: "FootnoteReference") -> None:
        """Visit a FootnoteReference node."""
        self._collect_if_match(node)

    def visit_math_inline(self, node: "MathInline") -> None:
        """Visit a MathInline node."""
        self._collect_if_match(node)

    def visit_footnote_definition(self, node: "FootnoteDefinition") -> None:
        """Visit a FootnoteDefinition node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_definition_list(self, node: "DefinitionList") -> None:
        """Visit a DefinitionList node."""
        self._collect_if_match(node)
        for term, descriptions in node.items:
            term.accept(self)
            for desc in descriptions:
                desc.accept(self)

    def visit_definition_term(self, node: "DefinitionTerm") -> None:
        """Visit a DefinitionTerm node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_definition_description(self, node: "DefinitionDescription") -> None:
        """Visit a DefinitionDescription node."""
        self._collect_if_match(node)
        self._visit_children(node.content)

    def visit_math_block(self, node: "MathBlock") -> None:
        """Visit a MathBlock node."""
        self._collect_if_match(node)


# Utility functions


def clone_node(node: Node) -> Node:
    """Create a deep copy of an AST node.

    Parameters
    ----------
    node : Node
        Node to clone

    Returns
    -------
    Node
        Deep copy of the node

    Examples
    --------
    >>> cloned_doc = clone_node(doc)
    >>> cloned_doc is doc  # False
    False

    """
    return copy.deepcopy(node)


def extract_nodes(doc: Document, node_type: Type[Node] | None = None) -> list[Node]:
    """Extract all nodes of a specific type from a document.

    Parameters
    ----------
    doc : Document
        Document to extract from
    node_type : type or None, default = None
        Node type to extract (None for all nodes)

    Returns
    -------
    list of Node
        All matching nodes

    Examples
    --------
    >>> headings = extract_nodes(doc, Heading)
    >>> images = extract_nodes(doc, Image)

    """
    predicate = (lambda n: isinstance(n, node_type)) if node_type else (lambda n: True)
    collector = NodeCollector(predicate=predicate)
    doc.accept(collector)
    return collector.collected


def filter_nodes(doc: Document, predicate: Callable[[Node], bool]) -> Document:
    """Filter nodes from a document based on a condition.

    Parameters
    ----------
    doc : Document
        Document to filter
    predicate : callable
        Function that takes a node and returns True to keep it

    Returns
    -------
    Document
        New document with filtered nodes

    Notes
    -----
    The root Document node is always preserved, regardless of the predicate.
    Only the children of the Document are filtered according to the predicate.

    Examples
    --------
    Remove all images:
        >>> filtered_doc = filter_nodes(doc, lambda n: not isinstance(n, Image))

    Keep only headings and paragraphs:
        >>> filtered_doc = filter_nodes(doc, lambda n: isinstance(n, (Heading, Paragraph)))

    """

    class FilterTransformer(NodeTransformer):
        def visit_document(self, node: Document) -> Document:
            # Always preserve the Document root, only filter children
            return Document(
                children=self._transform_children(node.children),
                metadata=node.metadata.copy(),
                source_location=node.source_location,
            )

        def transform(self, node: Node) -> Node | None:
            # Document is always preserved (handled by visit_document)
            if isinstance(node, Document):
                return super().transform(node)
            # Apply predicate to all other nodes
            if not predicate(node):
                return None
            return super().transform(node)

    transformer = FilterTransformer()
    result = transformer.transform(doc)
    # The FilterTransformer always preserves the Document root, so this is safe
    assert isinstance(result, Document), "FilterTransformer must always return a Document"
    return result


def transform_nodes(doc: Document, transformer: NodeTransformer) -> Document:
    """Apply a transformation visitor to a document.

    Parameters
    ----------
    doc : Document
        Document to transform
    transformer : NodeTransformer
        Transformer to apply

    Returns
    -------
    Document
        Transformed document

    Examples
    --------
    >>> transformer = HeadingLevelTransformer(offset=1)
    >>> new_doc = transform_nodes(doc, transformer)

    """
    return transformer.transform(doc)  # type: ignore


def last_write_wins_merger(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge metadata with last-write-wins strategy (default).

    Later document's metadata values overwrite earlier ones for duplicate keys.

    Parameters
    ----------
    existing : dict
        Existing accumulated metadata
    new : dict
        New metadata to merge in

    Returns
    -------
    dict
        Merged metadata dictionary

    Examples
    --------
    >>> existing = {"author": "Alice", "version": "1.0"}
    >>> new = {"version": "2.0", "date": "2025-01-01"}
    >>> last_write_wins_merger(existing, new)
    {"author": "Alice", "version": "2.0", "date": "2025-01-01"}

    """
    result = existing.copy()
    result.update(new)
    return result


def first_write_wins_merger(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge metadata with first-write-wins strategy.

    Earlier document's metadata values are preserved for duplicate keys.

    Parameters
    ----------
    existing : dict
        Existing accumulated metadata
    new : dict
        New metadata to merge in

    Returns
    -------
    dict
        Merged metadata dictionary

    Examples
    --------
    >>> existing = {"author": "Alice", "version": "1.0"}
    >>> new = {"version": "2.0", "date": "2025-01-01"}
    >>> first_write_wins_merger(existing, new)
    {"author": "Alice", "version": "1.0", "date": "2025-01-01"}

    """
    result = new.copy()
    result.update(existing)
    return result


def merge_lists_merger(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge metadata with list concatenation for list values.

    When both existing and new have list values for the same key, concatenate them.
    For non-list values, uses last-write-wins strategy.

    Parameters
    ----------
    existing : dict
        Existing accumulated metadata
    new : dict
        New metadata to merge in

    Returns
    -------
    dict
        Merged metadata dictionary

    Examples
    --------
    >>> existing = {"tags": ["python", "ast"], "version": "1.0"}
    >>> new = {"tags": ["markdown"], "version": "2.0"}
    >>> merge_lists_merger(existing, new)
    {"tags": ["python", "ast", "markdown"], "version": "2.0"}

    """
    result = existing.copy()
    for key, value in new.items():
        if key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


def merge_documents(
    docs: list[Document],
    metadata_merger: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None
) -> Document:
    """Merge multiple documents into a single document.

    Parameters
    ----------
    docs : list of Document
        Documents to merge
    metadata_merger : callable or None, default = None
        Optional function to customize metadata merging. Takes (existing_metadata, new_metadata)
        and returns merged metadata dict. If None, uses last-write-wins strategy where later
        documents overwrite earlier ones for duplicate keys.

        Common strategies provided:
        - last_write_wins_merger: Later values overwrite (default behavior)
        - first_write_wins_merger: Earlier values are preserved
        - merge_lists_merger: Concatenate list values, last-wins for others

    Returns
    -------
    Document
        Merged document with all children and combined metadata

    Examples
    --------
    Basic merge with default last-write-wins:

        >>> merged = merge_documents([doc1, doc2, doc3])

    Preserve first document's metadata values:

        >>> merged = merge_documents([doc1, doc2], metadata_merger=first_write_wins_merger)

    Concatenate list-valued metadata:

        >>> merged = merge_documents([doc1, doc2], metadata_merger=merge_lists_merger)

    Custom merger:

        >>> def custom_merger(existing, new):
        ...     # Custom logic here
        ...     return merged_dict
        >>> merged = merge_documents([doc1, doc2], metadata_merger=custom_merger)

    Notes
    -----
    The default behavior (when metadata_merger=None) uses last-write-wins strategy,
    meaning later documents' metadata values overwrite earlier ones for duplicate keys.

    """
    all_children: list[Node] = []
    merged_metadata: dict[str, Any] = {}

    # Use default merger if none provided
    merger = metadata_merger or last_write_wins_merger

    for doc in docs:
        all_children.extend(doc.children)
        merged_metadata = merger(merged_metadata, doc.metadata)

    return Document(children=all_children, metadata=merged_metadata)


# Specialized transformers


class HeadingLevelTransformer(NodeTransformer):
    """Transformer that adjusts heading levels by an offset.

    Parameters
    ----------
    offset : int
        Amount to shift heading levels (can be negative)
    min_level : int, default = 1
        Minimum allowed heading level
    max_level : int, default = 6
        Maximum allowed heading level

    Examples
    --------
    >>> # Increase all heading levels by 1
    >>> transformer = HeadingLevelTransformer(offset=1)
    >>> new_doc = transformer.transform(doc)

    """

    def __init__(self, offset: int, min_level: int = 1, max_level: int = 6):
        """Initialize the transform with offset and level constraints."""
        self.offset = offset
        self.min_level = min_level
        self.max_level = max_level

    def visit_heading(self, node: Heading) -> Heading:
        """Transform heading level."""
        new_level = node.level + self.offset
        new_level = max(self.min_level, min(self.max_level, new_level))
        return Heading(
            level=new_level,
            content=self._transform_children(node.content),
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )


class LinkRewriter(NodeTransformer):
    """Transformer that rewrites link URLs.

    Parameters
    ----------
    url_mapper : callable
        Function that takes a URL string and returns a new URL string
    validate_urls : bool, default = True
        Whether to validate URLs after rewriting for dangerous schemes.
        When True, raises ValueError if the url_mapper produces a URL
        with a dangerous scheme (javascript:, vbscript:, etc.). This
        provides defense-in-depth against accidentally creating unsafe URLs.

    Raises
    ------
    ValueError
        If validate_urls=True and url_mapper produces a URL with a dangerous
        or unrecognized scheme

    Examples
    --------
    >>> # Convert relative links to absolute
    >>> def make_absolute(url):
    ...     if url.startswith('/'):
    ...         return f'https://example.com{url}'
    ...     return url
    >>> transformer = LinkRewriter(make_absolute)
    >>> new_doc = transformer.transform(doc)

    >>> # Disable validation if you need to generate non-standard URLs
    >>> transformer = LinkRewriter(my_mapper, validate_urls=False)

    Notes
    -----
    Security Considerations:
        By default (validate_urls=True), this transformer validates that the
        url_mapper does not produce dangerous URLs. This prevents accidental
        creation of XSS vectors like javascript: or data:text/html URLs.
        Only disable validation if you have a specific need and understand
        the security implications.

    """

    def __init__(self, url_mapper: Callable[[str], str], validate_urls: bool = True):
        """Initialize the transform with a URL mapping function.

        Parameters
        ----------
        url_mapper : callable
            Function that takes a URL string and returns a new URL string
        validate_urls : bool, default = True
            Whether to validate URLs after rewriting for dangerous schemes

        """
        self.url_mapper = url_mapper
        self.validate_urls = validate_urls

    def visit_link(self, node: Link) -> Link:
        """Rewrite link URL."""
        new_url = self.url_mapper(node.url)

        # Validate URL if requested
        if self.validate_urls:
            _validate_url_scheme(new_url, context="Link")

        return Link(
            url=new_url,
            content=self._transform_children(node.content),
            title=node.title,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )

    def visit_image(self, node: Image) -> Image:
        """Rewrite image URL."""
        new_url = self.url_mapper(node.url)

        # Validate URL if requested
        if self.validate_urls:
            _validate_url_scheme(new_url, context="Image")

        return Image(
            url=new_url,
            alt_text=node.alt_text,
            title=node.title,
            width=node.width,
            height=node.height,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )


class TextReplacer(NodeTransformer):
    """Transformer that replaces text patterns.

    Parameters
    ----------
    pattern : str
        Pattern to search for
    replacement : str
        Replacement string
    use_regex : bool, default = False
        Whether to use regex matching

    Raises
    ------
    ValueError
        If use_regex=True and pattern is not a valid regular expression

    Examples
    --------
    >>> # Replace all occurrences of "foo" with "bar"
    >>> transformer = TextReplacer("foo", "bar")
    >>> new_doc = transformer.transform(doc)

    >>> # Use regex for pattern matching
    >>> transformer = TextReplacer(r"\\d+", "NUMBER", use_regex=True)
    >>> new_doc = transformer.transform(doc)

    """

    def __init__(self, pattern: str, replacement: str, use_regex: bool = False):
        """Initialize the transform with pattern and replacement.

        Parameters
        ----------
        pattern : str
            Pattern to search for (literal string or regex)
        replacement : str
            Replacement string
        use_regex : bool, default = False
            Whether to use regex matching

        Raises
        ------
        ValueError
            If use_regex=True and pattern is not a valid regular expression

        """
        self.pattern = pattern
        self.replacement = replacement
        self.use_regex = use_regex
        self._compiled_pattern: Pattern[str] | None = None

        # Compile and validate regex pattern if using regex mode
        if self.use_regex:
            try:
                self._compiled_pattern = re.compile(pattern)
            except re.error as e:
                raise ValueError(
                    f"Invalid regular expression pattern: {pattern!r}. "
                    f"Regex compilation error: {e}"
                ) from e

    def visit_text(self, node: Text) -> Text:
        """Replace text content."""
        if self.use_regex:
            assert self._compiled_pattern is not None, "Compiled pattern should exist when use_regex=True"
            new_content = self._compiled_pattern.sub(self.replacement, node.content)
        else:
            new_content = node.content.replace(self.pattern, self.replacement)

        return Text(
            content=new_content, metadata=node.metadata.copy(), source_location=node.source_location
        )


__all__ = [
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
]
