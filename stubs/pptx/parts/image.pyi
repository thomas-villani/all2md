"""Type stubs for pptx.parts.image module."""

class Image:
    """Represents an image part in a PowerPoint presentation."""

    @property
    def blob(self) -> bytes:
        """Raw image data bytes."""
        ...

    @property
    def content_type(self) -> str:
        """MIME type of the image."""
        ...

    @property
    def ext(self) -> str:
        """File extension for the image (e.g., 'png', 'jpg')."""
        ...

    @property
    def filename(self) -> str:
        """Filename of the image."""
        ...
