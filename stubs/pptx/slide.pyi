"""Type stubs for pptx.slide module."""

from typing import Any

class Slide:
    """Represents a slide in a PowerPoint presentation."""

    @property
    def shapes(self) -> Any:
        """Shapes collection for this slide."""
        ...

    @property
    def placeholders(self) -> Any:
        """Placeholders collection for this slide."""
        ...

    @property
    def slide_layout(self) -> Any:
        """Slide layout for this slide."""
        ...


class SlideLayout:
    """Represents a slide layout."""

    @property
    def name(self) -> str:
        """Name of the slide layout."""
        ...

    @property
    def placeholders(self) -> Any:
        """Placeholders in this layout."""
        ...


class Slides:
    """Collection of slides in a presentation."""

    def __iter__(self) -> Any:
        """Iterate over slides."""
        ...

    def __len__(self) -> int:
        """Return number of slides."""
        ...

    def __getitem__(self, index: int) -> Slide:
        """Get slide by index."""
        ...

    def add_slide(self, slide_layout: SlideLayout) -> Slide:
        """Add a new slide with the specified layout.

        Parameters
        ----------
        slide_layout : SlideLayout
            Layout to use for the new slide

        Returns
        -------
        Slide
            The newly created slide

        """
        ...
