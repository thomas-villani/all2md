#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_ipynb_ast.py
"""Unit tests for Jupyter Notebook to AST converter.

Tests cover:
- Markdown cell conversion to AST nodes
- Code cell conversion with language detection
- Output handling (stream, execute_result, display_data)
- Image output conversion
- Execution count display
- Output truncation
- HTMLInline usage for markdown preservation

"""

import base64

import pytest

from all2md.ast import CodeBlock, Document, Image, Paragraph
from all2md.options import IpynbOptions
from all2md.parsers.ipynb import IpynbToAstConverter


def _create_test_notebook(**kwargs):
    """Create a minimal test notebook with specified cells.

    Parameters
    ----------
    **kwargs
        cells : list
            List of cell dictionaries

    Returns
    -------
    dict
        Notebook dictionary

    """
    default_notebook = {
        "cells": kwargs.get("cells", []),
        "metadata": kwargs.get("metadata", {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        }),
        "nbformat": 4,
        "nbformat_minor": 5
    }
    return default_notebook


@pytest.mark.unit
class TestMarkdownCells:
    """Tests for markdown cell conversion."""

    def test_simple_markdown_cell(self) -> None:
        """Test converting a simple markdown cell."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Heading\n", "\n", "Some text."]
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        assert isinstance(doc, Document)
        # Markdown is now parsed into AST nodes (Heading + Paragraph)
        assert len(doc.children) == 2
        # First child should be a Heading
        from all2md.ast import Heading, Text
        assert isinstance(doc.children[0], Heading)
        heading = doc.children[0]
        assert heading.level == 1
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Heading"
        # Second child should be a Paragraph with Text
        assert isinstance(doc.children[1], Paragraph)
        para = doc.children[1]
        assert isinstance(para.content[0], Text)
        assert "Some text." in para.content[0].content

    def test_multiple_markdown_cells(self) -> None:
        """Test converting multiple markdown cells."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["First cell"]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["Second cell"]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["Third cell"]
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        assert len(doc.children) == 3
        assert all(isinstance(child, Paragraph) for child in doc.children)

    def test_empty_markdown_cell_skipped(self) -> None:
        """Test that empty markdown cells are skipped."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["First cell"]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [""]  # Empty
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["   \n"]  # Whitespace only
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["Second cell"]
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        # Only 2 cells should be in AST (empty ones skipped)
        assert len(doc.children) == 2

    def test_markdown_cell_source_as_string(self) -> None:
        """Test markdown cell with source as string instead of list."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "This is a string source"
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)


@pytest.mark.unit
class TestCodeCells:
    """Tests for code cell conversion."""

    def test_simple_code_cell(self) -> None:
        """Test converting a simple code cell."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["print('hello')"],
                    "outputs": []
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert code_block.language == "python"
        assert "print('hello')" in code_block.content

    def test_code_cell_with_execution_count(self) -> None:
        """Test code cell with execution count display."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 5,
                    "metadata": {},
                    "source": ["x = 42"],
                    "outputs": []
                }
            ]
        )

        options = IpynbOptions(show_execution_count=True)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "# In [5]:" in code_block.content
        assert "x = 42" in code_block.content

    def test_code_cell_no_execution_count(self) -> None:
        """Test code cell without execution count display."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 5,
                    "metadata": {},
                    "source": ["x = 42"],
                    "outputs": []
                }
            ]
        )

        options = IpynbOptions(show_execution_count=False)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "# In [5]:" not in code_block.content
        assert "x = 42" in code_block.content

    def test_code_cell_with_multiline_source(self) -> None:
        """Test code cell with multiple lines."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": [
                        "def greet(name):\n",
                        "    return f'Hello, {name}!'\n",
                        "\n",
                        "print(greet('World'))"
                    ],
                    "outputs": []
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "def greet(name):" in code_block.content
        assert "return f'Hello, {name}!'" in code_block.content
        assert "print(greet('World'))" in code_block.content

    def test_code_cell_include_inputs_false(self) -> None:
        """Test that code cells are skipped when include_inputs=False."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["print('hello')"],
                    "outputs": []
                }
            ]
        )

        options = IpynbOptions(include_inputs=False)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        # No code block should be present (inputs not included)
        assert len(doc.children) == 0

    def test_empty_code_cell_skipped(self) -> None:
        """Test that empty code cells are skipped."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": [""],
                    "outputs": []
                },
                {
                    "cell_type": "code",
                    "execution_count": 2,
                    "metadata": {},
                    "source": ["   \n"],
                    "outputs": []
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        # Empty cells should be skipped
        assert len(doc.children) == 0


@pytest.mark.unit
class TestOutputs:
    """Tests for cell output conversion."""

    def test_stream_output(self) -> None:
        """Test converting stream output."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["print('hello')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": ["hello\n"]
                        }
                    ]
                }
            ]
        )

        options = IpynbOptions(include_outputs=True)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        # Should have code block + output code block
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], CodeBlock)  # Input
        assert isinstance(doc.children[1], CodeBlock)  # Output
        output_block = doc.children[1]
        assert output_block.language == ""  # No language for output
        assert "hello" in output_block.content

    def test_execute_result_text(self) -> None:
        """Test converting execute_result with text/plain."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["42"],
                    "outputs": [
                        {
                            "output_type": "execute_result",
                            "execution_count": 1,
                            "data": {
                                "text/plain": ["42"]
                            },
                            "metadata": {}
                        }
                    ]
                }
            ]
        )

        options = IpynbOptions(include_outputs=True)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        assert len(doc.children) == 2
        output_block = doc.children[1]
        assert isinstance(output_block, CodeBlock)
        assert "42" in output_block.content

    def test_display_data_image(self) -> None:
        """Test converting display_data with image."""
        # Create a small valid PNG data (1x1 transparent PNG)
        png_data = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        ).decode('utf-8')

        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["display(image)"],
                    "outputs": [
                        {
                            "output_type": "display_data",
                            "data": {
                                "image/png": png_data
                            },
                            "metadata": {}
                        }
                    ]
                }
            ]
        )

        options = IpynbOptions(include_outputs=True, attachment_mode="embed")
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        # Should have code block + image
        assert len(doc.children) == 2
        assert isinstance(doc.children[0], CodeBlock)
        assert isinstance(doc.children[1], Image)
        img = doc.children[1]
        # Image should be created (URL generation depends on attachment processing)
        assert isinstance(img, Image)
        assert img.alt_text == "cell output"

    def test_outputs_disabled(self) -> None:
        """Test that outputs are skipped when include_outputs=False."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["print('hello')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": ["hello\n"]
                        }
                    ]
                }
            ]
        )

        options = IpynbOptions(include_outputs=False)
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        # Should only have code block, no output
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)

    def test_output_truncation(self) -> None:
        """Test long output truncation."""
        long_output = "\n".join([f"Line {i}" for i in range(100)])

        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["for i in range(100): print(f'Line {i}')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": [long_output]
                        }
                    ]
                }
            ]
        )

        options = IpynbOptions(
            include_outputs=True,
            truncate_long_outputs=10
        )
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        output_block = doc.children[1]
        assert isinstance(output_block, CodeBlock)
        # Output should be truncated
        assert "Line 9" in output_block.content
        assert "Line 50" not in output_block.content
        # Should have truncation message
        assert "..." in output_block.content or "truncated" in output_block.content.lower()

    def test_output_types_filter(self) -> None:
        """Test filtering outputs by type."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["x = 1"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": ["Stream output\n"]
                        },
                        {
                            "output_type": "execute_result",
                            "execution_count": 1,
                            "data": {"text/plain": ["42"]},
                            "metadata": {}
                        }
                    ]
                }
            ]
        )

        # Only include stream outputs
        options = IpynbOptions(
            include_outputs=True,
            output_types=["stream"]
        )
        converter = IpynbToAstConverter(options)
        doc = converter.convert_to_ast(notebook, "python")

        # Should have code block + only stream output
        assert len(doc.children) == 2
        assert isinstance(doc.children[1], CodeBlock)
        assert "Stream output" in doc.children[1].content
        assert "42" not in doc.children[1].content


@pytest.mark.unit
class TestLanguageDetection:
    """Tests for language detection from notebook metadata."""

    def test_default_python_language(self) -> None:
        """Test default language is python."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["x = 1"],
                    "outputs": []
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "python"

    def test_custom_language_from_metadata(self) -> None:
        """Test language detection from kernelspec metadata."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["x <- 42"],
                    "outputs": []
                }
            ],
            metadata={
                "kernelspec": {
                    "display_name": "R",
                    "language": "R",
                    "name": "ir"
                }
            }
        )

        converter = IpynbToAstConverter()
        # Pass the language from metadata for this test
        language = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "python")
        doc = converter.convert_to_ast(notebook, language)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "R"


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_notebook(self) -> None:
        """Test converting empty notebook."""
        notebook = _create_test_notebook(cells=[])

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        assert isinstance(doc, Document)
        assert len(doc.children) == 0

    def test_mixed_cell_types(self) -> None:
        """Test notebook with mixed markdown and code cells."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Introduction"]
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": ["print('hello')"],
                    "outputs": []
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["Some explanation"]
                },
                {
                    "cell_type": "code",
                    "execution_count": 2,
                    "metadata": {},
                    "source": ["x = 42"],
                    "outputs": []
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        # Should have 4 nodes: Heading (from "# Introduction"), code, Paragraph, code
        # Markdown is now parsed into proper AST nodes
        from all2md.ast import Heading
        assert len(doc.children) == 4
        assert isinstance(doc.children[0], Heading)  # "# Introduction" becomes Heading
        assert isinstance(doc.children[1], CodeBlock)
        assert isinstance(doc.children[2], Paragraph)  # "Some explanation" becomes Paragraph
        assert isinstance(doc.children[3], CodeBlock)

    def test_unknown_cell_type_skipped(self) -> None:
        """Test that raw and unknown cell types are preserved for round-trip fidelity."""
        notebook = _create_test_notebook(
            cells=[
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["Known cell"]
                },
                {
                    "cell_type": "raw",  # Raw cell type
                    "metadata": {},
                    "source": ["Raw content"]
                },
                {
                    "cell_type": "unknown",
                    "metadata": {},
                    "source": ["Unknown content"]
                }
            ]
        )

        converter = IpynbToAstConverter()
        doc = converter.convert_to_ast(notebook, "python")

        # All cells should be preserved for round-trip fidelity
        # Markdown -> Paragraph, Raw -> CodeBlock, Unknown -> Paragraph
        assert len(doc.children) == 3
        assert isinstance(doc.children[0], Paragraph)  # markdown
        assert isinstance(doc.children[1], CodeBlock)  # raw
        assert isinstance(doc.children[2], Paragraph)  # unknown

        # Verify metadata preserves cell types
        assert doc.children[0].metadata.get('ipynb', {}).get('cell_type') == 'markdown'
        assert doc.children[1].metadata.get('ipynb', {}).get('cell_type') == 'raw'
        assert doc.children[2].metadata.get('ipynb', {}).get('cell_type') == 'unknown'
