"""Type stubs for docx.table module."""

from typing import Any

class Table:
    """Represents a table in a Word document."""

    @property
    def rows(self) -> Any:
        """Collection of rows in the table."""
        ...

    @property
    def columns(self) -> Any:
        """Collection of columns in the table."""
        ...

    @property
    def style(self) -> Any:
        """Table style."""
        ...

    @style.setter
    def style(self, value: str | Any) -> None: ...

    def cell(self, row_idx: int, col_idx: int) -> Any:
        """Get a specific cell.

        Parameters
        ----------
        row_idx : int
            Row index
        col_idx : int
            Column index

        Returns
        -------
        _Cell
            The cell object

        """
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...


class _Row:
    """Represents a table row."""

    @property
    def cells(self) -> list[Any]:
        """List of cells in this row."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...


class _Cell:
    """Represents a table cell."""

    @property
    def text(self) -> str:
        """Plain text content of the cell."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def paragraphs(self) -> list[Any]:
        """List of paragraphs in the cell."""
        ...

    @property
    def tables(self) -> list[Table]:
        """List of nested tables in the cell."""
        ...

    def add_paragraph(self, text: str = "", style: str | None = None) -> Any:
        """Add a paragraph to the cell."""
        ...

    def merge(self, other_cell: _Cell) -> _Cell:
        """Merge this cell with another cell."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...
