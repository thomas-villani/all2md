"""reStructuredText fixture generators for converter testing."""

from __future__ import annotations

from io import BytesIO


def create_rst_with_directives() -> str:
    """Return RST text with sections, lists, code-blocks, and directives."""
    return (
        "Fixture Document\n"
        "================\n\n"
        ".. note:: This demonstrates typical reStructuredText constructs.\n\n"
        "Section Heading\n"
        "---------------\n\n"
        "Paragraph with **bold** and *italic* text and a reference_ link.\n\n"
        "Bullet list::\n\n"
        "- Item one\n"
        "- Item two\n\n"
        ".. code-block:: python\n\n"
        "    def greet(name):\n"
        "        return f\"Hello, {name}!\"\n\n"
        ".. table:: Sample Data\n\n"
        "   ========  ========\n"
        "   Column A  Column B\n"
        "   ========  ========\n"
        "   Alpha     1\n"
        "   Beta      2\n"
        "   ========  ========\n\n"
        ".. _reference: https://example.com\n"
    )


def rst_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode RST text to bytes."""
    return text.encode(encoding)


def rst_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream containing RST content."""
    return BytesIO(rst_to_bytes(text, encoding=encoding))
