r"""Tests for LaTeX math as Unicode text (the terminal renderer's ``math_mode="unicode"``).

The converter must never lose part of a formula: a script Unicode cannot raise
keeps its ``^``, an unknown macro stays as written, and a formula that does
not convert at all comes back as ``None`` so the renderer shows the LaTeX.
"""

from __future__ import annotations

import sys

import pytest

from all2md.ast.nodes import Document, MathBlock, MathInline, Paragraph, Text
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.terminal import TerminalRenderer
from all2md.renderers.terminal_math import latex_to_unicode, text_width

pytest.importorskip("pylatexenc")

NL = chr(10)


def plain(doc: Document, **kwargs) -> str:
    options = TerminalRendererOptions(**{"width": 60, "color_system": "none", **kwargs})
    output = TerminalRenderer(options).render_to_string(doc)
    return NL.join(line.rstrip() for line in output.split(NL)).strip(NL)


@pytest.mark.unit
class TestOneLine:
    @pytest.mark.parametrize(
        "latex, expected",
        [
            (r"\frac{a}{b} + \alpha^2", "a/b + α²"),
            (r"\sum_{i=1}^n x_i", "∑ᵢ₌₁ⁿ xᵢ"),
            (r"E = mc^2", "E = mc²"),
            (r"A^T A^{-1} x^{n + 1}", "Aᵀ A⁻¹ xⁿ⁺¹"),
            (r"x \in \mathbb{R}", "x ∈ ℝ"),
            (r"a \leq b \cdot c", "a ≤ b · c"),
            (r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}", "∇ · E = ρ/ε₀"),
            (r"\operatorname{tr}(A)", "tr(A)"),
            (r"x_{\text{max}}", "xₘₐₓ"),
            (r"f'(x) + f''(x)", "f′(x) + f″(x)"),
            (r"\hat{x} + \vec{v}", "x" + chr(0x302) + " + v" + chr(0x20D7)),
            (r"\overline{ab}", "a" + chr(0x305) + "b" + chr(0x305)),
            (r"\binom{n}{k}", "C(n, k)"),
            (r"\left( \frac{1}{2} \right)", "(½)"),
            (r"\left. \frac{df}{dx} \right|_{x=0}", "df/dx |ₓ₌₀"),
        ],
    )
    def test_converts(self, latex, expected):
        assert latex_to_unicode(latex) == expected

    def test_a_script_unicode_cannot_raise_keeps_its_caret(self):
        assert latex_to_unicode(r"\int_0^\infty e^{-x^2} dx") == "∫₀^∞ e^(-x²) dx"
        assert latex_to_unicode(r"x_{i,j} + x^{*}") == "x_(i,j) + x^*"

    def test_fraction_operands_are_grouped_unless_one_term(self):
        assert latex_to_unicode(r"\frac{a+b}{c-d}") == "(a+b)/(c-d)"
        assert latex_to_unicode(r"\frac{df}{dx}") == "df/dx"
        assert latex_to_unicode(r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}") == "x = (-b ± √(b² - 4ac))/(2a)"
        assert latex_to_unicode(r"\frac{\sqrt{\pi}}{2}") == "√π/2"

    def test_numeric_fractions(self):
        assert latex_to_unicode(r"\frac{1}{2} \frac12 \frac 1 3 \frac{1}{7}") == "½ ½ ⅓ ¹⁄₇"

    def test_roots(self):
        assert latex_to_unicode(r"\sqrt{2} + \sqrt{x+1} + \sqrt[3]{y} + \sqrt[n]{z}") == "√2 + √(x+1) + ∛y + ⁿ√z"

    def test_an_unknown_macro_is_kept_as_written(self):
        assert latex_to_unicode(r"\foo{x} + \mathcal{L}") == r"\foo{x} + ℒ"

    def test_text_keeps_its_spaces(self):
        assert latex_to_unicode(r"x \text{ if  y}") == "x  if  y"

    def test_quad_is_wider_than_a_thin_space(self):
        assert latex_to_unicode(r"a \quad b \, c") == "a    b c"


@pytest.mark.unit
class TestRows:
    def test_cases(self):
        latex = r"f(x) = \begin{cases} 1 & x > 0 \\ 0 & \text{otherwise} \end{cases}"
        assert latex_to_unicode(latex).splitlines() == ["f(x) = ⎧ 1  x > 0", "       ⎩ 0  otherwise"]
        assert latex_to_unicode(latex, inline=True) == "f(x) = {1 x > 0; 0 otherwise}"

    def test_matrix(self):
        latex = r"A = \begin{pmatrix} a & b \\ c & d \end{pmatrix}"
        assert latex_to_unicode(latex).splitlines() == ["A = ⎛ a  b ⎞", "    ⎝ c  d ⎠"]
        assert latex_to_unicode(latex, inline=True) == "A = (a, b; c, d)"

    def test_three_rows_put_the_text_beside_the_middle_one(self):
        latex = r"I = \begin{bmatrix} 1 & 0 & 0 \\ 0 & 1 & 0 \\ 0 & 0 & 1 \end{bmatrix}"
        assert latex_to_unicode(latex).splitlines() == ["    ⎡ 1  0  0 ⎤", "I = ⎢ 0  1  0 ⎥", "    ⎣ 0  0  1 ⎦"]

    def test_aligned_lines_up_at_the_ampersand(self):
        latex = r"\begin{aligned} x &= 1 + 2 \\ yy &= 3 \end{aligned}"
        assert latex_to_unicode(latex).splitlines() == [" x = 1 + 2", "yy = 3"]

    def test_rows_at_the_top_level(self):
        assert latex_to_unicode(r"a \\ b + c").splitlines() == ["  a", "b + c"]
        assert latex_to_unicode(r"a &= b \\ c &= d", inline=True) == "a = b; c = d"


@pytest.mark.unit
class TestFallback:
    def test_without_pylatexenc(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pylatexenc.latexwalker", None)
        assert latex_to_unicode(r"\alpha") is None

    def test_empty(self):
        assert latex_to_unicode("") is None

    def test_width_ignores_combining_marks(self):
        assert text_width("x" + chr(0x302)) == 1


@pytest.mark.unit
class TestRendererMathMode:
    def test_latex_is_the_default(self):
        doc = Document(children=[Paragraph(content=[Text(content="So "), MathInline(content=r"\alpha^2")])])
        assert plain(doc) == r"So \alpha^2"

    def test_unicode_inline(self):
        doc = Document(children=[Paragraph(content=[Text(content="So "), MathInline(content=r"\alpha^2")])])
        assert plain(doc, math_mode="unicode") == "So α²"

    def test_unicode_block(self):
        doc = Document(children=[MathBlock(content=r"\begin{pmatrix} a \\ b \end{pmatrix}")])
        assert plain(doc, math_mode="unicode").splitlines() == ["╭───────╮", "│ ⎛ a ⎞ │", "│ ⎝ b ⎠ │", "╰───────╯"]

    def test_unicode_falls_back_to_latex(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "pylatexenc.latexwalker", None)
        doc = Document(children=[Paragraph(content=[MathInline(content=r"\alpha^2")])])
        assert plain(doc, math_mode="unicode") == r"\alpha^2"

    def test_other_notations_are_left_alone(self):
        doc = Document(children=[Paragraph(content=[MathInline(content="<mi>x</mi>", notation="mathml")])])
        assert plain(doc, math_mode="unicode") == "<mi>x</mi>"
