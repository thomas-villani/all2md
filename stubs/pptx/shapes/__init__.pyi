"""Type stubs for pptx.shapes module."""

from typing import Any

from pptx.shapes.base import BaseShape
from pptx.util import Length

class ShapeCollection:
    """Collection of shapes on a slide."""

    def __iter__(self) -> Any:
        """Iterate over shapes."""
        ...

    def __len__(self) -> int:
        """Return number of shapes."""
        ...

    def __getitem__(self, index: int) -> BaseShape:
        """Get shape by index."""
        ...

    @property
    def title(self) -> BaseShape | None:
        """Title shape if present, None otherwise."""
        ...

    def add_textbox(self, left: Length, top: Length, width: Length, height: Length) -> BaseShape:
        """Add a textbox to the slide.

        Parameters
        ----------
        left : Length
            Left position
        top : Length
            Top position
        width : Length
            Width of textbox
        height : Length
            Height of textbox

        Returns
        -------
        BaseShape
            The created textbox shape

        """
        ...

    def add_table(self, rows: int, cols: int, left: Length, top: Length, width: Length, height: Length) -> Any:
        """Add a table to the slide.

        Parameters
        ----------
        rows : int
            Number of rows
        cols : int
            Number of columns
        left : Length
            Left position
        top : Length
            Top position
        width : Length
            Width of table
        height : Length
            Height of table

        Returns
        -------
        Shape with table
            The created table shape

        """
        ...

    def add_picture(
        self, image_file: str, left: Length, top: Length, width: Length | None = None, height: Length | None = None
    ) -> BaseShape:
        """Add a picture to the slide.

        Parameters
        ----------
        image_file : str
            Path to image file
        left : Length
            Left position
        top : Length
            Top position
        width : Length or None
            Width of picture (optional)
        height : Length or None
            Height of picture (optional)

        Returns
        -------
        BaseShape
            The created picture shape

        """
        ...
