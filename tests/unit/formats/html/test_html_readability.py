"""Tests for the optional readability extraction in the HTML parser."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from all2md.ast import Document, Heading, Text
from all2md.exceptions import DependencyError
from all2md.options import HtmlOptions
from all2md.parsers.html import HtmlToAstConverter


def _flatten_text(nodes: list) -> str:
    """Collect all text content from AST nodes for assertion convenience."""
    collected: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, Text):
            collected.append(node.content)
            return

        if hasattr(node, "content") and isinstance(node.content, list):
            for child in node.content:
                visit(child)

        if hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                visit(child)

    for entry in nodes:
        visit(entry)

    return "".join(collected)


def test_html_readability_uses_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the converter prefers readability summary content when enabled."""
    captured: dict[str, str] = {}

    class StubDocument:
        def __init__(self, html: str) -> None:
            captured["html"] = html

        def summary(self, html_partial: bool = True) -> str:  # noqa: D401 - interface parity
            return "<html><body><article><p>Readable article body</p></article></body></html>"

        def short_title(self) -> str:
            return "Readable Title"

        def title(self) -> str:
            return "Readable Title"

    stub_module = SimpleNamespace(Document=StubDocument)

    # Mock both importlib.import_module (for the decorator) and sys.modules (for the import statement)
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name == "readability":
            return stub_module
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    # Also add to sys.modules so that "import readability" finds it
    monkeypatch.setitem(sys.modules, "readability", stub_module)

    html_input = (
        "<html><head><title>Original Page</title></head><body>"
        "<nav>Site Navigation</nav><article><p>Readable article body</p></article>"
        "</body></html>"
    )

    options = HtmlOptions(extract_readable=True, extract_title=True)
    converter = HtmlToAstConverter(options)
    document = converter.convert_to_ast(html_input)

    assert captured["html"] == html_input

    assert isinstance(document, Document)
    text_content = _flatten_text(document.children)
    assert "Readable article body" in text_content
    assert "Site Navigation" not in text_content

    first_child = document.children[0]
    assert isinstance(first_child, Heading)
    heading_text = _flatten_text(getattr(first_child, "content", []))
    assert heading_text == "Readable Title"


def test_html_readability_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a helpful error is raised when readability-lxml is absent."""
    # Remove readability from sys.modules if it exists
    monkeypatch.delitem(sys.modules, "readability", raising=False)

    # Mock importlib.import_module to raise ImportError for readability
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name == "readability":
            raise ImportError("No module named 'readability'")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    converter = HtmlToAstConverter(HtmlOptions(extract_readable=True))

    with pytest.raises(DependencyError) as exc_info:
        converter.convert_to_ast("<html><body><p>content</p></body></html>")

    message = str(exc_info.value)
    assert "readability-lxml" in message
    assert "requires the following packages:" in message
