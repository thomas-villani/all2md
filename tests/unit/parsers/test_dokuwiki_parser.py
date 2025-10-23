#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for DokuWiki parser."""

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options.dokuwiki import DokuWikiParserOptions
from all2md.parsers.dokuwiki import DokuWikiParser


class TestDokuWikiParserBasics:
    """Tests for basic DokuWiki parser functionality."""

    def test_parse_simple_text(self) -> None:
        """Test parsing simple text."""
        parser = DokuWikiParser()
        doc = parser.parse("Hello world")

        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "Hello world"

    def test_parse_multiple_paragraphs(self) -> None:
        """Test parsing multiple paragraphs separated by blank lines."""
        parser = DokuWikiParser()
        doc = parser.parse("First paragraph\n\nSecond paragraph")

        assert len(doc.children) == 2
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], Paragraph)

    def test_parse_empty_document(self) -> None:
        """Test parsing empty document."""
        parser = DokuWikiParser()
        doc = parser.parse("")

        assert len(doc.children) == 0


class TestDokuWikiParserHeadings:
    """Tests for DokuWiki heading parsing."""

    def test_parse_heading_level_1(self) -> None:
        """Test parsing level 1 heading (6 equals)."""
        parser = DokuWikiParser()
        doc = parser.parse("====== Heading ======")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 1
        assert len(heading.content) == 1
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Heading"

    def test_parse_heading_level_2(self) -> None:
        """Test parsing level 2 heading (5 equals)."""
        parser = DokuWikiParser()
        doc = parser.parse("===== Heading =====")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 2

    def test_parse_heading_level_3(self) -> None:
        """Test parsing level 3 heading (4 equals)."""
        parser = DokuWikiParser()
        doc = parser.parse("==== Heading ====")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 3

    def test_parse_heading_level_4(self) -> None:
        """Test parsing level 4 heading (3 equals)."""
        parser = DokuWikiParser()
        doc = parser.parse("=== Heading ===")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 4

    def test_parse_heading_level_5(self) -> None:
        """Test parsing level 5 heading (2 equals)."""
        parser = DokuWikiParser()
        doc = parser.parse("== Heading ==")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 5

    def test_parse_heading_with_formatting(self) -> None:
        """Test parsing heading with inline formatting."""
        parser = DokuWikiParser()
        doc = parser.parse("====== **Bold** Heading ======")

        assert len(doc.children) == 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        # Check for Strong node in content
        has_strong = any(isinstance(node, Strong) for node in heading.content)
        assert has_strong


class TestDokuWikiParserInlineFormatting:
    """Tests for DokuWiki inline formatting parsing."""

    def test_parse_bold(self) -> None:
        """Test parsing bold text."""
        parser = DokuWikiParser()
        doc = parser.parse("This is **bold** text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Strong node
        strong_node = next((node for node in para.content if isinstance(node, Strong)), None)
        assert strong_node is not None
        assert isinstance(strong_node.content[0], Text)
        assert strong_node.content[0].content == "bold"

    def test_parse_italic(self) -> None:
        """Test parsing italic text."""
        parser = DokuWikiParser()
        doc = parser.parse("This is //italic// text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Emphasis node
        emphasis_node = next((node for node in para.content if isinstance(node, Emphasis)), None)
        assert emphasis_node is not None
        assert isinstance(emphasis_node.content[0], Text)
        assert emphasis_node.content[0].content == "italic"

    def test_parse_underline(self) -> None:
        """Test parsing underlined text."""
        parser = DokuWikiParser()
        doc = parser.parse("This is __underlined__ text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Underline node
        underline_node = next((node for node in para.content if isinstance(node, Underline)), None)
        assert underline_node is not None
        assert isinstance(underline_node.content[0], Text)
        assert underline_node.content[0].content == "underlined"

    def test_parse_monospace(self) -> None:
        """Test parsing monospace text."""
        parser = DokuWikiParser()
        doc = parser.parse("This is ''monospace'' text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Code node
        code_node = next((node for node in para.content if isinstance(node, Code)), None)
        assert code_node is not None
        assert code_node.content == "monospace"

    def test_parse_strikethrough(self) -> None:
        """Test parsing strikethrough text."""
        parser = DokuWikiParser()
        doc = parser.parse("This is <del>strikethrough</del> text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Strikethrough node
        strike_node = next((node for node in para.content if isinstance(node, Strikethrough)), None)
        assert strike_node is not None

    def test_parse_subscript(self) -> None:
        """Test parsing subscript text."""
        parser = DokuWikiParser()
        doc = parser.parse("H<sub>2</sub>O")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Subscript node
        sub_node = next((node for node in para.content if isinstance(node, Subscript)), None)
        assert sub_node is not None

    def test_parse_superscript(self) -> None:
        """Test parsing superscript text."""
        parser = DokuWikiParser()
        doc = parser.parse("E=mc<sup>2</sup>")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find Superscript node
        sup_node = next((node for node in para.content if isinstance(node, Superscript)), None)
        assert sup_node is not None

    def test_parse_nested_formatting(self) -> None:
        """Test parsing nested inline formatting."""
        parser = DokuWikiParser()
        doc = parser.parse("**//bold italic//**")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Should have Strong containing Emphasis
        strong_node = next((node for node in para.content if isinstance(node, Strong)), None)
        assert strong_node is not None
        # Check for nested Emphasis
        has_emphasis = any(isinstance(node, Emphasis) for node in strong_node.content)
        assert has_emphasis


class TestDokuWikiParserLinks:
    """Tests for DokuWiki link parsing."""

    def test_parse_simple_link(self) -> None:
        """Test parsing simple link without text."""
        parser = DokuWikiParser()
        doc = parser.parse("[[page:name]]")

        para = doc.children[0]
        link = next((node for node in para.content if isinstance(node, Link)), None)
        assert link is not None
        assert link.url == "page:name"

    def test_parse_link_with_text(self) -> None:
        """Test parsing link with custom text."""
        parser = DokuWikiParser()
        doc = parser.parse("[[page:name|Link Text]]")

        para = doc.children[0]
        link = next((node for node in para.content if isinstance(node, Link)), None)
        assert link is not None
        assert link.url == "page:name"
        # Check link text
        assert len(link.content) > 0

    def test_parse_external_link(self) -> None:
        """Test parsing external link."""
        parser = DokuWikiParser()
        doc = parser.parse("[[http://example.com|Example]]")

        para = doc.children[0]
        link = next((node for node in para.content if isinstance(node, Link)), None)
        assert link is not None
        assert "http://example.com" in link.url

    def test_parse_interwiki_link(self) -> None:
        """Test parsing interwiki link."""
        parser = DokuWikiParser()
        doc = parser.parse("[[wp>Article]]")

        para = doc.children[0]
        link = next((node for node in para.content if isinstance(node, Link)), None)
        assert link is not None
        assert "wp>Article" in link.url


class TestDokuWikiParserImages:
    """Tests for DokuWiki image parsing."""

    def test_parse_simple_image(self) -> None:
        """Test parsing simple image without alt text."""
        parser = DokuWikiParser()
        doc = parser.parse("{{image.png}}")

        para = doc.children[0]
        image = next((node for node in para.content if isinstance(node, Image)), None)
        assert image is not None
        assert image.url == "image.png"

    def test_parse_image_with_alt_text(self) -> None:
        """Test parsing image with alt text."""
        parser = DokuWikiParser()
        doc = parser.parse("{{image.png|Alt Text}}")

        para = doc.children[0]
        image = next((node for node in para.content if isinstance(node, Image)), None)
        assert image is not None
        assert image.url == "image.png"
        assert image.alt_text == "Alt Text"


class TestDokuWikiParserLists:
    """Tests for DokuWiki list parsing."""

    def test_parse_unordered_list(self) -> None:
        """Test parsing unordered list."""
        parser = DokuWikiParser()
        doc = parser.parse("* Item 1\n* Item 2\n* Item 3")

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert not list_node.ordered
        assert len(list_node.items) == 3

    def test_parse_ordered_list(self) -> None:
        """Test parsing ordered list."""
        parser = DokuWikiParser()
        doc = parser.parse("- Item 1\n- Item 2\n- Item 3")

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered
        assert len(list_node.items) == 3

    def test_parse_nested_list(self) -> None:
        """Test parsing nested list."""
        parser = DokuWikiParser()
        doc = parser.parse("* Item 1\n  * Nested item\n* Item 2")

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        # Check for nested list in first item
        first_item = list_node.items[0]
        # Should have more than just a paragraph
        assert len(first_item.children) >= 1


class TestDokuWikiParserTables:
    """Tests for DokuWiki table parsing."""

    def test_parse_simple_table(self) -> None:
        """Test parsing simple table."""
        parser = DokuWikiParser()
        doc = parser.parse("^ Header 1 ^ Header 2 ^\n| Cell 1 | Cell 2 |")

        assert len(doc.children) == 1
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is not None
        assert len(table.rows) >= 1

    def test_parse_table_without_header(self) -> None:
        """Test parsing table without header row."""
        parser = DokuWikiParser()
        doc = parser.parse("| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |")

        assert len(doc.children) == 1
        table = doc.children[0]
        assert isinstance(table, Table)
        assert len(table.rows) == 2


class TestDokuWikiParserCodeBlocks:
    """Tests for DokuWiki code block parsing."""

    def test_parse_code_block_without_language(self) -> None:
        """Test parsing code block without language."""
        parser = DokuWikiParser()
        doc = parser.parse("<code>\ncode here\n</code>")

        assert len(doc.children) == 1
        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "code here" in code_block.content
        assert code_block.language is None

    def test_parse_code_block_with_language(self) -> None:
        """Test parsing code block with language."""
        parser = DokuWikiParser()
        doc = parser.parse("<code python>\ndef hello():\n    pass\n</code>")

        assert len(doc.children) == 1
        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "def hello()" in code_block.content
        assert code_block.language == "python"


class TestDokuWikiParserBlockQuotes:
    """Tests for DokuWiki blockquote parsing."""

    def test_parse_single_line_blockquote(self) -> None:
        """Test parsing single-line blockquote."""
        parser = DokuWikiParser()
        doc = parser.parse("> Quoted text")

        assert len(doc.children) == 1
        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert len(blockquote.children) >= 1

    def test_parse_multi_line_blockquote(self) -> None:
        """Test parsing multi-line blockquote."""
        parser = DokuWikiParser()
        doc = parser.parse("> Line 1\n> Line 2\n> Line 3")

        assert len(doc.children) == 1
        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)


class TestDokuWikiParserMiscellaneous:
    """Tests for miscellaneous DokuWiki parsing."""

    def test_parse_thematic_break(self) -> None:
        """Test parsing thematic break (horizontal rule)."""
        parser = DokuWikiParser()
        doc = parser.parse("----")

        assert len(doc.children) == 1
        hr = doc.children[0]
        assert isinstance(hr, ThematicBreak)

    def test_parse_line_break(self) -> None:
        """Test parsing hard line break."""
        parser = DokuWikiParser()
        doc = parser.parse("Line 1\\\\Line 2")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find LineBreak node
        linebreak = next((node for node in para.content if isinstance(node, LineBreak)), None)
        assert linebreak is not None
        assert not linebreak.soft

    def test_parse_footnote(self) -> None:
        """Test parsing footnote."""
        parser = DokuWikiParser()
        doc = parser.parse("Text with ((footnote)) reference")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Find FootnoteReference node
        footnote = next((node for node in para.content if isinstance(node, FootnoteReference)), None)
        assert footnote is not None


class TestDokuWikiParserFootnotes:
    """Tests for DokuWiki footnote parsing with FootnoteDefinition support."""

    def test_footnote_creates_reference_and_definition(self) -> None:
        """Test that footnotes create both reference and definition nodes."""
        parser = DokuWikiParser()
        doc = parser.parse("Text with ((footnote text)) reference")

        # Check for FootnoteReference in paragraph
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        footnote_ref = next((node for node in para.content if isinstance(node, FootnoteReference)), None)
        assert footnote_ref is not None
        assert footnote_ref.identifier

        # Check for FootnoteDefinition at end of document
        footnote_defs = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnote_defs) == 1
        assert footnote_defs[0].identifier == footnote_ref.identifier
        # Check that definition contains the footnote text
        assert len(footnote_defs[0].content) > 0

    def test_multiple_footnotes(self) -> None:
        """Test parsing multiple footnotes creates multiple definitions."""
        parser = DokuWikiParser()
        doc = parser.parse("First ((footnote one)) and second ((footnote two)) references")

        # Find all footnote references
        para = doc.children[0]
        footnote_refs = [node for node in para.content if isinstance(node, FootnoteReference)]
        assert len(footnote_refs) == 2

        # Find all footnote definitions
        footnote_defs = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnote_defs) == 2

        # Verify identifiers match
        ref_ids = {ref.identifier for ref in footnote_refs}
        def_ids = {defn.identifier for defn in footnote_defs}
        assert ref_ids == def_ids

    def test_duplicate_footnotes_share_definition(self) -> None:
        """Test that duplicate footnote text shares the same definition."""
        parser = DokuWikiParser()
        doc = parser.parse("First ((same text)) and second ((same text)) references")

        # Find all footnote references
        para = doc.children[0]
        footnote_refs = [node for node in para.content if isinstance(node, FootnoteReference)]
        assert len(footnote_refs) == 2

        # Both references should have the same identifier
        assert footnote_refs[0].identifier == footnote_refs[1].identifier

        # Should only have one definition
        footnote_defs = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnote_defs) == 1

    def test_footnote_with_formatting(self) -> None:
        """Test footnote with inline formatting in content."""
        parser = DokuWikiParser()
        doc = parser.parse("Text ((footnote with **bold** text)) reference")

        # Find footnote definition
        footnote_defs = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnote_defs) == 1

        # Check that definition content has formatting
        # The definition should have a Paragraph containing Strong node
        defn = footnote_defs[0]
        assert len(defn.content) > 0
        para = defn.content[0]
        assert isinstance(para, Paragraph)
        # Look for Strong node in paragraph content
        has_strong = any(isinstance(node, Strong) for node in para.content)
        assert has_strong

    def test_footnote_in_complex_document(self) -> None:
        """Test footnotes in a complex document with multiple elements."""
        content = """====== Title ======

This paragraph has ((first footnote)) reference.

Another paragraph with ((second footnote)) here.

* List item with ((third footnote)) reference
* Another item

^ Header 1 ^
| Cell with ((fourth footnote)) |"""

        parser = DokuWikiParser()
        doc = parser.parse(content)

        # Find all footnote references
        all_refs = []
        for child in doc.children:
            if isinstance(child, Paragraph):
                all_refs.extend([node for node in child.content if isinstance(node, FootnoteReference)])
            elif isinstance(child, List):
                for item in child.items:
                    for item_child in item.children:
                        if isinstance(item_child, Paragraph):
                            all_refs.extend(
                                [node for node in item_child.content if isinstance(node, FootnoteReference)]
                            )
            elif isinstance(child, Table):
                for row in child.rows:
                    for cell in row.cells:
                        all_refs.extend([node for node in cell.content if isinstance(node, FootnoteReference)])

        assert len(all_refs) >= 3  # At least the paragraph footnotes

        # Find all footnote definitions
        footnote_defs = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnote_defs) >= 3  # At least the paragraph footnotes


class TestDokuWikiParserOptions:
    """Tests for DokuWiki parser options."""

    def test_strip_comments_option(self) -> None:
        """Test strip_comments option."""
        parser = DokuWikiParser(DokuWikiParserOptions(strip_comments=True))
        doc = parser.parse("Text /* comment */ more text")

        # Comments should be removed
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Check that comment is not in content
        full_text = "".join(node.content for node in para.content if isinstance(node, Text))
        assert "comment" not in full_text

    def test_parse_interwiki_disabled(self) -> None:
        """Test parse_interwiki option disabled."""
        parser = DokuWikiParser(DokuWikiParserOptions(parse_interwiki=False))
        doc = parser.parse("[[wp>Article]]")

        # Should still parse as link, but interwiki handling is different
        para = doc.children[0]
        link = next((node for node in para.content if isinstance(node, Link)), None)
        assert link is not None


class TestDokuWikiParserComplexDocuments:
    """Tests for parsing complex DokuWiki documents."""

    def test_parse_mixed_content(self) -> None:
        """Test parsing document with mixed content types."""
        content = """====== Main Title ======

This is a paragraph with **bold** and //italic// text.

===== Section =====

* List item 1
* List item 2

^ Header 1 ^ Header 2 ^
| Cell 1 | Cell 2 |

<code python>
def example():
    pass
</code>

> Quoted text

----"""

        parser = DokuWikiParser()
        doc = parser.parse(content)

        # Should have multiple children of different types
        assert len(doc.children) > 5
        # Check for variety of node types
        node_types = {type(child).__name__ for child in doc.children}
        assert "Heading" in node_types
        assert "Paragraph" in node_types
        assert "List" in node_types or "Table" in node_types
