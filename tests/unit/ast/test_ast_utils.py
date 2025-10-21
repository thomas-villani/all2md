#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_ast_utils.py
"""Tests for AST utility functions."""

from all2md.ast import (
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    Paragraph,
    Strong,
    Text,
    extract_text,
)


class TestExtractText:
    """Tests for extract_text utility function."""

    def test_extract_from_single_text_node(self):
        """Test extracting text from a single Text node."""
        text = Text(content="Hello World")
        result = extract_text(text)
        assert result == "Hello World"

    def test_extract_from_list_of_text_nodes(self):
        """Test extracting text from a list of Text nodes."""
        nodes = [
            Text(content="Hello"),
            Text(content="World"),
        ]
        result = extract_text(nodes)
        assert result == "Hello World"

    def test_extract_with_no_joiner(self):
        """Test extracting text with empty joiner."""
        nodes = [
            Text(content="Hello"),
            Text(content="World"),
        ]
        result = extract_text(nodes, joiner="")
        assert result == "HelloWorld"

    def test_extract_with_custom_joiner(self):
        """Test extracting text with custom joiner."""
        nodes = [
            Text(content="Hello"),
            Text(content="World"),
        ]
        result = extract_text(nodes, joiner=", ")
        assert result == "Hello, World"

    def test_extract_from_paragraph(self):
        """Test extracting text from a Paragraph node."""
        para = Paragraph(
            content=[
                Text(content="This is "),
                Text(content="a paragraph."),
            ]
        )
        result = extract_text(para)
        # Joiner adds space between nodes
        assert result == "This is  a paragraph."

    def test_extract_from_heading(self):
        """Test extracting text from a Heading node."""
        heading = Heading(
            level=1,
            content=[
                Text(content="Main "),
                Text(content="Title"),
            ],
        )
        result = extract_text(heading)
        # Joiner adds space between nodes
        assert result == "Main  Title"

    def test_extract_from_nested_emphasis(self):
        """Test extracting text from nested emphasis nodes."""
        para = Paragraph(
            content=[
                Text(content="This is "),
                Emphasis(content=[Text(content="emphasized")]),
                Text(content=" text."),
            ]
        )
        result = extract_text(para)
        # Joiner adds space between nodes at each level
        assert result == "This is  emphasized  text."

    def test_extract_from_nested_strong(self):
        """Test extracting text from nested strong nodes."""
        para = Paragraph(
            content=[
                Text(content="This is "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text."),
            ]
        )
        result = extract_text(para)
        # Joiner adds space between nodes at each level
        assert result == "This is  bold  text."

    def test_extract_from_deeply_nested_structure(self):
        """Test extracting text from deeply nested structure."""
        para = Paragraph(
            content=[
                Text(content="This is "),
                Strong(
                    content=[
                        Text(content="bold and "),
                        Emphasis(content=[Text(content="italic")]),
                    ]
                ),
                Text(content=" text."),
            ]
        )
        result = extract_text(para)
        # Joiner adds space at multiple nesting levels
        assert result == "This is  bold and  italic  text."

    def test_extract_from_document(self):
        """Test extracting text from entire document."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="First paragraph.")]),
                Paragraph(content=[Text(content="Second paragraph.")]),
            ]
        )
        result = extract_text(doc)
        assert result == "Title First paragraph. Second paragraph."

    def test_extract_ignores_image_nodes(self):
        """Test that image nodes don't contribute text."""
        para = Paragraph(
            content=[
                Text(content="Before "),
                Image(url="image.png", alt_text="An image"),
                Text(content=" after"),
            ]
        )
        result = extract_text(para)
        # Images don't have extractable text content, but joiner still adds space
        assert result == "Before   after"

    def test_extract_from_link_content(self):
        """Test extracting text from link content."""
        para = Paragraph(
            content=[
                Text(content="Click "),
                Link(url="https://example.com", content=[Text(content="here")]),
                Text(content=" to continue."),
            ]
        )
        result = extract_text(para)
        # Joiner adds space between nodes
        assert result == "Click  here  to continue."

    def test_extract_from_empty_list(self):
        """Test extracting from empty list returns empty string."""
        result = extract_text([])
        assert result == ""

    def test_extract_from_empty_paragraph(self):
        """Test extracting from empty paragraph returns empty string."""
        para = Paragraph(content=[])
        result = extract_text(para)
        assert result == ""

    def test_extract_with_mixed_empty_and_content_nodes(self):
        """Test extracting with some empty text nodes."""
        nodes = [
            Text(content="Hello"),
            Text(content=""),
            Text(content="World"),
        ]
        result = extract_text(nodes)
        # Empty text nodes are filtered out by the "if extracted:" check
        assert result == "Hello World"

    def test_extract_preserves_spaces_in_text_nodes(self):
        """Test that spaces within text nodes are preserved."""
        nodes = [
            Text(content="Hello   World"),
            Text(content="with   spaces"),
        ]
        result = extract_text(nodes)
        assert result == "Hello   World with   spaces"

    def test_extract_from_heading_for_id_generation(self):
        """Test extracting text suitable for ID generation."""
        heading = Heading(
            level=2,
            content=[
                Text(content="My "),
                Emphasis(content=[Text(content="Fancy")]),
                Text(content=" Heading!"),
            ],
        )
        # No joiner for ID generation - preserves original spaces in text
        result = extract_text(heading.content, joiner="")
        assert result == "My Fancy Heading!"

    def test_extract_from_list_with_nested_content(self):
        """Test extracting from list of nodes with nested content."""
        nodes = [
            Paragraph(
                content=[
                    Text(content="Para 1 with "),
                    Strong(content=[Text(content="bold")]),
                ]
            ),
            Paragraph(
                content=[
                    Text(content="Para 2 with "),
                    Emphasis(content=[Text(content="italic")]),
                ]
            ),
        ]
        result = extract_text(nodes)
        # Joiner adds space at each nesting level
        assert result == "Para 1 with  bold Para 2 with  italic"

    def test_extract_from_list_node(self):
        """Test extracting text from List nodes (Issue 7)."""
        from all2md.ast import List, ListItem

        lst = List(
            ordered=False,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
            ],
        )
        result = extract_text(lst)
        assert result == "Item 1 Item 2 Item 3"

    def test_extract_from_nested_list(self):
        """Test extracting text from nested List nodes."""
        from all2md.ast import List, ListItem

        nested_list = List(
            ordered=False,
            items=[
                ListItem(
                    children=[
                        Paragraph(content=[Text(content="Sub-item 1")]),
                    ]
                ),
                ListItem(
                    children=[
                        Paragraph(content=[Text(content="Sub-item 2")]),
                    ]
                ),
            ],
        )

        outer_list = List(
            ordered=False,
            items=[
                ListItem(
                    children=[
                        Paragraph(content=[Text(content="Item 1")]),
                        nested_list,
                    ]
                ),
                ListItem(
                    children=[
                        Paragraph(content=[Text(content="Item 2")]),
                    ]
                ),
            ],
        )

        result = extract_text(outer_list)
        assert result == "Item 1 Sub-item 1 Sub-item 2 Item 2"

    def test_extract_from_table_node(self):
        """Test extracting text from Table nodes (Issue 7)."""
        from all2md.ast import Table, TableCell, TableRow

        table = Table(
            header=TableRow(
                cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Age")]),
                ],
                is_header=True,
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Alice")]),
                        TableCell(content=[Text(content="30")]),
                    ]
                ),
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Bob")]),
                        TableCell(content=[Text(content="25")]),
                    ]
                ),
            ],
        )
        result = extract_text(table)
        # Should extract text from header and all rows
        assert result == "Name Age Alice 30 Bob 25"

    def test_extract_from_table_with_formatted_cells(self):
        """Test extracting text from Table with inline formatting."""
        from all2md.ast import Table, TableCell, TableRow

        table = Table(
            header=TableRow(
                cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Strong(content=[Text(content="Age")])]),
                ],
                is_header=True,
            ),
            rows=[
                TableRow(
                    cells=[
                        TableCell(content=[Text(content="Alice "), Emphasis(content=[Text(content="Smith")])]),
                        TableCell(content=[Text(content="30")]),
                    ]
                ),
            ],
        )
        result = extract_text(table)
        assert result == "Name Age Alice  Smith 30"

    def test_extract_from_document_with_list(self):
        """Test extracting text from Document containing Lists."""
        from all2md.ast import List, ListItem

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Shopping List")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Apples")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Oranges")])]),
                    ],
                ),
                Paragraph(content=[Text(content="Total: 2 items")]),
            ]
        )
        result = extract_text(doc)
        assert result == "Shopping List Apples Oranges Total: 2 items"
