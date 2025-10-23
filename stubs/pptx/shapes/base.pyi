"""Type stubs for pptx.shapes.base module."""

from typing import Any

class BaseShape:
    """Base class for all shapes in a PowerPoint presentation."""

    @property
    def shape_type(self) -> int:
        """Type of shape (from MSO_SHAPE_TYPE enumeration)."""
        ...

    @property
    def name(self) -> str:
        """Name of the shape."""
        ...

    @property
    def width(self) -> int:
        """Width of shape in EMUs."""
        ...

    @property
    def height(self) -> int:
        """Height of shape in EMUs."""
        ...

    @property
    def left(self) -> int:
        """Left position in EMUs."""
        ...

    @property
    def top(self) -> int:
        """Top position in EMUs."""
        ...

    @property
    def text(self) -> str:
        """Plain text content of the shape."""
        ...

    @property
    def text_frame(self) -> Any:
        """TextFrame object for this shape."""
        ...

    @property
    def has_text_frame(self) -> bool:
        """True if shape has a text frame."""
        ...

    @property
    def has_table(self) -> bool:
        """True if shape contains a table."""
        ...

    @property
    def table(self) -> Any:
        """Table object if shape has a table."""
        ...

    @property
    def image(self) -> Any:
        """Image object if shape is a picture."""
        ...

    @property
    def has_chart(self) -> bool:
        """True if shape contains a chart."""
        ...

    @property
    def chart(self) -> Any:
        """Chart object if shape has a chart."""
        ...

    @property
    def placeholder_format(self) -> Any:
        """PlaceholderFormat object for placeholder shapes."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element (low-level API)."""
        ...

    @property
    def _p(self) -> Any:
        """Internal paragraph XML element."""
        ...

class PlaceholderFormat:
    """Provides access to placeholder-specific properties."""

    @property
    def idx(self) -> int:
        """Placeholder index."""
        ...

    @property
    def type(self) -> int:
        """Placeholder type."""
        ...
