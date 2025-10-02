#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_ast_nodes.py
"""Unit tests for AST node classes.

Tests cover:
- Node creation and initialization
- Visitor pattern acceptance
- Validation of node constraints
- Metadata and source location tracking

"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    SourceLocation,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
    ValidationVisitor,
)


@pytest.mark.unit
class TestSourceLocation:
    """Tests for SourceLocation class."""

    def test_create_minimal(self):
        """Test creating a minimal source location."""
        loc = SourceLocation(format="pdf")
        assert loc.format == "pdf"
        assert loc.page is None
        assert loc.line is None

    def test_create_full(self):
        """Test creating a full source location."""
        loc = SourceLocation(
            format="html",
            page=1,
            line=10,
            column=5,
            element_id="main",
            metadata={"extra": "data"}
        )
        assert loc.format == "html"
        assert loc.page == 1
        assert loc.line == 10
        assert loc.column == 5
        assert loc.element_id == "main"
        assert loc.metadata == {"extra": "data"}


@pytest.mark.unit
class TestDocumentNode:
    """Tests for Document node."""

    def test_create_empty(self):
        """Test creating an empty document."""
        doc = Document()
        assert doc.children == []
        assert doc.metadata == {}

    def test_create_with_children(self):
        """Test creating a document with children."""
        heading = Heading(level=1, content=[Text(content="Title")])
        para = Paragraph(content=[Text(content="Content")])
        doc = Document(children=[heading, para])

        assert len(doc.children) == 2
        assert doc.children[0] == heading
        assert doc.children[1] == para

    def test_accept_visitor(self):
        """Test visitor pattern on document."""
        doc = Document()

        class MockVisitor:
            def visit_document(self, node):
                return "visited"

        result = doc.accept(MockVisitor())
        assert result == "visited"


@pytest.mark.unit
class TestHeadingNode:
    """Tests for Heading node."""

    def test_create_valid_levels(self):
        """Test creating headings with valid levels 1-6."""
        for level in range(1, 7):
            heading = Heading(level=level, content=[Text(content=f"H{level}")])
            assert heading.level == level

    def test_invalid_level_zero(self):
        """Test that level 0 raises ValueError."""
        with pytest.raises(ValueError, match="Heading level must be 1-6"):
            Heading(level=0, content=[Text(content="Bad")])

    def test_invalid_level_seven(self):
        """Test that level 7 raises ValueError."""
        with pytest.raises(ValueError, match="Heading level must be 1-6"):
            Heading(level=7, content=[Text(content="Bad")])

    def test_with_inline_content(self):
        """Test heading with mixed inline content."""
        content = [
            Text(content="Hello "),
            Strong(content=[Text(content="world")]),
            Text(content="!")
        ]
        heading = Heading(level=2, content=content)
        assert len(heading.content) == 3

    def test_accept_visitor(self):
        """Test visitor pattern on heading."""
        heading = Heading(level=1, content=[])

        class MockVisitor:
            def visit_heading(self, node):
                return node.level

        result = heading.accept(MockVisitor())
        assert result == 1


@pytest.mark.unit
class TestParagraphNode:
    """Tests for Paragraph node."""

    def test_create_empty(self):
        """Test creating an empty paragraph."""
        para = Paragraph()
        assert para.content == []

    def test_create_with_text(self):
        """Test creating a paragraph with text."""
        para = Paragraph(content=[Text(content="Hello world")])
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)


@pytest.mark.unit
class TestCodeBlockNode:
    """Tests for CodeBlock node."""

    def test_create_minimal(self):
        """Test creating a code block with just content."""
        code = CodeBlock(content="print('hello')")
        assert code.content == "print('hello')"
        assert code.language is None
        assert code.fence_char == '`'
        assert code.fence_length == 3

    def test_create_with_language(self):
        """Test creating a code block with language."""
        code = CodeBlock(content="x = 1", language="python")
        assert code.language == "python"

    def test_custom_fence(self):
        """Test creating a code block with custom fence."""
        code = CodeBlock(content="test", fence_char='~', fence_length=4)
        assert code.fence_char == '~'
        assert code.fence_length == 4


@pytest.mark.unit
class TestBlockQuoteNode:
    """Tests for BlockQuote node."""

    def test_create_empty(self):
        """Test creating an empty block quote."""
        quote = BlockQuote()
        assert quote.children == []

    def test_create_with_content(self):
        """Test creating a block quote with content."""
        para = Paragraph(content=[Text(content="Quoted")])
        quote = BlockQuote(children=[para])
        assert len(quote.children) == 1


@pytest.mark.unit
class TestListNodes:
    """Tests for List and ListItem nodes."""

    def test_create_unordered_list(self):
        """Test creating an unordered list."""
        list_node = List(ordered=False)
        assert list_node.ordered is False
        assert list_node.items == []
        assert list_node.tight is True

    def test_create_ordered_list(self):
        """Test creating an ordered list."""
        list_node = List(ordered=True, start=5)
        assert list_node.ordered is True
        assert list_node.start == 5

    def test_list_with_items(self):
        """Test creating a list with items."""
        item1 = ListItem(children=[Paragraph(content=[Text(content="One")])])
        item2 = ListItem(children=[Paragraph(content=[Text(content="Two")])])
        list_node = List(ordered=False, items=[item1, item2])
        assert len(list_node.items) == 2

    def test_task_list_item(self):
        """Test creating task list items."""
        checked_item = ListItem(
            children=[Paragraph(content=[Text(content="Done")])],
            task_status='checked'
        )
        unchecked_item = ListItem(
            children=[Paragraph(content=[Text(content="Todo")])],
            task_status='unchecked'
        )
        assert checked_item.task_status == 'checked'
        assert unchecked_item.task_status == 'unchecked'


@pytest.mark.unit
class TestTableNodes:
    """Tests for Table, TableRow, and TableCell nodes."""

    def test_create_empty_table(self):
        """Test creating an empty table."""
        table = Table()
        assert table.header is None
        assert table.rows == []
        assert table.alignments == []

    def test_create_table_with_header(self):
        """Test creating a table with a header row."""
        header = TableRow(
            cells=[
                TableCell(content=[Text(content="Name")]),
                TableCell(content=[Text(content="Age")])
            ],
            is_header=True
        )
        table = Table(header=header)
        assert table.header is not None
        assert table.header.is_header is True

    def test_table_with_alignments(self):
        """Test creating a table with column alignments."""
        table = Table(alignments=['left', 'center', 'right'])
        assert len(table.alignments) == 3
        assert table.alignments[0] == 'left'
        assert table.alignments[1] == 'center'
        assert table.alignments[2] == 'right'

    def test_table_cell_with_span(self):
        """Test creating a table cell with colspan/rowspan."""
        cell = TableCell(
            content=[Text(content="Merged")],
            colspan=2,
            rowspan=3
        )
        assert cell.colspan == 2
        assert cell.rowspan == 3


@pytest.mark.unit
class TestThematicBreakNode:
    """Tests for ThematicBreak node."""

    def test_create(self):
        """Test creating a thematic break."""
        br = ThematicBreak()
        assert br.metadata == {}


@pytest.mark.unit
class TestHTMLNodes:
    """Tests for HTMLBlock and HTMLInline nodes."""

    def test_html_block(self):
        """Test creating an HTML block."""
        html = HTMLBlock(content="<div>Test</div>")
        assert html.content == "<div>Test</div>"

    def test_html_inline(self):
        """Test creating inline HTML."""
        html = HTMLInline(content="<span>Test</span>")
        assert html.content == "<span>Test</span>"


@pytest.mark.unit
class TestInlineNodes:
    """Tests for inline node types."""

    def test_text_node(self):
        """Test creating a text node."""
        text = Text(content="Hello world")
        assert text.content == "Hello world"

    def test_emphasis_node(self):
        """Test creating an emphasis node."""
        em = Emphasis(content=[Text(content="italic")])
        assert len(em.content) == 1

    def test_strong_node(self):
        """Test creating a strong node."""
        strong = Strong(content=[Text(content="bold")])
        assert len(strong.content) == 1

    def test_code_node(self):
        """Test creating an inline code node."""
        code = Code(content="print()")
        assert code.content == "print()"

    def test_link_node(self):
        """Test creating a link node."""
        link = Link(
            url="https://example.com",
            content=[Text(content="Example")],
            title="Example Site"
        )
        assert link.url == "https://example.com"
        assert link.title == "Example Site"

    def test_image_node(self):
        """Test creating an image node."""
        img = Image(
            url="image.png",
            alt_text="An image",
            title="Image title",
            width=800,
            height=600
        )
        assert img.url == "image.png"
        assert img.alt_text == "An image"
        assert img.width == 800

    def test_line_break_soft(self):
        """Test creating a soft line break."""
        br = LineBreak(soft=True)
        assert br.soft is True

    def test_line_break_hard(self):
        """Test creating a hard line break."""
        br = LineBreak(soft=False)
        assert br.soft is False


@pytest.mark.unit
class TestExtendedInlineNodes:
    """Tests for extended inline node types."""

    def test_strikethrough_node(self):
        """Test creating a strikethrough node."""
        strike = Strikethrough(content=[Text(content="deleted")])
        assert len(strike.content) == 1

    def test_underline_node(self):
        """Test creating an underline node."""
        underline = Underline(content=[Text(content="underlined")])
        assert len(underline.content) == 1

    def test_superscript_node(self):
        """Test creating a superscript node."""
        sup = Superscript(content=[Text(content="2")])
        assert len(sup.content) == 1

    def test_subscript_node(self):
        """Test creating a subscript node."""
        sub = Subscript(content=[Text(content="0")])
        assert len(sub.content) == 1


@pytest.mark.unit
class TestNodeMetadata:
    """Tests for node metadata and source location."""

    def test_metadata_dict(self):
        """Test adding metadata to a node."""
        para = Paragraph(
            content=[Text(content="Test")],
            metadata={"author": "Alice", "date": "2025-01-01"}
        )
        assert para.metadata["author"] == "Alice"
        assert para.metadata["date"] == "2025-01-01"

    def test_source_location_tracking(self):
        """Test tracking source location."""
        loc = SourceLocation(format="pdf", page=5, line=20)
        heading = Heading(
            level=1,
            content=[Text(content="Chapter 1")],
            source_location=loc
        )
        assert heading.source_location is not None
        assert heading.source_location.format == "pdf"
        assert heading.source_location.page == 5


@pytest.mark.unit
class TestValidationVisitor:
    """Tests for ValidationVisitor."""

    def test_valid_document(self):
        """Test validating a well-formed document."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Content")])
        ])

        visitor = ValidationVisitor(strict=True)
        doc.accept(visitor)
        assert len(visitor.errors) == 0

    def test_invalid_heading_level(self):
        """Test that invalid heading levels are caught."""
        heading = Heading.__new__(Heading)
        heading.level = 10
        heading.content = []
        heading.metadata = {}
        heading.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_heading(heading)
        assert len(visitor.errors) > 0
        assert "Invalid heading level" in visitor.errors[0]

    def test_nested_validation(self):
        """Test validation of nested structures."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[
                    Paragraph(content=[
                        Text(content="Item 1")
                    ])
                ]),
                ListItem(children=[
                    Paragraph(content=[
                        Text(content="Item 2")
                    ])
                ])
            ])
        ])

        visitor = ValidationVisitor(strict=True)
        doc.accept(visitor)
        assert len(visitor.errors) == 0


@pytest.mark.unit
class TestExtendedMarkdownNodes:
    """Tests for extended Markdown AST nodes (footnotes, math, definition lists)."""

    def test_footnote_reference(self):
        """Test creating a footnote reference node."""
        ref = FootnoteReference(identifier="1")
        assert ref.identifier == "1"

        class TestVisitor:
            def visit_footnote_reference(self, node):
                return f"[^{node.identifier}]"

        visitor = TestVisitor()
        result = ref.accept(visitor)
        assert result == "[^1]"

    def test_footnote_definition(self):
        """Test creating a footnote definition node."""
        defn = FootnoteDefinition(
            identifier="1",
            content=[Paragraph(content=[Text(content="Footnote text here")])]
        )
        assert defn.identifier == "1"
        assert len(defn.content) == 1
        assert isinstance(defn.content[0], Paragraph)

    def test_math_inline(self):
        """Test creating an inline math node."""
        math = MathInline(content="E=mc^2")
        assert math.content == "E=mc^2"

    def test_math_block(self):
        """Test creating a math block node."""
        math = MathBlock(content="\\sum_{i=1}^{n} x_i")
        assert math.content == "\\sum_{i=1}^{n} x_i"

    def test_definition_list(self):
        """Test creating a definition list."""
        term1 = DefinitionTerm(content=[Text(content="Term 1")])
        desc1 = DefinitionDescription(content=[Paragraph(content=[Text(content="Description 1")])])
        desc2 = DefinitionDescription(content=[Paragraph(content=[Text(content="Description 2")])])

        dl = DefinitionList(items=[
            (term1, [desc1, desc2])
        ])

        assert len(dl.items) == 1
        assert dl.items[0][0] == term1
        assert len(dl.items[0][1]) == 2

    def test_definition_term(self):
        """Test creating a definition term."""
        term = DefinitionTerm(content=[Text(content="API")])
        assert len(term.content) == 1
        assert isinstance(term.content[0], Text)

    def test_definition_description(self):
        """Test creating a definition description."""
        desc = DefinitionDescription(content=[
            Paragraph(content=[Text(content="Application Programming Interface")])
        ])
        assert len(desc.content) == 1
        assert isinstance(desc.content[0], Paragraph)

    def test_footnote_validation(self):
        """Test validation of footnote nodes."""
        # Valid footnote reference
        ref = FootnoteReference(identifier="1")
        visitor = ValidationVisitor(strict=True)
        visitor.visit_footnote_reference(ref)
        assert len(visitor.errors) == 0

        # Invalid footnote reference (empty identifier)
        ref_invalid = FootnoteReference.__new__(FootnoteReference)
        ref_invalid.identifier = ""
        ref_invalid.metadata = {}
        ref_invalid.source_location = None

        visitor2 = ValidationVisitor(strict=False)
        visitor2.visit_footnote_reference(ref_invalid)
        assert len(visitor2.errors) > 0

    def test_definition_list_validation(self):
        """Test validation of definition lists."""
        term = DefinitionTerm(content=[Text(content="Term")])
        desc = DefinitionDescription(content=[Paragraph(content=[Text(content="Desc")])])
        dl = DefinitionList(items=[(term, [desc])])

        visitor = ValidationVisitor(strict=True)
        visitor.visit_definition_list(dl)
        assert len(visitor.errors) == 0
