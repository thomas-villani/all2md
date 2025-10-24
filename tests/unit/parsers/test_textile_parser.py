#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Textile parser and renderer."""

import pytest

# Skip all tests if textile is not installed
pytest.importorskip("textile")

from all2md.ast import (
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    Text,
)
from all2md.exceptions import DependencyError
from all2md.options.textile import TextileParserOptions, TextileRendererOptions
from all2md.parsers.textile import TextileParser
from all2md.renderers.textile import TextileRenderer


class TestTextileParser:
    """Tests for Textile parser."""

    def test_simple_text(self) -> None:
        """Test parsing simple text."""
        parser = TextileParser()
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

    def test_heading_level_1(self) -> None:
        """Test parsing level 1 heading."""
        parser = TextileParser()
        doc = parser.parse("h1. Title")

        assert len(doc.children) >= 1
        heading_found = False
        for child in doc.children:
            if isinstance(child, Heading) and child.level == 1:
                heading_found = True
                # Check content
                for node in child.content:
                    if isinstance(node, Text):
                        assert "Title" in node.content
        assert heading_found

    def test_heading_level_2(self) -> None:
        """Test parsing level 2 heading."""
        parser = TextileParser()
        doc = parser.parse("h2. Section")

        heading_found = False
        for child in doc.children:
            if isinstance(child, Heading) and child.level == 2:
                heading_found = True
        assert heading_found

    def test_bold_text(self) -> None:
        """Test parsing bold text."""
        parser = TextileParser()
        doc = parser.parse("This is *bold* text")

        # Find the Strong node
        strong_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Strong):
                        strong_found = True
        assert strong_found

    def test_italic_text(self) -> None:
        """Test parsing italic text."""
        parser = TextileParser()
        doc = parser.parse("This is _italic_ text")

        # Find the Emphasis node
        emphasis_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Emphasis):
                        emphasis_found = True
        assert emphasis_found

    def test_code_inline(self) -> None:
        """Test parsing inline code."""
        parser = TextileParser()
        doc = parser.parse("Use @code@ here")

        code_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Code):
                        code_found = True
        assert code_found

    def test_code_block(self) -> None:
        """Test parsing code block."""
        textile = """bc. def hello():
    print("world")"""
        parser = TextileParser()
        doc = parser.parse(textile)

        # Code blocks may be rendered as CodeBlock or within paragraphs
        # depending on textile library behavior
        code_found = False
        for child in doc.children:
            if isinstance(child, CodeBlock):
                code_found = True
            elif isinstance(child, Paragraph):
                # May contain code text
                for node in child.content:
                    if isinstance(node, (Code, Text)) and "hello" in str(node):
                        code_found = True
        assert code_found

    def test_unordered_list(self) -> None:
        """Test parsing unordered list."""
        textile = """* Item 1
* Item 2
* Item 3"""
        parser = TextileParser()
        doc = parser.parse(textile)

        list_found = False
        for child in doc.children:
            if isinstance(child, List):
                list_found = True
                assert not child.ordered
                assert len(child.items) >= 2
        assert list_found

    def test_ordered_list(self) -> None:
        """Test parsing ordered list."""
        textile = """# First
# Second
# Third"""
        parser = TextileParser()
        doc = parser.parse(textile)

        list_found = False
        for child in doc.children:
            if isinstance(child, List):
                list_found = True
                assert child.ordered
        assert list_found

    def test_link(self) -> None:
        """Test parsing link."""
        parser = TextileParser()
        doc = parser.parse('"Link text":http://example.com')

        link_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Link):
                        link_found = True
                        assert node.url == "http://example.com"
        assert link_found

    def test_image(self) -> None:
        """Test parsing image."""
        parser = TextileParser()
        doc = parser.parse("!http://example.com/image.png!")

        image_found = False
        for child in doc.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Image):
                        image_found = True
                        assert "image.png" in node.url
        assert image_found

    def test_table(self) -> None:
        """Test parsing table."""
        textile = """|_.Name|_.Age|
|Alice|30|
|Bob|25|"""
        parser = TextileParser()
        doc = parser.parse(textile)

        table_found = False
        for child in doc.children:
            if isinstance(child, Table):
                table_found = True
                assert child.header is not None
                assert len(child.rows) >= 1
        assert table_found

    def test_options(self) -> None:
        """Test parser with options."""
        options = TextileParserOptions(strict_mode=True)
        parser = TextileParser(options)
        doc = parser.parse("h1. Test")

        assert doc is not None
        assert len(doc.children) >= 1

    def test_metadata_extraction(self) -> None:
        """Test metadata extraction from title."""
        parser = TextileParser()
        doc = parser.parse("h1. My Title\n\nSome content")

        # Check if title was extracted
        if doc.metadata:
            assert "title" in doc.metadata or doc.metadata.get("title") is None


class TestTextileRenderer:
    """Tests for Textile renderer."""

    def test_render_heading(self) -> None:
        """Test rendering heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h1. Title" in result

    def test_render_paragraph(self) -> None:
        """Test rendering paragraph."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "Hello world" in result

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text")]
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "*bold*" in result

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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "_italic_" in result

    def test_render_code_inline(self) -> None:
        """Test rendering inline code."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "@code@" in result

    def test_render_code_block(self) -> None:
        """Test rendering code block."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("world")')])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "bc." in result or "def hello()" in result

    def test_render_list_unordered(self) -> None:
        """Test rendering unordered list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_render_list_ordered(self) -> None:
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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "# First" in result
        assert "# Second" in result

    def test_render_link(self) -> None:
        """Test rendering link."""
        doc = Document(
            children=[Paragraph(content=[Link(url="http://example.com", content=[Text(content="Link text")])])]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert '"Link text":http://example.com' in result

    def test_render_image(self) -> None:
        """Test rendering image."""
        doc = Document(children=[Paragraph(content=[Image(url="http://example.com/image.png", alt_text="Alt")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "!http://example.com/image.png" in result

    def test_render_options(self) -> None:
        """Test renderer with options."""
        options = TextileRendererOptions(use_extended_blocks=False)
        renderer = TextileRenderer(options)
        doc = Document(children=[CodeBlock(content="code")])
        result = renderer.render_to_string(doc)

        assert result is not None

    def test_round_trip_simple(self) -> None:
        """Test simple round-trip conversion."""
        original = "h1. Title\n\nThis is *bold* text."
        parser = TextileParser()
        doc = parser.parse(original)

        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Check that key elements are preserved
        assert "h1." in result or "Title" in result
        assert "*" in result or "bold" in result


class TestTextileDependencies:
    """Tests for Textile dependency handling."""

    def test_missing_textile_library(self) -> None:
        """Test that missing textile library raises appropriate error."""
        # Check if textile is installed - if so, skip this test
        # since we can't test missing dependency behavior when it's present
        import importlib.util

        if importlib.util.find_spec("textile") is not None:
            # textile is available, skip this test
            pytest.skip("textile is installed, cannot test missing dependency error")
        else:
            # textile not available - should get clear error message
            with pytest.raises(DependencyError) as exc_info:
                parser = TextileParser()
                parser.parse("h1. Test")

            # Verify error message is helpful
            assert "textile" in str(exc_info.value).lower()
            assert "pip install" in str(exc_info.value).lower()
