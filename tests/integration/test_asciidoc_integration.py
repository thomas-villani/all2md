"""Integration tests for AsciiDoc parser and renderer.

This module contains integration tests for the AsciiDoc converter,
testing full conversion pipelines with various AsciiDoc structures and edge cases.
"""

import pytest
from fixtures.generators.asciidoc_fixtures import (
    create_asciidoc_complex_document,
    create_asciidoc_with_attributes,
    create_asciidoc_with_code_blocks,
    create_asciidoc_with_formatting,
    create_asciidoc_with_links_and_images,
    create_asciidoc_with_lists,
    create_asciidoc_with_nested_formatting,
    create_asciidoc_with_tables,
    create_simple_asciidoc,
)
from utils import assert_markdown_valid

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionList,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Subscript,
    Superscript,
    Table,
    Text,
    ThematicBreak,
)
from all2md.options import AsciiDocOptions, AsciiDocParserOptions, MarkdownOptions
from all2md.parsers.asciidoc import AsciiDocParser
from all2md.renderers.asciidoc import AsciiDocRenderer
from all2md.renderers.markdown import MarkdownRenderer


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocIntegrationBasic:
    """Test basic AsciiDoc integration scenarios."""

    def test_simple_document_conversion(self) -> None:
        """Test conversion of a simple AsciiDoc document."""
        asciidoc = create_simple_asciidoc()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have heading and paragraphs
        has_heading = any(isinstance(child, Heading) for child in doc.children)
        has_paragraph = any(isinstance(child, Paragraph) for child in doc.children)
        assert has_heading
        assert has_paragraph

    def test_asciidoc_to_markdown_conversion(self) -> None:
        """Test converting AsciiDoc to Markdown via AST."""
        asciidoc = create_simple_asciidoc()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert len(result) > 0
        assert_markdown_valid(result)
        assert "Simple Document" in result

    def test_asciidoc_to_asciidoc_roundtrip(self) -> None:
        """Test round-trip AsciiDoc -> AST -> AsciiDoc conversion."""
        original = create_simple_asciidoc()

        parser = AsciiDocParser()
        doc = parser.parse(original)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert "Simple Document" in result
        assert "simple paragraph" in result

    def test_asciidoc_with_options(self) -> None:
        """Test AsciiDoc parsing with custom options."""
        asciidoc = create_asciidoc_with_attributes()

        options = AsciiDocParserOptions(
            parse_attributes=True,
            resolve_attribute_refs=True
        )
        parser = AsciiDocParser(options=options)
        doc = parser.parse(asciidoc)

        # Check that attributes were parsed
        assert "title" in doc.metadata
        assert doc.metadata["title"] == "Test Document with Attributes"
        assert doc.metadata["author"] == "John Doe"


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocContentTypes:
    """Test AsciiDoc conversion with different content types."""

    def test_formatting_conversion(self) -> None:
        """Test conversion of formatted text."""
        asciidoc = create_asciidoc_with_formatting()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find strong (bold) nodes
        def find_nodes_of_type(node, node_type):
            nodes = []
            if isinstance(node, node_type):
                nodes.append(node)
            if hasattr(node, 'children'):
                for child in node.children:
                    nodes.extend(find_nodes_of_type(child, node_type))
            if hasattr(node, 'content') and isinstance(node.content, list):
                for child in node.content:
                    nodes.extend(find_nodes_of_type(child, node_type))
            return nodes

        strong_nodes = find_nodes_of_type(doc, Strong)
        emphasis_nodes = find_nodes_of_type(doc, Emphasis)
        code_nodes = find_nodes_of_type(doc, Code)

        assert len(strong_nodes) > 0
        assert len(emphasis_nodes) > 0
        assert len(code_nodes) > 0

    def test_lists_conversion(self) -> None:
        """Test conversion of lists."""
        asciidoc = create_asciidoc_with_lists()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find list nodes
        lists = [child for child in doc.children if isinstance(child, List)]
        assert len(lists) > 0

        # Check for ordered and unordered lists
        ordered_lists = [lst for lst in lists if lst.ordered]
        unordered_lists = [lst for lst in lists if not lst.ordered]

        assert len(ordered_lists) > 0
        assert len(unordered_lists) > 0

    def test_tables_conversion(self) -> None:
        """Test conversion of tables."""
        asciidoc = create_asciidoc_with_tables()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find table nodes
        tables = [child for child in doc.children if isinstance(child, Table)]
        assert len(tables) > 0

        # Check first table has header and rows
        first_table = tables[0]
        assert first_table.header is not None
        assert len(first_table.rows) > 0

    def test_code_blocks_conversion(self) -> None:
        """Test conversion of code blocks."""
        asciidoc = create_asciidoc_with_code_blocks()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find code block nodes
        code_blocks = [child for child in doc.children if isinstance(child, CodeBlock)]
        assert len(code_blocks) > 0

        # Verify code block content is preserved
        assert any("def factorial" in cb.content for cb in code_blocks)

    def test_links_and_images_conversion(self) -> None:
        """Test conversion of links and images."""
        asciidoc = create_asciidoc_with_links_and_images()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find link and image nodes
        def find_nodes_of_type(node, node_type):
            nodes = []
            if isinstance(node, node_type):
                nodes.append(node)
            if hasattr(node, 'children'):
                for child in node.children:
                    nodes.extend(find_nodes_of_type(child, node_type))
            if hasattr(node, 'content') and isinstance(node.content, list):
                for child in node.content:
                    nodes.extend(find_nodes_of_type(child, node_type))
            return nodes

        links = find_nodes_of_type(doc, Link)
        images = find_nodes_of_type(doc, Image)

        assert len(links) > 0
        assert len(images) > 0


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocFormatting:
    """Test AsciiDoc conversion preserves formatting."""

    def test_formatting_preservation(self) -> None:
        """Test that formatting is preserved through conversion."""
        asciidoc = create_asciidoc_with_formatting()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        # Check that formatting is present in markdown output
        assert "**bold text**" in result or "*bold text*" in result
        assert "_italic text_" in result or "*italic text*" in result
        assert "`inline code`" in result

    def test_superscript_subscript(self) -> None:
        """Test superscript and subscript conversion."""
        asciidoc = create_asciidoc_with_formatting()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find superscript and subscript nodes
        def find_nodes_of_type(node, node_type):
            nodes = []
            if isinstance(node, node_type):
                nodes.append(node)
            if hasattr(node, 'children'):
                for child in node.children:
                    nodes.extend(find_nodes_of_type(child, node_type))
            if hasattr(node, 'content') and isinstance(node.content, list):
                for child in node.content:
                    nodes.extend(find_nodes_of_type(child, node_type))
            return nodes

        superscript_nodes = find_nodes_of_type(doc, Superscript)
        subscript_nodes = find_nodes_of_type(doc, Subscript)

        assert len(superscript_nodes) > 0
        assert len(subscript_nodes) > 0

    def test_block_quote_preservation(self) -> None:
        """Test that block quotes are preserved."""
        asciidoc = create_asciidoc_with_formatting()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find block quote nodes
        quotes = [child for child in doc.children if isinstance(child, BlockQuote)]
        assert len(quotes) > 0


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocRoundTrip:
    """Test round-trip conversion (AsciiDoc -> AST -> AsciiDoc)."""

    def test_roundtrip_headings(self) -> None:
        """Test round-trip preservation of headings."""
        original = """= Title

== Section

=== Subsection
"""
        parser = AsciiDocParser()
        doc = parser.parse(original)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "= Title" in result
        assert "== Section" in result
        assert "=== Subsection" in result

    def test_roundtrip_lists(self) -> None:
        """Test round-trip preservation of lists."""
        original = """* Item 1
* Item 2

. First
. Second
"""
        parser = AsciiDocParser()
        doc = parser.parse(original)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_roundtrip_code_blocks(self) -> None:
        """Test round-trip preservation of code blocks."""
        original = """----
def hello():
    print("world")
----
"""
        parser = AsciiDocParser()
        doc = parser.parse(original)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "----" in result
        assert "def hello():" in result
        assert 'print("world")' in result

    def test_roundtrip_tables(self) -> None:
        """Test round-trip preservation of tables."""
        original = """|===
|Name |Age

|Alice
|25

|Bob
|30
|===
"""
        parser = AsciiDocParser()
        doc = parser.parse(original)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "|===" in result
        assert "Alice" in result
        assert "Bob" in result


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocOptions:
    """Test AsciiDoc options in integration scenarios."""

    def test_parser_with_attributes(self) -> None:
        """Test parsing with attribute resolution."""
        asciidoc = create_asciidoc_with_attributes()

        options = AsciiDocParserOptions(
            parse_attributes=True,
            resolve_attribute_refs=True
        )
        parser = AsciiDocParser(options=options)
        doc = parser.parse(asciidoc)

        assert "title" in doc.metadata
        assert "author" in doc.metadata

    def test_parser_without_attributes(self) -> None:
        """Test parsing without attribute parsing."""
        asciidoc = create_asciidoc_with_attributes()

        options = AsciiDocParserOptions(parse_attributes=False)
        parser = AsciiDocParser(options=options)
        doc = parser.parse(asciidoc)

        # Attributes should not be in metadata
        assert len(doc.metadata) == 0 or "title" not in doc.metadata

    def test_renderer_heading_style_atx(self) -> None:
        """Test renderer with ATX heading style."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Heading(level=2, content=[Text(content="Section")])
        ])

        options = AsciiDocOptions(heading_style="atx")
        renderer = AsciiDocRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "= Title" in result
        assert "== Section" in result

    def test_renderer_heading_style_setext(self) -> None:
        """Test renderer with setext heading style for levels 1-2."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Heading(level=2, content=[Text(content="Section")])
        ])

        options = AsciiDocOptions(heading_style="setext")
        renderer = AsciiDocRenderer(options=options)
        result = renderer.render_to_string(doc)

        # Setext style uses underlines for levels 1-2
        assert "Title" in result
        assert "Section" in result

    def test_renderer_with_attributes(self) -> None:
        """Test renderer including metadata as attributes."""
        doc = Document(
            metadata={"title": "Test Doc", "author": "Test Author"},
            children=[
                Heading(level=1, content=[Text(content="Content")])
            ]
        )

        options = AsciiDocOptions(use_attributes=True)
        renderer = AsciiDocRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert ":title:" in result
        assert ":author:" in result


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocCrossFormat:
    """Test converting from other formats to AsciiDoc via AST."""

    def test_markdown_to_asciidoc(self) -> None:
        """Test converting Markdown to AsciiDoc."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        markdown = """# Title

This is a paragraph with **bold** and *italic* text.

- Item 1
- Item 2

```python
print("hello")
```
"""
        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "= Title" in result
        # Lists should be present (even if content isn't fully preserved)
        assert "*" in result  # List markers
        assert "----" in result  # Code block delimiter

    def test_ast_to_asciidoc(self) -> None:
        """Test creating AST programmatically and rendering to AsciiDoc."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Test Document")]),
            Paragraph(content=[
                Text(content="This has "),
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=".")
            ]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ])
        ])

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "= Test Document" in result
        assert "*bold*" in result
        assert "_italic_" in result
        assert "* Item 1" in result


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_nested_formatting(self) -> None:
        """Test nested formatting conversion."""
        asciidoc = create_asciidoc_with_nested_formatting()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Check that formatting is preserved
        assert "*" in result  # Bold markers
        assert "_" in result  # Italic markers

    def test_complex_document(self) -> None:
        """Test conversion of complex document with multiple elements."""
        asciidoc = create_asciidoc_complex_document()

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Verify all major element types are present
        has_headings = any(isinstance(child, Heading) for child in doc.children)
        has_paragraphs = any(isinstance(child, Paragraph) for child in doc.children)
        has_lists = any(isinstance(child, List) for child in doc.children)
        has_tables = any(isinstance(child, Table) for child in doc.children)
        has_code_blocks = any(isinstance(child, CodeBlock) for child in doc.children)

        assert has_headings
        assert has_paragraphs
        assert has_lists
        assert has_tables
        assert has_code_blocks

    def test_empty_content(self) -> None:
        """Test handling of empty or minimal content."""
        asciidoc = ""

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert isinstance(doc, Document)
        assert len(doc.children) >= 0

    def test_thematic_break(self) -> None:
        """Test thematic break conversion."""
        asciidoc = """Before break

'''

After break
"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find thematic break
        has_break = any(isinstance(child, ThematicBreak) for child in doc.children)
        assert has_break

    def test_definition_list(self) -> None:
        """Test definition list conversion."""
        asciidoc = """CPU:: The brain of the computer
RAM:: Random Access Memory
"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Find definition list
        def_lists = [child for child in doc.children if isinstance(child, DefinitionList)]
        assert len(def_lists) > 0


@pytest.mark.integration
@pytest.mark.asciidoc
class TestAsciiDocMetadataIntegration:
    """Test metadata handling in integration scenarios."""

    def test_metadata_in_attributes(self) -> None:
        """Test that metadata appears as attributes when rendering."""
        doc = Document(
            metadata={
                "title": "Integration Test",
                "author": "Test Suite",
                "description": "Testing metadata integration"
            },
            children=[
                Paragraph(content=[Text(content="Content here")])
            ]
        )

        options = AsciiDocOptions(use_attributes=True)
        renderer = AsciiDocRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert ":title: Integration Test" in result
        assert ":author: Test Suite" in result
        assert ":description:" in result

    def test_metadata_extraction(self) -> None:
        """Test metadata extraction from AsciiDoc."""
        asciidoc = create_asciidoc_with_attributes()

        options = AsciiDocParserOptions(parse_attributes=True)
        parser = AsciiDocParser(options=options)
        doc = parser.parse(asciidoc)

        assert "title" in doc.metadata
        assert "author" in doc.metadata
        assert "description" in doc.metadata
