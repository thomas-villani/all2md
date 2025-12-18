#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_latex_renderer.py
"""Unit tests for LaTeX rendering from AST.

Tests cover:
- Basic LaTeX rendering
- Heading level mapping
- Table rendering with spans
- List rendering (ordered/unordered)
- Math rendering (inline/display)
- Code blocks
- Inline formatting
- Links and images
- Footnotes
- Comments (various modes)
- Block quotes
- Special character escaping
- Document preamble
- File output
- Edge cases

"""

from io import StringIO
from pathlib import Path

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
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
    MathBlock,
    MathInline,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.exceptions import InvalidOptionsError
from all2md.options.latex import LatexRendererOptions
from all2md.renderers.latex import LatexRenderer


def create_simple_document(content: str) -> Document:
    """Helper to create a simple document with a paragraph.

    Parameters
    ----------
    content : str
        Text content for the paragraph

    Returns
    -------
    Document
        AST Document with single paragraph

    """
    return Document(children=[Paragraph(content=[Text(content=content)])])


def create_heading_document(title: str, level: int = 1) -> Document:
    """Helper to create a document with a heading.

    Parameters
    ----------
    title : str
        Heading text
    level : int
        Heading level (1-6)

    Returns
    -------
    Document
        AST Document with heading

    """
    return Document(children=[Heading(level=level, content=[Text(content=title)])])


def create_table_document(headers: list[str], rows: list[list[str]]) -> Document:
    """Helper to create a document with a table.

    Parameters
    ----------
    headers : list[str]
        Column headers
    rows : list[list[str]]
        Row data

    Returns
    -------
    Document
        AST Document with table

    """
    header_row = TableRow(cells=[TableCell(content=[Text(content=h)]) for h in headers])
    data_rows = [TableRow(cells=[TableCell(content=[Text(content=cell)]) for cell in row]) for row in rows]

    return Document(children=[Table(header=header_row, rows=data_rows)])


@pytest.mark.unit
class TestLatexBasicRendering:
    """Tests for basic LaTeX rendering functionality."""

    def test_render_simple_paragraph(self) -> None:
        """Test rendering a simple paragraph."""
        doc = create_simple_document("Hello, World!")
        renderer = LatexRenderer()
        result = renderer.render_to_string(doc)

        assert "Hello, World!" in result

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = LatexRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)
        assert "\\documentclass" in result
        assert "\\end{document}" in result

    def test_render_without_preamble(self) -> None:
        """Test rendering without document preamble."""
        doc = create_simple_document("Content only")
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\documentclass" not in result
        assert "\\begin{document}" not in result
        assert "Content only" in result


@pytest.mark.unit
class TestLatexHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1(self) -> None:
        """Test level 1 heading becomes section."""
        doc = create_heading_document("Introduction", level=1)
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\section{Introduction}" in result

    def test_heading_level_2(self) -> None:
        """Test level 2 heading becomes subsection."""
        doc = create_heading_document("Details", level=2)
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\subsection{Details}" in result

    def test_heading_level_3(self) -> None:
        """Test level 3 heading becomes subsubsection."""
        doc = create_heading_document("Specifics", level=3)
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\subsubsection{Specifics}" in result

    def test_heading_level_4(self) -> None:
        """Test level 4 heading becomes paragraph."""
        doc = create_heading_document("Point", level=4)
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\paragraph{Point}" in result

    def test_heading_level_5(self) -> None:
        """Test level 5 heading becomes subparagraph."""
        doc = create_heading_document("Subpoint", level=5)
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\subparagraph{Subpoint}" in result


@pytest.mark.unit
class TestLatexTableRendering:
    """Tests for table rendering."""

    def test_simple_table(self) -> None:
        """Test rendering a simple table."""
        doc = create_table_document(["Name", "Age"], [["Alice", "30"]])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{tabular}" in result
        assert "\\end{tabular}" in result
        assert "Name" in result
        assert "Alice" in result
        assert "\\hline" in result

    def test_table_with_colspan(self) -> None:
        """Test table with colspan."""
        header_row = TableRow(
            cells=[
                TableCell(content=[Text(content="Merged")], colspan=2),
            ]
        )
        data_rows = [
            TableRow(
                cells=[
                    TableCell(content=[Text(content="A")]),
                    TableCell(content=[Text(content="B")]),
                ]
            )
        ]
        doc = Document(children=[Table(header=header_row, rows=data_rows)])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\multicolumn{2}" in result
        assert "Merged" in result

    def test_table_with_rowspan(self) -> None:
        """Test table with rowspan."""
        header_row = TableRow(
            cells=[
                TableCell(content=[Text(content="H1")]),
                TableCell(content=[Text(content="H2")]),
            ]
        )
        data_rows = [
            TableRow(
                cells=[
                    TableCell(content=[Text(content="Spanning")], rowspan=2),
                    TableCell(content=[Text(content="B1")]),
                ]
            ),
            TableRow(
                cells=[
                    TableCell(content=[Text(content="B2")]),
                ]
            ),
        ]
        doc = Document(children=[Table(header=header_row, rows=data_rows)])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\multirow{2}" in result
        assert "Spanning" in result

    def test_empty_table(self) -> None:
        """Test handling empty table."""
        doc = Document(children=[Table(header=None, rows=[])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)


@pytest.mark.unit
class TestLatexListRendering:
    """Tests for list rendering."""

    def test_unordered_list(self) -> None:
        """Test rendering unordered list."""
        list_items = [
            ListItem(children=[Paragraph(content=[Text(content="First")])]),
            ListItem(children=[Paragraph(content=[Text(content="Second")])]),
        ]
        doc = Document(children=[List(items=list_items, ordered=False)])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{itemize}" in result
        assert "\\end{itemize}" in result
        assert "\\item First" in result

    def test_ordered_list(self) -> None:
        """Test rendering ordered list."""
        list_items = [
            ListItem(children=[Paragraph(content=[Text(content="Step 1")])]),
            ListItem(children=[Paragraph(content=[Text(content="Step 2")])]),
        ]
        doc = Document(children=[List(items=list_items, ordered=True)])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{enumerate}" in result
        assert "\\end{enumerate}" in result
        assert "\\item Step 1" in result


@pytest.mark.unit
class TestLatexMathRendering:
    """Tests for math rendering."""

    def test_inline_math(self) -> None:
        """Test inline math rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="The formula is "),
                        MathInline(content="E=mc^2"),
                        Text(content="."),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "$E=mc^2$" in result

    def test_math_block(self) -> None:
        """Test display math block rendering."""
        doc = Document(children=[MathBlock(content="\\int_0^1 x^2 dx")])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{equation}" in result
        assert "\\int_0^1 x^2 dx" in result
        assert "\\end{equation}" in result


@pytest.mark.unit
class TestLatexCodeRendering:
    """Tests for code rendering."""

    def test_code_block(self) -> None:
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="print('hello')", language="python")])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{verbatim}" in result
        assert "print('hello')" in result
        assert "\\end{verbatim}" in result

    def test_inline_code(self) -> None:
        """Test inline code rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Use "),
                        Code(content="print()"),
                        Text(content=" function"),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\texttt{print()}" in result


@pytest.mark.unit
class TestLatexInlineFormatting:
    """Tests for inline formatting."""

    def test_emphasis(self) -> None:
        """Test emphasis (italic) rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="emphasized")])])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\emph{emphasized}" in result

    def test_strong(self) -> None:
        """Test strong (bold) rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\textbf{bold}" in result

    def test_underline(self) -> None:
        """Test underline rendering."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\underline{underlined}" in result

    def test_strikethrough(self) -> None:
        """Test strikethrough rendering."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\sout{deleted}" in result

    def test_superscript(self) -> None:
        """Test superscript rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="x"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\textsuperscript{2}" in result

    def test_subscript(self) -> None:
        """Test subscript rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="H"),
                        Subscript(content=[Text(content="2")]),
                        Text(content="O"),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\textsubscript{2}" in result


@pytest.mark.unit
class TestLatexLinksAndImages:
    """Tests for link and image rendering."""

    def test_link(self) -> None:
        """Test link rendering."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Click here")])])]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\href{https://example.com}{Click here}" in result

    def test_image(self) -> None:
        """Test image rendering."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Test image")])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\includegraphics{image.png}" in result

    def test_image_with_dimensions(self) -> None:
        """Test image rendering with width/height."""
        doc = Document(children=[Paragraph(content=[Image(url="photo.jpg", alt_text="Photo", width=100, height=50)])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\includegraphics[" in result
        assert "width=100pt" in result
        assert "height=50pt" in result


@pytest.mark.unit
class TestLatexFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_reference(self) -> None:
        """Test footnote reference rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Some text"),
                        FootnoteReference(identifier="1"),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\footnotemark[1]" in result

    def test_footnote_definition(self) -> None:
        """Test footnote definition rendering."""
        doc = Document(
            children=[
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote content")])])
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\footnotetext[1]{Footnote content}" in result


@pytest.mark.unit
class TestLatexComments:
    """Tests for comment rendering modes."""

    def test_comment_percent_mode(self) -> None:
        """Test comment rendering in percent mode."""
        doc = Document(children=[Comment(content="This is a comment", metadata={})])
        options = LatexRendererOptions(include_preamble=False, comment_mode="percent")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "% This is a comment" in result

    def test_comment_todonotes_mode(self) -> None:
        """Test comment rendering in todonotes mode."""
        doc = Document(children=[Comment(content="Review this", metadata={"author": "Alice"})])
        options = LatexRendererOptions(include_preamble=False, comment_mode="todonotes")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\todo" in result
        assert "Review this" in result

    def test_comment_marginnote_mode(self) -> None:
        """Test comment rendering in marginnote mode."""
        doc = Document(children=[Comment(content="Note", metadata={})])
        options = LatexRendererOptions(include_preamble=False, comment_mode="marginnote")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\marginpar{Note}" in result

    def test_comment_ignore_mode(self) -> None:
        """Test that comments are ignored in ignore mode."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text")]),
                Comment(content="Hidden comment", metadata={}),
            ]
        )
        options = LatexRendererOptions(include_preamble=False, comment_mode="ignore")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Hidden comment" not in result
        assert "Text" in result

    def test_inline_comment_percent_mode(self) -> None:
        """Test inline comment in percent mode."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="inline note", metadata={}),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False, comment_mode="percent")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "% inline note" in result


@pytest.mark.unit
class TestLatexBlockQuote:
    """Tests for block quote rendering."""

    def test_block_quote(self) -> None:
        """Test block quote rendering."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="A wise saying")])])])
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\begin{quote}" in result
        assert "A wise saying" in result
        assert "\\end{quote}" in result


@pytest.mark.unit
class TestLatexThematicBreak:
    """Tests for thematic break rendering."""

    def test_thematic_break(self) -> None:
        """Test thematic break rendering."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\hrulefill" in result


@pytest.mark.unit
class TestLatexLineBreak:
    """Tests for line break rendering."""

    def test_hard_line_break(self) -> None:
        """Test hard line break rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\\\" in result

    def test_soft_line_break(self) -> None:
        """Test soft line break rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Word1"),
                        LineBreak(soft=True),
                        Text(content="Word2"),
                    ]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Word1 Word2" in result


@pytest.mark.unit
class TestLatexSpecialCharacters:
    """Tests for special character escaping."""

    def test_escape_ampersand(self) -> None:
        """Test escaping ampersand."""
        doc = create_simple_document("Tom & Jerry")
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert r"\&" in result

    def test_escape_dollar(self) -> None:
        """Test escaping dollar sign."""
        doc = create_simple_document("$100")
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert r"\$100" in result

    def test_escape_percent(self) -> None:
        """Test escaping percent sign."""
        doc = create_simple_document("50%")
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert r"\%}" in result or r"\%" in result

    def test_escape_underscore(self) -> None:
        """Test escaping underscore."""
        doc = create_simple_document("file_name")
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert r"\_" in result

    def test_escape_disabled(self) -> None:
        """Test with escaping disabled."""
        doc = create_simple_document("$100 & 50%")
        options = LatexRendererOptions(include_preamble=False, escape_special=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "$100 & 50%" in result


@pytest.mark.unit
class TestLatexPreamble:
    """Tests for document preamble."""

    def test_custom_document_class(self) -> None:
        """Test custom document class."""
        doc = create_simple_document("Content")
        options = LatexRendererOptions(document_class="report")
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\documentclass{report}" in result

    def test_custom_packages(self) -> None:
        """Test custom packages."""
        doc = create_simple_document("Content")
        options = LatexRendererOptions(packages=["amsmath", "geometry"])
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\usepackage{amsmath}" in result
        assert "\\usepackage{geometry}" in result

    def test_document_with_metadata(self) -> None:
        """Test document with title/author metadata."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Body")])],
            metadata={"title": "My Document", "author": "John Doe"},
        )
        renderer = LatexRenderer()
        result = renderer.render_to_string(doc)

        assert "\\title{My Document}" in result
        assert "\\author{John Doe}" in result
        assert "\\maketitle" in result


@pytest.mark.unit
class TestLatexFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file_path(self, tmp_path: Path) -> None:
        """Test rendering to file path."""
        doc = create_simple_document("Output test")
        output_file = tmp_path / "output.tex"

        renderer = LatexRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "Output test" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Test rendering to Path object."""
        doc = create_simple_document("Path output")
        output_file = tmp_path / "output.tex"

        renderer = LatexRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        doc = create_simple_document("Stream test")
        output = StringIO()

        renderer = LatexRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "Stream test" in result


@pytest.mark.unit
class TestLatexEdgeCases:
    """Tests for edge cases."""

    def test_nested_formatting(self) -> None:
        """Test nested inline formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Strong(content=[Text(content="Bold and "), Emphasis(content=[Text(content="italic")])])]
                )
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "\\textbf{Bold and \\emph{italic}}" in result

    def test_multiple_paragraphs(self) -> None:
        """Test multiple paragraphs with spacing."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        result = renderer.render_to_string(doc)

        assert "First paragraph" in result
        assert "Second paragraph" in result
        # Paragraphs should be separated by blank lines
        assert "\n\n" in result

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            LatexRenderer(options="invalid")

    def test_unsupported_output_type(self) -> None:
        """Test that unsupported output type raises error."""
        doc = create_simple_document("Content")
        renderer = LatexRenderer()

        with pytest.raises(TypeError):
            renderer.render(doc, 12345)  # type: ignore

    def test_line_width_validation(self) -> None:
        """Test that negative line width raises error."""
        with pytest.raises(ValueError):
            LatexRendererOptions(line_width=-1)
