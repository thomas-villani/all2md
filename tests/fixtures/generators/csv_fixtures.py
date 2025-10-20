"""CSV test fixture generators for spreadsheet-to-Markdown scenarios.

These helpers build deterministic CSV payloads that exercise quoting,
embedded commas, multiline cells, and Unicode-safe encodings while keeping
fixtures easy to regenerate in tests.
"""

from __future__ import annotations

from io import BytesIO
from typing import Iterable


def create_basic_csv() -> str:
    """Create a simple CSV dataset with headers and a few rows."""
    rows = [
        ["Name", "Department", "Score"],
        ["Alice Johnson", "Engineering", "92"],
        ["Bob Smith", "Support", "87"],
        ["Carol Davis", "Product", "95"],
    ]
    return _rows_to_csv(rows)


def create_csv_with_special_characters() -> str:
    """Create CSV content that includes commas, quotes, and newlines."""
    rows = [
        ["ID", "Notes", "Amount"],
        ["INV-001", "Contains, comma", "1000"],
        ["INV-002", 'Quoted "value" field', "850.50"],
        ["INV-003", "Multi-line\ncomment entry", "120"],
    ]
    return _rows_to_csv(rows)


def create_csv_with_unicode() -> str:
    """Create CSV content containing extended characters for encoding tests."""
    rows = [
        ["City", "Country", "Population"],
        ["Zürich", "Switzerland", "402762"],
        ["München", "Germany", "1471508"],
        ["São Paulo", "Brazil", "12330000"],
    ]
    return _rows_to_csv(rows)


def csv_to_bytes(csv_text: str, encoding: str = "utf-8") -> bytes:
    """Encode CSV text to bytes for IO-based tests."""
    return csv_text.encode(encoding)


def csv_bytes_io(csv_text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream for the provided CSV content."""
    return BytesIO(csv_to_bytes(csv_text, encoding=encoding))


def _rows_to_csv(rows: Iterable[Iterable[str]]) -> str:
    """Convert an iterable of rows into RFC4180-compliant CSV text."""
    lines: list[str] = []
    for row in rows:
        escaped = []
        for value in row:
            needs_quotes = any(char in value for char in {",", "\n", '"'})
            cell = value.replace('"', '""')
            if needs_quotes:
                cell = f'"{cell}"'
            escaped.append(cell)
        lines.append(",".join(escaped))
    return "\r\n".join(lines) + "\r\n"
