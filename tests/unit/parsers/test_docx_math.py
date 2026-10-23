r"""Word equations (OMML) read as LaTeX: :mod:`all2md.parsers.docx_math`.

The fragments are shaped like what Word writes, including the properties it leaves
out: an ``m:nary`` with no ``m:chr`` is an integral, an ``m:d`` with no characters
is in parentheses, an ``m:acc`` with no ``m:chr`` is a hat. The round trip at the
end goes through the DOCX renderer's equation writer and back.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

import pytest
from lxml import etree

from all2md.parsers.docx_math import MATH_NAMESPACE, omml_to_latex

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def omml(fragment: str) -> etree._Element:
    return etree.fromstring(f'<m:oMath xmlns:m="{MATH_NAMESPACE}">{fragment}</m:oMath>'.encode())


def run(text: str, properties: str = "") -> str:
    rpr = f"<m:rPr>{properties}</m:rPr>" if properties else ""
    return f'<m:r>{rpr}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def prop(name: str, value: str) -> str:
    return f'<m:{name} m:val="{value}"/>'


def latex(fragment: str) -> str:
    return omml_to_latex(omml(fragment))


def e(content: str, name: str = "e") -> str:
    return f"<m:{name}>{content}</m:{name}>"


class TestText:
    def test_symbols_are_macros(self):
        assert latex(run("α+β≤γ→∞")) == r"\alpha+\beta\le\gamma\to\infty"

    def test_a_macro_does_not_run_into_a_letter(self):
        assert latex(run("αx")) == r"\alpha x"

    def test_a_space_between_words_is_kept(self):
        assert latex(run("x if a")) == r"x\ if\ a"

    def test_a_space_beside_an_operator_is_dropped(self):
        assert latex(run("a + b")) == "a+b"

    def test_word_differential_and_constants(self):
        assert latex(run("ⅇ")) == "e"
        assert latex(run("ⅆx")) == r"\mathrm{d}x"

    def test_braces_are_escaped(self):
        assert latex(run("{x}")) == r"\{x\}"

    def test_normal_text_is_text(self):
        assert latex(run("if x & y", "<m:nor/>")) == r"\text{if x \& y}"

    def test_adjacent_runs_of_one_style_are_one_word(self):
        bold = prop("sty", "b")
        assert latex(run("A", bold) + run("B", bold)) == r"\mathbf{AB}"

    @pytest.mark.parametrize(
        ("script", "macro"),
        [("double-struck", "mathbb"), ("fraktur", "mathfrak"), ("script", "mathcal"), ("sans-serif", "mathsf")],
    )
    def test_scripts(self, script, macro):
        assert latex(run("R", prop("scr", script))) == rf"\{macro}{{R}}"

    def test_upright_letters_are_roman(self):
        assert latex(run("d", prop("sty", "p")) + run("x")) == r"\mathrm{d}x"

    def test_an_upright_function_name_is_its_macro(self):
        assert latex(run("sin", prop("sty", "p")) + run("x")) == r"\sin x"


class TestScripts:
    def test_a_long_base_is_braced(self):
        assert latex(f"<m:sSup>{e(run('ab'))}{e(run('2'), 'sup')}</m:sSup>") == "{ab}^{2}"

    def test_a_number_and_a_bracket_are_not(self):
        assert latex(f"<m:sSup>{e(run('10'))}{e(run('3'), 'sup')}</m:sSup>") == "10^{3}"
        assert latex(f"<m:sSup>{e(run('(a+b)'))}{e(run('2'), 'sup')}</m:sSup>") == "(a+b)^{2}"

    def test_a_prime_is_not_a_superscript(self):
        assert latex(f"<m:sSup>{e(run('f'))}{e(run('′'), 'sup')}</m:sSup>") == "f'"

    def test_both_scripts(self):
        assert latex(f"<m:sSubSup>{e(run('x'))}{e(run('i'), 'sub')}{e(run('2'), 'sup')}</m:sSubSup>") == "x_{i}^{2}"

    def test_prescripts(self):
        assert latex(f"<m:sPre>{e(run('1'), 'sub')}{e(run('2'), 'sup')}{e(run('X'))}</m:sPre>") == "{}_{1}^{2}X"


class TestFractions:
    def fraction(self, kind: str | None = None) -> str:
        properties = f"<m:fPr>{prop('type', kind)}</m:fPr>" if kind else ""
        return f"<m:f>{properties}{e(run('a'), 'num')}{e(run('b'), 'den')}</m:f>"

    def test_a_bar_fraction(self):
        assert latex(self.fraction()) == r"\frac{a}{b}"

    def test_a_linear_fraction(self):
        assert latex(self.fraction("lin")) == "a/b"

    def test_a_fraction_without_a_bar(self):
        assert latex(self.fraction("noBar")) == r"\genfrac{}{}{0pt}{}{a}{b}"

    def test_a_binomial(self):
        assert latex(f"<m:d>{e(self.fraction('noBar'))}</m:d>") == r"\binom{a}{b}"


class TestOperators:
    def nary(self, character: str | None, body: str = "x", hide: str = "") -> str:
        chr_ = prop("chr", character) if character else ""
        return (
            f"<m:nary><m:naryPr>{chr_}{hide}</m:naryPr>{e(run('i'), 'sub')}{e(run('n'), 'sup')}{e(run(body))}</m:nary>"
        )

    def test_the_character_is_read_from_the_properties(self):
        assert latex(self.nary("∑")) == r"\sum_{i}^{n}x"

    def test_no_character_is_an_integral(self):
        assert latex(self.nary(None)) == r"\int_{i}^{n}x"

    def test_hidden_limits_are_left_out(self):
        assert latex(self.nary("∏", hide=prop("subHide", "1") + prop("supHide", "1"))) == r"\prod x"

    def test_a_function(self):
        fragment = f"<m:func>{e(run('sin', prop('sty', 'p')), 'fName')}{e(run('θ'))}</m:func>"
        assert latex(fragment) == r"\sin\theta"

    def test_a_function_name_without_a_style(self):
        """Word writes function names without ``m:sty``; ``m:fName`` makes them upright."""
        assert latex(f"<m:func>{e(run('cos'), 'fName')}{e(run('x'))}</m:func>") == r"\cos x"

    def test_an_unknown_function_is_an_operator_name(self):
        assert latex(f"<m:func>{e(run('sgn'), 'fName')}{e(run('x'))}</m:func>") == r"\operatorname{sgn}x"

    def test_a_limit(self):
        name = f"<m:limLow>{e(run('lim'))}{e(run('x→0'), 'lim')}</m:limLow>"
        assert latex(f"<m:func>{e(name, 'fName')}{e(run('f'))}</m:func>") == r"\lim_{x\to0}f"

    def test_an_unknown_function_with_a_limit(self):
        name = f"<m:limLow>{e(run('argmax'))}{e(run('x'), 'lim')}</m:limLow>"
        assert latex(f"<m:func>{e(name, 'fName')}{e(run('f'))}</m:func>") == r"\operatorname*{argmax}_{x}f"

    def test_a_limit_under_anything_else(self):
        assert latex(f"<m:limLow>{e(run('='))}{e(run('def'), 'lim')}</m:limLow>") == r"\underset{def}{=}"
        assert latex(f"<m:limUpp>{e(run('→'))}{e(run('f'), 'lim')}</m:limUpp>") == r"\overset{f}{\to}"


class TestDelimiters:
    def d(self, content: str, properties: str = "") -> str:
        return f"<m:d><m:dPr>{properties}</m:dPr>{content}</m:d>"

    def test_parentheses_by_default(self):
        assert latex(self.d(e(run("x")))) == "(x)"

    def test_a_tall_group_is_sized(self):
        fraction = f"<m:f>{e(run('a'), 'num')}{e(run('b'), 'den')}</m:f>"
        assert latex(self.d(e(fraction))) == r"\left(\frac{a}{b}\right)"

    def test_characters_and_separators(self):
        properties = prop("begChr", "{") + prop("endChr", "}")
        assert latex(self.d(e(run("x")) + e(run("y")), properties)) == r"\{x|y\}"

    def test_a_missing_side_of_a_tall_group(self):
        fraction = f"<m:f>{e(run('a'), 'num')}{e(run('b'), 'den')}</m:f>"
        assert latex(self.d(e(fraction), prop("begChr", "") + prop("endChr", "|"))) == r"\left.\frac{a}{b}\right|"

    def test_angle_brackets(self):
        assert latex(self.d(e(run("x")), prop("begChr", "⟨") + prop("endChr", "⟩"))) == r"\langle x\rangle"


def matrix(*rows: list[str]) -> str:
    return "<m:m>" + "".join("<m:mr>" + "".join(e(run(cell)) for cell in row) + "</m:mr>" for row in rows) + "</m:m>"


class TestArrays:
    @pytest.mark.parametrize(
        ("opening", "closing", "environment"),
        [("(", ")", "pmatrix"), ("[", "]", "bmatrix"), ("{", "}", "Bmatrix"), ("|", "|", "vmatrix")],
    )
    def test_bracketed_matrices(self, opening, closing, environment):
        properties = prop("begChr", opening) + prop("endChr", closing)
        fragment = f"<m:d><m:dPr>{properties}</m:dPr>{e(matrix(['a', 'b'], ['c', 'd']))}</m:d>"
        assert latex(fragment) == rf"\begin{{{environment}}}a & b \\ c & d\end{{{environment}}}"

    def test_a_bare_matrix(self):
        assert latex(matrix(["1", "2"])) == r"\begin{matrix}1 & 2\end{matrix}"

    def test_cases_from_an_equation_array(self):
        """Word's own cases: a brace on the left only, around an ``m:eqArr``."""
        rows = e(run("x&x≥0")) + e(run("-x&x<0"))
        fragment = (
            f"<m:d><m:dPr>{prop('begChr', '{')}{prop('endChr', '')}</m:dPr>{e(f'<m:eqArr>{rows}</m:eqArr>')}</m:d>"
        )
        assert latex(fragment) == r"\begin{cases}x&x\ge0 \\ -x&x<0\end{cases}"

    def test_an_equation_array_with_alignment_is_aligned(self):
        rows = e(run("x&=1")) + e(run("y&=2"))
        assert latex(f"<m:eqArr>{rows}</m:eqArr>") == r"\begin{aligned}x&=1 \\ y&=2\end{aligned}"

    def test_one_without_is_gathered(self):
        rows = e(run("x=1")) + e(run("y=2"))
        assert latex(f"<m:eqArr>{rows}</m:eqArr>") == r"\begin{gathered}x=1 \\ y=2\end{gathered}"


class TestDecorations:
    def test_an_accent_is_a_hat_by_default(self):
        assert latex(f"<m:acc>{e(run('x'))}</m:acc>") == r"\hat{x}"

    def test_an_accent_over_more_is_wide(self):
        assert latex(f"<m:acc>{e(run('AB'))}</m:acc>") == r"\widehat{AB}"

    def test_a_vector(self):
        assert latex(f"<m:acc><m:accPr>{prop('chr', chr(0x20D7))}</m:accPr>{e(run('v'))}</m:acc>") == r"\vec{v}"

    def test_bars(self):
        assert latex(f"<m:bar>{e(run('x'))}</m:bar>") == r"\underline{x}"
        assert latex(f"<m:bar><m:barPr>{prop('pos', 'top')}</m:barPr>{e(run('x'))}</m:bar>") == r"\overline{x}"

    def test_braces_with_labels(self):
        brace = f"<m:groupChr>{e(run('a+b'))}</m:groupChr>"
        assert latex(f"<m:limLow>{e(brace)}{e(run('n'), 'lim')}</m:limLow>") == r"\underbrace{a+b}_{n}"

    def test_a_box(self):
        assert latex(f"<m:borderBox>{e(run('x=1'))}</m:borderBox>") == r"\boxed{x=1}"

    def test_a_square_root_with_a_hidden_degree(self):
        fragment = f"<m:rad><m:radPr>{prop('degHide', '1')}</m:radPr><m:deg>{run('3')}</m:deg>{e(run('x'))}</m:rad>"
        assert latex(fragment) == r"\sqrt{x}"


ROUND_TRIPS = [
    r"\sum_{i=1}^{n}x_{i}",
    r"\int_{0}^{1}f(x)\,dx",
    r"\lim_{x\to0}\frac{\sin x}{x}=1",
    r"\operatorname*{argmax}_{x}f(x)",
    r"\left(\frac{a}{b}\right)",
    r"\left.\frac{df}{dx}\right|_{x=0}",
    r"\binom{n}{k}",
    r"\begin{bmatrix}a & b \\ c & d\end{bmatrix}",
    r"f(x)=\begin{cases}x^{2} & \text{if }x\ge0 \\ -x & \text{otherwise}\end{cases}",
    r"\begin{aligned}a&=b+c \\ d&=e\end{aligned}",
    r"\hat{x}+\widehat{AB}+\vec{v}+\bar{y}",
    r"\underbrace{a+b}_{n}+\overbrace{c}^{m}",
    r"\mathbf{F}=m\mathbf{a}",
    r"\mathbb{R}^{n}\subseteq\mathcal{H}",
    r"\alpha+\beta\le\gamma\to\infty",
    r"\boxed{x=1}",
]


@pytest.mark.parametrize("formula", ROUND_TRIPS)
def test_round_trip_through_the_renderer(formula):
    pytest.importorskip("pylatexenc")
    from all2md.renderers.docx_math import latex_to_omml

    assert omml_to_latex(latex_to_omml(formula)) == formula
