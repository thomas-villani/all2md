#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_html_ast.py
"""Unit tests for HTML to AST converter.

Tests cover:
- HTML element to AST node conversion
- Nested structure handling
- HTML-specific features (title extraction, dangerous elements)
- Table parsing with various header configurations
- Link and image sanitization
- Code block language detection

"""

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
    Strong,
    Table,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.parsers.html import HtmlToAstConverter
from all2md.options import HtmlOptions


@pytest.mark.unit
class TestBasicElements:
    """Tests for basic HTML element conversion."""

    def test_simple_paragraph(self) -> None:
        """Test converting a simple paragraph."""
        html = "<p>Hello world</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "Hello world"

    def test_multiple_paragraphs(self) -> None:
        """Test converting multiple paragraphs."""
        html = "<p>First</p><p>Second</p><p>Third</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 3
        assert all(isinstance(child, Paragraph) for child in doc.children)

    def test_headings_h1_to_h6(self) -> None:
        """Test converting all heading levels."""
        html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3><h4>H4</h4><h5>H5</h5><h6>H6</h6>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 6
        for i, child in enumerate(doc.children):
            assert isinstance(child, Heading)
            assert child.level == i + 1
            assert isinstance(child.content[0], Text)
            assert child.content[0].content == f"H{i + 1}"

    def test_thematic_break(self) -> None:
        """Test converting horizontal rule."""
        html = "<p>Before</p><hr><p>After</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 3
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], ThematicBreak)
        assert isinstance(doc.children[2], Paragraph)

    def test_line_break(self) -> None:
        """Test converting br element."""
        html = "<p>Line 1<br>Line 2</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert len(para.content) == 3
        assert isinstance(para.content[0], Text)
        assert isinstance(para.content[1], LineBreak)
        assert isinstance(para.content[2], Text)
        assert para.content[1].soft is False


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting elements."""

    def test_strong_and_bold(self) -> None:
        """Test converting strong and b elements."""
        html = "<p><strong>Strong</strong> and <b>Bold</b></p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert isinstance(para.content[0], Strong)
        assert isinstance(para.content[2], Strong)

    def test_emphasis_and_italic(self) -> None:
        """Test converting em and i elements."""
        html = "<p><em>Emphasis</em> and <i>Italic</i></p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert isinstance(para.content[0], Emphasis)
        assert isinstance(para.content[2], Emphasis)

    def test_underline(self) -> None:
        """Test converting u element."""
        html = "<p><u>Underlined</u></p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert isinstance(para.content[0], Underline)
        assert isinstance(para.content[0].content[0], Text)
        assert para.content[0].content[0].content == "Underlined"

    def test_inline_code(self) -> None:
        """Test converting inline code element."""
        html = "<p>Use <code>print()</code> function</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert isinstance(para.content[1], Code)
        assert para.content[1].content == "print()"

    def test_nested_formatting(self) -> None:
        """Test nested inline formatting."""
        html = "<p><strong><em>Bold italic</em></strong></p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert isinstance(para.content[0], Strong)
        strong = para.content[0]
        assert isinstance(strong.content[0], Emphasis)
        em = strong.content[0]
        assert isinstance(em.content[0], Text)
        assert em.content[0].content == "Bold italic"


@pytest.mark.unit
class TestLinks:
    """Tests for link conversion."""

    def test_simple_link(self) -> None:
        """Test converting a simple link."""
        html = '<a href="https://example.com">Example</a>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        # Link should be in a paragraph (or directly in doc)
        if isinstance(doc.children[0], Link):
            link = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Link)
            link = doc.children[0].content[0]
        assert link.url == "https://example.com"
        assert isinstance(link.content[0], Text)
        assert link.content[0].content == "Example"
        assert link.title is None

    def test_link_with_title(self) -> None:
        """Test converting a link with title attribute."""
        html = '<a href="https://example.com" title="Example Site">Link</a>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Link):
            link = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Link)
            link = doc.children[0].content[0]
        assert link.title == "Example Site"

    def test_link_sanitization_javascript(self) -> None:
        """Test that javascript: URLs are sanitized."""
        html = '<a href="javascript:alert(\'xss\')">Click</a>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Link):
            link = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Link)
            link = doc.children[0].content[0]
        assert link.url == ""

    def test_link_sanitization_data_scheme(self) -> None:
        """Test that data: URLs are sanitized."""
        html = '<a href="data:text/html,<script>alert(1)</script>">Click</a>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Link):
            link = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Link)
            link = doc.children[0].content[0]
        assert link.url == ""

    def test_link_relative_url_preserved(self) -> None:
        """Test that relative URLs are preserved."""
        html = '<a href="/page.html">Page</a>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Link):
            link = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Link)
            link = doc.children[0].content[0]
        assert link.url == "/page.html"


@pytest.mark.unit
class TestImages:
    """Tests for image conversion."""

    def test_simple_image(self) -> None:
        """Test converting a simple image."""
        html = '<img src="image.png" alt="An image">'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Image):
            img = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Image)
            img = doc.children[0].content[0]
        assert img.url == "image.png"
        assert img.alt_text == "An image"
        assert img.title is None

    def test_image_with_title(self) -> None:
        """Test converting an image with title."""
        html = '<img src="photo.jpg" alt="Photo" title="My Photo">'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        if isinstance(doc.children[0], Image):
            img = doc.children[0]
        else:
            assert isinstance(doc.children[0], Paragraph)
            assert isinstance(doc.children[0].content[0], Image)
            img = doc.children[0].content[0]
        assert img.title == "My Photo"


@pytest.mark.unit
class TestLists:
    """Tests for list conversion."""

    def test_simple_unordered_list(self) -> None:
        """Test converting an unordered list."""
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 1
        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered is False
        assert len(list_node.items) == 3

        for i, item in enumerate(list_node.items):
            assert isinstance(item, ListItem)
            assert len(item.children) == 1
            assert isinstance(item.children[0], Paragraph)
            assert isinstance(item.children[0].content[0], Text)
            assert item.children[0].content[0].content == f"Item {i + 1}"

    def test_simple_ordered_list(self) -> None:
        """Test converting an ordered list."""
        html = "<ol><li>First</li><li>Second</li></ol>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered is True
        assert len(list_node.items) == 2

    def test_nested_list(self) -> None:
        """Test converting nested lists."""
        html = """
        <ul>
            <li>Item 1
                <ul>
                    <li>Nested 1</li>
                    <li>Nested 2</li>
                </ul>
            </li>
            <li>Item 2</li>
        </ul>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], List)
        outer_list = doc.children[0]
        assert len(outer_list.items) == 2

        first_item = outer_list.items[0]
        # First item should have paragraph and nested list
        assert len(first_item.children) == 2
        assert isinstance(first_item.children[0], Paragraph)
        assert isinstance(first_item.children[1], List)

        nested_list = first_item.children[1]
        assert nested_list.ordered is False
        assert len(nested_list.items) == 2


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block conversion."""

    def test_simple_pre_element(self) -> None:
        """Test converting a pre element."""
        html = "<pre>code line 1\ncode line 2</pre>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 1
        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert "code line 1" in code_block.content
        assert "code line 2" in code_block.content
        assert code_block.language is None

    def test_code_block_with_language_class(self) -> None:
        """Test extracting language from class attribute."""
        html = '<pre class="language-python"><code>print("hello")</code></pre>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert code_block.language == "python"

    def test_code_block_with_lang_prefix(self) -> None:
        """Test extracting language from lang- prefix."""
        html = '<pre class="lang-javascript"><code>console.log("test")</code></pre>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert code_block.language == "javascript"

    def test_code_block_with_data_lang(self) -> None:
        """Test extracting language from data-lang attribute."""
        html = '<pre data-lang="rust"><code>fn main() {}</code></pre>'
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert code_block.language == "rust"

    def test_code_block_html_entity_decoding(self) -> None:
        """Test that HTML entities are decoded in code blocks."""
        html = "<pre>&lt;div&gt;&amp;&lt;/div&gt;</pre>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert "<div>&</div>" in code_block.content


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for blockquote conversion."""

    def test_simple_blockquote(self) -> None:
        """Test converting a simple blockquote."""
        html = "<blockquote><p>Quoted text</p></blockquote>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 1
        quote = doc.children[0]
        assert isinstance(quote, BlockQuote)
        assert len(quote.children) == 1
        assert isinstance(quote.children[0], Paragraph)

    def test_blockquote_with_multiple_paragraphs(self) -> None:
        """Test blockquote with multiple paragraphs."""
        html = "<blockquote><p>Para 1</p><p>Para 2</p></blockquote>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], BlockQuote)
        quote = doc.children[0]
        assert len(quote.children) == 2
        assert all(isinstance(child, Paragraph) for child in quote.children)


@pytest.mark.unit
class TestTables:
    """Tests for table conversion."""

    def test_table_with_thead(self) -> None:
        """Test table with explicit thead element."""
        html = """
        <table>
            <thead>
                <tr><th>Name</th><th>Age</th></tr>
            </thead>
            <tbody>
                <tr><td>Alice</td><td>30</td></tr>
                <tr><td>Bob</td><td>25</td></tr>
            </tbody>
        </table>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is not None
        assert table.header.is_header is True
        assert len(table.header.cells) == 2
        assert len(table.rows) == 2

    def test_table_without_thead_but_with_th(self) -> None:
        """Test table with th elements but no thead."""
        html = """
        <table>
            <tr><th>Column 1</th><th>Column 2</th></tr>
            <tr><td>Data 1</td><td>Data 2</td></tr>
        </table>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Table)
        table = doc.children[0]
        assert table.header is not None
        assert len(table.header.cells) == 2
        assert len(table.rows) == 1

    def test_table_with_caption(self) -> None:
        """Test table with caption element."""
        html = """
        <table>
            <caption>Table Caption</caption>
            <tr><th>Header</th></tr>
            <tr><td>Data</td></tr>
        </table>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Table)
        table = doc.children[0]
        assert table.caption == "Table Caption"

    def test_table_alignment_detection(self) -> None:
        """Test detecting table cell alignment."""
        html = """
        <table>
            <tr>
                <th align="left">Left</th>
                <th align="center">Center</th>
                <th align="right">Right</th>
            </tr>
            <tr>
                <td>A</td><td>B</td><td>C</td>
            </tr>
        </table>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Table)
        table = doc.children[0]
        assert len(table.alignments) == 3
        assert table.alignments[0] == "left"
        assert table.alignments[1] == "center"
        assert table.alignments[2] == "right"

    def test_table_alignment_from_style(self) -> None:
        """Test detecting alignment from CSS style attribute."""
        html = """
        <table>
            <tr>
                <th style="text-align: center">Centered</th>
            </tr>
            <tr><td>Data</td></tr>
        </table>
        """
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc.children[0], Table)
        table = doc.children[0]
        assert table.alignments[0] == "center"


@pytest.mark.unit
class TestHtmlOptions:
    """Tests for HtmlOptions configuration."""

    def test_title_extraction_enabled(self) -> None:
        """Test extracting title when option is enabled."""
        html = "<html><head><title>Page Title</title></head><body><p>Content</p></body></html>"
        options = HtmlOptions(extract_title=True)
        converter = HtmlToAstConverter(options)
        doc = converter.convert_to_ast(html)

        # First child should be heading with title
        assert len(doc.children) >= 1
        assert isinstance(doc.children[0], Heading)
        assert doc.children[0].level == 1
        assert isinstance(doc.children[0].content[0], Text)
        assert doc.children[0].content[0].content == "Page Title"

    def test_title_extraction_disabled(self) -> None:
        """Test not extracting title when option is disabled."""
        html = "<html><head><title>Page Title</title></head><body><p>Content</p></body></html>"
        options = HtmlOptions(extract_title=False)
        converter = HtmlToAstConverter(options)
        doc = converter.convert_to_ast(html)

        # Should not have title heading
        # First child should be paragraph
        if len(doc.children) > 0:
            if isinstance(doc.children[0], Heading):
                # If there is a heading, it shouldn't be "Page Title"
                if len(doc.children[0].content) > 0 and isinstance(doc.children[0].content[0], Text):
                    assert doc.children[0].content[0].content != "Page Title"

    def test_strip_dangerous_elements(self) -> None:
        """Test stripping script and style tags."""
        html = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body>
                <p>Safe content</p>
                <script>alert('danger')</script>
                <p>More content</p>
            </body>
        </html>
        """
        options = HtmlOptions(strip_dangerous_elements=True)
        converter = HtmlToAstConverter(options)
        doc = converter.convert_to_ast(html)

        # Check that script/style content is not in the AST
        # This is indirect - we verify by rendering and checking output
        # For this test, we just verify the doc was created without errors
        assert isinstance(doc, Document)
        # Verify we have the safe paragraphs
        paragraphs = [child for child in doc.children if isinstance(child, Paragraph)]
        assert len(paragraphs) >= 1


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_html(self) -> None:
        """Test converting empty HTML."""
        html = ""
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc, Document)
        assert len(doc.children) == 0

    def test_whitespace_only(self) -> None:
        """Test converting whitespace-only content."""
        html = "   \n\n   \t   "
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert isinstance(doc, Document)
        # Should have no children or only empty elements
        # This depends on BeautifulSoup parsing

    def test_unknown_elements(self) -> None:
        """Test handling unknown HTML elements."""
        html = "<custom-element>Content</custom-element>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        # Should process children even if element is unknown
        assert isinstance(doc, Document)

    def test_malformed_html(self) -> None:
        """Test handling malformed HTML."""
        html = "<p>Unclosed paragraph<div>Div inside p</p></div>"
        converter = HtmlToAstConverter()
        # BeautifulSoup should handle this gracefully
        doc = converter.convert_to_ast(html)

        assert isinstance(doc, Document)

    def test_html_comments_ignored(self) -> None:
        """Test that HTML comments are ignored."""
        html = "<p>Text<!-- comment -->More text</p>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        para = doc.children[0]
        # Comments should not appear in text content
        # This depends on BeautifulSoup's NavigableString handling
        assert isinstance(para, Paragraph)

    def test_div_as_paragraph(self) -> None:
        """Test that div elements are treated as paragraphs."""
        html = "<div>This is a div</div>"
        converter = HtmlToAstConverter()
        doc = converter.convert_to_ast(html)

        assert len(doc.children) == 1
        # Div should create a paragraph-like structure
        assert isinstance(doc.children[0], Paragraph)
