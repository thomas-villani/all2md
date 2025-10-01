#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/nodes.py
"""AST node classes for document representation.

This module defines the complete node hierarchy for representing markdown documents
as Abstract Syntax Trees. Each node represents a structural or inline element in
the document.

The node hierarchy is designed to:
- Support all CommonMark elements plus common extensions
- Enable multiple rendering strategies via visitor pattern
- Preserve source information for debugging
- Allow format-specific metadata attachment

Node Hierarchy
--------------
All nodes inherit from the base Node class and support the visitor pattern.

Block-level nodes represent structural document elements:
    - Document, Heading, Paragraph, CodeBlock, BlockQuote
    - List, ListItem, Table, TableRow, TableCell
    - ThematicBreak, HTMLBlock

Inline nodes represent text formatting:
    - Text, Emphasis, Strong, Code
    - Link, Image, LineBreak
    - Strikethrough, Underline, Superscript, Subscript
    - HTMLInline

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class SourceLocation:
    """Source location information for AST nodes.

    Preserves information about where a node originated in the source document,
    useful for debugging, error messages, and round-trip conversions.

    Parameters
    ----------
    format : str
        Source format (e.g., 'pdf', 'html', 'docx')
    page : int or None, default = None
        Page number in source document (for paginated formats)
    line : int or None, default = None
        Line number in source document (for text formats)
    column : int or None, default = None
        Column number in source document
    element_id : str or None, default = None
        Source element identifier (e.g., HTML element ID)
    metadata : dict, default = empty dict
        Additional format-specific location information

    """

    format: str
    page: Optional[int] = None
    line: Optional[int] = None
    column: Optional[int] = None
    element_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Node(ABC):
    """Base class for all AST nodes.

    All document nodes inherit from this base class and support the visitor
    pattern for traversal and rendering.

    Parameters
    ----------
    metadata : dict, default = empty dict
        Arbitrary metadata associated with this node
    source_location : SourceLocation or None, default = None
        Information about where this node came from in the source

    """

    metadata: dict[str, Any]
    source_location: Optional[SourceLocation]

    @abstractmethod
    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this node.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_* methods

        Returns
        -------
        Any
            Result from the visitor's processing

        """
        pass


# ============================================================================
# Block-level Nodes
# ============================================================================


@dataclass
class Document(Node):
    """Root document node containing all other nodes.

    The Document node represents the complete document and contains a list
    of block-level children.

    Parameters
    ----------
    children : list of Node, default = empty list
        Block-level nodes in the document
    metadata : dict, default = empty dict
        Document-level metadata (title, author, etc.)
    source_location : SourceLocation or None, default = None
        Source location information

    """

    children: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this document.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_document method

        Returns
        -------
        Any
            Result from visitor.visit_document(self)

        """
        return visitor.visit_document(self)


@dataclass
class Heading(Node):
    """Heading node (h1-h6).

    Represents a document heading with a level from 1 to 6 and inline content.

    Parameters
    ----------
    level : int
        Heading level (1-6, where 1 is most important)
    content : list of Node, default = empty list
        Inline nodes representing heading text
    metadata : dict, default = empty dict
        Heading metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    level: int
    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def __post_init__(self) -> None:
        """Validate heading level is between 1 and 6."""
        if not 1 <= self.level <= 6:
            raise ValueError(f"Heading level must be 1-6, got {self.level}")

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this heading.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_heading method

        Returns
        -------
        Any
            Result from visitor.visit_heading(self)

        """
        return visitor.visit_heading(self)


@dataclass
class Paragraph(Node):
    """Paragraph node containing inline content.

    Represents a paragraph of text with inline formatting.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes representing paragraph content
    metadata : dict, default = empty dict
        Paragraph metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this paragraph.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_paragraph method

        Returns
        -------
        Any
            Result from visitor.visit_paragraph(self)

        """
        return visitor.visit_paragraph(self)


@dataclass
class CodeBlock(Node):
    """Code block node with optional language specification.

    Represents a fenced or indented code block.

    Parameters
    ----------
    content : str
        Code content (not parsed as markdown)
    language : str or None, default = None
        Programming language for syntax highlighting
    fence_char : str, default = '`'
        Character used for fencing (` or ~)
    fence_length : int, default = 3
        Number of fence characters
    metadata : dict, default = empty dict
        Code block metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    language: Optional[str] = None
    fence_char: str = '`'
    fence_length: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this code block.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_code_block method

        Returns
        -------
        Any
            Result from visitor.visit_code_block(self)

        """
        return visitor.visit_code_block(self)


@dataclass
class BlockQuote(Node):
    """Block quote node containing other block elements.

    Represents a quoted section of content.

    Parameters
    ----------
    children : list of Node, default = empty list
        Block-level nodes in the quote
    metadata : dict, default = empty dict
        Block quote metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    children: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this block quote.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_block_quote method

        Returns
        -------
        Any
            Result from visitor.visit_block_quote(self)

        """
        return visitor.visit_block_quote(self)


@dataclass
class List(Node):
    """List node (ordered or unordered).

    Represents an ordered (numbered) or unordered (bulleted) list.

    Parameters
    ----------
    ordered : bool
        True for ordered lists, False for unordered
    items : list of ListItem, default = empty list
        List items
    start : int, default = 1
        Starting number for ordered lists
    tight : bool, default = True
        Whether list is tight (no blank lines between items)
    metadata : dict, default = empty dict
        List metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    ordered: bool
    items: list[ListItem] = field(default_factory=list)
    start: int = 1
    tight: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this list.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_list method

        Returns
        -------
        Any
            Result from visitor.visit_list(self)

        """
        return visitor.visit_list(self)


@dataclass
class ListItem(Node):
    """List item node containing block content.

    Represents a single item in a list, which can contain paragraphs,
    nested lists, or other block elements.

    Parameters
    ----------
    children : list of Node, default = empty list
        Block-level nodes in the list item
    task_status : {'checked', 'unchecked'} or None, default = None
        For task lists (GFM extension)
    metadata : dict, default = empty dict
        List item metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    children: list[Node] = field(default_factory=list)
    task_status: Optional[Literal['checked', 'unchecked']] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this list item.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_list_item method

        Returns
        -------
        Any
            Result from visitor.visit_list_item(self)

        """
        return visitor.visit_list_item(self)


@dataclass
class Table(Node):
    """Table node with optional header and alignment.

    Represents a table structure (GFM extension).

    Parameters
    ----------
    rows : list of TableRow, default = empty list
        Table rows (excluding header)
    header : TableRow or None, default = None
        Optional header row
    alignments : list, default = empty list
        Column alignments ('left', 'center', 'right', or None)
    caption : str or None, default = None
        Optional table caption
    metadata : dict, default = empty dict
        Table metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    rows: list[TableRow] = field(default_factory=list)
    header: Optional[TableRow] = None
    alignments: list[Optional[Literal['left', 'center', 'right']]] = field(default_factory=list)
    caption: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this table.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_table method

        Returns
        -------
        Any
            Result from visitor.visit_table(self)

        """
        return visitor.visit_table(self)


@dataclass
class TableRow(Node):
    """Table row node containing cells.

    Represents a single row in a table.

    Parameters
    ----------
    cells : list of TableCell, default = empty list
        Cells in this row
    is_header : bool, default = False
        Whether this is a header row
    metadata : dict, default = empty dict
        Row metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    cells: list[TableCell] = field(default_factory=list)
    is_header: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this table row.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_table_row method

        Returns
        -------
        Any
            Result from visitor.visit_table_row(self)

        """
        return visitor.visit_table_row(self)


@dataclass
class TableCell(Node):
    """Table cell node with optional span and alignment.

    Represents a single cell in a table.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline content of the cell
    colspan : int, default = 1
        Number of columns this cell spans
    rowspan : int, default = 1
        Number of rows this cell spans
    alignment : {'left', 'center', 'right'} or None, default = None
        Cell alignment
    metadata : dict, default = empty dict
        Cell metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    alignment: Optional[Literal['left', 'center', 'right']] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this table cell.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_table_cell method

        Returns
        -------
        Any
            Result from visitor.visit_table_cell(self)

        """
        return visitor.visit_table_cell(self)


@dataclass
class ThematicBreak(Node):
    """Thematic break node (horizontal rule).

    Represents a thematic break/horizontal rule.

    Parameters
    ----------
    metadata : dict, default = empty dict
        Break metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this thematic break.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_thematic_break method

        Returns
        -------
        Any
            Result from visitor.visit_thematic_break(self)

        """
        return visitor.visit_thematic_break(self)


@dataclass
class HTMLBlock(Node):
    """Raw HTML block node.

    Represents a block of raw HTML content.

    Parameters
    ----------
    content : str
        Raw HTML content
    metadata : dict, default = empty dict
        HTML block metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this HTML block.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_html_block method

        Returns
        -------
        Any
            Result from visitor.visit_html_block(self)

        """
        return visitor.visit_html_block(self)


# ============================================================================
# Inline Nodes
# ============================================================================


@dataclass
class Text(Node):
    """Plain text node.

    Represents plain text content without formatting.

    Parameters
    ----------
    content : str
        Text content
    metadata : dict, default = empty dict
        Text metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this text.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_text method

        Returns
        -------
        Any
            Result from visitor.visit_text(self)

        """
        return visitor.visit_text(self)


@dataclass
class Emphasis(Node):
    """Emphasis (italic) node.

    Represents emphasized (typically italic) text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes with emphasis
    metadata : dict, default = empty dict
        Emphasis metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this emphasis.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_emphasis method

        Returns
        -------
        Any
            Result from visitor.visit_emphasis(self)

        """
        return visitor.visit_emphasis(self)


@dataclass
class Strong(Node):
    """Strong (bold) node.

    Represents strong (typically bold) text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes with strong emphasis
    metadata : dict, default = empty dict
        Strong metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this strong emphasis.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_strong method

        Returns
        -------
        Any
            Result from visitor.visit_strong(self)

        """
        return visitor.visit_strong(self)


@dataclass
class Code(Node):
    """Inline code node.

    Represents inline code (monospace text).

    Parameters
    ----------
    content : str
        Code content
    metadata : dict, default = empty dict
        Code metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this inline code.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_code method

        Returns
        -------
        Any
            Result from visitor.visit_code(self)

        """
        return visitor.visit_code(self)


@dataclass
class Link(Node):
    """Link node.

    Represents a hyperlink with optional title.

    Parameters
    ----------
    url : str
        Link destination URL
    content : list of Node, default = empty list
        Inline nodes representing link text
    title : str or None, default = None
        Optional link title (tooltip)
    metadata : dict, default = empty dict
        Link metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    url: str
    content: list[Node] = field(default_factory=list)
    title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this link.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_link method

        Returns
        -------
        Any
            Result from visitor.visit_link(self)

        """
        return visitor.visit_link(self)


@dataclass
class Image(Node):
    """Image node.

    Represents an embedded image.

    Parameters
    ----------
    url : str
        Image source URL or data URI
    alt_text : str, default = ''
        Alternative text description
    title : str or None, default = None
        Optional image title
    width : int or None, default = None
        Optional width in pixels
    height : int or None, default = None
        Optional height in pixels
    metadata : dict, default = empty dict
        Image metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    url: str
    alt_text: str = ''
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this image.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_image method

        Returns
        -------
        Any
            Result from visitor.visit_image(self)

        """
        return visitor.visit_image(self)


@dataclass
class LineBreak(Node):
    """Line break node.

    Represents a line break (hard or soft).

    Parameters
    ----------
    soft : bool, default = False
        True for soft breaks (newline in source), False for hard breaks
    metadata : dict, default = empty dict
        Line break metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    soft: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this line break.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_line_break method

        Returns
        -------
        Any
            Result from visitor.visit_line_break(self)

        """
        return visitor.visit_line_break(self)


# ============================================================================
# Extended Inline Nodes
# ============================================================================


@dataclass
class Strikethrough(Node):
    """Strikethrough node (GFM extension).

    Represents strikethrough text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes with strikethrough
    metadata : dict, default = empty dict
        Strikethrough metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this strikethrough.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_strikethrough method

        Returns
        -------
        Any
            Result from visitor.visit_strikethrough(self)

        """
        return visitor.visit_strikethrough(self)


@dataclass
class Underline(Node):
    """Underline node (non-standard extension).

    Represents underlined text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes with underline
    metadata : dict, default = empty dict
        Underline metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this underline.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_underline method

        Returns
        -------
        Any
            Result from visitor.visit_underline(self)

        """
        return visitor.visit_underline(self)


@dataclass
class Superscript(Node):
    """Superscript node (non-standard extension).

    Represents superscript text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes in superscript
    metadata : dict, default = empty dict
        Superscript metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this superscript.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_superscript method

        Returns
        -------
        Any
            Result from visitor.visit_superscript(self)

        """
        return visitor.visit_superscript(self)


@dataclass
class Subscript(Node):
    """Subscript node (non-standard extension).

    Represents subscript text.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline nodes in subscript
    metadata : dict, default = empty dict
        Subscript metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this subscript.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_subscript method

        Returns
        -------
        Any
            Result from visitor.visit_subscript(self)

        """
        return visitor.visit_subscript(self)


@dataclass
class HTMLInline(Node):
    """Inline HTML node.

    Represents inline HTML content.

    Parameters
    ----------
    content : str
        Raw HTML content
    metadata : dict, default = empty dict
        HTML metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this inline HTML.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_html_inline method

        Returns
        -------
        Any
            Result from visitor.visit_html_inline(self)

        """
        return visitor.visit_html_inline(self)
