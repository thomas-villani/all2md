"""LaTeX fixture generators for TeX-to-Markdown regression tests."""

from __future__ import annotations

from io import BytesIO


def create_basic_latex_document() -> str:
    """Return a LaTeX article with sections, lists, and emphasis."""
    return (
        "\\documentclass{article}\n"
        "\\title{Fixture Sample}\n"
        "\\author{Test Author}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\section{Introduction}\n"
        "This paragraph contains \\textbf{bold} and \\emph{italic} text.\\\n"
        "\\section{Lists}\n"
        "\\begin{itemize}\n"
        "  \\item First item\n"
        "  \\item Second item with a nested list\\\n"
        "  \\begin{enumerate}\n"
        "    \\item Nested entry one\\\n"
        "    \\item Nested entry two\\\n"
        "  \\end{enumerate}\n"
        "\\end{itemize}\n"
        "\\section{Table}\n"
        "\\begin{tabular}{lcr}\n"
        "Name & Role & Score\\\\\n"
        "Alice & Developer & 95\\\\\n"
        "Bob & Designer & 88\\\\\n"
        "\\end{tabular}\n"
        "\\end{document}\n"
    )


def create_latex_with_math() -> str:
    """Return a LaTeX document emphasising inline and block math."""
    return (
        "\\documentclass{article}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "Inline math such as $E = mc^2$ should render properly.\\\n"
        "\\[\\int_0^1 x^2 \\; dx = \\frac{1}{3}\\]\n"
        "\\begin{align}\n"
        "f(x) &= x^2 + 2x + 1\\\\\n"
        "g(x) &= \\frac{x^3}{3} - x\\n"
        "\\end{align}\n"
        "\\end{document}\n"
    )


def latex_to_bytes(text: str, encoding: str = "utf-8") -> bytes:
    """Encode LaTeX source for IO usage."""
    return text.encode(encoding)


def latex_bytes_io(text: str, encoding: str = "utf-8") -> BytesIO:
    """Return a BytesIO stream from LaTeX content."""
    return BytesIO(latex_to_bytes(text, encoding=encoding))
