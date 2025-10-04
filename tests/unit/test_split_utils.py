#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_split_utils.py
"""Unit tests for AST splitting utilities.

Tests cover:
- Separator-based splitting
- Heading-based splitting
- Auto-detection splitting
- Text extraction from headings
- Edge cases and empty documents

"""

import pytest

from all2md.ast import (
    Document,
    Heading,
    Paragraph,
    Text,
    ThematicBreak,
    Strong,
    Emphasis,
)
from all2md.renderers._split_utils import (
    split_ast_by_separator,
    split_ast_by_heading,
    auto_split_ast,
    extract_heading_text,
)


@pytest.mark.unit
class TestSplitBySeparator:
    """Tests for separator-based (ThematicBreak) splitting."""

    def test_split_empty_document(self):
        """Test splitting empty document returns empty list."""
        doc = Document()
        chunks = split_ast_by_separator(doc)
        assert chunks == []

    def test_split_no_separators(self):
        """Test splitting document with no separators returns single chunk."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content 1")]),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = split_ast_by_separator(doc)
        assert len(chunks) == 1
        assert len(chunks[0]) == 2

    def test_split_with_separators(self):
        """Test splitting document with separators creates multiple chunks."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Chapter 1")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Chapter 2")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Chapter 3")])
        ])
        chunks = split_ast_by_separator(doc)
        assert len(chunks) == 3
        assert len(chunks[0]) == 1
        assert len(chunks[1]) == 1
        assert len(chunks[2]) == 1

    def test_split_separators_consumed(self):
        """Test that ThematicBreak nodes are not included in output chunks."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="After")])
        ])
        chunks = split_ast_by_separator(doc)

        # Verify no ThematicBreak in output
        for chunk in chunks:
            for node in chunk:
                assert not isinstance(node, ThematicBreak)

    def test_split_leading_separator(self):
        """Test splitting with separator at start."""
        doc = Document(children=[
            ThematicBreak(),
            Paragraph(content=[Text(content="Content")])
        ])
        chunks = split_ast_by_separator(doc)
        assert len(chunks) == 1  # Empty chunk before separator is excluded

    def test_split_trailing_separator(self):
        """Test splitting with separator at end."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")]),
            ThematicBreak()
        ])
        chunks = split_ast_by_separator(doc)
        assert len(chunks) == 1  # Empty chunk after separator is excluded

    def test_split_consecutive_separators(self):
        """Test splitting with consecutive separators."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content 1")]),
            ThematicBreak(),
            ThematicBreak(),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = split_ast_by_separator(doc)
        assert len(chunks) == 2  # Empty chunks excluded


@pytest.mark.unit
class TestSplitByHeading:
    """Tests for heading-based splitting."""

    def test_split_empty_document(self):
        """Test splitting empty document returns empty list."""
        doc = Document()
        chunks = split_ast_by_heading(doc, heading_level=1)
        assert chunks == []

    def test_split_no_headings(self):
        """Test splitting document with no headings at specified level."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="Not level 1")]),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = split_ast_by_heading(doc, heading_level=1)

        # Returns single chunk with None heading
        assert len(chunks) == 1
        assert chunks[0][0] is None
        assert len(chunks[0][1]) == 3

    def test_split_with_headings(self):
        """Test splitting document with headings at specified level."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = split_ast_by_heading(doc, heading_level=1)

        assert len(chunks) == 2
        assert chunks[0][0].level == 1
        assert chunks[1][0].level == 1

    def test_split_heading_not_in_content(self):
        """Test that boundary heading is NOT included in content nodes."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Content")])
        ])
        chunks = split_ast_by_heading(doc, heading_level=1)

        heading, content = chunks[0]
        assert heading is not None
        assert len(content) == 1
        assert isinstance(content[0], Paragraph)

    def test_split_content_before_first_heading(self):
        """Test splitting with content before first heading."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Intro")]),
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Content")])
        ])
        chunks = split_ast_by_heading(doc, heading_level=1)

        assert len(chunks) == 2
        assert chunks[0][0] is None  # No heading for intro
        assert chunks[1][0] is not None  # Has heading

    def test_split_different_heading_levels(self):
        """Test splitting respects heading level parameter."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="H2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])

        # Split on H1
        chunks_h1 = split_ast_by_heading(doc, heading_level=1)
        assert len(chunks_h1) == 1  # Only one H1

        # Split on H2
        chunks_h2 = split_ast_by_heading(doc, heading_level=2)
        assert len(chunks_h2) == 2  # H1 content + H2 content


@pytest.mark.unit
class TestAutoSplit:
    """Tests for automatic splitting strategy detection."""

    def test_auto_split_prefers_separators(self):
        """Test that auto-split uses separators when available."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Paragraph(content=[Text(content="Content 1")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = auto_split_ast(doc, heading_level=1)

        # Should use separator splitting, so headings are None
        assert len(chunks) == 2
        assert chunks[0][0] is None

    def test_auto_split_fallback_to_headings(self):
        """Test that auto-split falls back to headings when no separators."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])
        chunks = auto_split_ast(doc, heading_level=1)

        # Should use heading splitting, so headings are not None
        assert len(chunks) == 2
        assert chunks[0][0] is not None
        assert chunks[1][0] is not None

    def test_auto_split_empty_document(self):
        """Test auto-split on empty document."""
        doc = Document()
        chunks = auto_split_ast(doc)
        assert chunks == []

    def test_auto_split_respects_heading_level(self):
        """Test that auto-split respects heading_level parameter."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="H2-1")]),
            Paragraph(content=[Text(content="Content 1")]),
            Heading(level=2, content=[Text(content="H2-2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])

        # Auto-split with level 2
        chunks = auto_split_ast(doc, heading_level=2)
        assert len(chunks) == 2
        assert chunks[0][0].level == 2


@pytest.mark.unit
class TestExtractHeadingText:
    """Tests for text extraction from headings."""

    def test_extract_from_simple_heading(self):
        """Test extracting text from simple heading."""
        heading = Heading(level=1, content=[Text(content="Chapter One")])
        text = extract_heading_text(heading)
        assert text == "Chapter One"

    def test_extract_from_none(self):
        """Test extracting text from None heading."""
        text = extract_heading_text(None)
        assert text == ""

    def test_extract_from_heading_with_formatting(self):
        """Test extracting text from heading with inline formatting."""
        heading = Heading(level=1, content=[
            Text(content="Chapter "),
            Strong(content=[Text(content="One")]),
            Text(content=" Title")
        ])
        text = extract_heading_text(heading)
        assert text == "Chapter One Title"

    def test_extract_from_nested_formatting(self):
        """Test extracting text from heading with nested formatting."""
        heading = Heading(level=1, content=[
            Text(content="Chapter "),
            Strong(content=[
                Text(content="Very "),
                Emphasis(content=[Text(content="Important")])
            ])
        ])
        text = extract_heading_text(heading)
        assert text == "Chapter Very Important"

    def test_extract_from_empty_heading(self):
        """Test extracting text from heading with no content."""
        heading = Heading(level=1, content=[])
        text = extract_heading_text(heading)
        assert text == ""

    def test_extract_preserves_order(self):
        """Test that text extraction preserves content order."""
        heading = Heading(level=1, content=[
            Text(content="A"),
            Text(content="B"),
            Text(content="C")
        ])
        text = extract_heading_text(heading)
        assert text == "ABC"
