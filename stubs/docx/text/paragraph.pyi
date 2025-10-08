"""Type stubs for docx.text.paragraph module."""

from typing import Any, Iterator

class Paragraph:
    """Represents a paragraph in a Word document."""

    @property
    def text(self) -> str:
        """Plain text content of the paragraph."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

    @property
    def style(self) -> Any:
        """Paragraph style."""
        ...

    @style.setter
    def style(self, value: str | Any) -> None: ...

    @property
    def runs(self) -> list[Any]:
        """List of Run objects in this paragraph."""
        ...

    def add_run(self, text: str = "", style: str | None = None) -> Any:
        """Add a run to the paragraph.

        Parameters
        ----------
        text : str
            Text for the run
        style : str or None
            Style to apply

        Returns
        -------
        Run
            The created run object
        """
        ...

    def insert_paragraph_before(self, text: str = "", style: str | None = None) -> Paragraph:
        """Insert a paragraph before this one."""
        ...

    def clear(self) -> Paragraph:
        """Remove all content from the paragraph."""
        ...

    @property
    def alignment(self) -> Any:
        """Paragraph alignment."""
        ...

    @alignment.setter
    def alignment(self, value: Any) -> None: ...

    @property
    def paragraph_format(self) -> Any:
        """ParagraphFormat object for this paragraph."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...

    def iter_inner_content(self) -> Iterator[Any]:
        """Iterate over inner content (runs, hyperlinks, etc.)."""
        ...


class Run:
    """Represents a run of text with specific formatting."""

    @property
    def text(self) -> str:
        """Text content of the run."""
        ...

    @text.setter
    def text(self, value: str) -> None: ...

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
    def font(self) -> Any:
        """Font object for detailed formatting."""
        ...

    @property
    def style(self) -> Any:
        """Run style."""
        ...

    @style.setter
    def style(self, value: str | Any) -> None: ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...
