#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/text_diff.py
"""Simple text-based document comparison using difflib.

This module provides a simplified diff implementation that works like Unix diff
but supports any document format. It extracts plain text from documents and uses
Python's built-in difflib.unified_diff() for symmetric, predictable comparison.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Iterator, Union

from all2md import to_ast
from all2md.ast.nodes import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Node,
    Paragraph,
    Table,
    Text,
    ThematicBreak,
    get_node_children,
)


def extract_text_content(node: Node) -> str:
    """Extract all text content from a node and its children.

    Parameters
    ----------
    node : Node
        AST node to extract text from

    Returns
    -------
    str
        All text content concatenated

    """
    if isinstance(node, Text):
        return node.content
    elif isinstance(node, CodeBlock):
        return node.content

    # Recursively extract from children
    text_parts: list[str] = []
    children = get_node_children(node)
    for child in children:
        text_parts.append(extract_text_content(child))

    return " ".join(text_parts)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Parameters
    ----------
    text : str
        Text to normalize

    Returns
    -------
    str
        Normalized text with consistent whitespace

    """
    # Replace all whitespace sequences with single space
    normalized = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return normalized.strip()


def extract_document_lines(doc: Document, ignore_whitespace: bool = False) -> list[str]:
    """Extract plain text lines from a document AST.

    This function converts the document structure into a list of text lines,
    one per structural element (heading, paragraph, list item, etc.). This
    preserves document structure while enabling line-based diff comparison.

    Parameters
    ----------
    doc : Document
        Document AST to extract lines from
    ignore_whitespace : bool, default = False
        If True, normalize whitespace in each line

    Returns
    -------
    list of str
        Lines of text, one per structural element

    """
    lines: list[str] = []

    def process_node(node: Node, prefix: str = "") -> None:
        """Process a single node and add its text to lines."""
        if isinstance(node, Heading):
            # Extract heading text with level indicator
            text = extract_text_content(node)
            if ignore_whitespace:
                text = normalize_whitespace(text)
            marker = "#" * node.level
            lines.append(f"{marker} {text}")

        elif isinstance(node, Paragraph):
            # Extract paragraph text
            text = extract_text_content(node)
            if ignore_whitespace:
                text = normalize_whitespace(text)
            if text:  # Skip empty paragraphs
                lines.append(text)

        elif isinstance(node, CodeBlock):
            # Code blocks: add language line, then content lines
            lang = node.language or ""
            lines.append(f"```{lang}")
            content = node.content
            if ignore_whitespace:
                # For code, only normalize blank lines
                code_lines = content.split("\n")
                code_lines = [line if line.strip() else "" for line in code_lines]
                content = "\n".join(code_lines)
            for line in content.split("\n"):
                lines.append(line)
            lines.append("```")

        elif isinstance(node, BlockQuote):
            # Block quotes: add content with > prefix
            for child in node.content:
                process_node(child, prefix="> ")

        elif isinstance(node, ThematicBreak):
            lines.append("---")

        elif isinstance(node, List):
            # Lists: process each item
            for i, item in enumerate(node.items):
                if node.ordered:
                    item_prefix = f"{prefix}{i + 1}. "
                else:
                    item_prefix = f"{prefix}- "
                process_list_item(item, item_prefix)

        elif isinstance(node, Table):
            # Tables: add header row, separator, then data rows
            if node.header:
                header_text = " | ".join(extract_text_content(cell) for cell in node.header.cells)
                if ignore_whitespace:
                    header_text = normalize_whitespace(header_text)
                lines.append(f"| {header_text} |")
                lines.append("|" + " --- |" * len(node.header.cells))

            for row in node.rows:
                row_text = " | ".join(extract_text_content(cell) for cell in row.cells)
                if ignore_whitespace:
                    row_text = normalize_whitespace(row_text)
                lines.append(f"| {row_text} |")

        else:
            # For other container nodes, process children
            children = get_node_children(node)
            for child in children:
                process_node(child, prefix)

    def process_list_item(item: ListItem, prefix: str) -> None:
        """Process a list item with given prefix."""
        # Extract list item content
        text = extract_text_content(item)
        if ignore_whitespace:
            text = normalize_whitespace(text)
        if text:
            lines.append(f"{prefix}{text}")

        # Process nested lists
        if item.children:
            for child in item.children:
                if isinstance(child, List):
                    process_node(child, prefix=prefix + "  ")

    # Process all top-level nodes in the document
    for node in doc.children:
        process_node(node)

    return lines


def compare_documents(
    old_doc: Document,
    new_doc: Document,
    old_label: str = "old",
    new_label: str = "new",
    context_lines: int = 3,
    ignore_whitespace: bool = False,
) -> Iterator[str]:
    """Compare two document ASTs and generate unified diff.

    This function extracts plain text lines from both documents and uses
    Python's difflib.unified_diff() to generate a standard unified diff.
    The result is guaranteed to be symmetric: comparing A to B produces
    the exact opposite of comparing B to A (with +/- swapped).

    Parameters
    ----------
    old_doc : Document
        Original document AST
    new_doc : Document
        New document AST
    old_label : str, default = "old"
        Label for old version in diff header
    new_label : str, default = "new"
        Label for new version in diff header
    context_lines : int, default = 3
        Number of context lines to show around changes
    ignore_whitespace : bool, default = False
        If True, normalize whitespace before comparison

    Returns
    -------
    Iterator[str]
        Lines of unified diff output

    """
    # Extract lines from both documents
    old_lines = extract_document_lines(old_doc, ignore_whitespace=ignore_whitespace)
    new_lines = extract_document_lines(new_doc, ignore_whitespace=ignore_whitespace)

    # Use difflib.unified_diff for symmetric comparison
    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=old_label,
        tofile=new_label,
        n=context_lines,
        lineterm="",
    )

    return diff_lines


def compare_files(
    old_path: Union[str, Path],
    new_path: Union[str, Path],
    old_label: str | None = None,
    new_label: str | None = None,
    context_lines: int = 3,
    ignore_whitespace: bool = False,
) -> Iterator[str]:
    """Compare two document files and generate unified diff.

    This is a convenience wrapper that loads documents from files,
    converts them to AST, and compares them using compare_documents().

    Parameters
    ----------
    old_path : str or Path
        Path to original document file
    new_path : str or Path
        Path to new document file
    old_label : str, optional
        Label for old version (defaults to filename)
    new_label : str, optional
        Label for new version (defaults to filename)
    context_lines : int, default = 3
        Number of context lines to show around changes
    ignore_whitespace : bool, default = False
        If True, normalize whitespace before comparison

    Returns
    -------
    Iterator[str]
        Lines of unified diff output

    """
    # Convert paths to Path objects
    old_path = Path(old_path)
    new_path = Path(new_path)

    # Use filenames as labels if not provided
    if old_label is None:
        old_label = str(old_path)
    if new_label is None:
        new_label = str(new_path)

    # Load documents as AST
    old_doc = to_ast(old_path)
    new_doc = to_ast(new_path)

    # Compare using compare_documents
    return compare_documents(
        old_doc,
        new_doc,
        old_label=old_label,
        new_label=new_label,
        context_lines=context_lines,
        ignore_whitespace=ignore_whitespace,
    )
