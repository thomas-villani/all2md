"""Type stubs for pptx.shapes.graphfrm module."""

from typing import Any

from pptx.shapes.base import BaseShape

class GraphicFrame(BaseShape):
    """Represents a graphic frame shape (chart, table, SmartArt, etc.)."""

    @property
    def has_chart(self) -> bool:
        """True if this graphic frame contains a chart."""
        ...

    @property
    def chart(self) -> Any:
        """Chart object if this frame contains a chart."""
        ...

    @property
    def has_table(self) -> bool:
        """True if this graphic frame contains a table."""
        ...

    @property
    def table(self) -> Any:
        """Table object if this frame contains a table."""
        ...
