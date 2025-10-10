"""Type stubs for pptx.table module."""

from typing import Any

class Table:
    """Represents a table in a PowerPoint slide."""

    @property
    def rows(self) -> list[_Row]:
        """List of table rows."""
        ...

    @property
    def columns(self) -> list[Any]:
        """List of table columns."""
        ...


class _Row:
    """Represents a row in a PowerPoint table."""

    @property
    def cells(self) -> list[_Cell]:
        """List of cells in this row."""
        ...

    @property
    def height(self) -> int:
        """Height of row in EMUs."""
        ...


class _Cell:
    """Represents a cell in a PowerPoint table."""

    @property
    def text(self) -> str:
        """Plain text content of the cell."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def text_frame(self) -> Any:
        """TextFrame object for this cell."""
        ...

    @property
    def margin_left(self) -> int:
        """Left margin in EMUs."""
        ...

    @property
    def margin_right(self) -> int:
        """Right margin in EMUs."""
        ...

    @property
    def margin_top(self) -> int:
        """Top margin in EMUs."""
        ...

    @property
    def margin_bottom(self) -> int:
        """Bottom margin in EMUs."""
        ...
