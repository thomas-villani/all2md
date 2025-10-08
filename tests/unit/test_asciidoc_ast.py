#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for AsciiDoc parser and renderer."""


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
    Subscript,
    Superscript,
    Table,
    Text,
    ThematicBreak,
)
from all2md.parsers.asciidoc import AsciiDocParser
from all2md.renderers.asciidoc import AsciiDocRenderer


class TestAsciiDocParser:
    """Tests for AsciiDoc parser."""

    def test_simple_text(self) -> None:
        """Test parsing simple text."""
        parser = AsciiDocParser()
        doc = parser.parse("Hello world")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)
        para = doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "Hello world"

    def test_heading_level_1(self) -> None:
        """Test parsing level 1 heading."""
        parser = AsciiDocParser()
        doc = parser.parse("= Title")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)
        heading = doc.children[0]
        assert heading.level == 1
        assert len(heading.content) == 1
        assert isinstance(heading.content[0], Text)
        assert heading.content[0].content == "Title"

    def test_heading_level_2(self) -> None:
        """Test parsing level 2 heading."""
        parser = AsciiDocParser()
        doc = parser.parse("== Section")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)
        heading = doc.children[0]
        assert heading.level == 2
        assert heading.content[0].content == "Section"

    def test_bold_text(self) -> None:
        """Test parsing bold text."""
        parser = AsciiDocParser()
        doc = parser.parse("This is *bold* text")

        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Should have: Text("This is "), Strong([Text("bold")]), Text(" text")
        assert len(para.content) >= 2
        # Find the Strong node
        strong_found = False
        for node in para.content:
            if isinstance(node, Strong):
                strong_found = True
                assert len(node.content) == 1
                assert isinstance(node.content[0], Text)
                assert node.content[0].content == "bold"
        assert strong_found

    def test_italic_text(self) -> None:
        """Test parsing italic text."""
        parser = AsciiDocParser()
        doc = parser.parse("This is _italic_ text")

        para = doc.children[0]
        # Find the Emphasis node
        emphasis_found = False
        for node in para.content:
            if isinstance(node, Emphasis):
                emphasis_found = True
                assert node.content[0].content == "italic"
        assert emphasis_found

    def test_code_inline(self) -> None:
        """Test parsing inline code."""
        parser = AsciiDocParser()
        doc = parser.parse("Use `code` here")

        para = doc.children[0]
        code_found = False
        for node in para.content:
            if isinstance(node, Code):
                code_found = True
                assert node.content == "code"
        assert code_found

    def test_code_block(self) -> None:
        """Test parsing code block."""
        asciidoc = """----
def hello():
    print("world")
----"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert 'def hello():' in code_block.content
        assert 'print("world")' in code_block.content

    def test_unordered_list(self) -> None:
        """Test parsing unordered list."""
        asciidoc = """* Item 1
* Item 2
* Item 3"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)
        list_node = doc.children[0]
        assert not list_node.ordered
        assert len(list_node.items) == 3

    def test_ordered_list(self) -> None:
        """Test parsing ordered list."""
        asciidoc = """. First
. Second
. Third"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)
        list_node = doc.children[0]
        assert list_node.ordered
        assert len(list_node.items) == 3

    def test_link_explicit(self) -> None:
        """Test parsing explicit link."""
        parser = AsciiDocParser()
        doc = parser.parse("Visit link:https://example.com[Example]")

        para = doc.children[0]
        link_found = False
        for node in para.content:
            if isinstance(node, Link):
                link_found = True
                assert node.url == "https://example.com"
                assert node.content[0].content == "Example"
        assert link_found

    def test_link_auto(self) -> None:
        """Test parsing auto-link."""
        parser = AsciiDocParser()
        doc = parser.parse("Visit https://example.com")

        para = doc.children[0]
        link_found = False
        for node in para.content:
            if isinstance(node, Link):
                link_found = True
                assert node.url == "https://example.com"
        assert link_found

    def test_image(self) -> None:
        """Test parsing image."""
        parser = AsciiDocParser()
        doc = parser.parse("image::photo.jpg[Photo]")

        para = doc.children[0]
        image_found = False
        for node in para.content:
            if isinstance(node, Image):
                image_found = True
                assert node.url == "photo.jpg"
                assert node.alt_text == "Photo"
        assert image_found

    def test_thematic_break(self) -> None:
        """Test parsing thematic break."""
        parser = AsciiDocParser()
        doc = parser.parse("'''")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ThematicBreak)

    def test_superscript(self) -> None:
        """Test parsing superscript."""
        parser = AsciiDocParser()
        doc = parser.parse("E=mc^2^")

        para = doc.children[0]
        super_found = False
        for node in para.content:
            if isinstance(node, Superscript):
                super_found = True
                assert node.content[0].content == "2"
        assert super_found

    def test_subscript(self) -> None:
        """Test parsing subscript."""
        parser = AsciiDocParser()
        doc = parser.parse("H~2~O")

        para = doc.children[0]
        sub_found = False
        for node in para.content:
            if isinstance(node, Subscript):
                sub_found = True
                assert node.content[0].content == "2"
        assert sub_found

    def test_table_simple(self) -> None:
        """Test parsing simple table."""
        asciidoc = """|===
|Header 1 |Header 2
|Cell 1 |Cell 2
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Table)
        table = doc.children[0]
        assert table.header is not None
        assert len(table.header.cells) == 2
        assert len(table.rows) == 1


class TestAsciiDocRenderer:
    """Tests for AsciiDoc renderer."""

    def test_render_simple_text(self) -> None:
        """Test rendering simple text."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello world")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "Hello world" in output

    def test_render_heading(self) -> None:
        """Test rendering heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "= Title" in output

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "*bold*" in output

    def test_render_italic(self) -> None:
        """Test rendering italic text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" text")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "_italic_" in output

    def test_render_code_inline(self) -> None:
        """Test rendering inline code."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Use "),
                Code(content="code"),
                Text(content=" here")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "`code`" in output

    def test_render_code_block(self) -> None:
        """Test rendering code block."""
        doc = Document(children=[
            CodeBlock(content='def hello():\n    print("world")', language="python")
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "[source,python]" in output
        assert "----" in output
        assert "def hello():" in output

    def test_render_list(self) -> None:
        """Test rendering list."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "* Item 1" in output
        assert "* Item 2" in output

    def test_render_link(self) -> None:
        """Test rendering link."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Visit "),
                Link(url="https://example.com", content=[Text(content="Example")])
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "link:https://example.com[Example]" in output

    def test_render_image(self) -> None:
        """Test rendering image."""
        doc = Document(children=[
            Paragraph(content=[
                Image(url="photo.jpg", alt_text="Photo")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "image::photo.jpg[Photo]" in output

    def test_render_thematic_break(self) -> None:
        """Test rendering thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "'''" in output


class TestAsciiDocRoundTrip:
    """Tests for round-trip conversion (parse -> render)."""

    def test_roundtrip_heading(self) -> None:
        """Test round-trip for heading."""
        original = "= Title"
        parser = AsciiDocParser()
        renderer = AsciiDocRenderer()

        doc = parser.parse(original)
        output = renderer.render_to_string(doc)

        assert "= Title" in output

    def test_roundtrip_paragraph(self) -> None:
        """Test round-trip for paragraph."""
        original = "Hello world"
        parser = AsciiDocParser()
        renderer = AsciiDocRenderer()

        doc = parser.parse(original)
        output = renderer.render_to_string(doc)

        assert "Hello world" in output

    def test_roundtrip_formatting(self) -> None:
        """Test round-trip for formatted text."""
        original = "This is *bold* and _italic_ text"
        parser = AsciiDocParser()
        renderer = AsciiDocRenderer()

        doc = parser.parse(original)
        output = renderer.render_to_string(doc)

        assert "*bold*" in output
        assert "_italic_" in output

    def test_roundtrip_code_block(self) -> None:
        """Test round-trip for code block."""
        original = """----
code here
----"""
        parser = AsciiDocParser()
        renderer = AsciiDocRenderer()

        doc = parser.parse(original)
        output = renderer.render_to_string(doc)

        assert "----" in output
        assert "code here" in output
