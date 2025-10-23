"""Type stubs for python-docx library.

This stub file provides type hints for the python-docx library,
which lacks official type annotations.
"""

from pathlib import Path
from typing import IO, Any

class Document:
    """Represents a Word document."""

    def __init__(self, docx: str | Path | IO[bytes] | None = None) -> None:
        """Create or open a Word document.

        Parameters
        ----------
        docx : str, Path, IO[bytes], or None
            Path to existing document or file-like object. If None, creates new document.

        """
        ...

    def add_paragraph(self, text: str = "", style: str | None = None) -> Any:
        """Add a paragraph to the document.

        Parameters
        ----------
        text : str
            Paragraph text
        style : str or None
            Style name to apply

        Returns
        -------
        Paragraph
            The created paragraph object

        """
        ...

    def add_heading(self, text: str = "", level: int = 1) -> Any:
        """Add a heading to the document.

        Parameters
        ----------
        text : str
            Heading text
        level : int
            Heading level (1-9)

        Returns
        -------
        Paragraph
            The created heading paragraph

        """
        ...

    def add_table(self, rows: int, cols: int, style: str | None = None) -> Any:
        """Add a table to the document.

        Parameters
        ----------
        rows : int
            Number of rows
        cols : int
            Number of columns
        style : str or None
            Table style name

        Returns
        -------
        Table
            The created table object

        """
        ...

    def add_comment(self, runs: Any, text: str = "", author: str = "", initials: str = "") -> Any:
        """Add a comment to the document.

        Parameters
        ----------
        runs : Run or sequence of Run
            Run or runs to attach the comment to
        text : str, default = ""
            Comment text content
        author : str, default = ""
            Comment author name
        initials : str, default = ""
            Author initials

        Returns
        -------
        Comment
            The created comment object

        """
        ...

    def save(self, path_or_stream: str | Path | IO[bytes]) -> None:
        """Save the document.

        Parameters
        ----------
        path_or_stream : str, Path, or IO[bytes]
            Output destination

        """
        ...

    @property
    def paragraphs(self) -> list[Any]:
        """List of paragraphs in the document."""
        ...

    @property
    def tables(self) -> list[Any]:
        """List of tables in the document."""
        ...

    @property
    def sections(self) -> Any:
        """Document sections collection."""
        ...

    @property
    def styles(self) -> Any:
        """Document styles collection."""
        ...

    @property
    def core_properties(self) -> Any:
        """Document core properties (metadata)."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element (low-level API)."""
        ...
