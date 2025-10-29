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
        '    print("Hello from markdown fixtures!")\n'
        "```\n"
    )


def create_markdown_with_math_blocks() -> str:
    """Return markdown showcasing inline and block math syntaxes."""
    return (
        "# Math Showcase\n\n"
        "Einstein noted that $E = mc^2$ while Euler loved $e^{i\\pi} + 1 = 0$.\n\n"
        "Here is a displayed equation:\n\n"
        "$$\\int_0^1 x^2\\,dx = \\frac{1}{3}$$\n\n"
        "We also mention inline Greek letters like $\\alpha$ and $\\beta$ for completeness.\n"
    )


def create_markdown_with_definition_lists() -> str:
    """Return markdown that exercises definition list formatting."""
    return (
        "Project Roles\n"
        "=============\n\n"
        "Developer\n"
        ": Implements core features and fixes bugs.\n\n"
        "Designer\n"
        ": Crafts the user experience, visuals, and accessibility guidance.\n\n"
        "QA Engineer\n"
        ":\n"
        ": - Creates regression suites\n"
        ": - Automates smoke checks\n"
        ": - Reports findings to the team\n"
    )


def markdown_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode markdown text for IO-based tests."""
    return text.encode(encoding)


def markdown_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream with markdown content."""
    return BytesIO(markdown_to_bytes(text, encoding=encoding))
