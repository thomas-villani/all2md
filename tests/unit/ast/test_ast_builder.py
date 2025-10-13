#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for AST builder utilities."""
import pytest

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    DocumentBuilder,
    FootnoteDefinition,
    Heading,
    HTMLBlock,
    List,
    ListItem,
    MathBlock,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)


@pytest.mark.unit
class TestDocumentBuilder:
    """Test DocumentBuilder functionality."""

    def test_init_creates_empty_children(self) -> None:
        """Test that initialization creates empty children list."""
        builder = DocumentBuilder()
        assert builder.children == []

    def test_add_heading(self) -> None:
        """Test adding a heading."""
        builder = DocumentBuilder()
        builder.add_heading(1, [Text(content="Title")])

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)
        assert doc.children[0].level == 1
        assert doc.children[0].content[0].content == "Title"

    def test_add_paragraph(self) -> None:
        """Test adding a paragraph."""
        builder = DocumentBuilder()
        builder.add_paragraph([Text(content="Content")])

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)
        assert doc.children[0].content[0].content == "Content"

    def test_add_code_block(self) -> None:
        """Test adding a code block."""
        builder = DocumentBuilder()
        builder.add_code_block("print('hello')", language="python")

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].content == "print('hello')"
        assert doc.children[0].language == "python"

    def test_add_code_block_without_language(self) -> None:
        """Test adding a code block without language."""
        builder = DocumentBuilder()
        builder.add_code_block("plain text")

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].language is None

    def test_add_thematic_break(self) -> None:
        """Test adding a thematic break."""
        builder = DocumentBuilder()
        builder.add_thematic_break()

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ThematicBreak)

    def test_add_block_quote(self) -> None:
        """Test adding a block quote."""
        builder = DocumentBuilder()
        para = Paragraph(content=[Text(content="Quoted text")])
        builder.add_block_quote([para])

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        assert len(doc.children[0].children) == 1
        assert isinstance(doc.children[0].children[0], Paragraph)

    def test_add_list(self) -> None:
        """Test adding a list."""
        builder = DocumentBuilder()
        item = ListItem(children=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_list([item], ordered=False)

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)
        assert doc.children[0].ordered is False
        assert len(doc.children[0].items) == 1

    def test_add_list_with_parameters(self) -> None:
        """Test adding a list with custom parameters."""
        builder = DocumentBuilder()
        item = ListItem(children=[Paragraph(content=[Text(content="Item 1")])])
        builder.add_list([item], ordered=True, start=5, tight=False)

        doc = builder.get_document()
        lst = doc.children[0]
        assert isinstance(lst, List)
        assert lst.ordered is True
        assert lst.start == 5
        assert lst.tight is False

    def test_add_table(self) -> None:
        """Test adding a table."""
        builder = DocumentBuilder()
        header = TableRow(cells=[TableCell(content=[Text(content="Header")])])
        row = TableRow(cells=[TableCell(content=[Text(content="Cell")])])
        builder.add_table(rows=[row], header=header)

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)
        assert doc.children[0].header is not None
        assert len(doc.children[0].rows) == 1

    def test_add_table_with_caption_and_alignments(self) -> None:
        """Test adding a table with caption and alignments."""
        builder = DocumentBuilder()
        row = TableRow(cells=[TableCell(content=[Text(content="Cell")])])
        builder.add_table(
            rows=[row],
            caption="Table caption",
            alignments=["left"]
        )

        doc = builder.get_document()
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.caption == "Table caption"
        assert table.alignments == ["left"]

    def test_add_html_block(self) -> None:
        """Test adding an HTML block."""
        builder = DocumentBuilder()
        builder.add_html_block("<div>HTML content</div>")

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], HTMLBlock)
        assert doc.children[0].content == "<div>HTML content</div>"

    def test_add_footnote_definition(self) -> None:
        """Test adding a footnote definition."""
        builder = DocumentBuilder()
        content = [Paragraph(content=[Text(content="Footnote text")])]
        builder.add_footnote_definition("1", content)

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], FootnoteDefinition)
        assert doc.children[0].identifier == "1"
        assert len(doc.children[0].content) == 1

    def test_add_definition_list(self) -> None:
        """Test adding a definition list."""
        builder = DocumentBuilder()
        term = DefinitionTerm(content=[Text(content="Term")])
        desc = DefinitionDescription(content=[Text(content="Description")])
        builder.add_definition_list([(term, [desc])])

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], DefinitionList)
        assert len(doc.children[0].items) == 1

    def test_add_math_block(self) -> None:
        """Test adding a math block."""
        builder = DocumentBuilder()
        builder.add_math_block("x^2 + y^2 = z^2", notation="latex")

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], MathBlock)
        assert doc.children[0].content == "x^2 + y^2 = z^2"
        assert doc.children[0].notation == "latex"

    def test_add_math_block_default_notation(self) -> None:
        """Test adding a math block with default notation."""
        builder = DocumentBuilder()
        builder.add_math_block("x^2")

        doc = builder.get_document()
        assert doc.children[0].notation == "latex"

    def test_add_node(self) -> None:
        """Test adding a single node."""
        builder = DocumentBuilder()
        node = Heading(level=2, content=[Text(content="Heading")])
        builder.add_node(node)

        doc = builder.get_document()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)

    def test_add_nodes(self) -> None:
        """Test adding multiple nodes at once."""
        builder = DocumentBuilder()
        nodes = [
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Paragraph 1")]),
            Paragraph(content=[Text(content="Paragraph 2")])
        ]
        builder.add_nodes(nodes)

        doc = builder.get_document()
        assert len(doc.children) == 3
        assert isinstance(doc.children[0], Heading)
        assert isinstance(doc.children[1], Paragraph)
        assert isinstance(doc.children[2], Paragraph)

    def test_method_chaining(self) -> None:
        """Test that all methods support chaining."""
        doc = (DocumentBuilder()
               .add_heading(1, [Text(content="Title")])
               .add_paragraph([Text(content="Intro")])
               .add_code_block("code", language="python")
               .add_thematic_break()
               .add_paragraph([Text(content="Conclusion")])
               .get_document())

        assert isinstance(doc, Document)
        assert len(doc.children) == 5

    def test_multiple_additions(self) -> None:
        """Test adding multiple elements of different types."""
        builder = DocumentBuilder()
        builder.add_heading(1, [Text(content="Title")])
        builder.add_paragraph([Text(content="Paragraph")])
        builder.add_code_block("code")
        builder.add_thematic_break()

        doc = builder.get_document()
        assert len(doc.children) == 4
        assert isinstance(doc.children[0], Heading)
        assert isinstance(doc.children[1], Paragraph)
        assert isinstance(doc.children[2], CodeBlock)
        assert isinstance(doc.children[3], ThematicBreak)

    def test_empty_document(self) -> None:
        """Test creating an empty document."""
        builder = DocumentBuilder()
        doc = builder.get_document()

        assert isinstance(doc, Document)
        assert len(doc.children) == 0

    def test_get_document_returns_new_instance(self) -> None:
        """Test that get_document creates a new Document instance each time."""
        builder = DocumentBuilder()
        builder.add_heading(1, [Text(content="Title")])

        doc1 = builder.get_document()
        doc2 = builder.get_document()

        # Should be different instances
        assert doc1 is not doc2
        # But with same children
        assert len(doc1.children) == len(doc2.children)

    def test_builder_reuse(self) -> None:
        """Test that builder accumulates children across multiple get_document calls."""
        builder = DocumentBuilder()
        builder.add_heading(1, [Text(content="First")])
        doc1 = builder.get_document()

        # Continue adding to same builder
        builder.add_paragraph([Text(content="Second")])
        doc2 = builder.get_document()

        # Both docs should have same accumulated children (builder doesn't reset)
        assert len(doc1.children) == 2  # Has both heading and paragraph
        assert len(doc2.children) == 2  # Also has both
        # But they are different Document instances
        assert doc1 is not doc2

    def test_add_nodes_maintains_order(self) -> None:
        """Test that add_nodes maintains the order of nodes."""
        builder = DocumentBuilder()
        nodes = [
            Heading(level=1, content=[Text(content="H1")]),
            Heading(level=2, content=[Text(content="H2")]),
            Heading(level=3, content=[Text(content="H3")])
        ]
        builder.add_nodes(nodes)

        doc = builder.get_document()
        assert doc.children[0].level == 1
        assert doc.children[1].level == 2
        assert doc.children[2].level == 3

    def test_add_empty_nodes_list(self) -> None:
        """Test adding an empty list of nodes."""
        builder = DocumentBuilder()
        builder.add_nodes([])

        doc = builder.get_document()
        assert len(doc.children) == 0
