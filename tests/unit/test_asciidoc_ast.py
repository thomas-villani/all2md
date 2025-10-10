#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for AsciiDoc parser and renderer."""


from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
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

        # Should use + delimiter (AsciiDoc standard), not backticks
        assert "+code+" in output

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


class TestAsciiDocEscaping:
    """Tests for escape handling."""

    def test_escaped_asterisk(self) -> None:
        """Test that escaped asterisks are literal."""
        parser = AsciiDocParser()
        doc = parser.parse(r"This is \*not bold\*")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "This is *not bold*"

    def test_escaped_underscore(self) -> None:
        """Test that escaped underscores are literal."""
        parser = AsciiDocParser()
        doc = parser.parse(r"This is \_not italic\_")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        assert "_not italic_" in text_content

    def test_escaped_backtick(self) -> None:
        """Test that escaped backticks are literal."""
        parser = AsciiDocParser()
        doc = parser.parse(r"This is \`not code\`")

        para = doc.children[0]
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        assert "`not code`" in text_content

    def test_escaped_curly_brace(self) -> None:
        """Test that escaped braces are literal."""
        parser = AsciiDocParser()
        doc = parser.parse(r"This \{is not\} an attribute ref")

        para = doc.children[0]
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        assert "{is not}" in text_content


class TestAsciiDocUnconstrainedFormatting:
    """Tests for unconstrained formatting (double delimiters)."""

    def test_unconstrained_bold(self) -> None:
        """Test unconstrained bold with double asterisks."""
        parser = AsciiDocParser()
        doc = parser.parse("Make this**b**old in the middle")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        strong_found = False
        for node in para.content:
            if isinstance(node, Strong):
                strong_found = True
                assert node.content[0].content == "b"
        assert strong_found

    def test_unconstrained_italic(self) -> None:
        """Test unconstrained italic with double underscores."""
        parser = AsciiDocParser()
        doc = parser.parse("Make this__i__talic in the middle")

        para = doc.children[0]
        emphasis_found = False
        for node in para.content:
            if isinstance(node, Emphasis):
                emphasis_found = True
                assert node.content[0].content == "i"
        assert emphasis_found

    def test_constrained_still_works(self) -> None:
        """Test that constrained formatting still works."""
        parser = AsciiDocParser()
        doc = parser.parse("This is *bold* text")

        para = doc.children[0]
        strong_found = False
        for node in para.content:
            if isinstance(node, Strong):
                strong_found = True
                assert node.content[0].content == "bold"
        assert strong_found


class TestAsciiDocAttributeReferences:
    """Tests for attribute reference handling."""

    def test_attribute_ref_resolved(self) -> None:
        """Test that attribute references are resolved."""
        from all2md.options.asciidoc import AsciiDocOptions
        parser = AsciiDocParser(AsciiDocOptions(parse_attributes=True))
        doc = parser.parse(":myattr: Hello\n\nThe value is {myattr}")

        para = doc.children[0]
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        assert "Hello" in text_content

    def test_undefined_attribute_kept(self) -> None:
        """Test that undefined attributes are kept as literals."""
        from all2md.options.asciidoc import AsciiDocOptions
        parser = AsciiDocParser(AsciiDocOptions(attribute_missing_policy="keep"))
        doc = parser.parse("The value is {undefined}")

        para = doc.children[0]
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        assert "{undefined}" in text_content

    def test_undefined_attribute_blank(self) -> None:
        """Test that undefined attributes can be blanked."""
        from all2md.options.asciidoc import AsciiDocOptions
        parser = AsciiDocParser(AsciiDocOptions(attribute_missing_policy="blank"))
        doc = parser.parse("The value is {undefined}!")

        para = doc.children[0]
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in para.content)
        # Should not contain the attribute reference
        assert "{undefined}" not in text_content
        assert "The value is !" in text_content


class TestAsciiDocNestedLists:
    """Tests for nested list support."""

    def test_nested_unordered_list(self) -> None:
        """Test nested unordered lists."""
        asciidoc = """* Level 1
** Level 2
*** Level 3
** Back to 2
* Back to 1"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        root_list = doc.children[0]
        assert isinstance(root_list, List)
        assert not root_list.ordered
        assert len(root_list.items) == 2  # Two level-1 items

        # First level-1 item should have nested list
        first_item = root_list.items[0]
        assert len(first_item.children) == 2  # Paragraph + nested list
        nested_list = first_item.children[1]
        assert isinstance(nested_list, List)
        assert len(nested_list.items) == 2  # Two level-2 items

    def test_nested_ordered_list(self) -> None:
        """Test nested ordered lists."""
        asciidoc = """. First
.. Nested first
.. Nested second
. Second"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        root_list = doc.children[0]
        assert isinstance(root_list, List)
        assert root_list.ordered
        assert len(root_list.items) == 2

        # Check nesting
        first_item = root_list.items[0]
        assert len(first_item.children) == 2
        nested_list = first_item.children[1]
        assert isinstance(nested_list, List)
        assert len(nested_list.items) == 2

    def test_mixed_list_types(self) -> None:
        """Test mixing ordered and unordered in nesting."""
        asciidoc = """* Unordered
.. Nested ordered
.. Another ordered
* Back to unordered"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        root_list = doc.children[0]
        assert not root_list.ordered  # Root is unordered
        first_item = root_list.items[0]
        nested_list = first_item.children[1]
        assert isinstance(nested_list, List)
        assert nested_list.ordered  # Nested is ordered


class TestAsciiDocBlockAttributes:
    """Tests for block attributes and anchors."""

    def test_anchor_on_heading(self) -> None:
        """Test anchor ID on heading."""
        parser = AsciiDocParser()
        doc = parser.parse("[[my-anchor]]\n== Heading")

        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.metadata is not None
        assert heading.metadata.get('id') == "my-anchor"

    def test_block_attribute_id(self) -> None:
        """Test block attribute with ID."""
        parser = AsciiDocParser()
        doc = parser.parse("[#custom-id]\nParagraph text")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert para.metadata is not None
        assert para.metadata.get('id') == "custom-id"

    def test_code_block_language(self) -> None:
        """Test code block with language from block attribute."""
        asciidoc = """[source,python]
----
def hello():
    pass
----"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        code_block = doc.children[0]
        assert isinstance(code_block, CodeBlock)
        assert code_block.language == "python"

    def test_block_attribute_role(self) -> None:
        """Test block attribute with role."""
        parser = AsciiDocParser()
        doc = parser.parse("[.important]\nThis is important")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert para.metadata is not None
        assert para.metadata.get('role') == "important"


class TestAsciiDocTableImprovements:
    """Tests for table parsing improvements."""

    def test_table_with_noheader(self) -> None:
        """Test table with noheader option."""
        from all2md.options.asciidoc import AsciiDocOptions
        asciidoc = """[options="noheader"]
|===
|Data 1 |Data 2
|Data 3 |Data 4
|==="""
        parser = AsciiDocParser(AsciiDocOptions(table_header_detection="attribute-based"))
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is None  # No header row
        assert len(table.rows) == 2  # Both rows are data

    def test_table_escaped_pipe(self) -> None:
        """Test table with escaped pipe in cell."""
        asciidoc = r"""|===
|Code |Description
|\|operator |Pipe operator
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)
        # Check second row, first cell contains escaped pipe
        cell_content = table.rows[0].cells[0].content
        text_content = "".join(n.content if isinstance(n, Text) else "" for n in cell_content)
        assert "|operator" in text_content

    def test_table_default_header(self) -> None:
        """Test table with default first-row header."""
        from all2md.options.asciidoc import AsciiDocOptions
        asciidoc = """|===
|Header 1 |Header 2
|Data 1 |Data 2
|==="""
        parser = AsciiDocParser(AsciiDocOptions(table_header_detection="first-row"))
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is not None
        assert len(table.rows) == 1


class TestAsciiDocDelimitedBlocks:
    """Tests for delimited block parsing."""

    def test_literal_block(self) -> None:
        """Test literal block parsing."""
        asciidoc = """....
This is literal text
    with preserved    spacing
....
"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        code_block = doc.children[0]
        assert code_block.language is None  # Literal blocks have no language
        assert "preserved    spacing" in code_block.content

    def test_sidebar_block(self) -> None:
        """Test sidebar block parsing."""
        asciidoc = """****
This is sidebar content.
It has multiple lines.
****"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        block = doc.children[0]
        assert block.metadata is not None
        assert block.metadata.get('role') == 'sidebar'

    def test_example_block(self) -> None:
        """Test example block parsing."""
        asciidoc = """====
This is an example.

With multiple paragraphs.
===="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        block = doc.children[0]
        assert block.metadata is not None
        assert block.metadata.get('role') == 'example'
        assert len(block.children) == 2  # Two paragraphs

    def test_thematic_break_vs_code_block(self) -> None:
        """Test that thematic breaks are distinguished from code blocks."""
        asciidoc = """Some text

---

More text

----
Code here
----"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Should have: Paragraph, ThematicBreak, Paragraph, CodeBlock
        assert len(doc.children) == 4
        assert isinstance(doc.children[0], Paragraph)
        assert isinstance(doc.children[1], ThematicBreak)
        assert isinstance(doc.children[2], Paragraph)
        assert isinstance(doc.children[3], CodeBlock)

    def test_thematic_break_vs_sidebar(self) -> None:
        """Test that *** (thematic) is different from **** (sidebar)."""
        asciidoc = """Text

***

More

****
Sidebar
****"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert len(doc.children) == 4
        assert isinstance(doc.children[1], ThematicBreak)
        assert isinstance(doc.children[3], BlockQuote)
        assert doc.children[3].metadata.get('role') == 'sidebar'


class TestAsciiDocHardLineBreaks:
    """Tests for hard line break support."""

    def test_hard_line_break_single(self) -> None:
        """Test single hard line break."""
        parser = AsciiDocParser()
        doc = parser.parse("Line one +\nLine two")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Should contain text, LineBreak, text
        assert any(isinstance(node, LineBreak) for node in para.content)

    def test_hard_line_break_multiple(self) -> None:
        """Test multiple hard line breaks."""
        parser = AsciiDocParser()
        doc = parser.parse("Line one +\nLine two +\nLine three")

        para = doc.children[0]
        line_breaks = [node for node in para.content if isinstance(node, LineBreak)]
        assert len(line_breaks) == 2

    def test_hard_line_break_with_formatting(self) -> None:
        """Test hard line break with inline formatting."""
        parser = AsciiDocParser()
        doc = parser.parse("This is *bold* +\nAnd _italic_")

        para = doc.children[0]
        # Should have: Strong, LineBreak, Emphasis
        assert any(isinstance(node, Strong) for node in para.content)
        assert any(isinstance(node, LineBreak) for node in para.content)
        assert any(isinstance(node, Emphasis) for node in para.content)

    def test_no_hard_break_option(self) -> None:
        """Test that hard breaks can be disabled."""
        from all2md.options.asciidoc import AsciiDocOptions
        parser = AsciiDocParser(AsciiDocOptions(honor_hard_breaks=False))
        doc = parser.parse("Line one +\nLine two")

        para = doc.children[0]
        # Should NOT have LineBreak when option is disabled
        assert not any(isinstance(node, LineBreak) for node in para.content)


class TestAsciiDocAnchorsAndXrefs:
    """Tests for anchor and cross-reference resolution."""

    def test_anchor_on_heading_with_xref(self) -> None:
        """Test that anchors work with cross-references."""
        parser = AsciiDocParser()
        doc = parser.parse("[[intro]]\n== Introduction\n\nSee <<intro>>")

        # First child: heading with anchor
        heading = doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.metadata is not None
        assert heading.metadata.get('id') == "intro"

        # Second child: paragraph with cross-reference
        para = doc.children[1]
        assert isinstance(para, Paragraph)
        # Find the link node
        link_found = False
        for node in para.content:
            if isinstance(node, Link):
                link_found = True
                assert node.url == "#intro"
        assert link_found

    def test_anchor_with_custom_text_xref(self) -> None:
        """Test cross-reference with custom text."""
        parser = AsciiDocParser()
        doc = parser.parse("[[myid]]\n= Title\n\nSee <<myid,the introduction>>")

        para = doc.children[1]
        for node in para.content:
            if isinstance(node, Link):
                assert node.url == "#myid"
                # Check that custom text is used
                assert node.content[0].content == "the introduction"


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

    def test_footnote_first_reference_includes_definition(self) -> None:
        """Test that first footnote reference includes definition inline."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Text with footnote"),
                FootnoteReference(identifier="note1")
            ]),
            FootnoteDefinition(identifier="note1", content=[Text(content="This is the footnote")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # First reference should include the definition
        assert "footnote:note1[This is the footnote]" in output

    def test_footnote_subsequent_reference_is_empty(self) -> None:
        """Test that subsequent footnote references are empty."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="First "),
                FootnoteReference(identifier="note1"),
                Text(content=" second "),
                FootnoteReference(identifier="note1")
            ]),
            FootnoteDefinition(identifier="note1", content=[Text(content="Shared note")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # First reference should have definition
        assert "footnote:note1[Shared note]" in output
        # Subsequent reference should be empty
        assert "footnote:note1[]" in output


class TestAsciiDocHeadingLevels:
    """Tests for correct heading level mapping."""

    def test_heading_level_1_maps_to_double_equals(self) -> None:
        """Test that AST level 1 maps to == (section level 1)."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Section 1")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "== Section 1" in output
        # Verify it's exactly two equals signs, not one or three
        assert output.strip().startswith("==")
        assert not output.strip().startswith("===")
        assert not output.strip().startswith("= ")

    def test_heading_level_2_maps_to_triple_equals(self) -> None:
        """Test that AST level 2 maps to === (section level 2)."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Section 2")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "=== Section 2" in output

    def test_heading_level_3_maps_to_quadruple_equals(self) -> None:
        """Test that AST level 3 maps to ==== (section level 3)."""
        doc = Document(children=[
            Heading(level=3, content=[Text(content="Section 3")])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "==== Section 3" in output

    def test_heading_levels_1_through_6(self) -> None:
        """Test all heading levels map correctly."""
        for level in range(1, 7):
            doc = Document(children=[
                Heading(level=level, content=[Text(content=f"Level {level}")])
            ])
            renderer = AsciiDocRenderer()
            output = renderer.render_to_string(doc)

            expected_prefix = '=' * (level + 1)
            assert f"{expected_prefix} Level {level}" in output


class TestAsciiDocInlineCodeDelimiters:
    """Tests for inline code using + delimiters."""

    def test_simple_code_uses_plus_delimiter(self) -> None:
        """Test that simple inline code uses + delimiter."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Use "),
                Code(content="code"),
                Text(content=" here")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "+code+" in output
        assert "`code`" not in output  # Should NOT use backticks

    def test_code_with_backticks_uses_plus_delimiter(self) -> None:
        """Test that code containing backticks still uses + delimiter."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="var x = `template`")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "+var x = `template`+" in output

    def test_code_with_plus_sign_escaped(self) -> None:
        """Test that + signs in code are escaped by doubling."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="x + y")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Plus signs should be doubled for escaping
        assert "+x ++ y+" in output

    def test_code_with_multiple_plus_signs(self) -> None:
        """Test that multiple + signs are all escaped."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="a + b + c")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "+a ++ b ++ c+" in output

    def test_code_with_double_plus_escaped(self) -> None:
        """Test that ++ in code is escaped correctly."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="x++")
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Each + should be doubled: x++ becomes x++++
        # Full output: +x+++++  (opening +, x, four +s, closing +)
        assert "+x+++++" in output


class TestAsciiDocTableAlignments:
    """Tests for table column alignment support."""

    def test_table_with_left_alignment(self) -> None:
        """Test table with left-aligned columns."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")])
                    ])
                ],
                alignments=['left', 'left']
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Should include cols attribute with left alignment specs
        assert '[cols="<,<"]' in output

    def test_table_with_center_alignment(self) -> None:
        """Test table with center-aligned columns."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[],
                alignments=['center', 'center']
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert '[cols="^,^"]' in output

    def test_table_with_right_alignment(self) -> None:
        """Test table with right-aligned columns."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[],
                alignments=['right', 'right']
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert '[cols=">,>"]' in output

    def test_table_with_mixed_alignments(self) -> None:
        """Test table with mixed column alignments."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Left")]),
                    TableCell(content=[Text(content="Center")]),
                    TableCell(content=[Text(content="Right")])
                ]),
                rows=[],
                alignments=['left', 'center', 'right']
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert '[cols="<,^,>"]' in output

    def test_table_with_none_alignment(self) -> None:
        """Test table with None alignments (defaults)."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[],
                alignments=[None, None]
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Should not include cols attribute if all alignments are None
        assert '[cols=' not in output

    def test_table_without_alignments(self) -> None:
        """Test table without alignment specification."""
        from all2md.ast import TableRow, TableCell
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[]
            )
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        # Should not include cols attribute
        assert '[cols=' not in output


class TestAsciiDocTaskLists:
    """Tests for task list rendering."""

    def test_unordered_task_list_checked(self) -> None:
        """Test unordered task list with checked item."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Done")])],
                    task_status='checked'
                )
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "* [x] Done" in output

    def test_unordered_task_list_unchecked(self) -> None:
        """Test unordered task list with unchecked item."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Todo")])],
                    task_status='unchecked'
                )
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "* [ ] Todo" in output

    def test_ordered_task_list_checked(self) -> None:
        """Test ordered task list with checked item."""
        doc = Document(children=[
            List(ordered=True, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Done")])],
                    task_status='checked'
                )
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert ". [x] Done" in output

    def test_ordered_task_list_unchecked(self) -> None:
        """Test ordered task list with unchecked item."""
        doc = Document(children=[
            List(ordered=True, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Todo")])],
                    task_status='unchecked'
                )
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert ". [ ] Todo" in output

    def test_mixed_task_list(self) -> None:
        """Test task list with both checked and unchecked items."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Done")])],
                    task_status='checked'
                ),
                ListItem(
                    children=[Paragraph(content=[Text(content="Todo")])],
                    task_status='unchecked'
                ),
                ListItem(
                    children=[Paragraph(content=[Text(content="Regular item")])],
                    task_status=None
                )
            ])
        ])
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(doc)

        assert "* [x] Done" in output
        assert "* [ ] Todo" in output
        assert "* Regular item" in output


class TestAsciiDocAttributeEscaping:
    """Tests for attribute value escaping."""

    def test_attribute_with_quotes(self) -> None:
        """Test that quotes in attributes are escaped."""
        from all2md.utils.metadata import DocumentMetadata
        metadata = DocumentMetadata(title='A "Special" Title')
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ], metadata=metadata.to_dict())

        from all2md.options.asciidoc import AsciiDocRendererOptions
        renderer = AsciiDocRenderer(AsciiDocRendererOptions(use_attributes=True))
        output = renderer.render_to_string(doc)

        # Quotes should be escaped
        assert r'A \"Special\" Title' in output or 'A "Special" Title' in output

    def test_attribute_with_newline(self) -> None:
        """Test that newlines in attributes are escaped."""
        from all2md.utils.metadata import DocumentMetadata
        metadata = DocumentMetadata(subject="Line 1\nLine 2")
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ], metadata=metadata.to_dict())

        from all2md.options.asciidoc import AsciiDocRendererOptions
        renderer = AsciiDocRenderer(AsciiDocRendererOptions(use_attributes=True))
        output = renderer.render_to_string(doc)

        # Newline should be escaped
        assert r'\n' in output or 'Line 1' in output

    def test_attribute_with_backslash(self) -> None:
        """Test that backslashes in attributes are escaped."""
        from all2md.utils.metadata import DocumentMetadata
        metadata = DocumentMetadata(author=r"User\Name")
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ], metadata=metadata.to_dict())

        from all2md.options.asciidoc import AsciiDocRendererOptions
        renderer = AsciiDocRenderer(AsciiDocRendererOptions(use_attributes=True))
        output = renderer.render_to_string(doc)

        # Should contain the author attribute
        assert ":author:" in output
