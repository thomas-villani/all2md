#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for MediaWiki renderer."""

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
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
from all2md.options import MediaWikiOptions
from all2md.renderers.mediawiki import MediaWikiRenderer


class TestMediaWikiRenderer:
    """Tests for MediaWiki renderer."""

    def test_render_simple_text(self) -> None:
        """Test rendering simple text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "Hello world" in output

    def test_render_heading_level_1(self) -> None:
        """Test rendering level 1 heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "= Title =" in output

    def test_render_heading_level_2(self) -> None:
        """Test rendering level 2 heading."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "== Section ==" in output

    def test_render_heading_level_3(self) -> None:
        """Test rendering level 3 heading."""
        doc = Document(children=[Heading(level=3, content=[Text(content="Subsection")])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "=== Subsection ===" in output

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text")]
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "'''bold'''" in output

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
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "''italic''" in output

    def test_render_bold_italic(self) -> None:
        """Test rendering bold and italic text."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "'''''bold italic'''''" in output

    def test_render_code_inline(self) -> None:
        """Test rendering inline code."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<code>code</code>" in output

    def test_render_code_block_with_language(self) -> None:
        """Test rendering code block with language."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("world")', language="python")])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert '<syntaxhighlight lang="python">' in output
        assert "def hello():" in output
        assert "</syntaxhighlight>" in output

    def test_render_code_block_without_language(self) -> None:
        """Test rendering code block without language."""
        doc = Document(children=[CodeBlock(content="code here")])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<pre>" in output
        assert "code here" in output
        assert "</pre>" in output

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
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "* Item 1" in output
        assert "* Item 2" in output
        assert "* Item 3" in output

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
                                    items=[ListItem(children=[Paragraph(content=[Text(content="Nested item")])])],
                                ),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "* Item 1" in output
        assert "** Nested item" in output

    def test_render_external_link(self) -> None:
        """Test rendering external link."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="Visit "), Link(url="https://example.com", content=[Text(content="Example")])]
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[https://example.com Example]" in output

    def test_render_external_link_auto(self) -> None:
        """Test rendering external link (auto-link)."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Visit "),
                        Link(url="https://example.com", content=[Text(content="https://example.com")]),
                    ]
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        # Auto-links should just output the URL
        assert "https://example.com" in output
        # Should not have the bracket syntax for auto-links
        lines = output.split("\n")
        assert any("Visit https://example.com" in line for line in lines)

    def test_render_internal_link(self) -> None:
        """Test rendering internal wiki link."""
        doc = Document(children=[Paragraph(content=[Link(url="Main Page", content=[Text(content="Home")])])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[Main Page|Home]]" in output

    def test_render_internal_link_simple(self) -> None:
        """Test rendering simple internal wiki link."""
        doc = Document(children=[Paragraph(content=[Link(url="Article", content=[Text(content="Article")])])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[Article]]" in output

    def test_render_image_with_thumb(self) -> None:
        """Test rendering image with thumbnail option."""
        doc = Document(children=[Paragraph(content=[Image(url="photo.jpg", alt_text="Photo description")])])
        renderer = MediaWikiRenderer(MediaWikiOptions(image_thumb=True))
        output = renderer.render_to_string(doc)

        assert "[[File:photo.jpg|thumb|alt=Photo description]]" in output

    def test_render_image_without_thumb(self) -> None:
        """Test rendering image without thumbnail option."""
        doc = Document(children=[Paragraph(content=[Image(url="photo.jpg", alt_text="Photo description")])])
        renderer = MediaWikiRenderer(MediaWikiOptions(image_thumb=False))
        output = renderer.render_to_string(doc)

        assert "[[File:photo.jpg|alt=Photo description]]" in output
        assert "thumb" not in output

    def test_render_thematic_break(self) -> None:
        """Test rendering thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "----" in output

    def test_render_block_quote(self) -> None:
        """Test rendering block quote."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="This is a quote")])])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert ": This is a quote" in output

    def test_render_strikethrough(self) -> None:
        """Test rendering strikethrough text."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<s>deleted</s>" in output

    def test_render_underline_with_html(self) -> None:
        """Test rendering underline with HTML fallback."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = MediaWikiRenderer(MediaWikiOptions(use_html_for_unsupported=True))
        output = renderer.render_to_string(doc)

        assert "<u>underlined</u>" in output

    def test_render_underline_without_html(self) -> None:
        """Test rendering underline without HTML fallback."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = MediaWikiRenderer(MediaWikiOptions(use_html_for_unsupported=False))
        output = renderer.render_to_string(doc)

        assert "underlined" in output
        assert "<u>" not in output

    def test_render_superscript(self) -> None:
        """Test rendering superscript."""
        doc = Document(children=[Paragraph(content=[Text(content="E=mc"), Superscript(content=[Text(content="2")])])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sup>2</sup>" in output

    def test_render_subscript(self) -> None:
        """Test rendering subscript."""
        doc = Document(
            children=[Paragraph(content=[Text(content="H"), Subscript(content=[Text(content="2")]), Text(content="O")])]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sub>2</sub>" in output

    def test_render_table_simple(self) -> None:
        """Test rendering simple table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Header 1")]),
                            TableCell(content=[Text(content="Header 2")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Cell 1")]),
                                TableCell(content=[Text(content="Cell 2")]),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert '{| class="wikitable"' in output
        assert "! Header 1 !! Header 2" in output
        assert "|-" in output
        assert "| Cell 1 || Cell 2" in output
        assert "|}" in output

    def test_render_table_with_caption(self) -> None:
        """Test rendering table with caption."""
        doc = Document(
            children=[
                Table(
                    caption="Table Caption",
                    header=TableRow(cells=[TableCell(content=[Text(content="Header")])]),
                    rows=[],
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "|+ Table Caption" in output

    def test_render_definition_list(self) -> None:
        """Test rendering definition list."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term 1")]),
                            [DefinitionDescription(content=[Paragraph(content=[Text(content="Definition 1")])])],
                        ),
                        (
                            DefinitionTerm(content=[Text(content="Term 2")]),
                            [DefinitionDescription(content=[Paragraph(content=[Text(content="Definition 2")])])],
                        ),
                    ]
                )
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "; Term 1" in output
        assert ": Definition 1" in output
        assert "; Term 2" in output
        assert ": Definition 2" in output

    def test_render_line_break_hard(self) -> None:
        """Test rendering hard line break."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=False), Text(content="Line 2")])]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<br />" in output

    def test_render_line_break_soft(self) -> None:
        """Test rendering soft line break."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=True), Text(content="Line 2")])]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        # Soft line breaks render as space in MediaWiki
        assert "Line 1 Line 2" in output

    def test_render_multiple_paragraphs(self) -> None:
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Paragraph 1")]),
                Paragraph(content=[Text(content="Paragraph 2")]),
                Paragraph(content=[Text(content="Paragraph 3")]),
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "Paragraph 1" in output
        assert "Paragraph 2" in output
        assert "Paragraph 3" in output
        # Paragraphs should be separated by blank lines
        assert "Paragraph 1\n\nParagraph 2" in output

    def test_render_complex_document(self) -> None:
        """Test rendering complex document with multiple elements."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Main Title")]),
                Paragraph(
                    content=[
                        Text(content="This is a paragraph with "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text."),
                    ]
                ),
                Heading(level=2, content=[Text(content="Section")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "= Main Title =" in output
        assert "'''bold'''" in output
        assert "''italic''" in output
        assert "== Section ==" in output
        assert "* Item 1" in output
        assert "* Item 2" in output

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        # Empty document should just be a newline
        assert output.strip() == ""

    def test_render_special_characters(self) -> None:
        """Test rendering text with special characters."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with * and _ and # characters")])])
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(doc)

        # MediaWiki is fairly lenient with special characters
        assert "Text with * and _ and # characters" in output
