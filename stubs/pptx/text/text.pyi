"""Type stubs for pptx.text.text module."""

from typing import Any

class TextFrame:
    """Represents a text frame in a PowerPoint shape."""

    @property
    def text(self) -> str:
        """Plain text content of the text frame."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def paragraphs(self) -> list[Any]:
        """List of Paragraph objects in this text frame."""
        ...

    def clear(self) -> None:
        """Remove all paragraphs and content from the text frame."""
        ...

    def add_paragraph(self) -> Any:
        """Add a new paragraph to the text frame.

        Returns
        -------
        Paragraph
            The newly created paragraph

        """
        ...


class _Paragraph:
    """Represents a paragraph in a text frame."""

    @property
    def text(self) -> str:
        """Plain text content of the paragraph."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def runs(self) -> list[Any]:
        """List of Run objects in this paragraph."""
        ...

    @property
    def level(self) -> int:
        """Indentation level (0-8) for this paragraph."""
        ...

    @level.setter
    def level(self, value: int) -> None: ...

    @property
    def font(self) -> Any:
        """Font object for paragraph-level formatting."""
        ...

    def add_run(self) -> Any:
        """Add a new run to the paragraph.

        Returns
        -------
        Run
            The newly created run

        """
        ...

    @property
    def _p(self) -> Any:
        """Internal paragraph XML element."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...


class _Run:
    """Represents a run of text with specific formatting."""

    @property
    def text(self) -> str:
        """Text content of the run."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def font(self) -> Any:
        """Font object for run-level formatting."""
        ...


class Font:
    """Provides access to font formatting properties."""

    @property
    def bold(self) -> bool | None:
        """Bold formatting."""
        ...

    @bold.setter
    def bold(self, value: bool) -> None: ...

    @property
    def italic(self) -> bool | None:
        """Italic formatting."""
        ...

    @italic.setter
    def italic(self, value: bool) -> None: ...

    @property
    def underline(self) -> bool | Any:
        """Underline formatting."""
        ...

    @underline.setter
    def underline(self, value: bool | Any) -> None: ...

    @property
    def name(self) -> str | None:
        """Font name (typeface)."""
        ...

    @name.setter
    def name(self, value: str) -> None: ...

    @property
    def size(self) -> Any:
        """Font size in points."""
        ...

    @size.setter
    def size(self, value: Any) -> None: ...

    @property
    def color(self) -> Any:
        """ColorFormat object for this font."""
        ...
