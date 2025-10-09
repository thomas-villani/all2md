"""Integration tests for PlainText renderer.

This module contains integration tests for the PlainText renderer,
testing conversion from various formats to plain text with formatting stripped.
"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathInline,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options import PlainTextOptions
from all2md.renderers.plaintext import PlainTextRenderer


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextIntegrationBasic:
    """Test basic PlainText rendering scenarios."""

    def test_simple_document_to_plaintext(self) -> None:
        """Test rendering a simple document to plain text."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="This is a simple paragraph.")])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert "Title" in result
        assert "This is a simple paragraph." in result
        # Headings should not have markdown markers
        assert "#" not in result

    def test_multiple_paragraphs_to_plaintext(self) -> None:
        """Test rendering multiple paragraphs with separators."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First paragraph.")]),
            Paragraph(content=[Text(content="Second paragraph.")]),
            Paragraph(content=[Text(content="Third paragraph.")])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "First paragraph." in result
        assert "Second paragraph." in result
        assert "Third paragraph." in result
        # Should have paragraph separators (double newline by default)
        assert "\n\n" in result

    def test_custom_paragraph_separator(self) -> None:
        """Test rendering with custom paragraph separator."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First")]),
            Paragraph(content=[Text(content="Second")])
        ])

        options = PlainTextOptions(paragraph_separator="\n---\n")
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "First" in result
        assert "Second" in result
        assert "\n---\n" in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextFormatStripping:
    """Test that all formatting is stripped in plain text output."""

    def test_strip_all_formatting(self) -> None:
        """Test that bold, italic, code, etc. are all stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" and "),
                Code(content="code"),
                Text(content=" text.")
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "Normal bold and italic and code text."
        # No markdown or formatting markers
        assert "*" not in result
        assert "_" not in result
        assert "`" not in result

    def test_strip_heading_markers(self) -> None:
        """Test that heading markers are stripped."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Heading(level=2, content=[
                Text(content="Section with "),
                Strong(content=[Text(content="bold")])
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Title" in result
        assert "Section with bold" in result
        # No heading markers
        assert "#" not in result
        assert "==" not in result

    def test_strip_link_urls(self) -> None:
        """Test that link URLs are stripped, keeping only text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Visit "),
                Link(
                    content=[Text(content="our website")],
                    url="https://example.com"
                ),
                Text(content=" for more.")
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "Visit our website for more."
        assert "https://" not in result
        assert "[" not in result
        assert "]" not in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextStructure:
    """Test rendering structured content (lists, tables, etc.)."""

    def test_list_rendering(self) -> None:
        """Test rendering lists with default prefix."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 3")])])
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Item 3" in result

    def test_list_custom_prefix(self) -> None:
        """Test rendering lists with custom prefix."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ])
        ])

        options = PlainTextOptions(list_item_prefix="* ")
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_table_rendering(self) -> None:
        """Test rendering tables with cell separators."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Age")]),
                    TableCell(content=[Text(content="City")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alice")]),
                        TableCell(content=[Text(content="25")]),
                        TableCell(content=[Text(content="NYC")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="Bob")]),
                        TableCell(content=[Text(content="30")]),
                        TableCell(content=[Text(content="LA")])
                    ])
                ]
            )
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        # Check header
        assert "Name | Age | City" in result
        # Check data rows
        assert "Alice | 25 | NYC" in result
        assert "Bob | 30 | LA" in result

    def test_table_custom_separator(self) -> None:
        """Test rendering tables with custom cell separator."""
        doc = Document(children=[
            Table(
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")]),
                        TableCell(content=[Text(content="C")])
                    ])
                ]
            )
        ])

        options = PlainTextOptions(table_cell_separator="\t")
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "A\tB\tC" in result

    def test_table_skip_header(self) -> None:
        """Test rendering tables without header."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Data1")]),
                        TableCell(content=[Text(content="Data2")])
                    ])
                ]
            )
        ])

        options = PlainTextOptions(include_table_headers=False)
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "Col1" not in result
        assert "Data1 | Data2" in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextCodeBlocks:
    """Test code block rendering options."""

    def test_code_block_preserved(self) -> None:
        """Test code blocks are preserved by default."""
        code = """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)"""

        doc = Document(children=[
            CodeBlock(content=code, language="python")
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "def factorial(n):" in result
        assert "return n * factorial(n - 1)" in result
        # Indentation should be preserved
        assert "    if n <= 1:" in result

    def test_code_block_not_preserved(self) -> None:
        """Test code blocks treated as paragraphs when not preserved."""
        code = """def hello():
    print("world")"""

        doc = Document(children=[
            CodeBlock(content=code, language="python")
        ])

        options = PlainTextOptions(preserve_code_blocks=False)
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "def hello():" in result
        assert 'print("world")' in result

    def test_inline_code(self) -> None:
        """Test inline code rendering."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Use the "),
                Code(content="print()"),
                Text(content=" function.")
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "Use the print() function."
        assert "`" not in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextOptions:
    """Test PlainText rendering options."""

    def test_line_wrapping_disabled(self) -> None:
        """Test with line wrapping disabled."""
        long_text = "This is a very long line of text " * 20

        doc = Document(children=[
            Paragraph(content=[Text(content=long_text)])
        ])

        options = PlainTextOptions(max_line_width=None)
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        # Should not wrap (all on one or few lines)
        lines = result.split('\n')
        # Most text should be on a single paragraph block
        assert len([line for line in lines if "very long" in line]) > 0

    def test_line_wrapping_enabled(self) -> None:
        """Test with line wrapping enabled at specific width."""
        long_text = "This is a very long line of text that should be wrapped " * 5

        doc = Document(children=[
            Paragraph(content=[Text(content=long_text)])
        ])

        options = PlainTextOptions(max_line_width=50)
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        # Should wrap to multiple lines
        lines = result.split('\n')
        assert len(lines) > 1
        # Most lines should be <= 50 characters
        long_lines = [line for line in lines if len(line) > 50]
        assert len(long_lines) == 0 or len(long_lines) < len(lines) // 2

    def test_all_options_combined(self) -> None:
        """Test using multiple options together."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First paragraph")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ]),
            Table(
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")])
                    ])
                ]
            )
        ])

        options = PlainTextOptions(
            paragraph_separator="\n\n",
            list_item_prefix=">> ",
            table_cell_separator=" | ",
            max_line_width=None
        )
        renderer = PlainTextRenderer(options=options)
        result = renderer.render_to_string(doc)

        assert "First paragraph" in result
        assert ">> Item 1" in result
        assert ">> Item 2" in result
        assert "A | B" in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextCrossFormat:
    """Test converting various formats to plain text."""

    def test_markdown_to_plaintext(self) -> None:
        """Test converting Markdown to plain text."""
        from all2md.parsers.markdown import MarkdownToAstConverter

        markdown = """# Title

This is a paragraph with **bold** and *italic* text.

- Item 1
- Item 2

[Link text](https://example.com)
"""

        parser = MarkdownToAstConverter()
        doc = parser.parse(markdown)

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Title" in result
        assert "bold and italic" in result
        # Lists should be present (even if content isn't fully preserved by markdown parser)
        assert "-" in result  # List markers
        assert "Link text" in result
        # No markdown markers or URLs
        assert "#" not in result
        assert "**" not in result
        assert "https://" not in result

    def test_html_to_plaintext(self) -> None:
        """Test converting HTML to plain text."""
        from all2md.parsers.html import HtmlToAstConverter

        html = """<html>
<body>
<h1>Title</h1>
<p>This is a <strong>bold</strong> paragraph.</p>
<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>
</body>
</html>"""

        parser = HtmlToAstConverter()
        doc = parser.parse(html)

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Title" in result
        assert "bold" in result
        assert "- Item 1" in result
        # No HTML tags
        assert "<" not in result
        assert ">" not in result

    def test_asciidoc_to_plaintext(self) -> None:
        """Test converting AsciiDoc to plain text."""
        from all2md.parsers.asciidoc import AsciiDocParser

        asciidoc = """= Title

This is a paragraph with *bold* and _italic_ text.

* Item 1
* Item 2

link:https://example.com[Example]
"""

        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Title" in result
        assert "bold and italic" in result
        assert "- Item 1" in result
        assert "Example" in result
        # No AsciiDoc markers or URLs
        assert "=" not in result or result.count("=") < 3
        assert "*" not in result or result.count("*") < 3
        assert "https://" not in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextEdgeCases:
    """Test edge cases and complex scenarios."""

    def test_nested_formatting(self) -> None:
        """Test deeply nested formatting is all stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Strong(content=[
                    Emphasis(content=[
                        Code(content="nested")
                    ])
                ])
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "nested"

    def test_block_quote_extraction(self) -> None:
        """Test block quotes extract text without markers."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="Quoted text here.")])
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "Quoted text here."
        assert ">" not in result

    def test_definition_list_rendering(self) -> None:
        """Test definition list rendering."""
        doc = Document(children=[
            DefinitionList(items=[
                (
                    DefinitionTerm(content=[Text(content="Term 1")]),
                    [DefinitionDescription(content=[
                        Paragraph(content=[Text(content="Definition 1")])
                    ])]
                ),
                (
                    DefinitionTerm(content=[Text(content="Term 2")]),
                    [DefinitionDescription(content=[
                        Paragraph(content=[Text(content="Definition 2")])
                    ])]
                )
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Term 1" in result
        assert "Definition 1" in result
        assert "Term 2" in result
        assert "Definition 2" in result

    def test_image_alt_text(self) -> None:
        """Test images render only alt text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="See "),
                Image(url="photo.jpg", alt_text="the photo"),
                Text(content=" here.")
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == "See the photo here."
        assert ".jpg" not in result

    def test_math_rendering(self) -> None:
        """Test math content is extracted."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Formula: "),
                MathInline(content="x^2 + y^2 = r^2", notation="latex")
            ])
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert "Formula: x^2 + y^2 = r^2" in result

    def test_empty_document(self) -> None:
        """Test empty document handling."""
        doc = Document(children=[])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        assert result == ""

    def test_complex_nested_structure(self) -> None:
        """Test complex nested structure conversion."""
        doc = Document(children=[
            Heading(level=1, content=[
                Text(content="Title with "),
                Strong(content=[Text(content="bold")])
            ]),
            Paragraph(content=[
                Text(content="Intro with "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" and "),
                Link(content=[Text(content="link")], url="http://example.com")
            ]),
            List(ordered=False, items=[
                ListItem(children=[
                    Paragraph(content=[
                        Text(content="Item with "),
                        Code(content="code")
                    ])
                ])
            ]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Strong(content=[Text(content="Header")])])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Emphasis(content=[Text(content="Cell")])])
                    ])
                ]
            )
        ])

        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        # All text should be present
        assert "Title with bold" in result
        assert "Intro with italic and link" in result
        assert "- Item with code" in result
        assert "Header" in result
        assert "Cell" in result

        # No formatting markers or URLs
        assert "**" not in result
        assert "__" not in result
        assert "`" not in result or result.count("`") == 0
        assert "http://" not in result


@pytest.mark.integration
@pytest.mark.plaintext
class TestPlainTextFileOutput:
    """Test file output functionality."""

    def test_render_to_file(self, tmp_path) -> None:
        """Test rendering to file."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Test Document")]),
            Paragraph(content=[Text(content="This is test content.")])
        ])

        renderer = PlainTextRenderer()
        output_file = tmp_path / "output.txt"
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")

        assert "Test Document" in content
        assert "This is test content." in content
        # No markdown markers
        assert "#" not in content
