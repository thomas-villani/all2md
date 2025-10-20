"""Integration coverage for readability-assisted HTML parsing."""

from __future__ import annotations

from pathlib import Path

from all2md import HtmlOptions, to_markdown
from all2md.ast import Heading
from all2md.parsers.html import HtmlToAstConverter

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "documents"
    / "html_readability_article.html"
)


def _flatten_text(nodes: list) -> str:
    """Collect text content from AST nodes for assertions."""
    parts: list[str] = []

    def visit(node: object) -> None:
        if hasattr(node, "content"):
            value = node.content
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        if hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                visit(child)
        if isinstance(node, str):
            parts.append(node)

    for item in nodes:
        visit(item)

    return "".join(parts)


def test_parser_with_readability_discards_navigation() -> None:
    """HtmlToAstConverter should prefer readability output when enabled."""
    html_content = FIXTURE_PATH.read_text(encoding="utf-8")
    options = HtmlOptions(extract_readable=True, extract_title=True)
    document = HtmlToAstConverter(options).convert_to_ast(html_content)

    assert document.children, "Expected children in converted document"
    first_child = document.children[0]
    assert isinstance(first_child, Heading)
    heading_text = _flatten_text(first_child.content)
    assert heading_text == "Sample Readability Article"

    full_text = _flatten_text(document.children)
    assert "The Future of Clean Energy" in full_text
    assert "Massive investments" in full_text
    assert "Home" not in full_text
    assert "Sponsored" not in full_text


def test_markdown_output_changes_with_readability() -> None:
    """Using readability should remove navigation boilerplate from markdown output."""
    html_content = FIXTURE_PATH.read_text(encoding="utf-8")

    standard_markdown = to_markdown(
        html_content,
        source_format="html",
        parser_options=HtmlOptions(extract_title=True),
    )

    readability_markdown = to_markdown(
        html_content,
        source_format="html",
        parser_options=HtmlOptions(extract_readable=True, extract_title=True),
    )

    assert "Home" in standard_markdown
    assert "Sponsored" in standard_markdown
    assert "Home" not in readability_markdown
    assert "Sponsored" not in readability_markdown
    assert "The Future of Clean Energy" in readability_markdown
