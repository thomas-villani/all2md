"""Plaintext fixture generators for baseline conversions."""

from __future__ import annotations

from io import BytesIO


def create_plaintext_with_sections() -> str:
    """Return plain text with headings simulated by underlines and spacing."""
    return (
        "Sample Document\n"
        "==============\n\n"
        "This is an example of plain text that contains a few paragraphs.\n"
        "It should convert to Markdown without any additional formatting.\n\n"
        "Another Section\n"
        "---------------\n\n"
        "Bullet-style lines:\n"
        "- Item one\n"
        "- Item two\n\n"
        "Numbered-style lines:\n"
        "1. First\n"
        "2. Second\n"
    )


def create_plaintext_with_code_block() -> str:
    """Return plain text that contains fenced code-like sections."""
    return (
        "Log Output\n"
        "==========\n\n"
        "The following snippet mimics a shell transcript:\n\n"
        "$ ls -la\n"
        "total 12\n"
        "drwxr-xr-x  3 user staff  96 Mar  1 10:00 .\n"
        "drwxr-xr-x 10 user staff 320 Mar  1 09:59 ..\n"
        "-rw-r--r--  1 user staff 120 Mar  1 10:00 README.txt\n"
    )


def plaintext_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode plain text to bytes with the desired encoding."""
    return text.encode(encoding)


def plaintext_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream from plain text content."""
    return BytesIO(plaintext_to_bytes(text, encoding=encoding))
