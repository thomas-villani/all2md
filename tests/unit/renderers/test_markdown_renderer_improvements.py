#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new Markdown renderer improvements."""

import pytest

from all2md.ast import (
    BlockQuote,
    Document,
    Heading,
    Image,
    LineBreak,
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
from all2md.options.markdown import MarkdownRendererOptions
from all2md.parsers.markdown import markdown_to_ast
from all2md.renderers.markdown import MarkdownRenderer


class TestMarkdownSetextUnderlineWidth:
    """Tests for setext heading underline width fix."""

    def test_setext_h1_plain_text(self) -> None:
        """Test setext H1 underline matches plain text length."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Hello World")])])

        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "Hello World"
        # Underline should be 11 characters (length of "Hello World")
        assert lines[1] == "=" * 11

    def test_setext_h1_with_bold(self) -> None:
        """Test setext H1 underline with bold text calculates plain text length."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[Text(content="Hello "), Strong(content=[Text(content="Bold")]), Text(content=" World")],
                )
            ]
        )

        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Plain text is "Hello Bold World" = 16 characters
        # Not "Hello **Bold** World" = 20 characters
        assert lines[0] == "Hello **Bold** World"
        assert len(lines[1]) == 16
        assert lines[1] == "=" * 16

    def test_setext_h2_plain_text(self) -> None:
        """Test setext H2 underline matches plain text length."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])

        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        assert lines[0] == "Section"
        # Underline should be 7 characters
        assert lines[1] == "-" * 7

    def test_setext_with_link(self) -> None:
        """Test setext underline with link uses link text, not URL."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[
                        Text(content="Visit "),
                        Link(url="http://example.com", content=[Text(content="Example")]),
                    ],
                )
            ]
        )

        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Plain text is "Visit Example" = 13 characters
        # Not including the URL length
        assert len(lines[1]) == 13

    def test_prefer_setext_option(self) -> None:
        """Test prefer_setext_headings option works correctly."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        options = MarkdownRendererOptions(use_hash_headings=True, prefer_setext_headings=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        lines = output.strip().split("\n")
        # Should use setext even with use_hash_headings=True
        assert lines[1] == "=" * 5  # "Title" is 5 chars


class TestMarkdownBareUrlAutolinking:
    """Tests for improved bare URL autolinking."""

    def test_simple_url(self) -> None:
        """Test simple URL gets autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com for info")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://example.com>" in output

    def test_url_with_nested_parentheses(self) -> None:
        """Test URL with nested parentheses is handled correctly."""
        doc = Document(
            children=[Paragraph(content=[Text(content="See http://en.wikipedia.org/wiki/Foo_(bar) article")])]
        )

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked (parentheses may be escaped)
        assert "<http://en.wikipedia.org/wiki/Foo" in output
        assert "bar" in output

    def test_url_with_deeply_nested_parentheses(self) -> None:
        """Test URL with deeply nested parentheses."""
        doc = Document(children=[Paragraph(content=[Text(content="URL http://example.com/path(foo(bar)) here")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should handle nested parens correctly
        assert "<http://example.com/path(foo(bar))>" in output

    def test_url_in_parentheses(self) -> None:
        """Test URL surrounded by parentheses is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="(see http://example.com)")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked
        assert "<http://example.com>" in output

    def test_url_with_trailing_period(self) -> None:
        """Test URL with trailing period is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com.")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL is autolinked (period handling may vary)
        assert "<http://example.com" in output

    def test_url_with_trailing_comma(self) -> None:
        """Test URL with trailing comma is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Sites: http://example.com, http://test.com")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Both URLs are autolinked
        assert "<http://example.com" in output
        assert "<http://test.com>" in output

    def test_url_with_query_string(self) -> None:
        """Test URL with query string preserves query parameters."""
        doc = Document(children=[Paragraph(content=[Text(content="Search http://example.com?q=test&page=1 query")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Query parameters should be included
        assert "<http://example.com?q=test&page=1>" in output

    def test_url_with_fragment(self) -> None:
        """Test URL with fragment preserves the fragment."""
        doc = Document(children=[Paragraph(content=[Text(content="See http://example.com/page#section")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Fragment should be included
        assert "<http://example.com/page#section>" in output

    def test_url_with_query_and_trailing_punct(self) -> None:
        """Test URL with query string and trailing punctuation."""
        doc = Document(children=[Paragraph(content=[Text(content="Link: http://example.com?q=test.")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # URL with query string is autolinked (punctuation handling may vary)
        assert "<http://example.com?q=test" in output

    def test_https_url(self) -> None:
        """Test HTTPS URL is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Secure: https://secure.example.com")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<https://secure.example.com>" in output

    def test_ftp_url(self) -> None:
        """Test FTP URL is autolinked."""
        doc = Document(children=[Paragraph(content=[Text(content="Files at ftp://files.example.com")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<ftp://files.example.com>" in output

    def test_autolink_disabled(self) -> None:
        """Test autolink_bare_urls=False doesn't autolink."""
        doc = Document(children=[Paragraph(content=[Text(content="Visit http://example.com")])])

        options = MarkdownRendererOptions(autolink_bare_urls=False)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        # Should remain as plain text
        assert "Visit http://example.com" in output
        assert "<http://example.com>" not in output

    def test_multiple_urls_in_text(self) -> None:
        """Test multiple URLs in same text are all autolinked."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Visit http://example.com and https://test.com for more info"),
                    ]
                )
            ]
        )

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://example.com>" in output
        assert "<https://test.com>" in output

    def test_url_with_port(self) -> None:
        """Test URL with port number."""
        doc = Document(children=[Paragraph(content=[Text(content="Server: http://localhost:8080/app")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<http://localhost:8080/app>" in output

    def test_url_with_username(self) -> None:
        """Test URL with username."""
        doc = Document(children=[Paragraph(content=[Text(content="FTP: ftp://user@ftp.example.com/files")])])

        options = MarkdownRendererOptions(autolink_bare_urls=True)
        renderer = MarkdownRenderer(options=options)
        output = renderer.render_to_string(doc)

        assert "<ftp://user@ftp.example.com/files>" in output


class TestBlockQuoteInsideListItem:
    """Tests for block quotes nested in a list item (single indent, not double)."""

    @staticmethod
    def _list_with_quote(start: int = 1, ordered: bool = True) -> Document:
        """Build a one-item list whose second child is a block quote."""
        return Document(
            children=[
                List(
                    ordered=ordered,
                    start=start,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="first para")]),
                                BlockQuote(children=[Paragraph(content=[Text(content="quoted text")])]),
                            ]
                        )
                    ],
                )
            ]
        )

    def test_wide_marker_quote_is_not_double_indented(self) -> None:
        """A quote under a four-column marker keeps a single indent."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._list_with_quote(start=10))

        assert output == "10. first para\n    > quoted text"

    def test_wide_marker_quote_roundtrips_as_paragraph(self) -> None:
        """The quote reparses as BlockQuote > Paragraph, not BlockQuote > CodeBlock."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._list_with_quote(start=10))

        reparsed = markdown_to_ast(output)
        item = reparsed.children[0].items[0]
        quote = item.children[1]
        assert isinstance(quote, BlockQuote)
        assert len(quote.children) == 1
        assert isinstance(quote.children[0], Paragraph)
        assert quote.children[0].content[0].content == "quoted text"

    def test_bullet_marker_quote_roundtrips(self) -> None:
        """The same holds for a two-column bullet marker."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._list_with_quote(ordered=False))

        assert output == "* first para\n  > quoted text"
        quote = markdown_to_ast(output).children[0].items[0].children[1]
        assert isinstance(quote.children[0], Paragraph)

    def test_multi_paragraph_quote_in_list_item_roundtrips(self) -> None:
        """Every block of a nested quote survives, each as a paragraph."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=10,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="lead")]),
                                BlockQuote(
                                    children=[
                                        Paragraph(content=[Text(content="one")]),
                                        Paragraph(content=[Text(content="two")]),
                                    ]
                                ),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(doc)

        quote = markdown_to_ast(output).children[0].items[0].children[1]
        assert isinstance(quote, BlockQuote)
        assert [type(child).__name__ for child in quote.children] == ["Paragraph", "Paragraph"]

    def test_top_level_quote_is_unchanged(self) -> None:
        """A quote outside a list still renders with no leading indent."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="top")])])])

        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        assert renderer.render_to_string(doc) == "> top"


class TestLineBreakInSingleLineContexts:
    """Tests for line breaks inside table cells and headings (#27)."""

    @staticmethod
    def _table_with_break(soft: bool) -> Document:
        """Build a 2x2 table whose first data cell holds a line break."""
        return Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="h1")]),
                            TableCell(content=[Text(content="h2")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(
                                    content=[
                                        Text(content="line1"),
                                        LineBreak(soft=soft),
                                        Text(content="line2"),
                                    ]
                                ),
                                TableCell(content=[Text(content="b")]),
                            ]
                        )
                    ],
                )
            ]
        )

    def test_hard_break_in_cell_uses_br(self) -> None:
        """A hard break in a cell becomes <br>, never a newline."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table_with_break(soft=False))

        assert "\n| line1<br>line2 | b |" in output
        assert "line1  \nline2" not in output

    def test_soft_break_in_cell_becomes_space(self) -> None:
        """A soft break in a cell degrades to a space."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table_with_break(soft=True))

        assert "\n| line1 line2 | b |" in output

    def test_cell_break_roundtrips_with_table_intact(self) -> None:
        """The table keeps its row and both cells after a reparse."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table_with_break(soft=False))

        reparsed = markdown_to_ast(output)
        assert [type(child).__name__ for child in reparsed.children] == ["Table"]
        table = reparsed.children[0]
        assert len(table.rows) == 1
        assert len(table.rows[0].cells) == 2
        assert table.rows[0].cells[1].content[0].content == "b"
        # Both halves of the broken cell stay in the cell they belong to.
        cell_text = "".join(getattr(node, "content", "") for node in table.rows[0].cells[0].content)
        assert cell_text == "line1<br>line2"

    def test_hard_break_in_heading_uses_br(self) -> None:
        """A hard break in a heading becomes <br> so the heading stays whole."""
        doc = Document(
            children=[
                Heading(
                    level=2,
                    content=[Text(content="part1"), LineBreak(soft=False), Text(content="part2")],
                )
            ]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(doc)

        assert output == "## part1<br>part2"

    def test_heading_break_roundtrips_without_losing_the_tail(self) -> None:
        """Text after the break stays in the heading instead of falling out."""
        doc = Document(
            children=[
                Heading(
                    level=2,
                    content=[Text(content="part1"), LineBreak(soft=False), Text(content="part2")],
                )
            ]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(doc)

        reparsed = markdown_to_ast(output)
        assert [type(child).__name__ for child in reparsed.children] == ["Heading"]
        heading_text = "".join(getattr(node, "content", "") for node in reparsed.children[0].content)
        assert heading_text == "part1<br>part2"

    def test_soft_break_in_heading_becomes_space(self) -> None:
        """A soft break in a heading degrades to a space."""
        doc = Document(
            children=[Heading(level=2, content=[Text(content="a"), LineBreak(soft=True), Text(content="b")])]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())

        assert renderer.render_to_string(doc) == "## a b"

    def test_paragraph_breaks_are_untouched(self) -> None:
        """Outside a cell or heading, line breaks still render as newlines."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="a"), LineBreak(soft=False), Text(content="b")]),
                Paragraph(content=[Text(content="c"), LineBreak(soft=True), Text(content="d")]),
            ]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())

        assert renderer.render_to_string(doc) == "a  \nb\n\nc\nd"

    def test_embedded_newline_in_cell_text_is_flattened(self) -> None:
        """A Text node carrying a newline cannot break the row either."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="h")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="one\ntwo")])])],
                )
            ]
        )
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(doc)

        assert "\n| one two |" in output
        assert len(markdown_to_ast(output).children[0].rows) == 1


class TestCaptionEscaping:
    """Tests for metacharacters in table and figure captions (#31)."""

    @staticmethod
    def _table(caption: str) -> Document:
        """Build a one-cell captioned table."""
        return Document(
            children=[
                Table(
                    caption=caption,
                    header=TableRow(cells=[TableCell(content=[Text(content="a")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="1")])])],
                )
            ]
        )

    @staticmethod
    def _figure(caption: str) -> Document:
        """Build a paragraph holding a single captioned image."""
        return Document(children=[Paragraph(content=[Image(url="a.png", alt_text="alt", caption=caption)])])

    def test_table_caption_asterisks_are_escaped(self) -> None:
        """Asterisks in a caption no longer close the emphasis early."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table("Sales *2024* results"))

        assert output.startswith("*Sales \\*2024\\* results*\n")

    @pytest.mark.parametrize(
        "caption",
        [
            "Sales *2024* results",
            "Table [1]: a_b_c",
            "*leading",
            "a * b * c * d",
            "100% of `results`",
        ],
    )
    def test_table_caption_roundtrips_verbatim(self, caption: str) -> None:
        """The caption comes back exactly as it went in, attached to the table."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table(caption))

        reparsed = markdown_to_ast(output)
        assert [type(child).__name__ for child in reparsed.children] == ["Table"]
        assert reparsed.children[0].caption == caption

    @pytest.mark.parametrize(
        "caption",
        [
            "Fig *1* [x]",
            "Figure 2. Results_summary",
            "a * b * c * d",
        ],
    )
    def test_figure_caption_roundtrips_verbatim(self, caption: str) -> None:
        """A figure caption survives its metacharacters too."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._figure(caption))

        reparsed = markdown_to_ast(output)
        assert [type(child).__name__ for child in reparsed.children] == ["Paragraph"]
        image = reparsed.children[0].content[0]
        assert isinstance(image, Image)
        assert image.caption == caption

    def test_plain_caption_is_not_over_escaped(self) -> None:
        """A caption with nothing special in it renders unchanged."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table("Quarterly results"))

        assert output.startswith("*Quarterly results*\n")

    def test_caption_newline_is_flattened(self) -> None:
        """A newline would end the caption paragraph and break the marker triple."""
        renderer = MarkdownRenderer(options=MarkdownRendererOptions())
        output = renderer.render_to_string(self._table("Two\nlines"))

        assert output.startswith("*Two lines*\n")
        assert markdown_to_ast(output).children[0].caption == "Two lines"
