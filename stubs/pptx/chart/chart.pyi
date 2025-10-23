"""Type stubs for pptx.chart.chart module."""

from typing import Any

class Chart:
    """Represents a chart in a PowerPoint presentation."""

    @property
    def chart_type(self) -> int:
        """Type of chart (from XL_CHART_TYPE enumeration)."""
        ...

    @property
    def has_title(self) -> bool:
        """True if chart has a title."""
        ...

    @property
    def chart_title(self) -> Any:
        """ChartTitle object for this chart."""
        ...

    @property
    def series(self) -> list[Any]:
        """List of Series objects in this chart."""
        ...

    @property
    def plots(self) -> list[Any]:
        """List of plot objects in this chart."""
        ...

    @property
    def category_axis(self) -> Any:
        """Category axis object (X-axis)."""
        ...

    @property
    def value_axis(self) -> Any:
        """Value axis object (Y-axis)."""
        ...

class ChartTitle:
    """Represents a chart title."""

    @property
    def has_text_frame(self) -> bool:
        """True if title has a text frame."""
        ...

    @property
    def text_frame(self) -> Any:
        """TextFrame object for the chart title."""
        ...

class Series:
    """Represents a data series in a chart."""

    @property
    def name(self) -> str:
        """Name of the series."""
        ...

    @property
    def values(self) -> Any:
        """Values (data points) in this series."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...

class Plot:
    """Represents a plot area in a chart."""

    @property
    def categories(self) -> list[Any]:
        """Category labels for the plot."""
        ...

class Category:
    """Represents a category in a chart."""

    @property
    def label(self) -> str:
        """Label text for this category."""
        ...

class Axis:
    """Represents an axis in a chart."""

    @property
    def has_title(self) -> bool:
        """True if axis has a title."""
        ...

    @property
    def axis_title(self) -> Any:
        """AxisTitle object for this axis."""
        ...

class AxisTitle:
    """Represents an axis title."""

    @property
    def text_frame(self) -> Any:
        """TextFrame object for the axis title."""
        ...
