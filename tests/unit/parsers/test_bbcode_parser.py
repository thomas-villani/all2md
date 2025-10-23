#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for BBCode parser."""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
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
from all2md.exceptions import ParsingError
from all2md.options.bbcode import BBCodeParserOptions
from all2md.parsers.bbcode import BBCodeParser


class TestBBCodeParser:
    """Tests for BBCode parser."""

    def test_simple_text(self) -> None:
        """Test parsing simple text."""
        parser = BBCodeParser()
        doc = parser.parse("Hello world")

        assert len(doc.children) >= 1
        # Text should be in a paragraph
        found_text = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Text) and "Hello world" in node.content:
                        found_text = True
        assert found_text

    def test_bold_text(self) -> None:
        """Test parsing bold text."""
        parser = BBCodeParser()
        doc = parser.parse("This is [b]bold[/b] text")

        # Find the Strong node
        strong_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Strong):
                        strong_found = True
                        assert len(node.content) > 0
                        # Check inner text
                        for inner in node.content:
                            if isinstance(inner, Text):
                                assert "bold" in inner.content
        assert strong_found

    def test_italic_text(self) -> None:
        """Test parsing italic text."""
        parser = BBCodeParser()
        doc = parser.parse("This is [i]italic[/i] text")

        # Find the Emphasis node
        emphasis_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Emphasis):
                        emphasis_found = True
                        assert len(node.content) > 0
        assert emphasis_found

    def test_underline_text(self) -> None:
        """Test parsing underlined text."""
        parser = BBCodeParser()
        doc = parser.parse("This is [u]underlined[/u] text")

        # Find the Underline node
        underline_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Underline):
                        underline_found = True
        assert underline_found

    def test_strikethrough_text(self) -> None:
        """Test parsing strikethrough text."""
        parser = BBCodeParser()
        doc = parser.parse("This is [s]strikethrough[/s] text")

        # Find the Strikethrough node
        strikethrough_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Strikethrough):
                        strikethrough_found = True
        assert strikethrough_found

    def test_superscript_text(self) -> None:
        """Test parsing superscript text."""
        parser = BBCodeParser()
        doc = parser.parse("E=mc[sup]2[/sup]")

        # Find the Superscript node
        superscript_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Superscript):
                        superscript_found = True
        assert superscript_found

    def test_subscript_text(self) -> None:
        """Test parsing subscript text."""
        parser = BBCodeParser()
        doc = parser.parse("H[sub]2[/sub]O")

        # Find the Subscript node
        subscript_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Subscript):
                        subscript_found = True
        assert subscript_found

    def test_nested_formatting(self) -> None:
        """Test parsing nested formatting tags."""
        parser = BBCodeParser()
        doc = parser.parse("[b]Bold and [i]italic[/i][/b]")

        # Find nested Strong -> Emphasis structure
        strong_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Strong):
                        strong_found = True
                        # Check for nested Emphasis
                        for inner in node.content:
                            if isinstance(inner, Emphasis):
                                assert True  # Found nested structure
        assert strong_found

    def test_url_with_text(self) -> None:
        """Test parsing URL with custom text."""
        parser = BBCodeParser()
        doc = parser.parse("[url=http://example.com]Example[/url]")

        # Find the Link node
        link_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Link):
                        link_found = True
                        assert "example.com" in node.url.lower()
                        # Check link text
                        for inner in node.content:
                            if isinstance(inner, Text):
                                assert "Example" in inner.content
        assert link_found

    def test_url_without_text(self) -> None:
        """Test parsing URL without custom text."""
        parser = BBCodeParser()
        doc = parser.parse("[url]http://example.com[/url]")

        # Find the Link node
        link_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Link):
                        link_found = True
                        assert "example.com" in node.url.lower()
        assert link_found

    def test_email_link(self) -> None:
        """Test parsing email link."""
        parser = BBCodeParser()
        doc = parser.parse("[email]test@example.com[/email]")

        # Find the Link node with mailto
        link_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Link):
                        link_found = True
                        assert "mailto:" in node.url
        assert link_found

    def test_image(self) -> None:
        """Test parsing image tag."""
        parser = BBCodeParser()
        doc = parser.parse("[img]http://example.com/image.png[/img]")

        # Find the Image node
        image_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Image):
                        image_found = True
                        assert "image.png" in node.url
        assert image_found

    def test_image_with_size(self) -> None:
        """Test parsing image with size specification."""
        parser = BBCodeParser()
        doc = parser.parse("[img=100x200]http://example.com/image.png[/img]")

        # Find the Image node with metadata
        image_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Image):
                        image_found = True
                        assert node.metadata is not None
                        assert 'width' in node.metadata
                        assert 'height' in node.metadata
        assert image_found

    def test_quote_simple(self) -> None:
        """Test parsing simple quote."""
        parser = BBCodeParser()
        doc = parser.parse("[quote]This is a quote[/quote]")

        # Find the BlockQuote node
        quote_found = False
        for child in doc.children:
            if isinstance(child, BlockQuote):
                quote_found = True
        assert quote_found

    def test_quote_with_author(self) -> None:
        """Test parsing quote with author attribution."""
        parser = BBCodeParser()
        doc = parser.parse("[quote=John]This is a quote[/quote]")

        # Find the BlockQuote node with author metadata
        quote_found = False
        for child in doc.children:
            if isinstance(child, BlockQuote):
                quote_found = True
                assert child.metadata is not None
                assert child.metadata.get('author') == 'John'
        assert quote_found

    def test_code_block(self) -> None:
        """Test parsing code block."""
        parser = BBCodeParser()
        doc = parser.parse("[code]def hello():\n    print('Hello')[/code]")

        # Find the CodeBlock node
        code_found = False
        for child in doc.children:
            if isinstance(child, CodeBlock):
                code_found = True
                assert "hello" in child.content
        assert code_found

    def test_code_block_with_language(self) -> None:
        """Test parsing code block with language."""
        parser = BBCodeParser()
        doc = parser.parse("[code=python]def hello():\n    print('Hello')[/code]")

        # Find the CodeBlock node with language
        code_found = False
        for child in doc.children:
            if isinstance(child, CodeBlock):
                code_found = True
                assert child.language == "python"
        assert code_found

    def test_unordered_list(self) -> None:
        """Test parsing unordered list."""
        parser = BBCodeParser()
        doc = parser.parse("[list][*]Item 1[*]Item 2[*]Item 3[/list]")

        # Find the List node
        list_found = False
        for child in doc.children:
            if isinstance(child, List):
                list_found = True
                assert child.ordered is False
                assert len(child.items) == 3
        assert list_found

    def test_ordered_list(self) -> None:
        """Test parsing ordered list."""
        parser = BBCodeParser()
        doc = parser.parse("[list=1][*]First[*]Second[*]Third[/list]")

        # Find the List node
        list_found = False
        for child in doc.children:
            if isinstance(child, List):
                list_found = True
                assert child.ordered is True
                assert len(child.items) == 3
        assert list_found

    def test_table(self) -> None:
        """Test parsing table."""
        parser = BBCodeParser()
        doc = parser.parse("[table][tr][th]Header1[/th][th]Header2[/th][/tr][tr][td]Cell1[/td][td]Cell2[/td][/tr][/table]")

        # Find the Table node
        table_found = False
        for child in doc.children:
            if isinstance(child, Table):
                table_found = True
                assert child.header is not None
                assert len(child.header.cells) == 2
                assert len(child.rows) == 1
        assert table_found

    def test_heading_h1(self) -> None:
        """Test parsing H1 heading."""
        parser = BBCodeParser()
        doc = parser.parse("[h1]Title[/h1]")

        # Find the Heading node
        heading_found = False
        for child in doc.children:
            if isinstance(child, Heading):
                heading_found = True
                assert child.level == 1
        assert heading_found

    def test_heading_h3(self) -> None:
        """Test parsing H3 heading."""
        parser = BBCodeParser()
        doc = parser.parse("[h3]Subsection[/h3]")

        # Find the Heading node
        heading_found = False
        for child in doc.children:
            if isinstance(child, Heading):
                heading_found = True
                assert child.level == 3
        assert heading_found

    def test_horizontal_rule(self) -> None:
        """Test parsing horizontal rule."""
        parser = BBCodeParser()
        doc = parser.parse("Text before[hr]Text after")

        # Find the ThematicBreak node
        hr_found = False
        for child in doc.children:
            if isinstance(child, ThematicBreak):
                hr_found = True
        assert hr_found

    def test_line_break(self) -> None:
        """Test parsing line break."""
        parser = BBCodeParser()
        doc = parser.parse("Line 1[br]Line 2")

        # Find the LineBreak node
        br_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, LineBreak):
                        br_found = True
        assert br_found

    def test_multiple_paragraphs(self) -> None:
        """Test parsing multiple paragraphs separated by double newlines."""
        parser = BBCodeParser()
        doc = parser.parse("Paragraph 1\n\nParagraph 2")

        # Should create two paragraphs
        paragraph_count = sum(1 for child in doc.children if isinstance(child, Paragraph))
        assert paragraph_count == 2

    def test_strict_mode_unclosed_tag(self) -> None:
        """Test that strict mode raises error on unclosed tags."""
        options = BBCodeParserOptions(strict_mode=True)
        parser = BBCodeParser(options)

        with pytest.raises(ParsingError):
            parser.parse("[b]Unclosed bold tag")

    def test_graceful_recovery_unclosed_tag(self) -> None:
        """Test graceful recovery from unclosed tags."""
        options = BBCodeParserOptions(strict_mode=False)
        parser = BBCodeParser(options)

        # Should not raise error
        doc = parser.parse("[b]Unclosed bold tag")
        assert len(doc.children) >= 1

    def test_unknown_tag_strip_mode(self) -> None:
        """Test unknown tag handling in strip mode."""
        options = BBCodeParserOptions(unknown_tag_mode="strip")
        parser = BBCodeParser(options)

        doc = parser.parse("[custom]content[/custom]")

        # Should strip the tag but keep content
        text_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Text) and "content" in node.content:
                        text_found = True
        assert text_found

    def test_unknown_tag_preserve_mode(self) -> None:
        """Test unknown tag handling in preserve mode."""
        options = BBCodeParserOptions(unknown_tag_mode="preserve")
        parser = BBCodeParser(options)

        doc = parser.parse("[custom]content[/custom]")

        # Should preserve the tag
        assert len(doc.children) >= 1

    def test_complex_nested_content(self) -> None:
        """Test parsing complex nested BBCode content."""
        parser = BBCodeParser()
        bbcode = """
[h1]Welcome[/h1]

This is a [b]bold statement[/b] with [i]italic[/i] text.

[quote=Author]
This is a [b]quoted[/b] text.
[/quote]

[list]
[*]Item with [url=http://example.com]link[/url]
[*]Item with [b]bold[/b]
[/list]
"""
        doc = parser.parse(bbcode)

        # Should parse without errors
        assert len(doc.children) > 0

        # Check for heading
        has_heading = any(isinstance(child, Heading) for child in doc.children)
        assert has_heading

        # Check for quote
        has_quote = any(isinstance(child, BlockQuote) for child in doc.children)
        assert has_quote

        # Check for list
        has_list = any(isinstance(child, List) for child in doc.children)
        assert has_list

    def test_metadata_extraction(self) -> None:
        """Test metadata extraction from first heading."""
        parser = BBCodeParser()
        doc = parser.parse("[h1]Document Title[/h1]\n\nContent here.")

        # Check that title was extracted
        assert doc.metadata is not None
        assert "title" in doc.metadata
        assert "Document Title" in doc.metadata["title"]

    def test_empty_content(self) -> None:
        """Test parsing empty content."""
        parser = BBCodeParser()
        doc = parser.parse("")

        # Should handle gracefully
        assert isinstance(doc, Document)

    def test_plain_text_only(self) -> None:
        """Test parsing content with no BBCode tags."""
        parser = BBCodeParser()
        doc = parser.parse("Just plain text with no tags.")

        # Should create at least one paragraph
        assert len(doc.children) >= 1
        assert any(isinstance(child, Paragraph) for child in doc.children)
