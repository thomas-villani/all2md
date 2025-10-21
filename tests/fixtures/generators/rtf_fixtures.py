"""RTF fixture generators using handcrafted Rich Text Format payloads."""

from __future__ import annotations

from io import BytesIO


# RTF specs expect ASCII; we keep content simple and deterministic.


def create_basic_rtf_document() -> str:
    """Return a minimal RTF document with headings, lists, and table."""
    return (
        "{\\rtf1\\ansi\\deff0"
        "{\\fonttbl{\\f0 Arial;}{\\f1 Courier New;}}"
        "\\pard\\fs28 Fixture Title\\par"
        "\\pard\\fs24\\par"
        "\\pard This paragraph contains \\b bold\\b0  and \\i italic\\i0  text.\\par"
        "\\pard\\par"
        "\\pard\\li720\\tx720\\bullet Item one\\par"
        "\\bullet Item two\\par"
        "\\pard\\par"
        "\\trowd\\trgaph108\\cellx2000\\cellx4000\\cellx6000"
        "\\intbl Name\\cell Role\\cell Score\\row"
        "\\intbl Alice\\cell Developer\\cell 95\\row"
        "\\intbl Bob\\cell Designer\\cell 88\\row"
        "\\pard\\par"
        "}"  # closing brace for document
    )


def create_rtf_with_code_block() -> str:
    """Return RTF text that simulates a monospace code block."""
    return (
        "{\\rtf1\\ansi\\deff0"
        "{\\fonttbl{\\f0 Arial;}{\\f1 Courier New;}}"
        "\\pard\\fs24 Code Listing\\par"
        "\\pard\\par"
        "\\pard\\f1\\fs20 def hello():\\line    return 'Hello RTF'\\line\\par"
        "}"  # closing brace
    )


def rtf_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode RTF text to bytes."""
    return text.encode(encoding)


def rtf_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream for RTF content."""
    return BytesIO(rtf_to_bytes(text, encoding=encoding))
