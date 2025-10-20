"""Markdown fixture generators for round-trip conversion tests."""

from __future__ import annotations

from io import BytesIO


def create_markdown_with_tables() -> str:
    """Return markdown text featuring tables and emphasis."""
    return (
        "# Quarterly Results\n\n"
        "Below is a table with the latest quarterly metrics.\n\n"
        "| Quarter | Revenue | Growth |\n"
        "|---------|---------|--------|\n"
        "| Q1      | $1.2M   | 12%    |\n"
        "| Q2      | $1.4M   | 16%    |\n"
        "| Q3      | $1.6M   | 18%    |\n"
        "| Q4      | $1.9M   | 22%    |\n\n"
        "**Highlights**: *Strong* growth in the second half of the year.\n"
    )


def create_markdown_with_code_and_lists() -> str:
    """Return markdown that includes nested lists and fenced code."""
    return (
        "# Setup Guide\n\n"
        "1. Install dependencies\n"
        "   - Use `uv pip install -r requirements.txt`\n"
        "   - Verify versions\n"
        "2. Run the application\n\n"
        "```python\n"
        "def main():\n"
        "    print(\"Hello from markdown fixtures!\")\n"
        "```\n"
    )


def markdown_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode markdown text for IO-based tests."""
    return text.encode(encoding)


def markdown_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream with markdown content."""
    return BytesIO(markdown_to_bytes(text, encoding=encoding))
