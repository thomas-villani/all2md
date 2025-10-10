"""Type stubs for pptx.presentation module."""

from pathlib import Path
from typing import IO, Any

class Presentation:
    """Represents a PowerPoint presentation."""

    def __init__(self, pptx: str | Path | IO[bytes] | None = None) -> None:
        """Create or open a PowerPoint presentation.

        Parameters
        ----------
        pptx : str, Path, IO[bytes], or None
            Path to existing presentation or file-like object. If None, creates new presentation.

        """
        ...

    def save(self, path_or_stream: str | Path | IO[bytes]) -> None:
        """Save the presentation.

        Parameters
        ----------
        path_or_stream : str, Path, or IO[bytes]
            Output destination

        """
        ...

    @property
    def slides(self) -> Any:
        """Slides collection for this presentation."""
        ...

    @property
    def slide_layouts(self) -> Any:
        """Slide layouts collection."""
        ...

    @property
    def core_properties(self) -> Any:
        """Core properties (metadata) of the presentation."""
        ...

    @property
    def slide_width(self) -> int:
        """Width of slides in EMUs (English Metric Units)."""
        ...

    @property
    def slide_height(self) -> int:
        """Height of slides in EMUs (English Metric Units)."""
        ...
