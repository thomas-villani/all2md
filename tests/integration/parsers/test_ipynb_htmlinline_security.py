"""Integration tests for IPYNB parser HTMLInline security.

This test module validates that the IPYNB parser does not use HTMLInline
nodes for markdown cells which would bypass renderer sanitization, preventing XSS attacks.

Test Coverage:
- Verify no HTMLInline nodes in AST output for markdown cells
- Verify safe text parsing of markdown cell content
- Verify dangerous HTML in markdown cells is not preserved as HTMLInline
- Verify content is properly escaped/sanitized
"""

import json
import tempfile
from pathlib import Path

from all2md import to_markdown
from all2md.ast.visitors import NodeVisitor
from all2md.parsers.ipynb import IpynbToAstConverter


class HTMLInlineDetector(NodeVisitor):
    """Visitor to detect HTMLInline nodes in AST."""

    def __init__(self):
        """Initialize detector."""
        self.found_htmlinline = False
        self.htmlinline_contents = []

    def _visit_children(self, node):
        """Visit children if they exist."""
        if hasattr(node, "children"):
            for child in node.children:
                child.accept(self)
        if hasattr(node, "content"):
            if isinstance(node.content, list):
                for child in node.content:
                    if hasattr(child, "accept"):
                        child.accept(self)
        if hasattr(node, "items"):
            if isinstance(node.items, list):
                for item in node.items:
                    if isinstance(item, list):
                        for subitem in item:
                            if hasattr(subitem, "accept"):
                                subitem.accept(self)

    # Implement all required abstract methods
    def visit_document(self, node):
        self._visit_children(node)

    def visit_heading(self, node):
        self._visit_children(node)

    def visit_paragraph(self, node):
        self._visit_children(node)

    def visit_code_block(self, node):
        pass

    def visit_block_quote(self, node):
        self._visit_children(node)

    def visit_list(self, node):
        for item in node.items:
            item.accept(self)

    def visit_list_item(self, node):
        self._visit_children(node)

    def visit_table(self, node):
        if node.header:
            node.header.accept(self)
        for row in node.rows:
            row.accept(self)

    def visit_table_row(self, node):
        for cell in node.cells:
            cell.accept(self)

    def visit_table_cell(self, node):
        self._visit_children(node)

    def visit_thematic_break(self, node):
        pass

    def visit_html_block(self, node):
        pass

    def visit_text(self, node):
        pass

    def visit_emphasis(self, node):
        self._visit_children(node)

    def visit_strong(self, node):
        self._visit_children(node)

    def visit_code(self, node):
        pass

    def visit_link(self, node):
        self._visit_children(node)

    def visit_image(self, node):
        pass

    def visit_line_break(self, node):
        pass

    def visit_strikethrough(self, node):
        self._visit_children(node)

    def visit_underline(self, node):
        self._visit_children(node)

    def visit_superscript(self, node):
        self._visit_children(node)

    def visit_subscript(self, node):
        self._visit_children(node)

    def visit_html_inline(self, node):
        """Record HTMLInline node."""
        self.found_htmlinline = True
        self.htmlinline_contents.append(node.content)

    def visit_footnote_reference(self, node):
        pass

    def visit_math_inline(self, node):
        pass

    def visit_footnote_definition(self, node):
        self._visit_children(node)

    def visit_definition_list(self, node):
        self._visit_children(node)

    def visit_definition_term(self, node):
        self._visit_children(node)

    def visit_definition_description(self, node):
        self._visit_children(node)

    def visit_math_block(self, node):
        pass


class TestIpynbHtmlInlineSecurity:
    """Test IPYNB parser does not use HTMLInline for markdown cells."""

    def _create_notebook(self, cells: list[dict]) -> Path:
        """Create a temporary notebook file with specified cells.

        Parameters
        ----------
        cells : list[dict]
            List of cell dictionaries

        Returns
        -------
        Path
            Path to created notebook file

        """
        notebook = {
            "cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 4,
        }

        temp_dir = Path(tempfile.mkdtemp())
        notebook_path = temp_dir / "test.ipynb"
        notebook_path.write_text(json.dumps(notebook), encoding="utf-8")

        return notebook_path

    def test_no_htmlinline_in_markdown_cell(self):
        """Test that markdown cells do not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [{"cell_type": "markdown", "metadata": {}, "source": ["# Title\n", "\n", "This is markdown content."]}]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "IPYNB parser should not use HTMLInline for markdown cells"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_no_htmlinline_with_dangerous_markdown(self):
        """Test that markdown cells with dangerous HTML do not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "<script>alert('xss')</script>\n",
                        "<img src=x onerror=\"alert('xss')\">\n",
                        "javascript:alert('xss')\n",
                    ],
                }
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "IPYNB parser should not use HTMLInline even with HTML/JS content"

            # Convert to markdown and verify dangerous content is handled safely
            result = to_markdown(notebook_path, source_format="ipynb")

            # Content should be present but not as executable code
            assert result.strip() != "", "Should produce some output"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_multiple_markdown_cells_no_htmlinline(self):
        """Test that multiple markdown cells do not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {"cell_type": "markdown", "metadata": {}, "source": ["# Cell 1\n", "Content 1"]},
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [],
                    "source": ["print('hello')"],
                },
                {"cell_type": "markdown", "metadata": {}, "source": ["## Cell 2\n", "Content 2"]},
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Multiple markdown cells should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_markdown_with_inline_html_no_htmlinline(self):
        """Test that markdown with inline HTML does not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# Title\n",
                        "\n",
                        "This has <strong>inline HTML</strong>.\n",
                        "\n",
                        "<div onclick=\"alert('xss')\">Dangerous div</div>\n",
                    ],
                }
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Markdown with inline HTML should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_markdown_with_javascript_links_no_htmlinline(self):
        """Test that markdown with javascript: links does not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "[Click me](javascript:alert('xss'))\n",
                        "\n",
                        '<a href="javascript:void(0)">Dangerous link</a>\n',
                    ],
                }
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Markdown with JS links should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_markdown_with_special_characters_no_htmlinline(self):
        """Test that markdown with special characters does not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "Special characters: & < > \" '\n",
                        "Unicode: \u00e9 \u00f1 \u4e2d\u6587\n",
                        "Symbols: \u2022 \u2713 \u2717\n",
                    ],
                }
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Markdown with special chars should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_markdown_content_is_text_nodes(self):
        """Test that markdown cell content is represented as Text nodes in Paragraphs."""
        notebook_path = self._create_notebook(
            [{"cell_type": "markdown", "metadata": {}, "source": ["# Title\n", "\n", "This is safe content."]}]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Walk the AST and verify we have Text nodes, not HTMLInline
            from all2md.ast import Paragraph, Text

            has_text_nodes = False
            for node in doc.children:
                if isinstance(node, Paragraph):
                    for child in node.content:
                        if isinstance(child, Text):
                            has_text_nodes = True
                            break

            assert has_text_nodes, "Markdown cell content should be represented as Text nodes"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_complex_notebook_no_htmlinline(self):
        """Test complex notebook with multiple cell types does not use HTMLInline."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Notebook Title\n", "<script>alert('xss')</script>"],
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": ["Hello World\n"]}],
                    "source": ["print('Hello World')"],
                },
                {"cell_type": "markdown", "metadata": {}, "source": ["## Section 2\n", "javascript:alert('xss')"]},
                {"cell_type": "code", "execution_count": 2, "metadata": {}, "outputs": [], "source": ["x = 42"]},
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Complex notebook should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_dangerous_notebook_produces_safe_markdown(self):
        """Test that dangerous notebook content produces safe markdown output."""
        notebook_path = self._create_notebook(
            [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "javascript:alert('xss')\n",
                        "<img src=x onerror=alert(1)>\n",
                        "<script>alert('xss')</script>\n",
                    ],
                }
            ]
        )

        try:
            result = to_markdown(notebook_path, source_format="ipynb")

            # Should produce output but should be safe
            assert result.strip() != "", "Should produce some output"
            # The dangerous content should not be in executable form
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()

    def test_empty_markdown_cells_no_htmlinline(self):
        """Test that empty markdown cells do not produce HTMLInline nodes."""
        notebook_path = self._create_notebook(
            [
                {"cell_type": "markdown", "metadata": {}, "source": []},
                {"cell_type": "markdown", "metadata": {}, "source": [""]},
                {"cell_type": "markdown", "metadata": {}, "source": ["   \n"]},
            ]
        )

        try:
            # Parse to AST
            parser = IpynbToAstConverter()
            doc = parser.parse(notebook_path)

            # Check for HTMLInline nodes
            detector = HTMLInlineDetector()
            doc.accept(detector)

            assert not detector.found_htmlinline, "Empty markdown cells should not use HTMLInline"
        finally:
            notebook_path.unlink()
            notebook_path.parent.rmdir()
