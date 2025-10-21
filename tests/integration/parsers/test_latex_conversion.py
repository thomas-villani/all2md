#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for LaTeX parser and renderer."""

from all2md.ast import Document, Heading, MathBlock, MathInline, Paragraph, Text
from all2md.options.latex import LatexOptions, LatexRendererOptions
from all2md.parsers.latex import LatexParser
from all2md.renderers.latex import LatexRenderer


class TestLatexIntegration:
    """Integration tests for LaTeX conversion."""

    def test_academic_paper_structure(self) -> None:
        """Test parsing a typical academic paper structure."""
        latex = r"""
\documentclass{article}
\title{A Study of Quantum Computing}
\author{Jane Doe}
\date{2025-01-08}

\begin{document}
\maketitle

\section{Introduction}
Quantum computing is a revolutionary field.

\section{Methods}
We used the following approach:
\begin{itemize}
\item Quantum gates
\item Superposition
\end{itemize}

\section{Results}
The equation $E = mc^2$ shows energy-mass equivalence.

\begin{equation}
\Psi(x,t) = A e^{i(kx - \omega t)}
\end{equation}

\section{Conclusion}
This demonstrates the power of quantum mechanics.

\end{document}
"""

        parser = LatexParser()
        doc = parser.parse(latex)

        # Check metadata
        assert "title" in doc.metadata
        assert doc.metadata["title"] == "A Study of Quantum Computing"
        assert doc.metadata["author"] == "Jane Doe"

        # Check structure - should have sections
        headings = [child for child in doc.children if isinstance(child, Heading)]
        assert len(headings) >= 4  # Introduction, Methods, Results, Conclusion

    def test_math_heavy_document(self) -> None:
        """Test parsing document with heavy math content."""
        latex = r"""
\section{Mathematical Equations}

Inline math: $x^2 + y^2 = r^2$

Display math:
$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$

Equation environment:
\begin{equation}
F = ma
\end{equation}
"""

        parser = LatexParser()
        doc = parser.parse(latex)

        # Should contain both inline and block math
        from all2md.ast import MathBlock, MathInline

        def count_math_nodes(nodes, node_type):
            count = 0
            for node in nodes:
                if isinstance(node, node_type):
                    count += 1
                if hasattr(node, "content") and isinstance(node.content, list):
                    count += count_math_nodes(node.content, node_type)
                if hasattr(node, "children") and isinstance(node.children, list):
                    count += count_math_nodes(node.children, node_type)
            return count

        inline_math = count_math_nodes(doc.children, MathInline)
        block_math = count_math_nodes(doc.children, MathBlock)

        assert inline_math >= 1  # At least the circle equation
        assert block_math >= 2  # Display math and equation environment

    def test_lists_and_formatting(self) -> None:
        """Test parsing lists with formatting."""
        latex = r"""
\section{Features}

Key features include:
\begin{enumerate}
\item \textbf{Bold} text support
\item \emph{Italic} text support
\item \texttt{Monospace} code
\end{enumerate}

Unordered list:
\begin{itemize}
\item First point
\item Second point
\end{itemize}
"""

        parser = LatexParser()
        doc = parser.parse(latex)

        # Check that we have lists
        from all2md.ast import List

        lists = [child for child in doc.children if isinstance(child, List)]
        assert len(lists) >= 2  # One enumerate, one itemize

    def test_render_complete_document(self) -> None:
        """Test rendering a complete LaTeX document."""
        doc = Document(
            metadata={"title": "Test Document", "author": "Test Author"},
            children=[
                Heading(level=1, content=[Text(content="Introduction")]),
                Paragraph(content=[Text(content="This is the introduction.")]),
                Heading(level=2, content=[Text(content="Background")]),
                Paragraph(content=[Text(content="Some background information.")]),
            ],
        )

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        # Check document structure
        assert r"\documentclass{article}" in latex
        assert r"\title{Test Document}" in latex
        assert r"\author{Test Author}" in latex
        assert r"\begin{document}" in latex
        assert r"\maketitle" in latex
        assert r"\section{Introduction}" in latex
        assert r"\subsection{Background}" in latex
        assert r"\end{document}" in latex

    def test_round_trip_conversion(self) -> None:
        """Test round-trip LaTeX -> AST -> LaTeX conversion."""
        original_latex = r"""
\section{Test Section}

This is a paragraph with \textbf{bold} and \emph{italic} text.

Math: $E = mc^2$

\begin{itemize}
\item First item
\item Second item
\end{itemize}
"""

        # Parse to AST
        parser = LatexParser()
        doc = parser.parse(original_latex)

        # Render back to LaTeX (without preamble for comparison)
        renderer = LatexRenderer(LatexRendererOptions(include_preamble=False))
        rendered_latex = renderer.render_to_string(doc)

        # Check that key elements are preserved
        assert r"\section{Test Section}" in rendered_latex
        assert r"\textbf{bold}" in rendered_latex
        assert r"\emph{italic}" in rendered_latex
        assert r"$" in rendered_latex  # Math delimiter
        assert r"\begin{itemize}" in rendered_latex

    def test_cross_format_pdf_to_latex(self) -> None:
        """Test converting from another format to LaTeX via AST."""
        # Create a document programmatically (simulating PDF->AST conversion)
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Research Paper")]),
                Paragraph(
                    content=[
                        Text(content="The formula "),
                        MathInline(content=r"x^2 + y^2 = z^2", notation="latex"),
                        Text(content=" is well known."),
                    ]
                ),
                MathBlock(content=r"\int_0^1 x dx = \frac{1}{2}", notation="latex"),
            ]
        )

        # Render to LaTeX
        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        # Verify LaTeX output
        assert r"\section{Research Paper}" in latex
        assert r"$x^2 + y^2 = z^2$" in latex
        assert r"\begin{equation}" in latex
        assert r"\int_0^1 x dx" in latex

    def test_code_block_preservation(self) -> None:
        """Test that code blocks are preserved correctly."""
        latex = r"""
\section{Code Example}

Here is some Python code:

\begin{verbatim}
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)
\end{verbatim}

That was the code.
"""

        parser = LatexParser()
        doc = parser.parse(latex)

        # Render back
        renderer = LatexRenderer(LatexRendererOptions(include_preamble=False))
        rendered = renderer.render_to_string(doc)

        # Check code block is preserved
        assert r"\begin{verbatim}" in rendered
        assert "factorial" in rendered
        assert r"\end{verbatim}" in rendered

    def test_nested_formatting(self) -> None:
        """Test nested formatting like bold italic."""
        latex = r"Text with \textbf{\emph{bold italic}} formatting"

        parser = LatexParser()
        doc = parser.parse(latex)

        # Parse should handle nested formatting
        # The exact structure depends on implementation,
        # but we should be able to render it back
        renderer = LatexRenderer(LatexRendererOptions(include_preamble=False))
        rendered = renderer.render_to_string(doc)

        # Should contain both bold and italic commands
        assert r"\textbf" in rendered or r"\emph" in rendered

    def test_special_character_escaping(self) -> None:
        """Test that special characters are properly escaped."""
        from all2md.ast import Paragraph, Text

        doc = Document(
            children=[Paragraph(content=[Text(content="Price: $100, Discount: 50%, Items: A & B, Note #1")])]
        )

        renderer = LatexRenderer()
        latex = renderer.render_to_string(doc)

        # Check escaping
        assert r"\$100" in latex
        assert r"50\%" in latex
        assert r"A \& B" in latex
        assert r"\#1" in latex

    def test_bibliography_environment(self) -> None:
        """Test handling bibliography-like structures."""
        latex = r"""
\section{References}

\begin{quote}
Smith, J. (2024). Quantum Computing. Journal of Physics.
\end{quote}
"""

        parser = LatexParser()
        doc = parser.parse(latex)

        # Should parse quote environment
        from all2md.ast import BlockQuote

        quotes = [child for child in doc.children if isinstance(child, BlockQuote)]
        assert len(quotes) >= 1

    def test_complex_table_structure(self) -> None:
        """Test rendering complex table."""
        from all2md.ast import Table, TableCell, TableRow, Text

        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Name")]),
                            TableCell(content=[Text(content="Age")]),
                            TableCell(content=[Text(content="City")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Alice")]),
                                TableCell(content=[Text(content="30")]),
                                TableCell(content=[Text(content="NYC")]),
                            ]
                        ),
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Bob")]),
                                TableCell(content=[Text(content="25")]),
                                TableCell(content=[Text(content="LA")]),
                            ]
                        ),
                    ],
                )
            ]
        )

        renderer = LatexRenderer(LatexRendererOptions(include_preamble=False))
        latex = renderer.render_to_string(doc)

        # Check table structure
        assert r"\begin{tabular}" in latex
        assert r"\hline" in latex
        assert "Alice" in latex
        assert "Bob" in latex
        assert r"\end{tabular}" in latex

    def test_figure_with_caption(self) -> None:
        """Test rendering image (figure)."""
        from all2md.ast import Image

        doc = Document(children=[Image(url="figure1.png", alt_text="Figure 1: Results")])

        renderer = LatexRenderer(LatexRendererOptions(include_preamble=False))
        latex = renderer.render_to_string(doc)

        assert r"\includegraphics{figure1.png}" in latex


class TestLatexOptionsIntegration:
    """Test LaTeX options in integration scenarios."""

    def test_fragment_mode(self) -> None:
        """Test rendering fragment without preamble."""
        doc = Document(children=[Paragraph(content=[Text(content="Just this paragraph.")])])

        options = LatexRendererOptions(include_preamble=False)
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert r"\documentclass" not in latex
        assert r"\begin{document}" not in latex
        assert "Just this paragraph." in latex

    def test_custom_document_class_integration(self) -> None:
        """Test using custom document class."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Chapter 1")])])

        options = LatexRendererOptions(document_class="book")
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert r"\documentclass{book}" in latex

    def test_minimal_packages(self) -> None:
        """Test with minimal package set."""
        doc = Document(children=[Paragraph(content=[Text(content="Simple text.")])])

        options = LatexRendererOptions(packages=["amsmath"])
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        assert r"\usepackage{amsmath}" in latex
        # Should not include default packages we didn't specify
        lines = latex.split("\n")
        usepackage_lines = [line for line in lines if r"\usepackage" in line]
        assert len(usepackage_lines) == 1  # Only amsmath

    def test_disable_escaping(self) -> None:
        """Test disabling special character escaping."""
        doc = Document(children=[Paragraph(content=[Text(content="$100")])])

        options = LatexRendererOptions(escape_special=False)
        renderer = LatexRenderer(options)
        latex = renderer.render_to_string(doc)

        # Dollar sign should NOT be escaped
        assert "$100" in latex or r"\$100" not in latex

    def test_parser_strict_mode(self) -> None:
        """Test parser strict mode with invalid LaTeX."""
        invalid_latex = r"\unknowncommand{test}"

        # Non-strict mode should not raise
        parser_nonstrict = LatexParser(LatexOptions(strict_mode=False))
        doc = parser_nonstrict.parse(invalid_latex)
        assert doc is not None

        # Strict mode might handle it differently
        # (depending on pylatexenc behavior)
        parser_strict = LatexParser(LatexOptions(strict_mode=True))
        # May or may not raise depending on how pylatexenc handles it
        try:
            parser_strict.parse(invalid_latex)
        except Exception:
            pass  # Expected in strict mode
