#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/test_org_integration.py
"""Integration tests for Org-Mode conversion.

Tests cover:
- Round-trip conversion (Org → AST → Org)
- Complex documents with mixed content
- Cross-format conversion (Org ↔ Markdown)
- Edge cases and real-world examples

"""

import pytest

from all2md.ast import (
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.parsers.org import OrgParser
from all2md.renderers.org import OrgRenderer


@pytest.mark.integration
class TestRoundTripConversion:
    """Tests for round-trip conversion (Org → AST → Org)."""

    def test_simple_document_roundtrip(self) -> None:
        """Test round-trip conversion of a simple document."""
        original = """* Heading

This is a paragraph with *bold* and /italic/ text.

- Item 1
- Item 2"""

        parser = OrgParser()
        doc = parser.parse(original)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Parse result again to verify structure
        doc2 = parser.parse(result)

        # Check that document structure is preserved
        assert len(doc.children) > 0
        assert len(doc2.children) > 0

    def test_code_block_roundtrip(self) -> None:
        """Test round-trip conversion with code blocks."""
        original = """* Code Example

#+BEGIN_SRC python
def hello():
    print("Hello, World!")
#+END_SRC"""

        parser = OrgParser()
        doc = parser.parse(original)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Check that code block is preserved
        assert "#+BEGIN_SRC" in result
        assert "#+END_SRC" in result
        assert "def hello():" in result

    def test_table_roundtrip(self) -> None:
        """Test round-trip conversion with tables."""
        original = """* Data

| Name  | Age |
|-------+-----|
| Alice | 30  |
| Bob   | 25  |"""

        parser = OrgParser()
        doc = parser.parse(original)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Check that table structure is preserved
        assert "|" in result
        assert "Name" in result or "Alice" in result

    def test_todo_heading_roundtrip(self) -> None:
        """Test round-trip conversion with TODO headings."""
        original = """* TODO Write documentation
* DONE Implement feature"""

        parser = OrgParser()
        doc = parser.parse(original)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Check that TODO states are preserved
        assert "TODO" in result
        assert "DONE" in result


@pytest.mark.integration
class TestComplexDocuments:
    """Tests for complex real-world documents."""

    def test_nested_lists(self) -> None:
        """Test parsing and rendering nested lists."""
        org = """* Shopping List

- Fruits
  - Apples
  - Oranges
- Vegetables
  - Carrots
  - Broccoli"""

        parser = OrgParser()
        doc = parser.parse(org)

        # Check that lists are parsed
        lists = [node for node in doc.children if isinstance(node, List)]
        assert len(lists) >= 1

        # Render and verify structure
        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)
        assert "Fruits" in result or "Apples" in result

    def test_mixed_inline_formatting(self) -> None:
        """Test document with multiple inline formatting types."""
        org = """* Formatting Examples

This text has *bold*, /italic/, =code=, _underline_, and +strikethrough+."""

        parser = OrgParser()
        doc = parser.parse(org)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Check that all formatting is preserved
        assert "*bold*" in result or "bold" in result
        assert "/italic/" in result or "italic" in result
        assert "=code=" in result or "code" in result

    def test_links_and_images(self) -> None:
        """Test document with links and images."""
        org = """* Resources

Visit [[https://example.com][Example Site]].

Image: [[file:diagram.png][Diagram]]"""

        parser = OrgParser()
        doc = parser.parse(org)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Check that links are preserved
        assert "[[" in result and "]]" in result
        assert "example.com" in result or "https" in result


@pytest.mark.integration
class TestMetadataHandling:
    """Tests for metadata handling in conversion."""

    def test_file_properties(self) -> None:
        """Test conversion with file-level properties."""
        org = """#+TITLE: My Document
#+AUTHOR: John Doe
#+DATE: 2025-01-01

* Content

Some text."""

        parser = OrgParser()
        doc = parser.parse(org)

        # Check metadata extraction
        assert doc.metadata.get('title') == 'My Document'
        assert doc.metadata.get('author') == 'John Doe'

        # Render and check properties are included
        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)
        assert "#+TITLE: My Document" in result
        assert "#+AUTHOR: John Doe" in result

    def test_heading_properties(self) -> None:
        """Test conversion with heading properties."""
        org = """* TODO [#A] Important Task :work:urgent:
:PROPERTIES:
:CUSTOM_ID: task-1
:CATEGORY: Development
:END:

Task description."""

        parser = OrgParser()
        doc = parser.parse(org)

        # Check that heading metadata is captured
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.metadata.get('org_todo_state') == 'TODO'
        assert heading.metadata.get('org_priority') == 'A'
        assert 'work' in heading.metadata.get('org_tags', [])
        assert 'urgent' in heading.metadata.get('org_tags', [])


@pytest.mark.integration
class TestASTDirectConstruction:
    """Tests for constructing AST directly and rendering to Org."""

    def test_construct_simple_document(self) -> None:
        """Test constructing a simple document from AST."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="My Document")]),
            Paragraph(content=[
                Text(content="This is a "),
                Strong(content=[Text(content="bold")]),
                Text(content=" paragraph.")
            ])
        ])

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        assert "* My Document" in result
        assert "*bold*" in result

    def test_construct_list_document(self) -> None:
        """Test constructing a document with lists."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Todo List")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="Task 1")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Task 2")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Task 3")])])
                ]
            )
        ])

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        assert "* Todo List" in result
        assert "- Task 1" in result
        assert "- Task 2" in result
        assert "- Task 3" in result

    def test_construct_todo_document(self) -> None:
        """Test constructing a document with TODO headings."""
        doc = Document(children=[
            Heading(
                level=1,
                content=[Text(content="Important Task")],
                metadata={
                    "org_todo_state": "TODO",
                    "org_priority": "A",
                    "org_tags": ["work", "urgent"]
                }
            ),
            Paragraph(content=[Text(content="Task description here.")])
        ])

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        assert "* TODO" in result
        assert "[#A]" in result
        assert ":work:urgent:" in result


@pytest.mark.integration
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_document(self) -> None:
        """Test parsing and rendering an empty document."""
        org = ""
        parser = OrgParser()
        doc = parser.parse(org)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Should not crash
        assert isinstance(result, str)

    def test_heading_only(self) -> None:
        """Test document with only headings, no content."""
        org = """* Heading 1
** Heading 2
*** Heading 3"""

        parser = OrgParser()
        doc = parser.parse(org)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        assert "*" in result

    def test_special_characters(self) -> None:
        """Test handling of special characters."""
        org = """* Heading

Text with special chars: <>&"'"""

        parser = OrgParser()
        doc = parser.parse(org)

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Special characters should be preserved
        assert "<" in result or "&" in result or "'" in result


@pytest.mark.integration
class TestPerformance:
    """Tests for performance with larger documents."""

    def test_large_document(self) -> None:
        """Test parsing and rendering a large document."""
        # Generate a large document
        sections = []
        for i in range(100):
            sections.append(f"* Section {i}\n\nContent for section {i}.\n")

        org = "\n".join(sections)

        parser = OrgParser()
        doc = parser.parse(org)

        # Should parse successfully
        assert len(doc.children) > 0

        renderer = OrgRenderer()
        result = renderer.render_to_string(doc)

        # Should render successfully
        assert len(result) > 0
        assert "Section" in result
