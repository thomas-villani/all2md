#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/builder.py
"""Builder helper classes for constructing AST structures.

This module provides helper classes that simplify the construction of
complex AST structures like nested lists and tables. These builders
handle the bookkeeping of nesting and structure, allowing parsers
to focus on content extraction.

"""

from __future__ import annotations

from typing import Literal, Sequence

from all2md.ast.nodes import (
    Alignment,
    Document,
    List,
    ListItem,
    Node,
    Table,
    TableCell,
    TableRow,
)


class ListBuilder:
    """Helper for building nested list structures.

    This class manages the complexity of creating properly nested lists,
    handling level transitions and list type changes automatically.

    Parameters
    ----------
    root : Document or None, default = None
        Root document to append lists to. If None, creates a new Document.
    allow_placeholders : bool, default = False
        If True, allows creation of placeholder list items when nesting without
        a parent item. Placeholder items will be marked with metadata
        {"placeholder": True}. If False, raises ValueError on invalid nesting.
    default_start : int, default = 1
        Default starting number for ordered lists
    default_tight : bool, default = True
        Default tight spacing for lists (True means no blank lines between items)

    Examples
    --------
    >>> builder = ListBuilder()
    >>> builder.add_item(level=1, ordered=False, content=[Text("Item 1")])
    >>> builder.add_item(level=2, ordered=False, content=[Text("Nested")])
    >>> builder.add_item(level=1, ordered=False, content=[Text("Item 2")])
    >>> doc = builder.get_document()

    """

    def __init__(
            self,
            root: Document | None = None,
            allow_placeholders: bool = False,
            default_start: int = 1,
            default_tight: bool = True
    ):
        """Initialize the list builder with an optional root document."""
        self.root = root or Document()
        self._list_stack: list[tuple[List, int]] = []
        self.allow_placeholders = allow_placeholders
        self.default_start = default_start
        self.default_tight = default_tight

    def add_item(
            self,
            level: int,
            ordered: bool,
            content: list[Node],
            task_status: Literal['checked', 'unchecked'] | None = None,
            start: int | None = None,
            tight: bool | None = None
    ) -> None:
        """Add a list item at the specified nesting level.

        Parameters
        ----------
        level : int
            Nesting level (1 is top-level, 2 is nested once, etc.)
        ordered : bool
            True for ordered lists, False for unordered
        content : list of Node
            Block content for the list item
        task_status : {'checked', 'unchecked'} or None, default = None
            Optional task list status
        start : int or None, default = None
            Starting number for ordered lists. If None, uses default_start.
            Only applies when a new list is created.
        tight : bool or None, default = None
            Tight spacing for lists. If None, uses default_tight.
            Only applies when a new list is created.

        Raises
        ------
        ValueError
            If level is less than 1, or if allow_placeholders=False and
            nesting is attempted without a parent item

        """
        if level < 1:
            raise ValueError(f"Level must be >= 1, got {level}")

        # Pop stack while current level is greater than target level
        while self._list_stack and self._list_stack[-1][1] > level:
            self._list_stack.pop()

        # Determine current level
        current_level = self._list_stack[-1][1] if self._list_stack else 0

        # Handle same-level continuation or type change
        if self._list_stack and current_level == level:
            parent_list, _ = self._list_stack[-1]

            # Check if list type changed at same level
            if parent_list.ordered != ordered:
                # Start a sibling list at the same level
                self._list_stack.pop()

                # Create new list and attach to appropriate parent
                new_list = List(
                    ordered=ordered,
                    items=[],
                    start=start if start is not None else self.default_start,
                    tight=tight if tight is not None else self.default_tight
                )
                if level == 1:
                    # Top-level: attach to root
                    self.root.children.append(new_list)
                else:
                    # Nested: attach to parent level's last item
                    if self._list_stack:
                        parent_item = self._list_stack[-1][0].items[-1]
                        parent_item.children.append(new_list)
                    else:
                        # Shouldn't happen, but fallback to root
                        self.root.children.append(new_list)

                self._list_stack.append((new_list, level))
                parent_list = new_list

        # Handle nesting down: create intermediate lists as needed
        while current_level < level:
            new_list = List(
                ordered=ordered,
                items=[],
                start=start if start is not None else self.default_start,
                tight=tight if tight is not None else self.default_tight
            )

            if current_level == 0:
                # First list: attach to root
                self.root.children.append(new_list)
            else:
                # Nested list: attach to last item of previous level
                parent_list = self._list_stack[-1][0]
                if not parent_list.items:
                    # Parent list has no items yet
                    if not self.allow_placeholders:
                        raise ValueError(
                            f"Cannot nest to level {level} without a parent item at level {current_level}. "
                            f"Either add an item at level {current_level} first, or enable allow_placeholders."
                        )
                    # Create a placeholder item with metadata
                    placeholder_item = ListItem(children=[], metadata={"placeholder": True})
                    parent_list.items.append(placeholder_item)

                parent_item = parent_list.items[-1]
                parent_item.children.append(new_list)

            current_level += 1
            self._list_stack.append((new_list, current_level))

        # Add the item to the current list
        parent_list, _ = self._list_stack[-1]
        item = ListItem(children=content, task_status=task_status)
        parent_list.items.append(item)

    def get_document(self) -> Document:
        """Get the constructed document.

        Returns
        -------
        Document
            Document containing all built lists

        """
        return self.root


class TableBuilder:
    """Helper for building table structures.

    This class simplifies table construction by handling row and cell
    management, alignment tracking, and header designation.

    Parameters
    ----------
    has_header : bool, default = False
        Whether the first row should be designated as a header

    Examples
    --------
    >>> builder = TableBuilder(has_header=True)
    >>> builder.add_row([Text("Name"), Text("Age")], is_header=True)
    >>> builder.add_row([Text("Alice"), Text("30")])
    >>> builder.add_row([Text("Bob"), Text("25")])
    >>> table = builder.get_table()

    """

    def __init__(self, has_header: bool = False):
        """Initialize the table builder with optional header flag."""
        self.has_header = has_header
        self.header: TableRow | None = None
        self.rows: list[TableRow] = []
        self.alignments: list[Alignment | None] = []
        self.caption: str | None = None

    def add_row(
            self,
            cells: Sequence[str | Node | Sequence[Node]],
            is_header: bool = False,
            alignments: list[Alignment | None] | None = None
    ) -> None:
        """Add a row to the table.

        This method accepts a flexible cell specification allowing mixed types
        per cell. Each cell can be a plain string, a single Node, or a sequence
        of inline Node objects.

        Parameters
        ----------
        cells : Sequence of str, Node, or Sequence of Node
            Cell contents where each cell can be:
            - A plain string (e.g., "Hello")
            - A single Node (e.g., Text("Hello"))
            - A sequence of inline nodes (e.g., [Text("Hello"), Strong(content=[Text("world")])])

            Mixed types are supported per-cell. An empty sequence creates an empty row.
        is_header : bool, default False
            Whether this is a header row. If has_header=True and no header exists yet,
            the first row added will automatically be treated as a header regardless
            of this parameter.
        alignments : list of Alignment or None, optional
            Column alignments (only used for header rows). Length should match the
            number of cells. If not specified and this is a header row, all alignments
            will be set to None (default alignment).

        Examples
        --------
                ["Name", "Age"]  # All strings
                [Text("Name"), Text("Age")]  # All single nodes
                [[Text("Name")], [Text("Age")]]  # All node sequences
                ["Name", [Text("Age: "), Strong(content=[Text("30")])]]  # Mixed
                [Text("Name"), [Text("Age: "), Strong(content=[Text("30")])]]  # Mixed

        Notes
        -----
        The flexible typing allows for ergonomic table building while maintaining
        type safety. The implementation normalizes all inputs to TableCell objects
        internally.

        """
        from all2md.ast.nodes import Text

        # Auto-detect header row if has_header is True and no header exists yet
        if self.has_header and self.header is None and not is_header:
            is_header = True

        table_cells: list[TableCell] = []
        for cell_content in cells:
            if isinstance(cell_content, str):
                cell_nodes: list[Node] = [Text(content=cell_content)]
            elif isinstance(cell_content, Node):
                # Handle single Node instances (Issue 8)
                cell_nodes = [cell_content]
            else:
                cell_nodes = list(cell_content)

            table_cells.append(TableCell(content=cell_nodes))

        row = TableRow(cells=table_cells, is_header=is_header)

        if is_header:
            # Prevent overwriting existing header (Issue 10)
            if self.header is not None:
                raise ValueError(
                    "Table already has a header row. Cannot add another header. "
                    "Use is_header=False for body rows."
                )
            self.header = row
            if alignments:
                # Validate alignment length matches cell count (Issue 9)
                if len(alignments) != len(table_cells):
                    raise ValueError(
                        f"Alignment count ({len(alignments)}) must match cell count ({len(table_cells)})"
                    )
                self.alignments = alignments
            elif not self.alignments:
                # Initialize alignments to match number of columns
                self.alignments = [None] * len(table_cells)
        else:
            # Auto-pad alignments if row has more columns (Issue 9)
            if len(table_cells) > len(self.alignments):
                self.alignments.extend([None] * (len(table_cells) - len(self.alignments)))
            self.rows.append(row)

    def set_caption(self, caption: str) -> None:
        """Set the table caption.

        Parameters
        ----------
        caption : str
            Table caption text

        """
        self.caption = caption

    def set_column_alignment(
            self,
            column_index: int,
            alignment: Alignment | None
    ) -> None:
        """Set alignment for a specific column.

        Parameters
        ----------
        column_index : int
            Zero-based column index
        alignment : {'left', 'center', 'right'} or None
            Column alignment

        """
        while len(self.alignments) <= column_index:
            self.alignments.append(None)
        self.alignments[column_index] = alignment

    def get_table(self) -> Table:
        """Get the constructed table.

        Returns
        -------
        Table
            Completed table node

        """
        return Table(
            header=self.header,
            rows=self.rows,
            alignments=self.alignments,
            caption=self.caption
        )


class DocumentBuilder:
    """Helper for building complete documents.

    This class provides a fluent interface for constructing documents
    with multiple block-level elements.

    Examples
    --------
    >>> builder = DocumentBuilder()
    >>> builder.add_heading(1, [Text("Title")])
    >>> builder.add_paragraph([Text("Content")])
    >>> doc = builder.get_document()

    """

    def __init__(self) -> None:
        """Initialize the document builder with an empty children list."""
        self.children: list[Node] = []

    def add_node(self, node: Node) -> DocumentBuilder:
        """Add a node to the document.

        Parameters
        ----------
        node : Node
            Block-level node to add

        Returns
        -------
        DocumentBuilder
            Self for method chaining

        """
        self.children.append(node)
        return self

    def add_heading(self, level: int, content: list[Node]) -> DocumentBuilder:
        """Add a heading to the document.

        Parameters
        ----------
        level : int
            Heading level (1-6)
        content : list of Node
            Inline content

        Returns
        -------
        DocumentBuilder
            Self for method chaining

        """
        from all2md.ast.nodes import Heading
        self.children.append(Heading(level=level, content=content))
        return self

    def add_paragraph(self, content: list[Node]) -> DocumentBuilder:
        """Add a paragraph to the document.

        Parameters
        ----------
        content : list of Node
            Inline content

        Returns
        -------
        DocumentBuilder
            Self for method chaining

        """
        from all2md.ast.nodes import Paragraph
        self.children.append(Paragraph(content=content))
        return self

    def add_code_block(
            self,
            content: str,
            language: str | None = None
    ) -> DocumentBuilder:
        """Add a code block to the document.

        Parameters
        ----------
        content : str
            Code content
        language : str or None, default = None
            Programming language

        Returns
        -------
        DocumentBuilder
            Self for method chaining

        """
        from all2md.ast.nodes import CodeBlock
        self.children.append(CodeBlock(content=content, language=language))
        return self

    def add_thematic_break(self) -> DocumentBuilder:
        """Add a thematic break to the document.

        Returns
        -------
        DocumentBuilder
            Self for method chaining

        """
        from all2md.ast.nodes import ThematicBreak
        self.children.append(ThematicBreak())
        return self

    def get_document(self) -> Document:
        """Get the constructed document.

        Returns
        -------
        Document
            Completed document

        """
        return Document(children=self.children)
