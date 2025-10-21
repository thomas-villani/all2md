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
        loc = SourceLocation(format="html", page=1, line=10, column=5, element_id="main", metadata={"extra": "data"})
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
        content = [Text(content="Hello "), Strong(content=[Text(content="world")]), Text(content="!")]
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
        assert code.fence_char == "`"
        assert code.fence_length == 3

    def test_create_with_language(self):
        """Test creating a code block with language."""
        code = CodeBlock(content="x = 1", language="python")
        assert code.language == "python"

    def test_custom_fence(self):
        """Test creating a code block with custom fence."""
        code = CodeBlock(content="test", fence_char="~", fence_length=4)
        assert code.fence_char == "~"
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
        checked_item = ListItem(children=[Paragraph(content=[Text(content="Done")])], task_status="checked")
        unchecked_item = ListItem(children=[Paragraph(content=[Text(content="Todo")])], task_status="unchecked")
        assert checked_item.task_status == "checked"
        assert unchecked_item.task_status == "unchecked"


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
            cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])], is_header=True
        )
        table = Table(header=header)
        assert table.header is not None
        assert table.header.is_header is True

    def test_table_with_alignments(self):
        """Test creating a table with column alignments."""
        table = Table(alignments=["left", "center", "right"])
        assert len(table.alignments) == 3
        assert table.alignments[0] == "left"
        assert table.alignments[1] == "center"
        assert table.alignments[2] == "right"

    def test_table_cell_with_span(self):
        """Test creating a table cell with colspan/rowspan."""
        cell = TableCell(content=[Text(content="Merged")], colspan=2, rowspan=3)
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
        link = Link(url="https://example.com", content=[Text(content="Example")], title="Example Site")
        assert link.url == "https://example.com"
        assert link.title == "Example Site"

    def test_image_node(self):
        """Test creating an image node."""
        img = Image(url="image.png", alt_text="An image", title="Image title", width=800, height=600)
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
        para = Paragraph(content=[Text(content="Test")], metadata={"author": "Alice", "date": "2025-01-01"})
        assert para.metadata["author"] == "Alice"
        assert para.metadata["date"] == "2025-01-01"

    def test_source_location_tracking(self):
        """Test tracking source location."""
        loc = SourceLocation(format="pdf", page=5, line=20)
        heading = Heading(level=1, content=[Text(content="Chapter 1")], source_location=loc)
        assert heading.source_location is not None
        assert heading.source_location.format == "pdf"
        assert heading.source_location.page == 5


@pytest.mark.unit
class TestValidationVisitor:
    """Tests for ValidationVisitor."""

    def test_valid_document(self):
        """Test validating a well-formed document."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Content")])]
        )

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
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )

        visitor = ValidationVisitor(strict=True)
        doc.accept(visitor)
        assert len(visitor.errors) == 0

    def test_table_inconsistent_column_count(self):
        """Test that tables with inconsistent column counts are caught."""
        table = Table(
            header=TableRow(
                cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])], is_header=True
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="1")]),
                        TableCell(content=[Text(content="2")]),
                        TableCell(content=[Text(content="3")]),
                    ]
                )
            ],
        )

        visitor = ValidationVisitor(strict=False)
        visitor.visit_table(table)
        assert len(visitor.errors) > 0
        assert "has 3 cells, expected 2" in visitor.errors[0]

    def test_table_invalid_alignments_length(self):
        """Test that tables with mismatched alignments length are caught."""
        table = Table(
            header=TableRow(
                cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])], is_header=True
            ),
            rows=[],
            alignments=["left", "center", "right"],
        )

        visitor = ValidationVisitor(strict=False)
        visitor.visit_table(table)
        assert len(visitor.errors) > 0
        assert "3 alignments but 2 columns" in visitor.errors[0]

    def test_table_cell_invalid_colspan(self):
        """Test that table cells with colspan < 1 are caught."""
        cell = TableCell.__new__(TableCell)
        cell.content = []
        cell.colspan = 0
        cell.rowspan = 1
        cell.alignment = None
        cell.metadata = {}
        cell.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_table_cell(cell)
        assert len(visitor.errors) > 0
        assert "colspan must be >= 1" in visitor.errors[0]

    def test_table_cell_invalid_rowspan(self):
        """Test that table cells with rowspan < 1 are caught."""
        cell = TableCell.__new__(TableCell)
        cell.content = []
        cell.colspan = 1
        cell.rowspan = -1
        cell.alignment = None
        cell.metadata = {}
        cell.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_table_cell(cell)
        assert len(visitor.errors) > 0
        assert "rowspan must be >= 1" in visitor.errors[0]

    def test_list_invalid_start(self):
        """Test that ordered lists with start < 1 are caught."""
        lst = List.__new__(List)
        lst.ordered = True
        lst.items = [ListItem(children=[])]
        lst.start = 0
        lst.tight = True
        lst.metadata = {}
        lst.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_list(lst)
        assert len(visitor.errors) > 0
        assert "start must be >= 1" in visitor.errors[0]

    def test_list_empty_items(self):
        """Test that lists with no items are caught."""
        lst = List(ordered=False, items=[])

        visitor = ValidationVisitor(strict=False)
        visitor.visit_list(lst)
        assert len(visitor.errors) > 0
        assert "must have at least one item" in visitor.errors[0]

    def test_code_block_invalid_fence_length(self):
        """Test that code blocks with fence_length < 1 are caught."""
        code = CodeBlock.__new__(CodeBlock)
        code.content = "test"
        code.language = None
        code.fence_char = "`"
        code.fence_length = 0
        code.metadata = {}
        code.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_code_block(code)
        assert len(visitor.errors) > 0
        assert "fence_length must be >= 1" in visitor.errors[0]

    def test_code_block_invalid_fence_char(self):
        """Test that code blocks with invalid fence_char are caught."""
        code = CodeBlock.__new__(CodeBlock)
        code.content = "test"
        code.language = None
        code.fence_char = "*"
        code.fence_length = 3
        code.metadata = {}
        code.source_location = None

        visitor = ValidationVisitor(strict=False)
        visitor.visit_code_block(code)
        assert len(visitor.errors) > 0
        assert "fence_char must be" in visitor.errors[0]

    def test_link_empty_url(self):
        """Test that links with empty url are caught."""
        link = Link(url="", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=False)
        visitor.visit_link(link)
        assert len(visitor.errors) > 0
        assert "url must be non-empty" in visitor.errors[0]

    def test_link_invalid_scheme_strict(self):
        """Test that links with unrecognized scheme are caught in strict mode."""
        import pytest

        link = Link(url="unknown://example.com", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="unrecognized scheme"):
            visitor.visit_link(link)

    def test_link_valid_schemes(self):
        """Test that links with valid schemes pass validation."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "mailto:test@example.com",
            "ftp://example.com",
            "#anchor",
            "/relative/path",
            "relative/path",
        ]

        for url in valid_urls:
            link = Link(url=url, content=[Text(content="link")])
            visitor = ValidationVisitor(strict=True)
            visitor.visit_link(link)
            assert len(visitor.errors) == 0, f"URL {url} should be valid"

    def test_image_empty_url(self):
        """Test that images with empty url are caught."""
        image = Image(url="", alt_text="test")

        visitor = ValidationVisitor(strict=False)
        visitor.visit_image(image)
        assert len(visitor.errors) > 0
        assert "url must be non-empty" in visitor.errors[0]


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
        defn = FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote text here")])])
        assert defn.identifier == "1"
        assert len(defn.content) == 1
        assert isinstance(defn.content[0], Paragraph)

    def test_math_inline(self):
        """Test creating an inline math node."""
        math = MathInline(content="E=mc^2")
        assert math.content == "E=mc^2"
        assert math.notation == "latex"
        assert math.representations["latex"] == "E=mc^2"

    def test_math_block(self):
        """Test creating a math block node."""
        math = MathBlock(content="\\sum_{i=1}^{n} x_i")
        assert math.content == "\\sum_{i=1}^{n} x_i"
        assert math.notation == "latex"
        assert math.representations["latex"] == "\\sum_{i=1}^{n} x_i"

    def test_definition_list(self):
        """Test creating a definition list."""
        term1 = DefinitionTerm(content=[Text(content="Term 1")])
        desc1 = DefinitionDescription(content=[Paragraph(content=[Text(content="Description 1")])])
        desc2 = DefinitionDescription(content=[Paragraph(content=[Text(content="Description 2")])])

        dl = DefinitionList(items=[(term1, [desc1, desc2])])

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
        desc = DefinitionDescription(content=[Paragraph(content=[Text(content="Application Programming Interface")])])
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


@pytest.mark.unit
class TestHTMLValidation:
    """Tests for HTML node validation with security constraints."""

    def test_html_block_allowed_by_default(self):
        """Test that HTMLBlock is allowed by default."""
        html = HTMLBlock(content="<div>Test</div>")
        visitor = ValidationVisitor(strict=True, allow_raw_html=True)

        visitor.visit_html_block(html)
        assert len(visitor.errors) == 0

    def test_html_inline_allowed_by_default(self):
        """Test that HTMLInline is allowed by default."""
        html = HTMLInline(content="<span>Test</span>")
        visitor = ValidationVisitor(strict=True, allow_raw_html=True)

        visitor.visit_html_inline(html)
        assert len(visitor.errors) == 0

    def test_html_block_rejected_in_strict_mode(self):
        """Test that HTMLBlock is rejected when allow_raw_html=False."""
        html = HTMLBlock(content="<div>Test</div>")
        visitor = ValidationVisitor(strict=False, allow_raw_html=False)

        visitor.visit_html_block(html)
        assert len(visitor.errors) == 1
        assert "HTMLBlock" in visitor.errors[0]
        assert "strict mode" in visitor.errors[0]

    def test_html_inline_rejected_in_strict_mode(self):
        """Test that HTMLInline is rejected when allow_raw_html=False."""
        html = HTMLInline(content="<span>Test</span>")
        visitor = ValidationVisitor(strict=False, allow_raw_html=False)

        visitor.visit_html_inline(html)
        assert len(visitor.errors) == 1
        assert "HTMLInline" in visitor.errors[0]
        assert "strict mode" in visitor.errors[0]

    def test_html_block_raises_in_strict_validation(self):
        """Test that HTMLBlock raises exception in strict validation mode."""
        html = HTMLBlock(content="<script>alert('xss')</script>")
        visitor = ValidationVisitor(strict=True, allow_raw_html=False)

        with pytest.raises(ValueError, match="Raw HTML content.*not allowed"):
            visitor.visit_html_block(html)

    def test_html_inline_raises_in_strict_validation(self):
        """Test that HTMLInline raises exception in strict validation mode."""
        html = HTMLInline(content="<img src=x onerror=alert(1)>")
        visitor = ValidationVisitor(strict=True, allow_raw_html=False)

        with pytest.raises(ValueError, match="Raw HTML content.*not allowed"):
            visitor.visit_html_inline(html)

    def test_document_with_html_validated(self):
        """Test validation of entire document containing HTML."""
        # Document with HTMLBlock
        doc = Document(
            children=[Paragraph(content=[Text(content="Safe content")]), HTMLBlock(content="<div>Unsafe HTML</div>")]
        )

        # Should pass with default settings
        visitor1 = ValidationVisitor(strict=True, allow_raw_html=True)
        visitor1.visit_document(doc)
        assert len(visitor1.errors) == 0

        # Should fail with allow_raw_html=False
        visitor2 = ValidationVisitor(strict=False, allow_raw_html=False)
        visitor2.visit_document(doc)
        assert len(visitor2.errors) == 1

    def test_paragraph_with_html_inline_validated(self):
        """Test validation of paragraph containing inline HTML."""
        para = Paragraph(
            content=[Text(content="Text with "), HTMLInline(content="<strong>HTML</strong>"), Text(content=" inline")]
        )

        # Should pass with default settings
        visitor1 = ValidationVisitor(strict=True, allow_raw_html=True)
        visitor1.visit_paragraph(para)
        assert len(visitor1.errors) == 0

        # Should fail with allow_raw_html=False
        visitor2 = ValidationVisitor(strict=False, allow_raw_html=False)
        visitor2.visit_paragraph(para)
        assert len(visitor2.errors) == 1


@pytest.mark.unit
class TestValidationVisitorContainmentRules:
    """Tests for block/inline containment rule validation."""

    def test_paragraph_with_list_child_fails(self):
        """Test that Paragraph with List child fails validation in strict mode."""
        para = Paragraph(content=[Text(content="Some text"), List(ordered=False, items=[ListItem(children=[])])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="Paragraph can only contain inline nodes"):
            visitor.visit_paragraph(para)

    def test_heading_with_codeblock_child_fails(self):
        """Test that Heading with CodeBlock child fails validation in strict mode."""
        heading = Heading(level=1, content=[Text(content="Title "), CodeBlock(content="code")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="Heading can only contain inline nodes"):
            visitor.visit_heading(heading)

    def test_emphasis_with_paragraph_child_fails(self):
        """Test that Emphasis with Paragraph child fails validation in strict mode."""
        emphasis = Emphasis(content=[Paragraph(content=[Text(content="wrong")])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="Emphasis can only contain inline nodes"):
            visitor.visit_emphasis(emphasis)

    def test_list_item_with_inline_only_fails(self):
        """Test that ListItem with inline-only content fails validation in strict mode."""
        list_item = ListItem(children=[Text(content="This should be in a paragraph")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="ListItem can only contain block nodes"):
            visitor.visit_list_item(list_item)

    def test_table_cell_with_block_node_fails(self):
        """Test that TableCell with block nodes fails validation in strict mode."""
        cell = TableCell(content=[Paragraph(content=[Text(content="Should be inline")])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="TableCell can only contain inline nodes"):
            visitor.visit_table_cell(cell)

    def test_valid_nested_structures_pass(self):
        """Test that valid nested structures pass validation."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[
                        Text(content="Title with "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" text"),
                    ],
                ),
                Paragraph(
                    content=[
                        Text(content="Paragraph with "),
                        Emphasis(content=[Text(content="emphasis")]),
                        Text(content=" and "),
                        Link(url="https://example.com", content=[Text(content="link")]),
                    ]
                ),
                List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Item 1")])])]),
            ]
        )

        visitor = ValidationVisitor(strict=True)
        doc.accept(visitor)
        assert len(visitor.errors) == 0

    def test_containment_not_enforced_in_non_strict_mode(self):
        """Test that containment rules are not enforced in non-strict mode."""
        para = Paragraph(content=[Text(content="Some text"), List(ordered=False, items=[ListItem(children=[])])])

        visitor = ValidationVisitor(strict=False)
        visitor.visit_paragraph(para)
        assert len(visitor.errors) == 0

    def test_strong_with_block_fails(self):
        """Test that Strong with block child fails validation in strict mode."""
        strong = Strong(content=[BlockQuote(children=[Paragraph(content=[Text(content="wrong")])])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="Strong can only contain inline nodes"):
            visitor.visit_strong(strong)

    def test_link_with_block_fails(self):
        """Test that Link with block child fails validation in strict mode."""
        link = Link(url="https://example.com", content=[Heading(level=1, content=[Text(content="wrong")])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="Link can only contain inline nodes"):
            visitor.visit_link(link)

    def test_definition_term_with_block_fails(self):
        """Test that DefinitionTerm with block child fails validation in strict mode."""
        term = DefinitionTerm(content=[Paragraph(content=[Text(content="wrong")])])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="DefinitionTerm can only contain inline nodes"):
            visitor.visit_definition_term(term)

    def test_definition_description_with_inline_fails(self):
        """Test that DefinitionDescription with inline-only content fails validation in strict mode."""
        desc = DefinitionDescription(content=[Text(content="Should be in a paragraph")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="DefinitionDescription can only contain block nodes"):
            visitor.visit_definition_description(desc)


@pytest.mark.unit
class TestValidationVisitorURLSecurity:
    """Tests for URL security validation enhancements."""

    def test_link_javascript_url_rejected_strict(self):
        """Test that javascript: URLs are rejected in strict mode."""
        link = Link(url="javascript:alert(1)", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="dangerous scheme"):
            visitor.visit_link(link)

    def test_link_vbscript_url_rejected_strict(self):
        """Test that vbscript: URLs are rejected in strict mode."""
        link = Link(url="vbscript:msgbox(1)", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="dangerous scheme"):
            visitor.visit_link(link)

    def test_link_data_html_rejected_strict(self):
        """Test that data:text/html URLs are rejected in strict mode."""
        link = Link(url="data:text/html,<script>alert(1)</script>", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="dangerous scheme"):
            visitor.visit_link(link)

    def test_link_valid_http_https_pass(self):
        """Test that valid HTTP/HTTPS URLs pass validation."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "https://example.com/path?query=value",
        ]

        for url in valid_urls:
            link = Link(url=url, content=[Text(content="link")])
            visitor = ValidationVisitor(strict=True)
            visitor.visit_link(link)
            assert len(visitor.errors) == 0, f"URL {url} should be valid"

    def test_link_relative_urls_pass(self):
        """Test that relative URLs pass validation."""
        valid_urls = [
            "#anchor",
            "/absolute/path",
            "relative/path",
            "../parent/path",
        ]

        for url in valid_urls:
            link = Link(url=url, content=[Text(content="link")])
            visitor = ValidationVisitor(strict=True)
            visitor.visit_link(link)
            assert len(visitor.errors) == 0, f"URL {url} should be valid"

    def test_link_mailto_tel_ftp_pass(self):
        """Test that mailto:, tel:, ftp: URLs pass validation."""
        valid_urls = [
            "mailto:test@example.com",
            "tel:+1234567890",
            "ftp://ftp.example.com/file.txt",
            "ftps://ftp.example.com/file.txt",
        ]

        for url in valid_urls:
            link = Link(url=url, content=[Text(content="link")])
            visitor = ValidationVisitor(strict=True)
            visitor.visit_link(link)
            assert len(visitor.errors) == 0, f"URL {url} should be valid"

    def test_image_javascript_url_rejected_strict(self):
        """Test that javascript: URLs are rejected for images in strict mode."""
        image = Image(url="javascript:alert(1)", alt_text="test")

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="dangerous scheme"):
            visitor.visit_image(image)

    def test_image_data_image_png_passes(self):
        """Test that valid data:image/png URLs pass validation."""
        image = Image(
            url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            alt_text="1x1 pixel",
        )

        visitor = ValidationVisitor(strict=True)
        visitor.visit_image(image)
        assert len(visitor.errors) == 0

    def test_image_data_non_image_rejected_strict(self):
        """Test that data: URIs with non-image MIME types are rejected for images."""
        image = Image(url="data:text/html,<script>alert(1)</script>", alt_text="test")

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="data URI must have image"):
            visitor.visit_image(image)

    def test_image_excessively_long_data_uri_rejected_strict(self):
        """Test that excessively long data URIs are rejected in strict mode."""
        # Create a data URI that exceeds DEFAULT_MAX_ASSET_SIZE_BYTES
        long_data = "data:image/png;base64," + "A" * (50 * 1024 * 1024 + 1)
        image = Image(url=long_data, alt_text="huge")

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            visitor.visit_image(image)

    def test_url_validation_not_enforced_in_non_strict_mode(self):
        """Test that URL validation is not enforced in non-strict mode."""
        link = Link(url="javascript:alert(1)", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=False)
        visitor.visit_link(link)
        assert len(visitor.errors) == 0

    def test_image_valid_http_https_pass(self):
        """Test that valid HTTP/HTTPS image URLs pass validation."""
        valid_urls = [
            "http://example.com/image.png",
            "https://example.com/image.jpg",
        ]

        for url in valid_urls:
            image = Image(url=url, alt_text="test")
            visitor = ValidationVisitor(strict=True)
            visitor.visit_image(image)
            assert len(visitor.errors) == 0, f"URL {url} should be valid"

    def test_link_unknown_scheme_rejected_strict(self):
        """Test that unknown URL schemes are rejected in strict mode."""
        link = Link(url="unknown://example.com", content=[Text(content="link")])

        visitor = ValidationVisitor(strict=True)
        with pytest.raises(ValueError, match="unrecognized scheme"):
            visitor.visit_link(link)


@pytest.mark.unit
class TestReplaceNodeChildren:
    """Tests for replace_node_children helper function."""

    def test_replace_node_children_import(self):
        """Test that replace_node_children can be imported."""
        from all2md.ast.nodes import replace_node_children

        assert callable(replace_node_children)

    def test_replace_heading_content(self):
        """Test replacing heading content."""
        from all2md.ast.nodes import replace_node_children

        heading = Heading(level=1, content=[Text(content="Old")])
        new_heading = replace_node_children(heading, [Text(content="New")])

        assert isinstance(new_heading, Heading)
        assert new_heading.level == 1
        assert len(new_heading.content) == 1
        assert new_heading.content[0].content == "New"
        # Original unchanged
        assert heading.content[0].content == "Old"

    def test_replace_paragraph_content(self):
        """Test replacing paragraph content."""
        from all2md.ast.nodes import replace_node_children

        para = Paragraph(content=[Text(content="Old")])
        new_para = replace_node_children(para, [Text(content="New")])

        assert isinstance(new_para, Paragraph)
        assert len(new_para.content) == 1
        assert new_para.content[0].content == "New"

    def test_replace_document_children(self):
        """Test replacing document children."""
        from all2md.ast.nodes import replace_node_children

        doc = Document(children=[Paragraph(content=[Text(content="Old")])])
        new_children = [Heading(level=1, content=[Text(content="New")])]
        new_doc = replace_node_children(doc, new_children)

        assert isinstance(new_doc, Document)
        assert len(new_doc.children) == 1
        assert isinstance(new_doc.children[0], Heading)

    def test_replace_list_items(self):
        """Test replacing list items."""
        from all2md.ast.nodes import replace_node_children

        lst = List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Old")])])])
        new_items = [
            ListItem(children=[Paragraph(content=[Text(content="New 1")])]),
            ListItem(children=[Paragraph(content=[Text(content="New 2")])]),
        ]
        new_list = replace_node_children(lst, new_items)

        assert isinstance(new_list, List)
        assert len(new_list.items) == 2

    def test_replace_table_children_add_header(self):
        """Test adding header to headerless table."""
        from all2md.ast.nodes import replace_node_children

        # Original table without header
        table = Table(
            rows=[
                TableRow(cells=[TableCell(content=[Text(content="Row 1")])], is_header=False),
                TableRow(cells=[TableCell(content=[Text(content="Row 2")])], is_header=False),
            ]
        )

        # New children with header
        new_header = TableRow(cells=[TableCell(content=[Text(content="Header")])], is_header=True)
        new_children = [new_header] + table.rows

        new_table = replace_node_children(table, new_children)

        assert isinstance(new_table, Table)
        assert new_table.header is not None
        assert new_table.header.is_header is True
        assert new_table.header.cells[0].content[0].content == "Header"
        assert len(new_table.rows) == 2

    def test_replace_table_children_remove_header(self):
        """Test removing header from table."""
        from all2md.ast.nodes import replace_node_children

        # Original table with header
        header = TableRow(cells=[TableCell(content=[Text(content="Header")])], is_header=True)
        table = Table(
            header=header, rows=[TableRow(cells=[TableCell(content=[Text(content="Row 1")])], is_header=False)]
        )

        # New children without header (all rows have is_header=False)
        new_children = [
            TableRow(cells=[TableCell(content=[Text(content="Row 1")])], is_header=False),
            TableRow(cells=[TableCell(content=[Text(content="Row 2")])], is_header=False),
        ]

        new_table = replace_node_children(table, new_children)

        assert isinstance(new_table, Table)
        assert new_table.header is None
        assert len(new_table.rows) == 2

    def test_replace_table_children_change_header(self):
        """Test changing header of table."""
        from all2md.ast.nodes import replace_node_children

        # Original table with header
        old_header = TableRow(cells=[TableCell(content=[Text(content="Old Header")])], is_header=True)
        table = Table(
            header=old_header, rows=[TableRow(cells=[TableCell(content=[Text(content="Row 1")])], is_header=False)]
        )

        # New children with different header
        new_header = TableRow(cells=[TableCell(content=[Text(content="New Header")])], is_header=True)
        new_children = [new_header, table.rows[0]]

        new_table = replace_node_children(table, new_children)

        assert isinstance(new_table, Table)
        assert new_table.header is not None
        assert new_table.header.cells[0].content[0].content == "New Header"
        assert len(new_table.rows) == 1

    def test_replace_table_children_preserve_header(self):
        """Test preserving header while changing rows."""
        from all2md.ast.nodes import replace_node_children

        # Original table with header
        header = TableRow(cells=[TableCell(content=[Text(content="Header")])], is_header=True)
        table = Table(
            header=header, rows=[TableRow(cells=[TableCell(content=[Text(content="Old Row")])], is_header=False)]
        )

        # Keep header, change rows
        new_children = [
            header,
            TableRow(cells=[TableCell(content=[Text(content="New Row 1")])], is_header=False),
            TableRow(cells=[TableCell(content=[Text(content="New Row 2")])], is_header=False),
        ]

        new_table = replace_node_children(table, new_children)

        assert isinstance(new_table, Table)
        assert new_table.header is not None
        assert new_table.header is header
        assert len(new_table.rows) == 2
        assert new_table.rows[0].cells[0].content[0].content == "New Row 1"

    def test_replace_table_children_multiple_headers_only_first_used(self):
        """Test that only first row with is_header=True becomes header."""
        from all2md.ast.nodes import replace_node_children

        table = Table(rows=[])

        # Multiple rows marked as header
        new_children = [
            TableRow(cells=[TableCell(content=[Text(content="Header 1")])], is_header=True),
            TableRow(cells=[TableCell(content=[Text(content="Header 2")])], is_header=True),
            TableRow(cells=[TableCell(content=[Text(content="Row")])], is_header=False),
        ]

        new_table = replace_node_children(table, new_children)

        assert isinstance(new_table, Table)
        assert new_table.header is not None
        assert new_table.header.cells[0].content[0].content == "Header 1"
        # Second "header" and regular row become body rows
        assert len(new_table.rows) == 2

    def test_replace_table_children_empty_list(self):
        """Test replacing table children with empty list."""
        from all2md.ast.nodes import replace_node_children

        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Header")])], is_header=True),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Row")])], is_header=False)],
        )

        new_table = replace_node_children(table, [])

        assert isinstance(new_table, Table)
        assert new_table.header is None
        assert new_table.rows == []

    def test_replace_table_children_wrong_type_raises_error(self):
        """Test that non-TableRow children raise ValueError."""
        from all2md.ast.nodes import replace_node_children

        table = Table(rows=[])

        # Try to add a Paragraph as child (invalid)
        new_children = [Paragraph(content=[Text(content="Invalid")])]

        with pytest.raises(ValueError, match="Table children must be TableRow instances"):
            replace_node_children(table, new_children)

    def test_replace_table_row_cells(self):
        """Test replacing table row cells."""
        from all2md.ast.nodes import replace_node_children

        row = TableRow(cells=[TableCell(content=[Text(content="Old 1")]), TableCell(content=[Text(content="Old 2")])])

        new_cells = [
            TableCell(content=[Text(content="New 1")]),
            TableCell(content=[Text(content="New 2")]),
            TableCell(content=[Text(content="New 3")]),
        ]

        new_row = replace_node_children(row, new_cells)

        assert isinstance(new_row, TableRow)
        assert len(new_row.cells) == 3
        assert new_row.cells[0].content[0].content == "New 1"
