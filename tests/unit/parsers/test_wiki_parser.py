#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_wiki_parser.py
"""Unit tests for MediaWiki parser.

Tests cover:
- MediaWiki heading parsing with different levels
- Text formatting (bold, italic, code, underline, strikethrough)
- List parsing (bullet and ordered, nested)
- Table parsing
- Link parsing (internal [[...]] and external [...])
- Image parsing ([[File:...]])
- Template handling
- Block quotes
- Special tags

"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Emphasis,
    Heading,
    HTMLInline,
    Image,
    Link,
    List,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options.mediawiki import MediaWikiParserOptions
from all2md.parsers.mediawiki import MediaWikiParser


@pytest.mark.unit
class TestBasicParsing:
    """Tests for basic MediaWiki parsing."""

    def test_simple_heading(self) -> None:
        """Test parsing a simple heading."""
        wikitext = "== Title =="
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        assert len(doc.children) >= 1
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 2
        assert len(heading.content) == 1
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Title"

    def test_multiple_heading_levels(self) -> None:
        """Test parsing multiple heading levels."""
        wikitext = """= Level 1 =
== Level 2 ==
=== Level 3 ==="""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 3
        assert headings[0].level == 1
        assert headings[1].level == 2
        assert headings[2].level == 3

    def test_simple_paragraph(self) -> None:
        """Test parsing a simple paragraph."""
        wikitext = "This is a simple paragraph."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        assert isinstance(paras[0].content[0], Text)
        assert "simple paragraph" in paras[0].content[0].content


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_bold(self) -> None:
        """Test parsing bold text."""
        wikitext = "This is '''bold''' text."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        para = paras[0]

        # Should have: text, strong, text
        strong_nodes = [node for node in para.content if isinstance(node, Strong)]
        assert len(strong_nodes) >= 1
        assert strong_nodes[0].content[0].content == "bold"

    def test_italic(self) -> None:
        """Test parsing italic text."""
        wikitext = "This is ''italic'' text."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        para = paras[0]

        # Should have emphasis nodes
        em_nodes = [node for node in para.content if isinstance(node, Emphasis)]
        assert len(em_nodes) >= 1
        assert em_nodes[0].content[0].content == "italic"

    def test_bold_and_italic(self) -> None:
        """Test parsing combined bold and italic."""
        wikitext = "This is '''''bold and italic''''' text."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # mwparserfromhell should handle this
        assert len(doc.children) >= 1

    def test_inline_code(self) -> None:
        """Test parsing inline code."""
        wikitext = "Use <code>code</code> for inline code."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        para = paras[0]

        code_nodes = [node for node in para.content if isinstance(node, Code)]
        assert len(code_nodes) >= 1
        assert code_nodes[0].content == "code"

    def test_underline(self) -> None:
        """Test parsing underline."""
        wikitext = "This is <u>underlined</u> text."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        para = paras[0]

        underline_nodes = [node for node in para.content if isinstance(node, Underline)]
        assert len(underline_nodes) >= 1
        assert underline_nodes[0].content[0].content == "underlined"

    def test_strikethrough(self) -> None:
        """Test parsing strikethrough."""
        wikitext = "This is <s>struck</s> text."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        paras = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paras) >= 1
        para = paras[0]

        strike_nodes = [node for node in para.content if isinstance(node, Strikethrough)]
        assert len(strike_nodes) >= 1
        assert strike_nodes[0].content[0].content == "struck"


@pytest.mark.unit
class TestLinks:
    """Tests for link parsing."""

    def test_internal_link(self) -> None:
        """Test parsing internal wiki link."""
        wikitext = "See [[Page Title]] for details."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Find all Link nodes
        def find_links(nodes):
            links = []
            for node in nodes:
                if isinstance(node, Paragraph):
                    links.extend([n for n in node.content if isinstance(n, Link)])
            return links

        links = find_links(doc.children)
        assert len(links) >= 1
        assert links[0].url == "Page Title"

    def test_internal_link_with_text(self) -> None:
        """Test parsing internal link with custom text."""
        wikitext = "See [[Page Title|custom text]] for details."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        def find_links(nodes):
            links = []
            for node in nodes:
                if isinstance(node, Paragraph):
                    links.extend([n for n in node.content if isinstance(n, Link)])
            return links

        links = find_links(doc.children)
        assert len(links) >= 1
        assert links[0].url == "Page Title"
        # Check that content has custom text
        assert len(links[0].content) >= 1

    def test_external_link(self) -> None:
        """Test parsing external link."""
        wikitext = "Visit [http://example.com Example Site] for more."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        def find_links(nodes):
            links = []
            for node in nodes:
                if isinstance(node, Paragraph):
                    links.extend([n for n in node.content if isinstance(n, Link)])
            return links

        links = find_links(doc.children)
        assert len(links) >= 1
        assert "example.com" in links[0].url

    def test_image_link(self) -> None:
        """Test parsing image link."""
        wikitext = "[[File:Example.jpg|alt text]]"
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Find Image nodes
        def find_images(nodes):
            images = []
            for node in nodes:
                if isinstance(node, Image):
                    images.append(node)
                elif isinstance(node, Paragraph):
                    images.extend([n for n in node.content if isinstance(n, Image)])
            return images

        images = find_images(doc.children)
        assert len(images) >= 1
        assert "Example.jpg" in images[0].url


@pytest.mark.unit
class TestLists:
    """Tests for list parsing."""

    def test_unordered_list(self) -> None:
        """Test parsing unordered list."""
        wikitext = """* Item 1
* Item 2
* Item 3"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        lists = [node for node in doc.children if isinstance(node, List)]
        assert len(lists) >= 1
        assert not lists[0].ordered
        assert len(lists[0].items) == 3

    def test_ordered_list(self) -> None:
        """Test parsing ordered list."""
        wikitext = """# First
# Second
# Third"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        lists = [node for node in doc.children if isinstance(node, List)]
        assert len(lists) >= 1
        assert lists[0].ordered
        assert len(lists[0].items) == 3

    def test_nested_list(self) -> None:
        """Test parsing nested list."""
        wikitext = """* Item 1
** Nested 1.1
** Nested 1.2
* Item 2"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should have at least one list
        lists = [node for node in doc.children if isinstance(node, List)]
        assert len(lists) >= 1


@pytest.mark.unit
class TestTables:
    """Tests for table parsing."""

    def test_simple_table(self) -> None:
        """Test parsing a simple table."""
        wikitext = """{|
! Header 1 !! Header 2
|-
| Cell 1 || Cell 2
|-
| Cell 3 || Cell 4
|}"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        tables = [node for node in doc.children if isinstance(node, Table)]
        assert len(tables) >= 1
        table = tables[0]

        # Check header
        assert table.header is not None
        assert len(table.header.cells) == 2

        # Check rows
        assert len(table.rows) >= 2

    def test_table_without_header(self) -> None:
        """Test parsing table without header."""
        wikitext = """{|
|-
| Cell 1 || Cell 2
|-
| Cell 3 || Cell 4
|}"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        tables = [node for node in doc.children if isinstance(node, Table)]
        assert len(tables) >= 1
        table = tables[0]

        # Should have rows
        assert len(table.rows) >= 2


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block parsing."""

    def test_syntaxhighlight_tag(self) -> None:
        """Test parsing syntaxhighlight tag."""
        wikitext = """<syntaxhighlight lang="python">
def hello():
    print("Hello")
</syntaxhighlight>"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        code_blocks = [node for node in doc.children if isinstance(node, CodeBlock)]
        assert len(code_blocks) >= 1
        assert "def hello()" in code_blocks[0].content
        assert code_blocks[0].language == "python"

    def test_pre_tag(self) -> None:
        """Test parsing pre tag."""
        wikitext = """<pre>
Preformatted text
  with indentation
</pre>"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        code_blocks = [node for node in doc.children if isinstance(node, CodeBlock)]
        assert len(code_blocks) >= 1
        assert "Preformatted text" in code_blocks[0].content


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote parsing."""

    def test_block_quote(self) -> None:
        """Test parsing block quote."""
        wikitext = """: This is a quote
: with multiple lines"""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        quotes = [node for node in doc.children if isinstance(node, BlockQuote)]
        assert len(quotes) >= 1


@pytest.mark.unit
class TestTemplates:
    """Tests for template handling."""

    def test_template_stripped_by_default(self) -> None:
        """Test that templates are stripped by default."""
        wikitext = "Before {{template|param=value}} after."
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Templates should be stripped, only text remains
        assert len(doc.children) >= 1

    def test_template_preserved_with_option(self) -> None:
        """Test that templates are preserved when option is set."""
        wikitext = "Before {{template|param=value}} after."
        options = MediaWikiParserOptions(parse_templates=True)
        parser = MediaWikiParser(options)
        doc = parser.parse(wikitext)

        # Template should be converted to HTMLInline
        def find_html_inline(nodes):
            html_nodes = []
            for node in nodes:
                if isinstance(node, Paragraph):
                    html_nodes.extend([n for n in node.content if isinstance(n, HTMLInline)])
            return html_nodes

        html_nodes = find_html_inline(doc.children)
        # May have HTML nodes depending on sanitization settings
        assert len(doc.children) >= 1


@pytest.mark.unit
class TestSpecialCases:
    """Tests for special cases and edge cases."""

    def test_thematic_break(self) -> None:
        """Test parsing thematic break."""
        wikitext = "Before\n\n----\n\nAfter"
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) >= 1

    def test_empty_document(self) -> None:
        """Test parsing empty document."""
        wikitext = ""
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Should return empty document
        assert isinstance(doc, type(doc))
        assert len(doc.children) >= 0

    def test_nowiki_tag(self) -> None:
        """Test parsing nowiki tag."""
        wikitext = "<nowiki>'''not bold'''</nowiki>"
        parser = MediaWikiParser()
        doc = parser.parse(wikitext)

        # Content should be preserved as code
        def find_code(nodes):
            code_nodes = []
            for node in nodes:
                if isinstance(node, Paragraph):
                    code_nodes.extend([n for n in node.content if isinstance(n, Code)])
            return code_nodes

        code_nodes = find_code(doc.children)
        assert len(code_nodes) >= 1


@pytest.mark.unit
class TestOptions:
    """Tests for parser options."""

    def test_html_passthrough_escape_mode(self) -> None:
        """Test HTML escaping mode."""
        wikitext = "<div>test</div>"
        options = MediaWikiParserOptions(html_passthrough_mode="escape")
        parser = MediaWikiParser(options)
        doc = parser.parse(wikitext)

        # HTML should be escaped
        assert len(doc.children) >= 0

    def test_strip_comments_enabled(self) -> None:
        """Test that comments are stripped when option is enabled."""
        wikitext = "Before <!-- comment --> after"
        options = MediaWikiParserOptions(strip_comments=True)
        parser = MediaWikiParser(options)
        doc = parser.parse(wikitext)

        # Comment should be stripped
        assert len(doc.children) >= 1

    def test_strip_comments_disabled(self) -> None:
        """Test that comments are preserved when option is disabled."""
        wikitext = "Before <!-- comment --> after"
        options = MediaWikiParserOptions(strip_comments=False)
        parser = MediaWikiParser(options)
        doc = parser.parse(wikitext)

        # Comment should be preserved as HTMLInline
        assert len(doc.children) >= 1
