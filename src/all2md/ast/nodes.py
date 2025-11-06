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
    - ThematicBreak, HTMLBlock, Comment
    - FootnoteDefinition, DefinitionList, MathBlock

Inline nodes represent text formatting:
    - Text, Emphasis, Strong, Code
    - Link, Image, LineBreak
    - Strikethrough, Underline, Superscript, Subscript
    - HTMLInline, CommentInline
    - FootnoteReference, MathInline

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal, Optional

if TYPE_CHECKING:
    from all2md.ast.sections import Section

MathNotation = Literal["latex", "mathml", "html"]
Alignment = Literal["left", "center", "right"]


def _normalize_math_representations(
    content: str,
    notation: MathNotation,
    representations: dict[MathNotation, str],
) -> None:
    if notation not in {"latex", "mathml", "html"}:
        raise ValueError(f"Unsupported math notation: {notation}")
    if notation not in representations and content:
        representations[notation] = content


def _select_math_representation(
    content: str,
    notation: MathNotation,
    representations: dict[MathNotation, str],
    preferred: MathNotation,
) -> tuple[str, MathNotation]:
    if preferred in representations:
        return representations[preferred], preferred

    if preferred == notation:
        return content, notation

    for fallback in ("latex", "mathml", "html"):
        if fallback in representations:
            return representations[fallback], fallback
        if fallback == notation:
            return content, notation

    return content, notation


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

    def add_section_after(
        self, target: str | int, new_section: "Section | Document", case_sensitive: bool = False
    ) -> Document:
        """Add a new section after the specified target section.

        Parameters
        ----------
        target : str or int
            Heading text or section index to insert after
        new_section : Section or Document
            Section or document to insert
        case_sensitive : bool, default = False
            Whether text matching is case-sensitive (for string targets)

        Returns
        -------
        Document
            New document with the section inserted

        Raises
        ------
        ValueError
            If target section is not found

        Examples
        --------
        >>> from all2md.ast.sections import Section
        >>> from all2md.ast.nodes import Heading, Paragraph, Text
        >>> new_section = Section(
        ...     heading=Heading(level=2, content=[Text("New Section")]),
        ...     content=[Paragraph(content=[Text("Content")])],
        ...     level=2, start_index=0, end_index=0
        ... )
        >>> updated_doc = doc.add_section_after("Introduction", new_section)

        """
        from all2md.ast.sections import query_sections, section_or_doc_to_nodes

        # Find target section
        if isinstance(target, int):
            target_sections = query_sections(self, target)
        else:
            target_sections = query_sections(self, target, case_sensitive=case_sensitive)

        if not target_sections:
            raise ValueError(f"Target section not found: {target}")

        target_section = target_sections[0]

        # Convert new_section to list of nodes
        new_nodes = section_or_doc_to_nodes(new_section)

        # Insert after target section
        insert_pos = target_section.end_index
        new_children = self.children[:insert_pos] + new_nodes + self.children[insert_pos:]

        return Document(children=new_children, metadata=self.metadata.copy(), source_location=self.source_location)

    def add_section_before(
        self, target: str | int, new_section: "Section | Document", case_sensitive: bool = False
    ) -> Document:
        """Add a new section before the specified target section.

        Parameters
        ----------
        target : str or int
            Heading text or section index to insert before
        new_section : Section or Document
            Section or document to insert
        case_sensitive : bool, default = False
            Whether text matching is case-sensitive (for string targets)

        Returns
        -------
        Document
            New document with the section inserted

        Raises
        ------
        ValueError
            If target section is not found

        Examples
        --------
        >>> from all2md.ast.sections import Section
        >>> from all2md.ast.nodes import Heading, Paragraph, Text
        >>> new_section = Section(
        ...     heading=Heading(level=2, content=[Text("Preface")]),
        ...     content=[Paragraph(content=[Text("Introduction text")])],
        ...     level=2, start_index=0, end_index=0
        ... )
        >>> updated_doc = doc.add_section_before("Chapter 1", new_section)

        """
        from all2md.ast.sections import query_sections, section_or_doc_to_nodes

        # Find target section
        if isinstance(target, int):
            target_sections = query_sections(self, target)
        else:
            target_sections = query_sections(self, target, case_sensitive=case_sensitive)

        if not target_sections:
            raise ValueError(f"Target section not found: {target}")

        target_section = target_sections[0]

        # Convert new_section to list of nodes
        new_nodes = section_or_doc_to_nodes(new_section)

        # Insert before target section
        insert_pos = target_section.start_index
        new_children = self.children[:insert_pos] + new_nodes + self.children[insert_pos:]

        return Document(children=new_children, metadata=self.metadata.copy(), source_location=self.source_location)

    def remove_section(self, target: str | int, case_sensitive: bool = False) -> Document:
        """Remove a section from the document.

        Parameters
        ----------
        target : str or int
            Heading text or section index to remove
        case_sensitive : bool, default = False
            Whether text matching is case-sensitive (for string targets)

        Returns
        -------
        Document
            New document with the section removed

        Raises
        ------
        ValueError
            If target section is not found

        Examples
        --------
        >>> updated_doc = doc.remove_section("Obsolete Section")
        >>> updated_doc = doc.remove_section(2)  # Remove third section

        """
        from all2md.ast.sections import query_sections

        # Find target section
        if isinstance(target, int):
            target_sections = query_sections(self, target)
        else:
            target_sections = query_sections(self, target, case_sensitive=case_sensitive)

        if not target_sections:
            raise ValueError(f"Target section not found: {target}")

        target_section = target_sections[0]

        # Remove section (heading + content)
        new_children = self.children[: target_section.start_index] + self.children[target_section.end_index :]

        return Document(children=new_children, metadata=self.metadata.copy(), source_location=self.source_location)

    def replace_section(
        self, target: str | int, new_content: "Section | Document | list[Node]", case_sensitive: bool = False
    ) -> Document:
        """Replace a section with new content.

        Parameters
        ----------
        target : str or int
            Heading text or section index to replace
        new_content : Section, Document, or list of Node
            New content to replace the section with
        case_sensitive : bool, default = False
            Whether text matching is case-sensitive (for string targets)

        Returns
        -------
        Document
            New document with the section replaced

        Raises
        ------
        ValueError
            If target section is not found

        Examples
        --------
        Replace with a new section:
            >>> from all2md.ast.sections import Section
            >>> from all2md.ast.nodes import Heading, Paragraph, Text
            >>> new_section = Section(
            ...     heading=Heading(level=2, content=[Text("Updated")]),
            ...     content=[Paragraph(content=[Text("New content")])],
            ...     level=2, start_index=0, end_index=0
            ... )
            >>> updated_doc = doc.replace_section("Old Section", new_section)

        Replace with custom nodes:
            >>> new_nodes = [
            ...     Heading(level=2, content=[Text("New Heading")]),
            ...     Paragraph(content=[Text("Content here")])
            ... ]
            >>> updated_doc = doc.replace_section(0, new_nodes)

        """
        from all2md.ast.sections import query_sections, section_or_doc_to_nodes

        # Find target section
        if isinstance(target, int):
            target_sections = query_sections(self, target)
        else:
            target_sections = query_sections(self, target, case_sensitive=case_sensitive)

        if not target_sections:
            raise ValueError(f"Target section not found: {target}")

        target_section = target_sections[0]

        # Convert new_content to list of nodes
        new_nodes = section_or_doc_to_nodes(new_content)

        # Replace section
        new_children = (
            self.children[: target_section.start_index] + new_nodes + self.children[target_section.end_index :]
        )

        return Document(children=new_children, metadata=self.metadata.copy(), source_location=self.source_location)

    def insert_into_section(
        self,
        target: str | int,
        content: "Node | list[Node]",
        position: Literal["start", "end", "after_heading"] = "end",
        case_sensitive: bool = False,
    ) -> Document:
        """Insert content into an existing section.

        Parameters
        ----------
        target : str or int
            Heading text or section index to insert into
        content : Node or list of Node
            Content to insert
        position : {"start", "end", "after_heading"}, default = "end"
            Where to insert the content within the section
        case_sensitive : bool, default = False
            Whether text matching is case-sensitive (for string targets)

        Returns
        -------
        Document
            New document with content inserted

        Raises
        ------
        ValueError
            If target section is not found

        Notes
        -----
        - "start": Insert at the beginning of the section content (before all content)
        - "after_heading": Insert immediately after the heading (same as "start")
        - "end": Insert at the end of the section content (after all content)

        Examples
        --------
        >>> from all2md.ast.nodes import Paragraph, Text
        >>> new_para = Paragraph(content=[Text("Additional info")])
        >>> updated_doc = doc.insert_into_section("Methods", new_para, position="end")

        """
        from all2md.ast.sections import query_sections

        # Find target section
        if isinstance(target, int):
            target_sections = query_sections(self, target)
        else:
            target_sections = query_sections(self, target, case_sensitive=case_sensitive)

        if not target_sections:
            raise ValueError(f"Target section not found: {target}")

        target_section = target_sections[0]

        # Convert content to list
        new_nodes = [content] if isinstance(content, Node) else content

        # Determine insert position
        if position == "start" or position == "after_heading":
            # Insert right after heading
            insert_pos = target_section.start_index + 1
        elif position == "end":
            # Insert at end of section
            insert_pos = target_section.end_index
        else:
            raise ValueError(f"Invalid position: {position}")

        # Insert content
        new_children = self.children[:insert_pos] + new_nodes + self.children[insert_pos:]

        return Document(children=new_children, metadata=self.metadata.copy(), source_location=self.source_location)


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
    fence_char: str = "`"
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
    task_status: Optional[Literal["checked", "unchecked"]] = None
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
    alignments: list[Alignment | None] = field(default_factory=list)
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
    alignment: Alignment | None = None
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

    Represents a block of raw HTML content. This node preserves HTML as-is
    without modification or sanitization.

    Parameters
    ----------
    content : str
        Raw HTML content
    metadata : dict, default = empty dict
        HTML block metadata
    source_location : SourceLocation or None, default = None
        Source location information

    Warnings
    --------
    Security: Raw HTML content is preserved without sanitization. Renderers
    MUST sanitize user-provided HTML content before rendering to prevent
    XSS attacks and other security vulnerabilities. For strict security
    contexts, consider using ValidationVisitor with allow_raw_html=False
    to reject documents containing raw HTML.

    See Also
    --------
    ValidationVisitor : AST validator with optional HTML rejection

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
    alt_text: str = ""
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

    Represents inline HTML content. This node preserves HTML as-is
    without modification or sanitization.

    Parameters
    ----------
    content : str
        Raw HTML content
    metadata : dict, default = empty dict
        HTML metadata
    source_location : SourceLocation or None, default = None
        Source location information

    Warnings
    --------
    Security: Raw HTML content is preserved without sanitization. Renderers
    MUST sanitize user-provided HTML content before rendering to prevent
    XSS attacks and other security vulnerabilities. For strict security
    contexts, consider using ValidationVisitor with allow_raw_html=False
    to reject documents containing raw HTML.

    See Also
    --------
    ValidationVisitor : AST validator with optional HTML rejection

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


@dataclass
class FootnoteReference(Node):
    """Footnote reference node (inline).

    Represents an inline reference to a footnote, typically rendered as [^id].
    This is used with flavors that support footnotes (e.g., MultiMarkdown, Pandoc).

    Parameters
    ----------
    identifier : str
        Footnote identifier (e.g., "1", "note1")
    metadata : dict, default = empty dict
        Footnote reference metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    identifier: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this footnote reference.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_footnote_reference method

        Returns
        -------
        Any
            Result from visitor.visit_footnote_reference(self)

        """
        return visitor.visit_footnote_reference(self)


@dataclass
class MathInline(Node):
    """Inline math node.

    Represents inline mathematical content, typically rendered with $ delimiters.
    Supported by GFM, Pandoc, Kramdown, and MarkdownPlus flavors.

    Parameters
    ----------
    content : str
        LaTeX math content (without delimiters)
    notation : {"latex", "mathml", "html"}, default "latex"
        Format of the primary math representation stored in ``content``.
    representations : dict, default = empty dict
        Additional representations keyed by notation. The primary notation is
        automatically registered when missing.
    metadata : dict, default = empty dict
        Math metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    notation: MathNotation = "latex"
    representations: dict[MathNotation, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this inline math.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_math_inline method

        Returns
        -------
        Any
            Result from visitor.visit_math_inline(self)

        """
        return visitor.visit_math_inline(self)

    def __post_init__(self) -> None:
        """Normalize math representations and ensure notation validity."""
        _normalize_math_representations(self.content, self.notation, self.representations)

    def get_preferred_representation(self, preferred: MathNotation) -> tuple[str, MathNotation]:
        """Return math content for the requested representation with fallback.

        Parameters
        ----------
        preferred : {"latex", "mathml", "html"}
            Requested representation for rendering

        Returns
        -------
        tuple[str, MathNotation]
            Math content and notation actually provided

        """
        return _select_math_representation(
            self.content,
            self.notation,
            self.representations,
            preferred,
        )


@dataclass
class CommentInline(Node):
    """Inline comment node.

    Represents an inline comment that appears within the text flow.
    Comments can originate from HTML comments, DOCX reviewer comments,
    or other format-specific comment mechanisms.

    The node uses metadata to store variant information such as comment type,
    author, date, identifier, and other format-specific attributes.

    Parameters
    ----------
    content : str
        Comment text content
    metadata : dict, default = empty dict
        Comment metadata. Common metadata keys:
        - 'comment_type': str - Type of comment ('html', 'docx_review', 'latex', 'code', 'generic')
        - 'author': str - Comment author name
        - 'date': str - Comment timestamp
        - 'identifier': str - Comment ID for linking/referencing
        - 'label': str - Comment label/number
        - 'range_start': str - Start of commented text range
        - 'range_end': str - End of commented text range
    source_location : SourceLocation or None, default = None
        Source location information

    Examples
    --------
    HTML comment:
        >>> CommentInline(
        ...     content="TODO: Fix this logic",
        ...     metadata={'comment_type': 'html'}
        ... )

    DOCX reviewer comment:
        >>> CommentInline(
        ...     content="This needs clarification",
        ...     metadata={
        ...         'comment_type': 'docx_review',
        ...         'author': 'John Doe',
        ...         'date': '2025-01-20',
        ...         'identifier': 'comment1'
        ...     }
        ... )

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this inline comment.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_comment_inline method

        Returns
        -------
        Any
            Result from visitor.visit_comment_inline(self)

        """
        return visitor.visit_comment_inline(self)


# ============================================================================
# Extended Block Nodes (Markdown Extensions)
# ============================================================================


@dataclass
class FootnoteDefinition(Node):
    """Footnote definition node (block).

    Represents a footnote definition, typically rendered as [^id]: content.
    Used with MultiMarkdown, Pandoc, Kramdown, and MarkdownPlus flavors.

    Parameters
    ----------
    identifier : str
        Footnote identifier matching a FootnoteReference
    content : list of Node, default = empty list
        Block-level content of the footnote
    metadata : dict, default = empty dict
        Footnote definition metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    identifier: str
    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this footnote definition.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_footnote_definition method

        Returns
        -------
        Any
            Result from visitor.visit_footnote_definition(self)

        """
        return visitor.visit_footnote_definition(self)


@dataclass
class DefinitionList(Node):
    """Definition list node (block).

    Represents a definition list containing terms and their descriptions.
    Supported by MultiMarkdown, Pandoc, Kramdown, and MarkdownPlus flavors.

    Parameters
    ----------
    items : list of tuple, default = empty list
        List of (DefinitionTerm, list[DefinitionDescription]) tuples
    metadata : dict, default = empty dict
        Definition list metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this definition list.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_definition_list method

        Returns
        -------
        Any
            Result from visitor.visit_definition_list(self)

        """
        return visitor.visit_definition_list(self)


@dataclass
class DefinitionTerm(Node):
    """Definition term node (block).

    Represents a term in a definition list.

    Parameters
    ----------
    content : list of Node, default = empty list
        Inline content of the term
    metadata : dict, default = empty dict
        Term metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this definition term.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_definition_term method

        Returns
        -------
        Any
            Result from visitor.visit_definition_term(self)

        """
        return visitor.visit_definition_term(self)


@dataclass
class DefinitionDescription(Node):
    """Definition description node (block).

    Represents a description/definition in a definition list.

    Parameters
    ----------
    content : list of Node, default = empty list
        Block-level content of the description
    metadata : dict, default = empty dict
        Description metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: list[Node] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this definition description.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_definition_description method

        Returns
        -------
        Any
            Result from visitor.visit_definition_description(self)

        """
        return visitor.visit_definition_description(self)


@dataclass
class MathBlock(Node):
    """Math block node.

    Represents a block of mathematical content, typically rendered with $$ delimiters.
    Supported by GFM, MultiMarkdown, Pandoc, Kramdown, and MarkdownPlus flavors.

    Parameters
    ----------
    content : str
        LaTeX math content (without delimiters)
    notation : {"latex", "mathml", "html"}, default "latex"
        Format of the primary math representation stored in ``content``.
    representations : dict, default = empty dict
        Additional representations keyed by notation. The primary notation is
        automatically registered when missing.
    metadata : dict, default = empty dict
        Math block metadata
    source_location : SourceLocation or None, default = None
        Source location information

    """

    content: str
    notation: MathNotation = "latex"
    representations: dict[MathNotation, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this math block.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_math_block method

        Returns
        -------
        Any
            Result from visitor.visit_math_block(self)

        """
        return visitor.visit_math_block(self)

    def __post_init__(self) -> None:
        """Normalize math representations and ensure notation validity."""
        _normalize_math_representations(self.content, self.notation, self.representations)

    def get_preferred_representation(self, preferred: MathNotation) -> tuple[str, MathNotation]:
        """Return math content for the requested representation with fallback."""
        return _select_math_representation(
            self.content,
            self.notation,
            self.representations,
            preferred,
        )


@dataclass
class Comment(Node):
    """Block-level comment node.

    Represents a standalone comment block that appears at the block level.
    Comments can originate from HTML comments, LaTeX comments, code comments,
    or other format-specific comment mechanisms.

    The node uses metadata to store variant information such as comment type,
    author, date, identifier, and other format-specific attributes.

    Parameters
    ----------
    content : str
        Comment text content
    metadata : dict, default = empty dict
        Comment metadata. Common metadata keys:
        - 'comment_type': str - Type of comment ('html', 'docx_review', 'latex', 'code', 'generic')
        - 'author': str - Comment author name
        - 'date': str - Comment timestamp
        - 'identifier': str - Comment ID for linking/referencing
        - 'label': str - Comment label/number
        - 'range_start': str - Start of commented text range
        - 'range_end': str - End of commented text range
    source_location : SourceLocation or None, default = None
        Source location information

    Examples
    --------
    HTML block comment:
        >>> Comment(
        ...     content="This section needs review",
        ...     metadata={'comment_type': 'html'}
        ... )

    DOCX reviewer comment at document end:
        >>> Comment(
        ...     content="Please verify these numbers",
        ...     metadata={
        ...         'comment_type': 'docx_review',
        ...         'author': 'Jane Smith',
        ...         'date': '2025-01-20',
        ...         'identifier': 'comment2',
        ...         'label': '2'
        ...     }
        ... )

    LaTeX comment:
        >>> Comment(
        ...     content="TODO: Add more examples here",
        ...     metadata={'comment_type': 'latex'}
        ... )

    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source_location: Optional[SourceLocation] = None

    def accept(self, visitor: Any) -> Any:
        """Accept a visitor for processing this comment block.

        Parameters
        ----------
        visitor : Any
            A visitor object with visit_comment method

        Returns
        -------
        Any
            Result from visitor.visit_comment(self)

        """
        return visitor.visit_comment(self)


def get_node_children(node: Node) -> list[Node]:
    """Get all child nodes from a node.

    This is a helper function for visitor pattern implementations that need
    to traverse the AST. It returns a list of all child nodes regardless of
    the node type.

    Parameters
    ----------
    node : Node
        The node to get children from

    Returns
    -------
    list of Node
        List of child nodes (empty list if node has no children)

    Examples
    --------
    >>> heading = Heading(level=1, content=[Text("Hello"), Strong(content=[Text("world")])])
    >>> children = get_node_children(heading)
    >>> len(children)
    2

    """
    # Block nodes with 'children' attribute
    if isinstance(node, (Document, BlockQuote, ListItem)):
        return list(node.children)

    # Inline nodes with 'content' attribute (containing inline nodes)
    if isinstance(
        node,
        (
            Heading,
            Paragraph,
            Emphasis,
            Strong,
            Strikethrough,
            Underline,
            Superscript,
            Subscript,
            Link,
            TableCell,
            DefinitionTerm,
            DefinitionDescription,
        ),
    ):
        return list(node.content)

    # List has items
    if isinstance(node, List):
        return list(node.items)

    # Table has header and rows
    if isinstance(node, Table):
        children: list[Node] = []
        if node.header:
            children.append(node.header)
        children.extend(node.rows)
        return children

    # TableRow has cells
    if isinstance(node, TableRow):
        return list(node.cells)

    # FootnoteDefinition has content
    if isinstance(node, FootnoteDefinition):
        return list(node.content)

    # DefinitionList has terms and descriptions
    if isinstance(node, DefinitionList):
        dl_children: list[Node] = []
        for term, descriptions in node.items:
            dl_children.append(term)
            dl_children.extend(descriptions)
        return dl_children

    # Leaf nodes (no children)
    return []


def replace_node_children(node: Node, new_children: list[Node]) -> Node:
    """Create a copy of a node with replaced children.

    This is a helper function for transformer pattern implementations. It
    creates a new node of the same type with the children replaced.

    Parameters
    ----------
    node : Node
        The node to copy and modify
    new_children : list of Node
        New children to use in the copy

    Returns
    -------
    Node
        New node with replaced children

    Raises
    ------
    ValueError
        If the node type doesn't support children, if children are of the
        wrong type, or if the structure is invalid

    Notes
    -----
    Special handling for Table nodes:
        The function inspects new_children to determine header vs body rows.
        The first TableRow with is_header=True becomes the table header.
        All other rows become body rows. This allows:
        - Adding a header: Include a TableRow with is_header=True
        - Removing a header: Omit rows with is_header=True
        - Preserving structure: Set is_header appropriately on rows

        All new_children must be TableRow instances, or ValueError is raised.

    Examples
    --------
    Replace heading content:
        >>> heading = Heading(level=1, content=[Text("Hello")])
        >>> new_heading = replace_node_children(heading, [Text("Goodbye")])
        >>> new_heading.content[0].content
        'Goodbye'

    Add header to table:
        >>> table = Table(rows=[TableRow(cells=[...], is_header=False)])
        >>> header = TableRow(cells=[...], is_header=True)
        >>> new_table = replace_node_children(table, [header] + table.rows)
        >>> new_table.header is not None
        True

    """
    # Block nodes with 'children' attribute
    if isinstance(node, (Document, BlockQuote, ListItem)):
        return replace(node, children=new_children)

    # Inline nodes with 'content' attribute
    if isinstance(
        node,
        (
            Heading,
            Paragraph,
            Emphasis,
            Strong,
            Strikethrough,
            Underline,
            Superscript,
            Subscript,
            Link,
            TableCell,
            DefinitionTerm,
            DefinitionDescription,
        ),
    ):
        return replace(node, content=new_children)

    # List has items
    if isinstance(node, List):
        return replace(node, items=new_children)  # type: ignore[arg-type]

    # Table needs special handling
    if isinstance(node, Table):
        # Determine header and rows based on new_children state (not old state)
        # Find first TableRow with is_header=True, if any
        header_row: TableRow | None = None
        body_rows: list[TableRow] = []

        for child in new_children:
            if not isinstance(child, TableRow):
                raise ValueError(
                    f"Table children must be TableRow instances, got {type(child).__name__}. "
                    f"Use get_node_children() to understand the expected structure."
                )
            if child.is_header and header_row is None:
                # First row marked as header becomes the header
                header_row = child
            else:
                # All other rows (including additional rows marked is_header) go to body
                body_rows.append(child)

        return replace(node, header=header_row, rows=body_rows)

    # TableRow has cells
    if isinstance(node, TableRow):
        return replace(node, cells=new_children)  # type: ignore[arg-type]

    # FootnoteDefinition has content
    if isinstance(node, FootnoteDefinition):
        return replace(node, content=new_children)

    # DefinitionList needs special handling
    if isinstance(node, DefinitionList):
        raise NotImplementedError(
            "replace_node_children does not support DefinitionList. "
            "DefinitionList has a complex structure with (term, descriptions) tuples "
            "that cannot be directly replaced from a flat children list. "
            "To modify a DefinitionList, reconstruct the items list manually "
            "or use a specialized transformer that understands the structure."
        )

    # Leaf nodes - return as-is
    return node
