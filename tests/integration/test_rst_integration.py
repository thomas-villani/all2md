#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/test_rst_integration.py
"""Integration tests for reStructuredText parser and renderer.

Tests cover:
- Full parsing and rendering pipeline
- Round-trip conversion (RST -> AST -> RST)
- Complex document structures
- Real-world RST examples
- Integration with all2md main API

"""

import tempfile
from pathlib import Path

import pytest

from all2md.ast import (
    CodeBlock,
    DefinitionList,
    Document,
    Heading,
    Paragraph,
    Table,
    Text,
)
from all2md.options import RstRendererOptions
from all2md.parsers.rst import RestructuredTextParser
from all2md.renderers.rst import RestructuredTextRenderer


@pytest.mark.integration
class TestFullPipeline:
    """Tests for full parsing and rendering pipeline."""

    def test_complete_document(self) -> None:
        """Test parsing and rendering a complete document."""
        rst_content = """
My Document
===========

:Author: John Doe
:Date: 2025-01-01

Introduction
------------

This is the introduction paragraph with **bold** and *italic* text.

Features
--------

Here are the main features:

* Feature 1
* Feature 2
* Feature 3

Code Example
------------

Here is a code example:

.. code-block:: python

   def hello():
       print("Hello, world!")

Conclusion
----------

This is the conclusion.
"""
        # Parse
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        # Verify AST structure
        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Render back to RST
        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Verify key elements are preserved
        assert "My Document" in output_rst
        assert "Introduction" in output_rst
        assert "**bold**" in output_rst
        assert "*italic*" in output_rst
        assert "Feature 1" in output_rst
        assert "code-block" in output_rst or "::" in output_rst

    def test_complex_lists(self) -> None:
        """Test parsing and rendering complex nested lists."""
        rst_content = """
* Top level item 1

  * Nested item 1a
  * Nested item 1b

* Top level item 2

  1. Numbered nested 1
  2. Numbered nested 2

* Top level item 3
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Verify structure is maintained
        assert "Top level item 1" in output_rst
        assert "Nested item 1a" in output_rst

    def test_table_rendering(self) -> None:
        """Test parsing and rendering tables."""
        rst_content = """
+--------+--------+
| Header | Header |
| 1      | 2      |
+========+========+
| Cell   | Cell   |
| 1      | 2      |
+--------+--------+
| Cell   | Cell   |
| 3      | 4      |
+--------+--------+
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        # Verify table was parsed
        tables = [child for child in doc.children if isinstance(child, Table)]
        assert len(tables) > 0

        # Render with grid style
        options = RstRendererOptions(table_style="grid")
        renderer = RestructuredTextRenderer(options)
        output_rst = renderer.render_to_string(doc)

        # Verify table structure
        assert "+" in output_rst
        assert "|" in output_rst

    def test_definition_list_round_trip(self) -> None:
        """Test round-trip of definition lists."""
        rst_content = """
Term 1
   This is the definition of term 1.
   It can span multiple lines.

Term 2
   This is the definition of term 2.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        # Verify definition list was parsed
        def_lists = [child for child in doc.children if isinstance(child, DefinitionList)]
        assert len(def_lists) > 0

        # Render
        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Verify terms and definitions are present
        assert "Term 1" in output_rst
        assert "Term 2" in output_rst


@pytest.mark.integration
class TestRoundTripFidelity:
    """Tests for round-trip conversion fidelity."""

    def test_headings_round_trip(self) -> None:
        """Test that headings maintain structure through round-trip."""
        rst_content = """
Level 1
=======

Level 2
-------

Level 3
~~~~~~~
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Parse again to verify structure
        doc2 = parser.parse(output_rst)

        # Both should have same number of headings
        headings1 = [child for child in doc.children if isinstance(child, Heading)]
        headings2 = [child for child in doc2.children if isinstance(child, Heading)]

        assert len(headings1) == len(headings2)
        for h1, h2 in zip(headings1, headings2, strict=False):
            assert h1.level == h2.level

    def test_inline_formatting_round_trip(self) -> None:
        """Test that inline formatting is preserved."""
        rst_content = "This has **bold**, *italic*, and ``code`` formatting."

        parser = RestructuredTextParser()
        doc = parser.parse(rst_content)

        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # All formatting should be preserved
        assert "**bold**" in output_rst
        assert "*italic*" in output_rst
        assert "``code``" in output_rst

    def test_code_blocks_round_trip(self) -> None:
        """Test that code blocks maintain content and language."""
        rst_content = """
.. code-block:: python

   def hello():
       return "world"
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        options = RstRendererOptions(code_directive_style="directive")
        renderer = RestructuredTextRenderer(options)
        output_rst = renderer.render_to_string(doc)

        # Code content should be preserved
        assert "def hello():" in output_rst
        assert 'return "world"' in output_rst


@pytest.mark.integration
class TestFileIO:
    """Tests for file I/O operations."""

    def test_parse_from_file(self) -> None:
        """Test parsing RST from a file."""
        rst_content = """
Test Document
=============

This is a test document.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rst', delete=False) as f:
            f.write(rst_content)
            temp_file = f.name

        try:
            parser = RestructuredTextParser()
            doc = parser.parse(temp_file)

            assert isinstance(doc, Document)
            assert len(doc.children) > 0
        finally:
            Path(temp_file).unlink()

    def test_render_to_file(self) -> None:
        """Test rendering RST to a file."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Test")]),
            Paragraph(content=[Text(content="Content here.")])
        ])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.rst', delete=False) as f:
            temp_file = f.name

        try:
            renderer = RestructuredTextRenderer()
            renderer.render(doc, temp_file)

            # Read back and verify
            content = Path(temp_file).read_text()
            assert "Test" in content
            assert "Content here." in content
        finally:
            Path(temp_file).unlink()

    def test_parse_from_bytes(self) -> None:
        """Test parsing RST from bytes."""
        rst_content = b"Test\n====\n\nContent."

        parser = RestructuredTextParser()
        doc = parser.parse(rst_content)

        assert isinstance(doc, Document)


@pytest.mark.integration
class TestOptionsIntegration:
    """Tests for options integration."""

    def test_heading_chars_option(self) -> None:
        """Test custom heading characters option."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Heading(level=2, content=[Text(content="H2")]),
            Heading(level=3, content=[Text(content="H3")]),
        ])

        # Use custom heading chars
        options = RstRendererOptions(heading_chars="#*+")
        renderer = RestructuredTextRenderer(options)
        output_rst = renderer.render_to_string(doc)

        # Should use custom chars (matching text length)
        assert "##" in output_rst  # Level 1 (H1 is 2 chars)
        assert "**" in output_rst  # Level 2 (H2 is 2 chars)
        assert "++" in output_rst  # Level 3 (H3 is 2 chars)

    def test_table_style_option(self) -> None:
        """Test table style option."""
        from all2md.ast import TableCell, TableRow

        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="A")]),
                    TableCell(content=[Text(content="B")]),
                ], is_header=True),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="1")]),
                        TableCell(content=[Text(content="2")]),
                    ], is_header=False),
                ]
            )
        ])

        # Test grid style
        options_grid = RstRendererOptions(table_style="grid")
        renderer_grid = RestructuredTextRenderer(options_grid)
        grid_output = renderer_grid.render_to_string(doc)
        assert "+" in grid_output

        # Test simple style
        options_simple = RstRendererOptions(table_style="simple")
        renderer_simple = RestructuredTextRenderer(options_simple)
        simple_output = renderer_simple.render_to_string(doc)
        # Simple tables use = for separators (may have spaces between)
        assert "=" in simple_output
        # Verify it doesn't have grid table markers
        assert "+" not in simple_output or simple_output.count("+") < grid_output.count("+")

    def test_code_style_option(self) -> None:
        """Test code block style option."""
        doc = Document(children=[
            CodeBlock(content="print('hello')", language="python")
        ])

        # Test directive style
        options_directive = RstRendererOptions(code_directive_style="directive")
        renderer_directive = RestructuredTextRenderer(options_directive)
        directive_output = renderer_directive.render_to_string(doc)
        assert ".. code-block::" in directive_output

        # Test double colon style
        options_colon = RstRendererOptions(code_directive_style="double_colon")
        renderer_colon = RestructuredTextRenderer(options_colon)
        colon_output = renderer_colon.render_to_string(doc)
        assert "::" in colon_output


@pytest.mark.integration
class TestComplexDocuments:
    """Tests for complex real-world documents."""

    def test_sphinx_style_document(self) -> None:
        """Test parsing a Sphinx-style RST document."""
        rst_content = """
API Documentation
=================

.. module:: mymodule

Overview
--------

This module provides functionality for X, Y, and Z.

Classes
-------

.. class:: MyClass

   A description of MyClass.

   .. method:: do_something()

      Does something interesting.

Functions
---------

.. function:: helper(arg1, arg2)

   A helper function.

   :param arg1: First argument
   :param arg2: Second argument
   :returns: Result value
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        # Should parse without errors
        assert isinstance(doc, Document)

        # Render back
        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Key elements should be preserved
        assert "API Documentation" in output_rst
        assert "Overview" in output_rst

    def test_readme_style_document(self) -> None:
        """Test parsing a README-style document."""
        rst_content = """
Project Title
=============

A brief description of the project.

Installation
------------

To install::

   pip install myproject

Usage
-----

Basic usage example:

.. code-block:: python

   import myproject
   myproject.run()

Features
--------

* Feature A
* Feature B
* Feature C

License
-------

This project is licensed under MIT License.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst_content.strip())

        renderer = RestructuredTextRenderer()
        output_rst = renderer.render_to_string(doc)

        # Verify structure
        assert "Project Title" in output_rst
        assert "Installation" in output_rst
        assert "License" in output_rst
