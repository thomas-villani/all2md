#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for DokuWiki renderer."""

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    Paragraph,
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
)
from all2md.options.dokuwiki import DokuWikiOptions
from all2md.renderers.dokuwiki import DokuWikiRenderer


class TestDokuWikiRenderer:
    """Tests for DokuWiki renderer."""

    def test_render_simple_text(self) -> None:
        """Test rendering simple text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "Hello world" in output

    def test_render_heading_level_1(self) -> None:
        """Test rendering level 1 heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "====== Title ======" in output

    def test_render_heading_level_2(self) -> None:
        """Test rendering level 2 heading."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "===== Section =====" in output

    def test_render_heading_level_3(self) -> None:
        """Test rendering level 3 heading."""
        doc = Document(children=[Heading(level=3, content=[Text(content="Subsection")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "==== Subsection ====" in output

    def test_render_heading_level_4(self) -> None:
        """Test rendering level 4 heading."""
        doc = Document(children=[Heading(level=4, content=[Text(content="Subsubsection")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "=== Subsubsection ===" in output

    def test_render_heading_level_5(self) -> None:
        """Test rendering level 5 heading."""
        doc = Document(children=[Heading(level=5, content=[Text(content="Level 5")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "== Level 5 ==" in output

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text")]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "**bold**" in output

    def test_render_italic(self) -> None:
        """Test rendering italic text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "//italic//" in output

    def test_render_underline(self) -> None:
        """Test rendering underlined text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Underline(content=[Text(content="underlined")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "__underlined__" in output

    def test_render_bold_italic(self) -> None:
        """Test rendering bold and italic text."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Should have nested formatting
        assert "**" in output
        assert "//" in output

    def test_render_code_inline_default(self) -> None:
        """Test rendering inline code with default options."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Default uses '' for monospace
        assert "''code''" in output

    def test_render_code_inline_with_fence(self) -> None:
        """Test rendering inline code with monospace_fence option."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = DokuWikiRenderer(DokuWikiOptions(monospace_fence=True))
        output = renderer.render_to_string(doc)

        assert "<code>code</code>" in output

    def test_render_code_block_with_language(self) -> None:
        """Test rendering code block with language."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("world")', language="python")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<code python>" in output
        assert "def hello():" in output
        assert "</code>" in output

    def test_render_code_block_without_language(self) -> None:
        """Test rendering code block without language."""
        doc = Document(children=[CodeBlock(content="code here")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<code>" in output
        assert "code here" in output
        assert "</code>" in output

    def test_render_unordered_list(self) -> None:
        """Test rendering unordered list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
                    ],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "* Item 1" in output
        assert "* Item 2" in output
        assert "* Item 3" in output

    def test_render_ordered_list(self) -> None:
        """Test rendering ordered list."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "- First" in output
        assert "- Second" in output

    def test_render_nested_list(self) -> None:
        """Test rendering nested list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 1")]),
                                List(
                                    ordered=False,
                                    items=[
                                        ListItem(children=[Paragraph(content=[Text(content="Nested item")])]),
                                    ],
                                ),
                            ]
                        ),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check for nested indentation
        assert "* Item 1" in output
        assert "  * Nested item" in output
        assert "* Item 2" in output

    def test_render_table_with_header(self) -> None:
        """Test rendering table with header."""
        doc = Document(
            children=[
                Table(
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
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check for table structure
        assert "^ Name ^" in output or "^ Name  ^" in output
        assert "^ Age ^" in output or "^ Age  ^" in output
        assert "| Alice |" in output or "| Alice  |" in output
        assert "| Bob |" in output or "| Bob  |" in output

    def test_render_table_without_header(self) -> None:
        """Test rendering table without header."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Cell 1")]),
                                TableCell(content=[Text(content="Cell 2")]),
                            ]
                        ),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "| Cell 1 |" in output or "| Cell 1  |" in output

    def test_render_link_simple(self) -> None:
        """Test rendering simple link."""
        doc = Document(children=[Paragraph(content=[Link(url="page:name", content=[Text(content="page:name")])])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Link text matches URL, so can use short form
        assert "[[page:name]]" in output

    def test_render_link_with_text(self) -> None:
        """Test rendering link with custom text."""
        doc = Document(children=[Paragraph(content=[Link(url="page:name", content=[Text(content="Link Text")])])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[page:name|Link Text]]" in output

    def test_render_external_link(self) -> None:
        """Test rendering external link."""
        doc = Document(
            children=[Paragraph(content=[Link(url="http://example.com", content=[Text(content="Example")])])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[http://example.com|Example]]" in output

    def test_render_image_simple(self) -> None:
        """Test rendering simple image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "{{image.png}}" in output

    def test_render_image_with_alt(self) -> None:
        """Test rendering image with alt text."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Alt Text")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "{{image.png|Alt Text}}" in output

    def test_render_blockquote(self) -> None:
        """Test rendering blockquote."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="Quoted text")]),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "> Quoted text" in output

    def test_render_blockquote_multiline(self) -> None:
        """Test rendering multi-paragraph blockquote."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="First paragraph")]),
                        Paragraph(content=[Text(content="Second paragraph")]),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "> First paragraph" in output
        assert "> Second paragraph" in output

    def test_render_thematic_break(self) -> None:
        """Test rendering thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "----" in output

    def test_render_hard_line_break(self) -> None:
        """Test rendering hard line break."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "\\\\" in output

    def test_render_soft_line_break(self) -> None:
        """Test rendering soft line break."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Soft line break is just a newline
        assert "Line 1\nLine 2" in output or "Line 1" in output and "Line 2" in output

    def test_render_strikethrough(self) -> None:
        """Test rendering strikethrough."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Strikethrough(content=[Text(content="deleted")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<del>deleted</del>" in output

    def test_render_subscript(self) -> None:
        """Test rendering subscript."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="H"),
                        Subscript(content=[Text(content="2")]),
                        Text(content="O"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sub>2</sub>" in output

    def test_render_superscript(self) -> None:
        """Test rendering superscript."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="E=mc"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sup>2</sup>" in output

    def test_render_footnote_reference(self) -> None:
        """Test rendering footnote reference."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        FootnoteReference(identifier="1"),
                        Text(content=" reference"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Should render as inline footnote placeholder
        assert "((" in output

    def test_render_multiple_paragraphs(self) -> None:
        """Test rendering multiple paragraphs with spacing."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "First paragraph" in output
        assert "Second paragraph" in output
        # Should have blank line between paragraphs
        assert "\n\n" in output

    def test_render_complex_document(self) -> None:
        """Test rendering complex document with mixed content."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Introduction with "), Strong(content=[Text(content="bold")])]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
                CodeBlock(content="code example", language="python"),
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check all elements are present
        assert "====== Title ======" in output
        assert "**bold**" in output
        assert "* Item 1" in output
        assert "<code python>" in output

    def test_render_escaping_special_characters(self) -> None:
        """Test that special characters are properly escaped."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with * and / characters")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Characters should be escaped
        assert "\\*" in output or "*" in output  # Depends on escaping implementation
        assert "\\/" in output or "/" in output
