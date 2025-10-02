#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/visitors.py
"""Visitor pattern implementation for AST traversal.

This module provides the visitor pattern base classes for traversing and
processing AST nodes. Visitors enable separation of algorithms (like rendering,
validation, transformation) from the node structure itself.

The visitor pattern allows for:
- Clean separation of concerns
- Easy addition of new processing algorithms
- Type-safe node processing
- Flexible tree traversal strategies

"""

from __future__ import annotations

from abc import ABC, abstractmethod
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


class NodeVisitor(ABC):
    """Abstract base class for AST node visitors.

    Subclasses should implement visit_* methods for each node type they
    want to process. The visitor pattern allows algorithms to be separated
    from the node structure.

    All visit methods should accept a node and return Any (typically None
    for side-effect visitors, or accumulated results for transforming visitors).

    Examples
    --------
    Simple visitor that counts nodes:

        >>> class NodeCounter(NodeVisitor):
        ...     def __init__(self):
        ...         self.count = 0
        ...
        ...     def generic_visit(self, node):
        ...         self.count += 1
        ...         # Visit children if they exist
        ...         if hasattr(node, 'children'):
        ...             for child in node.children:
        ...                 child.accept(self)
        ...
        >>> counter = NodeCounter()
        >>> document.accept(counter)
        >>> print(counter.count)

    """

    @abstractmethod
    def visit_document(self, node: Document) -> Any:
        """Visit a Document node.

        Parameters
        ----------
        node : Document
            The document node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_heading(self, node: Heading) -> Any:
        """Visit a Heading node.

        Parameters
        ----------
        node : Heading
            The heading node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_paragraph(self, node: Paragraph) -> Any:
        """Visit a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            The paragraph node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_code_block(self, node: CodeBlock) -> Any:
        """Visit a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            The code block node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_block_quote(self, node: BlockQuote) -> Any:
        """Visit a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            The block quote node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_list(self, node: List) -> Any:
        """Visit a List node.

        Parameters
        ----------
        node : List
            The list node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_list_item(self, node: ListItem) -> Any:
        """Visit a ListItem node.

        Parameters
        ----------
        node : ListItem
            The list item node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_table(self, node: Table) -> Any:
        """Visit a Table node.

        Parameters
        ----------
        node : Table
            The table node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_table_row(self, node: TableRow) -> Any:
        """Visit a TableRow node.

        Parameters
        ----------
        node : TableRow
            The table row node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_table_cell(self, node: TableCell) -> Any:
        """Visit a TableCell node.

        Parameters
        ----------
        node : TableCell
            The table cell node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_thematic_break(self, node: ThematicBreak) -> Any:
        """Visit a ThematicBreak node.

        Parameters
        ----------
        node : ThematicBreak
            The thematic break node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_html_block(self, node: HTMLBlock) -> Any:
        """Visit an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            The HTML block node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_text(self, node: Text) -> Any:
        """Visit a Text node.

        Parameters
        ----------
        node : Text
            The text node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_emphasis(self, node: Emphasis) -> Any:
        """Visit an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            The emphasis node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_strong(self, node: Strong) -> Any:
        """Visit a Strong node.

        Parameters
        ----------
        node : Strong
            The strong node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_code(self, node: Code) -> Any:
        """Visit a Code node.

        Parameters
        ----------
        node : Code
            The code node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_link(self, node: Link) -> Any:
        """Visit a Link node.

        Parameters
        ----------
        node : Link
            The link node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_image(self, node: Image) -> Any:
        """Visit an Image node.

        Parameters
        ----------
        node : Image
            The image node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_line_break(self, node: LineBreak) -> Any:
        """Visit a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            The line break node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_strikethrough(self, node: Strikethrough) -> Any:
        """Visit a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            The strikethrough node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_underline(self, node: Underline) -> Any:
        """Visit an Underline node.

        Parameters
        ----------
        node : Underline
            The underline node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_superscript(self, node: Superscript) -> Any:
        """Visit a Superscript node.

        Parameters
        ----------
        node : Superscript
            The superscript node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_subscript(self, node: Subscript) -> Any:
        """Visit a Subscript node.

        Parameters
        ----------
        node : Subscript
            The subscript node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_html_inline(self, node: HTMLInline) -> Any:
        """Visit an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            The inline HTML node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_footnote_reference(self, node: "FootnoteReference") -> Any:
        """Visit a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            The footnote reference node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_math_inline(self, node: "MathInline") -> Any:
        """Visit a MathInline node.

        Parameters
        ----------
        node : MathInline
            The inline math node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_footnote_definition(self, node: "FootnoteDefinition") -> Any:
        """Visit a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            The footnote definition node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_definition_list(self, node: "DefinitionList") -> Any:
        """Visit a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            The definition list node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_definition_term(self, node: "DefinitionTerm") -> Any:
        """Visit a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            The definition term node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_definition_description(self, node: "DefinitionDescription") -> Any:
        """Visit a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            The definition description node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    @abstractmethod
    def visit_math_block(self, node: "MathBlock") -> Any:
        """Visit a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            The math block node to visit

        Returns
        -------
        Any
            Result of processing this node

        """
        pass

    def generic_visit(self, node: Node) -> Any:
        """Fallback visitor for unhandled node types.

        This method is called when no specific visit_* method exists.
        The default implementation does nothing but can be overridden.

        Parameters
        ----------
        node : Node
            The node to visit

        Returns
        -------
        Any
            Result of processing (default: None)

        """
        return None


class ValidationVisitor(NodeVisitor):
    """Visitor that validates AST structure.

    This visitor checks for structural issues in the AST, such as:
    - Invalid nesting (e.g., block nodes inside inline nodes)
    - Missing required fields
    - Invalid field values

    Parameters
    ----------
    strict : bool, default = True
        Whether to raise errors on validation failures

    """

    def __init__(self, strict: bool = True):
        self.strict = strict
        self.errors: list[str] = []

    def _add_error(self, message: str) -> None:
        """Add a validation error.

        Parameters
        ----------
        message : str
            Error message

        """
        self.errors.append(message)
        if self.strict:
            raise ValueError(message)

    def visit_document(self, node: Document) -> None:
        """Validate a Document node."""
        for child in node.children:
            child.accept(self)

    def visit_heading(self, node: Heading) -> None:
        """Validate a Heading node."""
        if not 1 <= node.level <= 6:
            self._add_error(f"Invalid heading level: {node.level}")
        for child in node.content:
            child.accept(self)

    def visit_paragraph(self, node: Paragraph) -> None:
        """Validate a Paragraph node."""
        for child in node.content:
            child.accept(self)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Validate a CodeBlock node."""
        pass

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Validate a BlockQuote node."""
        for child in node.children:
            child.accept(self)

    def visit_list(self, node: List) -> None:
        """Validate a List node."""
        for item in node.items:
            item.accept(self)

    def visit_list_item(self, node: ListItem) -> None:
        """Validate a ListItem node."""
        for child in node.children:
            child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Validate a Table node."""
        if node.header:
            node.header.accept(self)
        for row in node.rows:
            row.accept(self)

    def visit_table_row(self, node: TableRow) -> None:
        """Validate a TableRow node."""
        for cell in node.cells:
            cell.accept(self)

    def visit_table_cell(self, node: TableCell) -> None:
        """Validate a TableCell node."""
        for child in node.content:
            child.accept(self)

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Validate a ThematicBreak node."""
        pass

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Validate an HTMLBlock node."""
        pass

    def visit_text(self, node: Text) -> None:
        """Validate a Text node."""
        pass

    def visit_emphasis(self, node: Emphasis) -> None:
        """Validate an Emphasis node."""
        for child in node.content:
            child.accept(self)

    def visit_strong(self, node: Strong) -> None:
        """Validate a Strong node."""
        for child in node.content:
            child.accept(self)

    def visit_code(self, node: Code) -> None:
        """Validate a Code node."""
        pass

    def visit_link(self, node: Link) -> None:
        """Validate a Link node."""
        for child in node.content:
            child.accept(self)

    def visit_image(self, node: Image) -> None:
        """Validate an Image node."""
        pass

    def visit_line_break(self, node: LineBreak) -> None:
        """Validate a LineBreak node."""
        pass

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Validate a Strikethrough node."""
        for child in node.content:
            child.accept(self)

    def visit_underline(self, node: Underline) -> None:
        """Validate an Underline node."""
        for child in node.content:
            child.accept(self)

    def visit_superscript(self, node: Superscript) -> None:
        """Validate a Superscript node."""
        for child in node.content:
            child.accept(self)

    def visit_subscript(self, node: Subscript) -> None:
        """Validate a Subscript node."""
        for child in node.content:
            child.accept(self)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Validate an HTMLInline node."""
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Validate a FootnoteReference node."""
        if not node.identifier:
            self._add_error("FootnoteReference must have an identifier")

    def visit_math_inline(self, node: MathInline) -> None:
        """Validate a MathInline node."""
        pass

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Validate a FootnoteDefinition node."""
        if not node.identifier:
            self._add_error("FootnoteDefinition must have an identifier")
        for child in node.content:
            child.accept(self)

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Validate a DefinitionList node."""
        for term, descriptions in node.items:
            term.accept(self)
            for desc in descriptions:
                desc.accept(self)

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Validate a DefinitionTerm node."""
        for child in node.content:
            child.accept(self)

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Validate a DefinitionDescription node."""
        for child in node.content:
            child.accept(self)

    def visit_math_block(self, node: MathBlock) -> None:
        """Validate a MathBlock node."""
        pass
