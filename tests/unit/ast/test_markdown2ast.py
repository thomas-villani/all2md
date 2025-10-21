#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Unit tests for Markdown to AST converter."""

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
    Table,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.options import MarkdownParserOptions
from all2md.parsers.markdown import MarkdownToAstConverter, markdown_to_ast


class TestMarkdownBasics:
    """Test basic markdown parsing."""

    def test_simple_paragraph(self) -> None:
        """Test parsing a simple paragraph."""
        markdown = "This is a paragraph."
        doc = markdown_to_ast(markdown)

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)

        para = doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "This is a paragraph."

    def test_multiple_paragraphs(self) -> None:
        """Test parsing multiple paragraphs."""
        markdown = "First paragraph.\n\nSecond paragraph."
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 2
        assert all(isinstance(child, Paragraph) for child in doc.children)

    def test_heading_levels(self) -> None:
        """Test parsing different heading levels."""
        markdown = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 6
        for i, child in enumerate(doc.children):
            assert isinstance(child, Heading)
            assert child.level == i + 1
            assert len(child.content) == 1
            assert isinstance(child.content[0], Text)
            assert child.content[0].content == f"H{i + 1}"


class TestInlineFormatting:
    """Test inline formatting elements."""

    def test_bold(self) -> None:
        """Test bold/strong text."""
        markdown = "This is **bold** text."
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert len(para.content) == 3
        assert isinstance(para.content[0], Text)
        assert isinstance(para.content[1], Strong)
        assert isinstance(para.content[2], Text)

        strong = para.content[1]
        assert len(strong.content) == 1
        assert strong.content[0].content == "bold"

    def test_italic(self) -> None:
        """Test italic/emphasis text."""
        markdown = "This is *italic* text."
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert len(para.content) == 3
        assert isinstance(para.content[1], Emphasis)

    def test_inline_code(self) -> None:
        """Test inline code."""
        markdown = "Use `code` here."
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert len(para.content) == 3
        assert isinstance(para.content[1], Code)
        assert para.content[1].content == "code"

    def test_strikethrough(self) -> None:
        """Test strikethrough text."""
        markdown = "This is ~~strikethrough~~ text."
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert isinstance(para.content[1], Strikethrough)

    def test_combined_formatting(self) -> None:
        """Test combined inline formatting."""
        markdown = "This is **bold and *italic* combined**."
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert isinstance(para.content[1], Strong)
        # Strong should contain text, emphasis, and text
        strong = para.content[1]
        assert len(strong.content) == 3
        assert isinstance(strong.content[1], Emphasis)


class TestLinks:
    """Test link parsing."""

    def test_simple_link(self) -> None:
        """Test simple link."""
        markdown = "[Link text](https://example.com)"
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Link)

        link = para.content[0]
        assert link.url == "https://example.com"
        assert len(link.content) == 1
        assert link.content[0].content == "Link text"

    def test_link_with_title(self) -> None:
        """Test link with title."""
        markdown = '[Link](https://example.com "Title")'
        doc = markdown_to_ast(markdown)

        link = doc.children[0].content[0]
        assert isinstance(link, Link)
        assert link.url == "https://example.com"
        assert link.title == "Title"


class TestImages:
    """Test image parsing."""

    def test_simple_image(self) -> None:
        """Test simple image."""
        markdown = "![Alt text](https://example.com/image.png)"
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Image)

        image = para.content[0]
        assert image.url == "https://example.com/image.png"
        assert image.alt_text == "Alt text"

    def test_image_with_title(self) -> None:
        """Test image with title."""
        markdown = '![Alt](https://example.com/image.png "Title")'
        doc = markdown_to_ast(markdown)

        image = doc.children[0].content[0]
        assert isinstance(image, Image)
        assert image.title == "Title"


class TestLists:
    """Test list parsing."""

    def test_unordered_list(self) -> None:
        """Test unordered list."""
        markdown = "- Item 1\n- Item 2\n- Item 3"
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)

        list_node = doc.children[0]
        assert list_node.ordered is False
        assert len(list_node.items) == 3

        for item in list_node.items:
            assert isinstance(item, ListItem)

    def test_ordered_list(self) -> None:
        """Test ordered list."""
        markdown = "1. First\n2. Second\n3. Third"
        doc = markdown_to_ast(markdown)

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert list_node.ordered is True
        assert list_node.start == 1

    def test_task_list(self) -> None:
        """Test task list."""
        markdown = "- [ ] Unchecked\n- [x] Checked"
        doc = markdown_to_ast(markdown)

        list_node = doc.children[0]
        assert isinstance(list_node, List)
        assert len(list_node.items) == 2

        assert list_node.items[0].task_status == "unchecked"
        assert list_node.items[1].task_status == "checked"

    def test_nested_list(self) -> None:
        """Test nested lists."""
        markdown = "- Item 1\n  - Nested 1\n  - Nested 2\n- Item 2"
        doc = markdown_to_ast(markdown)

        outer_list = doc.children[0]
        assert isinstance(outer_list, List)

        # First item should contain nested list
        first_item = outer_list.items[0]
        assert len(first_item.children) >= 1
        # Find the nested list in children
        nested_lists = [c for c in first_item.children if isinstance(c, List)]
        assert len(nested_lists) >= 1


class TestCodeBlocks:
    """Test code block parsing."""

    def test_fenced_code_block(self) -> None:
        """Test fenced code block."""
        markdown = "```\ncode line 1\ncode line 2\n```"
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)

        code_block = doc.children[0]
        assert "code line 1" in code_block.content
        assert "code line 2" in code_block.content

    def test_code_block_with_language(self) -> None:
        """Test code block with language specification."""
        markdown = "```python\ndef hello():\n    print('Hello')\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "python"


class TestBlockQuotes:
    """Test block quote parsing."""

    def test_simple_blockquote(self) -> None:
        """Test simple block quote."""
        markdown = "> This is a quote."
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)

        quote = doc.children[0]
        assert len(quote.children) == 1
        assert isinstance(quote.children[0], Paragraph)

    def test_multi_line_blockquote(self) -> None:
        """Test multi-line block quote."""
        markdown = "> Line 1\n> Line 2"
        doc = markdown_to_ast(markdown)

        quote = doc.children[0]
        assert isinstance(quote, BlockQuote)
        # Content should be combined in a paragraph
        assert len(quote.children) >= 1


class TestTables:
    """Test table parsing."""

    def test_simple_table(self) -> None:
        """Test simple table."""
        markdown = """| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |"""
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)

        table = doc.children[0]
        assert table.header is not None
        assert isinstance(table.header, TableRow)
        assert len(table.header.cells) == 2

        assert len(table.rows) == 2
        for row in table.rows:
            assert isinstance(row, TableRow)
            assert len(row.cells) == 2

    def test_table_alignments(self) -> None:
        """Test table with alignments."""
        markdown = """| Left | Center | Right |
|:-----|:------:|------:|
| L    | C      | R     |"""
        doc = markdown_to_ast(markdown)

        table = doc.children[0]
        assert isinstance(table, Table)
        # Alignments should be captured
        assert len(table.alignments) == 3


class TestMiscellaneous:
    """Test miscellaneous elements."""

    def test_thematic_break(self) -> None:
        """Test thematic break (horizontal rule)."""
        markdown = "---"
        doc = markdown_to_ast(markdown)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ThematicBreak)

    def test_line_breaks(self) -> None:
        """Test line breaks."""
        markdown = "Line 1  \nLine 2"  # Two spaces before newline = hard break
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        # Should contain: Text, LineBreak, Text
        assert len(para.content) == 3
        assert isinstance(para.content[1], LineBreak)


class TestOptions:
    """Test parser options."""

    def test_disable_tables(self) -> None:
        """Test disabling table parsing."""
        markdown = """| Header |
|--------|
| Cell   |"""

        options = MarkdownParserOptions(parse_tables=False)
        doc = markdown_to_ast(markdown, options)

        # Without table parsing, should not create a Table node
        assert not any(isinstance(child, Table) for child in doc.children)

    def test_disable_strikethrough(self) -> None:
        """Test disabling strikethrough."""
        markdown = "This is ~~strikethrough~~ text."

        options = MarkdownParserOptions(parse_strikethrough=False)
        doc = markdown_to_ast(markdown, options)

        para = doc.children[0]
        # Should not have Strikethrough node
        assert not any(isinstance(node, Strikethrough) for node in para.content)


class TestConverterClass:
    """Test converter class directly."""

    def test_converter_initialization(self) -> None:
        """Test converter initialization."""
        converter = MarkdownToAstConverter()
        assert converter.options is not None
        assert isinstance(converter.options, MarkdownParserOptions)

    def test_converter_with_options(self) -> None:
        """Test converter with custom options."""
        options = MarkdownParserOptions(parse_tables=False)
        converter = MarkdownToAstConverter(options)
        assert converter.options.parse_tables is False

    def test_convert_method(self) -> None:
        """Test parse method."""
        converter = MarkdownToAstConverter()
        doc = converter.parse("# Hello")

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)


class TestComplexDocuments:
    """Test complex document structures."""

    def test_mixed_content(self) -> None:
        """Test document with mixed content types."""
        markdown = """# Title

This is a paragraph with **bold** and *italic* text.

## Section

- List item 1
- List item 2

```python
code here
```

> A quote

---
"""
        doc = markdown_to_ast(markdown)

        assert isinstance(doc, Document)
        assert len(doc.children) >= 6

        # Verify we have different node types
        node_types = {type(child).__name__ for child in doc.children}
        assert "Heading" in node_types
        assert "Paragraph" in node_types
        assert "List" in node_types
        assert "CodeBlock" in node_types
        assert "BlockQuote" in node_types
        assert "ThematicBreak" in node_types

    def test_empty_document(self) -> None:
        """Test empty document."""
        markdown = ""
        doc = markdown_to_ast(markdown)

        assert isinstance(doc, Document)
        assert len(doc.children) == 0

    def test_whitespace_only(self) -> None:
        """Test document with only whitespace."""
        markdown = "   \n\n   \n"
        doc = markdown_to_ast(markdown)

        assert isinstance(doc, Document)
        # Should have no meaningful content
        assert len(doc.children) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unclosed_emphasis(self) -> None:
        """Test handling of unclosed emphasis."""
        markdown = "This has *unclosed emphasis"
        doc = markdown_to_ast(markdown)

        # Should gracefully handle and parse what it can
        assert isinstance(doc, Document)
        assert len(doc.children) >= 1

    def test_special_characters(self) -> None:
        """Test handling of special characters."""
        markdown = "Text with special chars: <>&\"'"
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        text = para.content[0]
        assert isinstance(text, Text)
        # Characters should be preserved
        assert "<" in text.content
        assert ">" in text.content

    def test_unicode_content(self) -> None:
        """Test Unicode content."""
        markdown = "Unicode: émojis 😀 中文"
        doc = markdown_to_ast(markdown)

        para = doc.children[0]
        text = para.content[0]
        assert "émojis" in text.content
        assert "😀" in text.content
        assert "中文" in text.content


class TestCodeBlockMetadata:
    """Test code block metadata preservation."""

    def test_code_block_with_info_string_metadata(self) -> None:
        """Test that code blocks preserve info string metadata."""
        markdown = "```python linenums=1\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "python"
        assert code_block.metadata.get("info_string") == "python linenums=1"
        assert code_block.metadata.get("info_attrs") == "linenums=1"

    def test_code_block_with_complex_metadata(self) -> None:
        """Test code blocks with complex info string metadata."""
        markdown = "```javascript {.class #id attr=value}\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "javascript"
        assert code_block.metadata.get("info_string") == "javascript {.class #id attr=value}"
        assert code_block.metadata.get("info_attrs") == "{.class #id attr=value}"

    def test_code_block_without_metadata(self) -> None:
        """Test that code blocks without metadata still work."""
        markdown = "```python\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "python"
        assert code_block.metadata.get("info_string") == "python"
        assert "info_attrs" not in code_block.metadata

    def test_code_block_with_no_language(self) -> None:
        """Test that code blocks with no language have no metadata."""
        markdown = "```\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language in [None, ""]
        assert code_block.metadata == {}


class TestCodeBlockLanguageSanitization:
    """Test code block language identifier sanitization."""

    def test_valid_language_identifiers(self) -> None:
        """Test that valid language identifiers are preserved."""
        valid_languages = ["python", "javascript", "c++", "rust-nightly", "c_sharp"]

        for lang in valid_languages:
            markdown = f"```{lang}\ncode\n```"
            doc = markdown_to_ast(markdown)

            assert len(doc.children) == 1
            code_block = doc.children[0]
            assert isinstance(code_block, CodeBlock)
            assert code_block.language == lang

    def test_malicious_language_with_newline(self) -> None:
        """Test that language identifiers with newlines are blocked."""
        # This could be used for markdown injection
        markdown = "```python\\nmalicious\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        # Should be sanitized to empty or just "python"
        # Since .split()[0] extracts "python\nmalicious", sanitizer should reject it
        assert code_block.language in [None, ""]

    def test_malicious_language_with_spaces(self) -> None:
        """Test that language identifiers with spaces are blocked."""
        markdown = "```python javascript\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        # After split()[0], we get "python", which should be valid
        assert code_block.language == "python"

    def test_excessively_long_language_identifier(self) -> None:
        """Test that excessively long language identifiers are blocked."""
        long_lang = "x" * 100  # Exceeds MAX_LANGUAGE_IDENTIFIER_LENGTH (50)
        markdown = f"```{long_lang}\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        # Should be sanitized to empty
        assert code_block.language in [None, ""]

    def test_language_with_special_characters(self) -> None:
        """Test that language identifiers with disallowed special characters are blocked."""
        malicious_langs = ["python;rm -rf", "python$(whoami)", "python|ls", "python<script>"]

        for lang in malicious_langs:
            markdown = f"```{lang}\ncode\n```"
            doc = markdown_to_ast(markdown)

            code_block = doc.children[0]
            assert isinstance(code_block, CodeBlock)
            # Should be sanitized - either empty or only the valid prefix
            # After split()[0], we get things like "python;rm", which should be blocked
            # Only alphanumeric, hyphens, underscores, and plus signs are allowed
            assert code_block.language in [None, ""]

    def test_empty_language_identifier(self) -> None:
        """Test that empty language identifiers are handled correctly."""
        markdown = "```\ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language in [None, ""]

    def test_whitespace_only_language(self) -> None:
        """Test that whitespace-only language identifiers are treated as empty."""
        markdown = "```   \ncode\n```"
        doc = markdown_to_ast(markdown)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language in [None, ""]


class TestMistuneTokenRobustness:
    """Test robustness against malformed Mistune 3 tokens."""

    def test_heading_with_invalid_level(self) -> None:
        """Test that headings with invalid levels are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a malformed token with invalid level
        malformed_token = {
            "type": "heading",
            "attrs": {"level": 99},  # Invalid level
            "children": [{"type": "text", "raw": "Test"}],
        }

        heading = converter._process_heading(malformed_token)
        assert heading.level == 1  # Should default to 1

    def test_heading_with_missing_attrs(self) -> None:
        """Test that headings with missing attrs are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a token with missing attrs
        malformed_token = {"type": "heading", "children": [{"type": "text", "raw": "Test"}]}

        heading = converter._process_heading(malformed_token)
        assert heading.level == 1
        assert len(heading.content) == 1

    def test_heading_with_non_dict_attrs(self) -> None:
        """Test that headings with non-dict attrs are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a token with non-dict attrs
        malformed_token = {"type": "heading", "attrs": "not a dict", "children": [{"type": "text", "raw": "Test"}]}

        heading = converter._process_heading(malformed_token)
        assert heading.level == 1

    def test_list_with_missing_children(self) -> None:
        """Test that lists with missing children are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a token with missing children
        malformed_token = {"type": "list", "attrs": {"ordered": True}}

        list_node = converter._process_list(malformed_token)
        assert len(list_node.items) == 0

    def test_link_with_non_dict_attrs(self) -> None:
        """Test that links with non-dict attrs are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a token with non-dict attrs
        malformed_token = {
            "type": "link",
            "attrs": None,  # Should be a dict
            "children": [{"type": "text", "raw": "Link"}],
        }

        link = converter._process_inline_token(malformed_token)
        assert isinstance(link, Link)
        assert link.url == ""

    def test_image_with_malformed_children(self) -> None:
        """Test that images with malformed children are handled gracefully."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        # Simulate a token with malformed children (not a list)
        malformed_token = {"type": "image", "attrs": {"url": "test.png"}, "children": "not a list"}

        image = converter._process_inline_token(malformed_token)
        assert isinstance(image, Image)
        assert image.alt_text == ""

    def test_code_block_with_empty_info_string(self) -> None:
        """Test that code blocks with empty info strings are handled."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        token = {"type": "block_code", "raw": "code content", "attrs": {"info": "   "}}  # Whitespace only

        code_block = converter._process_code_block(token)
        assert code_block.language in [None, ""]
        # Empty info string still gets stored, which is fine
        assert code_block.metadata.get("info_string") == ""

    def test_code_block_with_metadata_and_invalid_language(self) -> None:
        """Test code blocks with metadata but invalid language."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        converter = MarkdownToAstConverter()

        token = {"type": "block_code", "raw": "code content", "attrs": {"info": "python;rm-rf linenums=1"}}

        code_block = converter._process_code_block(token)
        # Language should be sanitized to empty
        assert code_block.language in [None, ""]
        # But metadata should still preserve the full info string
        assert "info_string" in code_block.metadata
        assert "info_attrs" in code_block.metadata
