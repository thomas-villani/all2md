#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for LaTeX parser and renderer."""


from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    Underline,
)
from all2md.options import LatexOptions, LatexParserOptions
from all2md.parsers.latex import LatexParser
from all2md.renderers.latex import LatexRenderer


class TestLatexParser:
    """Tests for LaTeX parser."""

    def test_simple_text(self) -> None:
        """Test parsing simple text."""
        parser = LatexParser()
        doc = parser.parse("Hello world")

        assert len(doc.children) >= 1
        # Find text in children
        has_hello = any(
            isinstance(child, Paragraph) and
            any(isinstance(node, Text) and "Hello" in node.content for node in child.content)
            for child in doc.children
        )
        assert has_hello or any(
            isinstance(child, Text) and "Hello" in child.content
            for child in doc.children
        )

    def test_section_heading(self) -> None:
        """Test parsing section heading."""
        parser = LatexParser()
        doc = parser.parse(r"\section{Introduction}")

        # Find heading in children
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) >= 1

        heading = headings[0]
        assert heading.level == 1
        assert len(heading.content) >= 1
        assert any("Introduction" in getattr(node, 'content', '') for node in heading.content)

    def test_subsection_heading(self) -> None:
        """Test parsing subsection heading."""
        parser = LatexParser()
        doc = parser.parse(r"\subsection{Methods}")

        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) >= 1
        assert headings[0].level == 2

    def test_textbf_bold(self) -> None:
        """Test parsing bold text."""
        parser = LatexParser()
        doc = parser.parse(r"This is \textbf{bold} text")

        # Find Strong node in tree
        def has_strong(nodes):
            for node in nodes:
                if isinstance(node, Strong):
                    return True
                if isinstance(node, (Paragraph, ListItem)) and hasattr(node, 'content'):
                    if has_strong(node.content):
                        return True
                if isinstance(node, (List, BlockQuote)) and hasattr(node, 'children'):
                    if has_strong(node.children):
                        return True
            return False

        assert has_strong(doc.children)

    def test_emph_italic(self) -> None:
        """Test parsing italic text."""
        parser = LatexParser()
        doc = parser.parse(r"This is \emph{italic} text")

        # Find Emphasis node in tree
        def has_emphasis(nodes):
            for node in nodes:
                if isinstance(node, Emphasis):
                    return True
                if isinstance(node, (Paragraph, ListItem)) and hasattr(node, 'content'):
                    if has_emphasis(node.content):
                        return True
                if isinstance(node, (List, BlockQuote)) and hasattr(node, 'children'):
                    if has_emphasis(node.children):
                        return True
            return False

        assert has_emphasis(doc.children)

    def test_texttt_code(self) -> None:
        """Test parsing inline code."""
        parser = LatexParser()
        doc = parser.parse(r"Code: \texttt{print('hello')}")

        # Find Code node in tree
        def has_code(nodes):
            for node in nodes:
                if isinstance(node, Code):
                    return True
                if isinstance(node, (Paragraph, ListItem)) and hasattr(node, 'content'):
                    if has_code(node.content):
                        return True
                if isinstance(node, (List, BlockQuote)) and hasattr(node, 'children'):
                    if has_code(node.children):
                        return True
            return False

        assert has_code(doc.children)

    def test_math_inline(self) -> None:
        """Test parsing inline math."""
        parser = LatexParser()
        doc = parser.parse(r"Equation $E = mc^2$ is famous")

        # Find MathInline node
        def has_math_inline(nodes):
            for node in nodes:
                if isinstance(node, MathInline):
                    return True
                if isinstance(node, (Paragraph, ListItem)) and hasattr(node, 'content'):
                    if has_math_inline(node.content):
                        return True
                if isinstance(node, (List, BlockQuote)) and hasattr(node, 'children'):
                    if has_math_inline(node.children):
                        return True
            return False

        assert has_math_inline(doc.children)

    def test_math_display(self) -> None:
        """Test parsing display math."""
        parser = LatexParser()
        doc = parser.parse(r"$$E = mc^2$$")

        # Find MathBlock node
        math_blocks = [child for child in doc.children if isinstance(child, MathBlock)]
        assert len(math_blocks) >= 1

    def test_equation_environment(self) -> None:
        """Test parsing equation environment."""
        parser = LatexParser()
        doc = parser.parse(r"\begin{equation}x^2 + y^2 = z^2\end{equation}")

        # Find MathBlock node
        math_blocks = [child for child in doc.children if isinstance(child, MathBlock)]
        assert len(math_blocks) >= 1

    def test_itemize_list(self) -> None:
        """Test parsing itemize environment."""
        parser = LatexParser()
        latex = r"""
\begin{itemize}
\item First item
\item Second item
\end{itemize}
"""
        doc = parser.parse(latex)

        # Find List node
        lists = [child for child in doc.children if isinstance(child, List)]
        assert len(lists) >= 1
        assert lists[0].ordered is False

    def test_enumerate_list(self) -> None:
        """Test parsing enumerate environment."""
        parser = LatexParser()
        latex = r"""
\begin{enumerate}
\item First
\item Second
\end{enumerate}
"""
        doc = parser.parse(latex)

        # Find List node
        lists = [child for child in doc.children if isinstance(child, List)]
        assert len(lists) >= 1
        assert lists[0].ordered is True

    def test_quote_environment(self) -> None:
        """Test parsing quote environment."""
        parser = LatexParser()
        latex = r"\begin{quote}This is a quote\end{quote}"
        doc = parser.parse(latex)

        # Find BlockQuote node
        quotes = [child for child in doc.children if isinstance(child, BlockQuote)]
        assert len(quotes) >= 1

    def test_verbatim_environment(self) -> None:
        """Test parsing verbatim environment."""
        parser = LatexParser()
        latex = r"""
\begin{verbatim}
def hello():
    print("world")
\end{verbatim}
"""
        doc = parser.parse(latex)

        # Find CodeBlock node
        code_blocks = [child for child in doc.children if isinstance(child, CodeBlock)]
        assert len(code_blocks) >= 1

    def test_metadata_extraction(self) -> None:
        """Test extracting metadata from preamble."""
        parser = LatexParser()
        latex = r"""
\title{My Document}
\author{John Doe}
\date{2025-01-01}
\begin{document}
Content here
\end{document}
"""
        doc = parser.parse(latex)

        assert 'title' in doc.metadata
        assert doc.metadata['title'] == 'My Document'
        assert 'author' in doc.metadata
        assert doc.metadata['author'] == 'John Doe'


class TestLatexRenderer:
    """Tests for LaTeX renderer."""

    def test_render_simple_text(self) -> None:
        """Test rendering simple text."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello world")])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert "Hello world" in latex
        assert r"\documentclass" in latex  # Has preamble by default

    def test_render_heading_level_1(self) -> None:
        """Test rendering level 1 heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Introduction")])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\section{Introduction}" in latex

    def test_render_heading_level_2(self) -> None:
        """Test rendering level 2 heading."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Methods")])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\subsection{Methods}" in latex

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text")
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\textbf{bold}" in latex

    def test_render_italic(self) -> None:
        """Test rendering italic text."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" text")
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\emph{italic}" in latex

    def test_render_code(self) -> None:
        """Test rendering inline code."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Code: "),
                Code(content="x = 42")
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\texttt{x = 42}" in latex

    def test_render_math_inline(self) -> None:
        """Test rendering inline math."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Equation "),
                MathInline(content="E = mc^2", notation="latex"),
                Text(content=" is famous")
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert "$E = mc^2$" in latex

    def test_render_math_block(self) -> None:
        """Test rendering display math."""
        doc = Document(children=[
            MathBlock(content="E = mc^2", notation="latex")
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{equation}" in latex
        assert "E = mc^2" in latex
        assert r"\end{equation}" in latex

    def test_render_unordered_list(self) -> None:
        """Test rendering unordered list."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="First")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second")])])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{itemize}" in latex
        assert r"\item First" in latex
        assert r"\item Second" in latex
        assert r"\end{itemize}" in latex

    def test_render_ordered_list(self) -> None:
        """Test rendering ordered list."""
        doc = Document(children=[
            List(ordered=True, items=[
                ListItem(children=[Paragraph(content=[Text(content="First")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second")])])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{enumerate}" in latex
        assert r"\item First" in latex
        assert r"\item Second" in latex
        assert r"\end{enumerate}" in latex

    def test_render_blockquote(self) -> None:
        """Test rendering block quote."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="This is a quote")])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{quote}" in latex
        assert "This is a quote" in latex
        assert r"\end{quote}" in latex

    def test_render_code_block(self) -> None:
        """Test rendering code block."""
        code_content = """def hello():
    print("world")"""

        doc = Document(children=[
            CodeBlock(content=code_content)
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{verbatim}" in latex
        assert "def hello():" in latex
        assert r'\end{verbatim}' in latex

    def test_render_table(self) -> None:
        """Test rendering table."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Age")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alice")]),
                        TableCell(content=[Text(content="30")])
                    ])
                ]
            )
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\begin{tabular}" in latex
        assert "Name" in latex
        assert "Age" in latex
        assert "Alice" in latex
        assert r"\end{tabular}" in latex

    def test_render_link(self) -> None:
        """Test rendering link."""
        doc = Document(children=[
            Paragraph(content=[
                Link(url="https://example.com", content=[Text(content="Example")])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\href{https://example.com}{Example}" in latex

    def test_render_image(self) -> None:
        """Test rendering image."""
        doc = Document(children=[
            Image(url="image.png", alt_text="A picture")
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\includegraphics{image.png}" in latex

    def test_render_without_preamble(self) -> None:
        """Test rendering without preamble."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Just content")])
        ])

        options = LatexOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert "Just content" in latex
        assert r"\documentclass" not in latex
        assert r"\begin{document}" not in latex

    def test_escape_special_characters(self) -> None:
        """Test escaping special LaTeX characters."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Price: $100 & 50%")])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        # Check that special chars are escaped
        assert r"\$" in latex
        assert r"\&" in latex
        assert r"\%" in latex

    def test_render_superscript(self) -> None:
        """Test rendering superscript."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="x"),
                Superscript(content=[Text(content="2")])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\textsuperscript{2}" in latex

    def test_render_subscript(self) -> None:
        """Test rendering subscript."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="H"),
                Subscript(content=[Text(content="2")]),
                Text(content="O")
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\textsubscript{2}" in latex

    def test_render_underline(self) -> None:
        """Test rendering underline."""
        doc = Document(children=[
            Paragraph(content=[
                Underline(content=[Text(content="underlined")])
            ])
        ])

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        assert r"\underline{underlined}" in latex

    def test_round_trip_simple(self) -> None:
        """Test round-trip conversion for simple content."""
        # Create AST
        original = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Some text")])
        ])

        # Render to LaTeX
        renderer = LatexRenderer(LatexOptions(include_preamble=False))
        latex = renderer.render_to_string(original)

        # Parse back
        parser = LatexParser()
        parsed = parser.parse(latex)

        # Check structure is preserved
        assert len([c for c in parsed.children if isinstance(c, Heading)]) >= 1
        # Content should be present
        latex_content = renderer.render_to_string(parsed)
        assert "Title" in latex_content


class TestLatexOptions:
    """Tests for LaTeX options."""

    def test_parser_options_defaults(self) -> None:
        """Test default parser options."""
        options = LatexParserOptions()

        assert options.parse_preamble is True
        assert options.parse_math is True
        assert options.parse_custom_commands is False
        assert options.strict_mode is False
        assert options.encoding == "utf-8"

    def test_renderer_options_defaults(self) -> None:
        """Test default renderer options."""
        options = LatexOptions()

        assert options.document_class == "article"
        assert options.include_preamble is True
        assert "amsmath" in options.packages
        assert "graphicx" in options.packages
        assert options.math_mode == "display"
        assert options.escape_special is True
        assert options.use_unicode is True

    def test_custom_document_class(self) -> None:
        """Test custom document class."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ])

        options = LatexOptions(document_class="report")
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert r"\documentclass{report}" in latex

    def test_custom_packages(self) -> None:
        """Test custom packages."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Content")])
        ])

        options = LatexOptions(packages=["geometry", "fancyhdr"])
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert r"\usepackage{geometry}" in latex
        assert r"\usepackage{fancyhdr}" in latex
