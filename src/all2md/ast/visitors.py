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
from all2md.constants import (
    DANGEROUS_SCHEMES,
    DEFAULT_MAX_ASSET_SIZE_BYTES,
    SAFE_LINK_SCHEMES,
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
    def visit_comment(self, node: Comment) -> Any:
        """Visit a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            The comment block node to visit

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
    def visit_comment_inline(self, node: CommentInline) -> Any:
        """Visit a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            The inline comment node to visit

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
    - Presence of raw HTML content (when disallowed)
    - Block/inline containment rules (in strict mode)
    - URL scheme validation (in strict mode)

    Parameters
    ----------
    strict : bool, default = True
        Whether to raise errors on validation failures
    allow_raw_html : bool, default = False
        Whether to allow HTMLBlock and HTMLInline nodes. By default (False),
        any raw HTML content will trigger a validation error for security.
        Set to True only when you trust the HTML source and need to preserve
        raw HTML content. This follows security best practices of default-deny
        for potentially unsafe content.

    Notes
    -----
    Security Considerations:
        Raw HTML in documents can pose security risks (XSS attacks, code injection).
        This validator defaults to rejecting HTML to enforce security best practices.
        Only set allow_raw_html=True when:
        - You trust the document source
        - HTML will be sanitized before rendering
        - You're working in a trusted/non-web context

    Examples
    --------
    Strict validation (rejects HTML by default):
        >>> validator = ValidationVisitor(strict=True)
        >>> doc.accept(validator)  # Raises ValueError if HTML present

    Allow HTML from trusted sources:
        >>> validator = ValidationVisitor(strict=True, allow_raw_html=True)
        >>> doc.accept(validator)  # Permits HTMLBlock/HTMLInline nodes

    """

    # Node type classification for containment validation
    INLINE_NODES = frozenset(
        {
            Text,
            Emphasis,
            Strong,
            Code,
            Link,
            Image,
            LineBreak,
            Strikethrough,
            Underline,
            Superscript,
            Subscript,
            HTMLInline,
            MathInline,
            FootnoteReference,
        }
    )

    BLOCK_NODES = frozenset(
        {
            Document,
            Heading,
            Paragraph,
            CodeBlock,
            BlockQuote,
            List,
            ListItem,
            Table,
            TableRow,
            TableCell,
            ThematicBreak,
            HTMLBlock,
            FootnoteDefinition,
            DefinitionList,
            DefinitionTerm,
            DefinitionDescription,
            MathBlock,
        }
    )

    def __init__(self, strict: bool = True, allow_raw_html: bool = False):
        """Initialize the validator with strictness and HTML policy.

        Parameters
        ----------
        strict : bool, default = True
            Whether to raise errors immediately on validation failures
        allow_raw_html : bool, default = False
            Whether to allow raw HTML nodes (security: default deny)

        """
        self.strict = strict
        self.allow_raw_html = allow_raw_html
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

    def _validate_children_are_inline(self, children: list[Node], context: str) -> None:
        """Validate that all children are inline nodes.

        Parameters
        ----------
        children : list of Node
            Child nodes to validate
        context : str
            Context description for error messages (e.g., "Heading", "Paragraph")

        """
        if not self.strict:
            return

        for i, child in enumerate(children):
            if type(child) not in self.INLINE_NODES:
                self._add_error(f"{context} can only contain inline nodes, but child {i} is {type(child).__name__}")

    def _validate_children_are_blocks(self, children: list[Node], context: str) -> None:
        """Validate that all children are block nodes.

        Parameters
        ----------
        children : list of Node
            Child nodes to validate
        context : str
            Context description for error messages (e.g., "ListItem", "Document")

        """
        if not self.strict:
            return

        for i, child in enumerate(children):
            if type(child) not in self.BLOCK_NODES:
                self._add_error(f"{context} can only contain block nodes, but child {i} is {type(child).__name__}")

    def _validate_url_scheme(self, url: str, context: str, allow_data_uri: bool = False) -> None:
        """Validate URL scheme for security.

        Parameters
        ----------
        url : str
            URL to validate
        context : str
            Context description for error messages (e.g., "Link", "Image")
        allow_data_uri : bool, default = False
            Whether to allow data: URIs (with additional validation)

        """
        if not self.strict or not url:
            return

        url_lower = url.lower()

        # Special handling for data: URIs when explicitly allowed (for images)
        if allow_data_uri and url_lower.startswith("data:"):
            if url_lower.startswith("data:image/"):
                # Validate data URI length
                if len(url) > DEFAULT_MAX_ASSET_SIZE_BYTES:
                    self._add_error(
                        f"{context} data URI exceeds maximum length "
                        f"({len(url)} > {DEFAULT_MAX_ASSET_SIZE_BYTES} bytes)"
                    )
                # If length is OK, allow it
                return
            else:
                # data: URI but not image/* - reject it
                self._add_error(f"{context} data URI must have image/* MIME type, got: {url[:50]}")
                return

        # Check for dangerous schemes
        for dangerous_scheme in DANGEROUS_SCHEMES:
            if url_lower.startswith(dangerous_scheme.lower()):
                self._add_error(f"{context} URL uses dangerous scheme '{dangerous_scheme}': {url[:50]}")
                return

        # Check if URL has a scheme
        if "://" in url:
            # Extract scheme
            scheme = url.split("://", 1)[0].lower()

            # Check if scheme is in safe list
            if scheme not in SAFE_LINK_SCHEMES:
                self._add_error(f"{context} URL has unrecognized scheme '{scheme}': {url[:50]}")
                return
        else:
            # Check for scheme-like patterns without ://
            # This catches things like "javascript:alert(1)" which don't have ://
            if ":" in url and not url.startswith(("/", "#")):
                potential_scheme = url.split(":", 1)[0].lower()
                # Check if this looks like a dangerous scheme
                for dangerous_scheme in DANGEROUS_SCHEMES:
                    if dangerous_scheme.lower().startswith(potential_scheme + ":"):
                        self._add_error(f"{context} URL uses dangerous scheme '{potential_scheme}': {url[:50]}")
                        return

    def visit_document(self, node: Document) -> None:
        """Validate a Document node."""
        for child in node.children:
            child.accept(self)

    def visit_heading(self, node: Heading) -> None:
        """Validate a Heading node."""
        if not 1 <= node.level <= 6:
            self._add_error(f"Invalid heading level: {node.level}")
        # Validate that heading content contains only inline nodes
        self._validate_children_are_inline(node.content, "Heading")
        for child in node.content:
            child.accept(self)

    def visit_paragraph(self, node: Paragraph) -> None:
        """Validate a Paragraph node."""
        # Validate that paragraph content contains only inline nodes
        self._validate_children_are_inline(node.content, "Paragraph")
        for child in node.content:
            child.accept(self)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Validate a CodeBlock node."""
        # Validate fence_length is >= 1
        if node.fence_length < 1:
            self._add_error(f"CodeBlock fence_length must be >= 1, got {node.fence_length}")

        # Validate fence_char is ` or ~
        if node.fence_char not in {"`", "~"}:
            self._add_error(f"CodeBlock fence_char must be '`' or '~', got '{node.fence_char}'")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Validate a BlockQuote node."""
        for child in node.children:
            child.accept(self)

    def visit_list(self, node: List) -> None:
        """Validate a List node."""
        # Validate start is >= 1 for ordered lists
        if node.ordered and node.start < 1:
            self._add_error(f"Ordered list start must be >= 1, got {node.start}")

        # Validate items list is non-empty
        if not node.items:
            self._add_error("List must have at least one item")

        for item in node.items:
            item.accept(self)

    def visit_list_item(self, node: ListItem) -> None:
        """Validate a ListItem node."""
        # Validate that list item children are block nodes
        self._validate_children_are_blocks(node.children, "ListItem")
        for child in node.children:
            child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Validate a Table node."""
        # Determine expected column count from header or first row
        expected_cols = None
        if node.header:
            expected_cols = len(node.header.cells)
            node.header.accept(self)
        elif node.rows:
            expected_cols = len(node.rows[0].cells)

        # Validate consistent column counts across all rows
        if expected_cols is not None:
            for i, row in enumerate(node.rows):
                if len(row.cells) != expected_cols:
                    self._add_error(f"Table row {i} has {len(row.cells)} cells, expected {expected_cols}")

        # Validate alignments length matches column count
        if node.alignments and expected_cols is not None:
            if len(node.alignments) != expected_cols:
                self._add_error(f"Table has {len(node.alignments)} alignments but {expected_cols} columns")

        # Visit all rows to validate cells
        for row in node.rows:
            row.accept(self)

    def visit_table_row(self, node: TableRow) -> None:
        """Validate a TableRow node."""
        for cell in node.cells:
            cell.accept(self)

    def visit_table_cell(self, node: TableCell) -> None:
        """Validate a TableCell node."""
        # Validate colspan and rowspan are >= 1
        if node.colspan < 1:
            self._add_error(f"TableCell colspan must be >= 1, got {node.colspan}")
        if node.rowspan < 1:
            self._add_error(f"TableCell rowspan must be >= 1, got {node.rowspan}")

        # Validate that table cell content contains only inline nodes
        self._validate_children_are_inline(node.content, "TableCell")
        for child in node.content:
            child.accept(self)

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Validate a ThematicBreak node."""
        pass

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Validate an HTMLBlock node.

        Checks if raw HTML is allowed based on the allow_raw_html setting.
        """
        if not self.allow_raw_html:
            self._add_error(
                "Raw HTML content (HTMLBlock) not allowed in strict mode. "
                "Consider sanitizing or removing HTML content for security."
            )

    def visit_comment(self, node: Comment) -> None:
        """Validate a Comment node (block-level).

        Comments are informational and generally safe, but we validate
        that they have content.
        """
        if not node.content:
            self._add_error("Comment node should have content")

    def visit_text(self, node: Text) -> None:
        """Validate a Text node."""
        pass

    def visit_emphasis(self, node: Emphasis) -> None:
        """Validate an Emphasis node."""
        # Validate that emphasis content contains only inline nodes
        self._validate_children_are_inline(node.content, "Emphasis")
        for child in node.content:
            child.accept(self)

    def visit_strong(self, node: Strong) -> None:
        """Validate a Strong node."""
        # Validate that strong content contains only inline nodes
        self._validate_children_are_inline(node.content, "Strong")
        for child in node.content:
            child.accept(self)

    def visit_code(self, node: Code) -> None:
        """Validate a Code node."""
        pass

    def visit_link(self, node: Link) -> None:
        """Validate a Link node."""
        # Validate url is non-empty
        if not node.url:
            self._add_error("Link url must be non-empty")

        # Validate URL scheme for security (strict mode only)
        self._validate_url_scheme(node.url, "Link", allow_data_uri=False)

        # Validate that link content contains only inline nodes
        self._validate_children_are_inline(node.content, "Link")

        for child in node.content:
            child.accept(self)

    def visit_image(self, node: Image) -> None:
        """Validate an Image node."""
        # Validate url is non-empty
        if not node.url:
            self._add_error("Image url must be non-empty")

        # Validate URL scheme for security (strict mode only)
        # Allow data:image/* URIs for images with length validation
        self._validate_url_scheme(node.url, "Image", allow_data_uri=True)

    def visit_line_break(self, node: LineBreak) -> None:
        """Validate a LineBreak node."""
        pass

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Validate a Strikethrough node."""
        # Validate that strikethrough content contains only inline nodes
        self._validate_children_are_inline(node.content, "Strikethrough")
        for child in node.content:
            child.accept(self)

    def visit_underline(self, node: Underline) -> None:
        """Validate an Underline node."""
        # Validate that underline content contains only inline nodes
        self._validate_children_are_inline(node.content, "Underline")
        for child in node.content:
            child.accept(self)

    def visit_superscript(self, node: Superscript) -> None:
        """Validate a Superscript node."""
        # Validate that superscript content contains only inline nodes
        self._validate_children_are_inline(node.content, "Superscript")
        for child in node.content:
            child.accept(self)

    def visit_subscript(self, node: Subscript) -> None:
        """Validate a Subscript node."""
        # Validate that subscript content contains only inline nodes
        self._validate_children_are_inline(node.content, "Subscript")
        for child in node.content:
            child.accept(self)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Validate an HTMLInline node.

        Checks if raw HTML is allowed based on the allow_raw_html setting.
        """
        if not self.allow_raw_html:
            self._add_error(
                "Raw HTML content (HTMLInline) not allowed in strict mode. "
                "Consider sanitizing or removing HTML content for security."
            )

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Validate a CommentInline node (inline).

        Comments are informational and generally safe, but we validate
        that they have content.
        """
        if not node.content:
            self._add_error("CommentInline node should have content")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Validate a FootnoteReference node."""
        if not node.identifier:
            self._add_error("FootnoteReference must have an identifier")

    def visit_math_inline(self, node: MathInline) -> None:
        """Validate a MathInline node."""
        valid_notations = {"latex", "mathml", "html"}
        if node.notation not in valid_notations:
            self._add_error(f"MathInline uses unsupported notation '{node.notation}'")
        for notation, value in node.representations.items():
            if notation not in valid_notations:
                self._add_error(f"MathInline has invalid representation key '{notation}'")
            elif not isinstance(value, str):
                self._add_error("MathInline representations must be strings")  # type: ignore[unreachable]

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
        # Validate that definition term content contains only inline nodes
        self._validate_children_are_inline(node.content, "DefinitionTerm")
        for child in node.content:
            child.accept(self)

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Validate a DefinitionDescription node."""
        # Validate that definition description content contains block nodes
        self._validate_children_are_blocks(node.content, "DefinitionDescription")
        for child in node.content:
            child.accept(self)

    def visit_math_block(self, node: MathBlock) -> None:
        """Validate a MathBlock node."""
        valid_notations = {"latex", "mathml", "html"}
        if node.notation not in valid_notations:
            self._add_error(f"MathBlock uses unsupported notation '{node.notation}'")
        for notation, value in node.representations.items():
            if notation not in valid_notations:
                self._add_error(f"MathBlock has invalid representation key '{notation}'")
            elif not isinstance(value, str):
                self._add_error("MathBlock representations must be strings")  # type: ignore[unreachable]
