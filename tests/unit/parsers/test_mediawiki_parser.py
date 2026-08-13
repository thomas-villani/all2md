#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for MediaWiki parser."""

from all2md.ast import Table
from all2md.parsers.mediawiki import MediaWikiParser
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer


class TestMediaWikiParserTables:
    """Tests for MediaWiki table parsing."""

    def test_parse_table_caption(self) -> None:
        """Test that |+ caption lines populate Table.caption."""
        wiki = """{|
|+ Cap
! Header
|-
| Cell
|}"""
        parser = MediaWikiParser()
        doc = parser.parse(wiki)

        assert len(doc.children) == 1
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.caption == "Cap"

        rendered = MediaWikiRenderer().render_to_string(doc)
        assert "|+ Cap" in rendered
        roundtrip = parser.parse(rendered)
        assert isinstance(roundtrip.children[0], Table)
        assert roundtrip.children[0].caption == "Cap"

    def test_parse_table_caption_strips_attributes(self) -> None:
        """|+ attrs | caption must keep caption text only, like cell attrs."""
        wiki = '{|\n|+ style="color:red" | Cap Title\n| a\n|}'
        doc = MediaWikiParser().parse(wiki)
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.caption == "Cap Title"

    def test_parse_table_caption_keeps_literal_pipe_without_attrs(self) -> None:
        """Caption text with a pipe but no key=value attrs must stay intact."""
        wiki = "{|\n|+ Cap with | pipe\n| a\n|}"
        doc = MediaWikiParser().parse(wiki)
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.caption == "Cap with | pipe"


class TestMediaWikiParserLists:
    """Tests for MediaWiki list parsing."""

    def test_keep_empty_unordered_list_item(self) -> None:
        """Bare '*' lines must keep an empty list item, not drop it."""
        parser = MediaWikiParser()
        doc = parser.parse("* \n* b\n")

        assert len(doc.children) == 1
        lst = doc.children[0]
        from all2md.ast import List, ListItem, Paragraph, Text

        assert isinstance(lst, List)
        assert lst.ordered is False
        assert len(lst.items) == 2
        assert isinstance(lst.items[0], ListItem)
        assert isinstance(lst.items[0].children[0], Paragraph)
        assert lst.items[0].children[0].content == []
        assert isinstance(lst.items[1].children[0].content[0], Text)
        assert lst.items[1].children[0].content[0].content == "b"

    def test_keep_empty_ordered_list_item(self) -> None:
        """Bare '#' lines must keep an empty ordered list item."""
        parser = MediaWikiParser()
        doc = parser.parse("# \n# b\n")

        from all2md.ast import List, Text

        assert len(doc.children) == 1
        lst = doc.children[0]
        assert isinstance(lst, List)
        assert lst.ordered is True
        assert len(lst.items) == 2
        assert lst.items[0].children[0].content == []
        assert isinstance(lst.items[1].children[0].content[0], Text)
        assert lst.items[1].children[0].content[0].content == "b"

    def test_text_after_list_is_not_dropped(self) -> None:
        """Paragraphs following a list must survive, not be swallowed by the last item.

        mwparserfromhell lumps everything up to the next markup construct into a single
        Text node, so the last list item's Text node also contains any trailing prose.
        """
        parser = MediaWikiParser()
        doc = parser.parse("* item one\n* item two\nParagraph after list.\n\nAnother para.")

        from all2md.ast import List, Paragraph, Text

        assert len(doc.children) == 3
        lst = doc.children[0]
        assert isinstance(lst, List)
        assert len(lst.items) == 2

        para1 = doc.children[1]
        assert isinstance(para1, Paragraph)
        assert isinstance(para1.content[0], Text)
        assert para1.content[0].content == "Paragraph after list."

        para2 = doc.children[2]
        assert isinstance(para2, Paragraph)
        assert isinstance(para2.content[0], Text)
        assert para2.content[0].content == "Another para."

    def test_list_with_no_trailing_text_emits_no_empty_paragraphs(self) -> None:
        """A list whose Text node ends exactly at the list must not add stray paragraphs."""
        parser = MediaWikiParser()
        doc = parser.parse("* item one\n* item two\n")

        from all2md.ast import List

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)


class TestMediaWikiParserBlockQuotes:
    """Tests for MediaWiki ':' block quote parsing."""

    def test_text_after_blockquote_is_not_dropped(self) -> None:
        """Paragraphs following a ':' block quote must survive, not be swallowed."""
        parser = MediaWikiParser()
        doc = parser.parse(": quoted line\nParagraph after quote.\n\nAnother para.")

        from all2md.ast import BlockQuote, Paragraph, Text

        assert len(doc.children) == 3
        quote = doc.children[0]
        assert isinstance(quote, BlockQuote)

        para1 = doc.children[1]
        assert isinstance(para1, Paragraph)
        assert isinstance(para1.content[0], Text)
        assert para1.content[0].content == "Paragraph after quote."

        para2 = doc.children[2]
        assert isinstance(para2, Paragraph)
        assert isinstance(para2.content[0], Text)
        assert para2.content[0].content == "Another para."

    def test_blockquote_with_no_trailing_text_emits_no_empty_paragraphs(self) -> None:
        """A ':' quote whose Text node ends exactly at the quote must add no stray paragraphs."""
        parser = MediaWikiParser()
        doc = parser.parse(": quoted line\n")

        from all2md.ast import BlockQuote

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)


class TestMediaWikiParserInlineWhitespace:
    """Tests that Text fragments around inline formatting keep a single separating space.

    mwparserfromhell splits a paragraph into one Text node per inline-markup boundary, so
    fully stripping each fragment fuses adjacent words together on render.
    """

    def test_bold_does_not_fuse_with_surrounding_words(self) -> None:
        """'''bold''' between two words must not swallow the spaces around it."""
        parser = MediaWikiParser()
        doc = parser.parse("This is '''bold''' text.")

        rendered = MarkdownRenderer().render_to_string(doc)
        assert rendered.strip() == "This is **bold** text."

    def test_italic_does_not_fuse_with_surrounding_words(self) -> None:
        """''italic'' between two words must not swallow the spaces around it."""
        parser = MediaWikiParser()
        doc = parser.parse("This is ''italic'' text.")

        rendered = MarkdownRenderer().render_to_string(doc)
        assert rendered.strip() == "This is *italic* text."

    def test_nested_formatting_keeps_separating_spaces(self) -> None:
        """A nested ''italic'' inside '''bold''' must not fuse with its bold neighbours."""
        parser = MediaWikiParser()
        doc = parser.parse("This has '''bold with ''nested italic'' inside''' text.")

        rendered = MarkdownRenderer().render_to_string(doc)
        assert rendered.strip() == "This has **bold with *nested italic* inside** text."

    def test_heading_title_has_no_stray_edge_whitespace(self) -> None:
        """A heading's title text must still be fully trimmed, not padded with edge spaces."""
        parser = MediaWikiParser()
        doc = parser.parse("== Heading ==")

        from all2md.ast import Heading, Text

        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Heading"

    def test_paragraph_has_no_stray_edge_whitespace(self) -> None:
        """A plain paragraph must not gain a leading/trailing space from a trailing newline."""
        parser = MediaWikiParser()
        doc = parser.parse("Hello world\n")

        from all2md.ast import Paragraph, Text

        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "Hello world"
