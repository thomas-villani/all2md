"""Type stubs for docx.text.hyperlink module."""

from typing import Any

class Hyperlink:
    """Represents a hyperlink in a Word document."""

    @property
    def address(self) -> str | None:
        """The URL or target of the hyperlink."""
        ...

    @property
    def runs(self) -> list[Any]:
        """List of Run objects in this hyperlink."""
        ...

    @property
    def text(self) -> str:
        """Display text of the hyperlink."""
        ...

    @property
    def _element(self) -> Any:
        """Internal XML element."""
        ...
