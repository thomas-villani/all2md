r"""Math is written as Word equations (OMML) in DOCX.

The renderer used to write ``$x^2$`` as the LaTeX source between dollar signs, and
display math as a code block, so Markdown with math (most LLM-written technical
text) arrived in Word as source code. ``math_mode="native"`` (the default) writes
``m:oMath`` that Word's equation tools edit; ``"latex"`` keeps the old text.
"""

from __future__ import annotations

import builtins
from io import BytesIO

import pytest

from all2md.ast import Document, Paragraph, Text
from all2md.ast.nodes import MathBlock, MathInline
from all2md.options.docx import DocxRendererOptions
from all2md.parsers.docx import DocxToAstConverter
from all2md.renderers.docx import DocxRenderer

docx = pytest.importorskip("docx")
pytest.importorskip("pylatexenc")

from all2md.renderers.docx_math import latex_to_omml  # noqa: E402 - needs pylatexenc

pytestmark = [pytest.mark.unit, pytest.mark.docx]

_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _omml(latex: str, display: bool = False):
    element = latex_to_omml(latex, display=display)
    assert element is not None
    return element


def _text(element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{_M}t"))


def _one(element, path: str):
    found = element.findall(path.replace("m:", _M))
    assert len(found) == 1, f"{path}: {len(found)} found"
    return found[0]


def _val(element, path: str) -> str | None:
    return _one(element, path).get(f"{_M}val")


class TestStructures:
    def test_scripts(self):
        assert _text(_one(_omml("x^2"), "m:sSup/m:sup")) == "2"
        both = _one(_omml("x_i^2"), "m:sSubSup")
        assert (_text(_one(both, "m:e")), _text(_one(both, "m:sub")), _text(_one(both, "m:sup"))) == ("x", "i", "2")

    def test_script_base_is_the_whole_number(self):
        assert _text(_one(_omml("10^{3}"), "m:sSup/m:e")) == "10"
        assert _text(_one(_omml("2x^{3}"), "m:sSup/m:e")) == "x"

    def test_script_base_is_a_braced_group(self):
        assert _text(_one(_omml("{a+b}^2"), "m:sSup/m:e")) == "a+b"

    def test_fraction_and_binomial(self):
        fraction = _one(_omml(r"\frac{a+b}{2}"), "m:f")
        assert (_text(_one(fraction, "m:num")), _text(_one(fraction, "m:den"))) == ("a+b", "2")
        assert _val(_omml(r"\binom{n}{k}"), "m:d/m:e/m:f/m:fPr/m:type") == "noBar"

    def test_roots(self):
        square = _one(_omml(r"\sqrt{x}"), "m:rad")
        assert _val(square, "m:radPr/m:degHide") == "1"
        cube = _one(_omml(r"\sqrt[3]{x}"), "m:rad")
        assert _text(_one(cube, "m:deg")) == "3"
        assert cube.find(f"{_M}radPr/{_M}degHide") is None

    def test_sum_names_its_character_and_its_body_stops_at_the_relation(self):
        # An m:nary without m:chr is an integral, so a sum must say it is one.
        math = _omml(r"\sum_{i=1}^n i^2 = \frac{n(n+1)(2n+1)}{6}")
        nary = _one(math, "m:nary")
        assert _val(nary, "m:naryPr/m:chr") == "∑"
        assert _val(nary, "m:naryPr/m:limLoc") == "undOvr"
        assert (_text(_one(nary, "m:sub")), _text(_one(nary, "m:sup"))) == ("i=1", "n")
        assert _text(_one(nary, "m:e")) == "i2"
        assert _one(math, "m:f") is not None  # the right side is outside the sum

    def test_integral_limits_sit_beside_the_sign(self):
        nary = _one(_omml(r"\int_0^1 f(x)\,dx"), "m:nary")
        assert _val(nary, "m:naryPr/m:chr") == "∫"
        assert _val(nary, "m:naryPr/m:limLoc") == "subSup"

    def test_operator_without_limits_hides_them(self):
        properties = _one(_omml(r"\sum x"), "m:nary/m:naryPr")
        assert properties.find(f"{_M}subHide") is not None and properties.find(f"{_M}supHide") is not None

    def test_functions(self):
        math = _omml(r"\sin x + \cos y")
        functions = math.findall(f"{_M}func")
        assert [_text(f.find(f"{_M}fName")) for f in functions] == ["sin", "cos"]
        assert [_text(f.find(f"{_M}e")) for f in functions] == ["x", "y"]
        assert _val(functions[0], "m:fName/m:r/m:rPr/m:sty") == "p"

    def test_function_body_keeps_its_brackets(self):
        assert _text(_one(_omml(r"\max(a, b) + 1"), "m:func/m:e")) == "(a,b)"

    def test_limit_goes_underneath(self):
        limit = _one(_omml(r"\lim_{x\to 0} f(x) = 1"), "m:func/m:fName/m:limLow")
        assert (_text(_one(limit, "m:e")), _text(_one(limit, "m:lim"))) == ("lim", "x→0")

    def test_starred_operatorname_takes_limits(self):
        limit = _one(_omml(r"\operatorname*{argmax}_x f(x)"), "m:func/m:fName/m:limLow")
        assert _text(_one(limit, "m:e")) == "argmax"

    def test_left_middle_right(self):
        delimiter = _one(_omml(r"\left\{ x \middle| x > 0 \right\}"), "m:d")
        assert [_val(delimiter, f"m:dPr/m:{name}") for name in ("begChr", "sepChr", "endChr")] == ["{", "|", "}"]
        assert [_text(e) for e in delimiter.findall(f"{_M}e")] == ["x", "x>0"]

    def test_right_dot_is_no_delimiter(self):
        assert _val(_omml(r"\left( a \right."), "m:d/m:dPr/m:endChr") == ""

    def test_matrix(self):
        math = _omml(r"\begin{bmatrix} 1 & 2 \\ 3 & 4 \end{bmatrix}")
        assert [_val(math, f"m:d/m:dPr/m:{name}") for name in ("begChr", "endChr")] == ["[", "]"]
        matrix = _one(math, "m:d/m:e/m:m")
        assert _val(matrix, "m:mPr/m:mcs/m:mc/m:mcPr/m:count") == "2"
        rows = [[_text(e) for e in row.findall(f"{_M}e")] for row in matrix.findall(f"{_M}mr")]
        assert rows == [["1", "2"], ["3", "4"]]

    def test_cases_are_left_aligned_columns_after_a_brace(self):
        # Word ignores an equation array's ``&`` before text, so cases are a matrix.
        math = _omml(r"f(x) = \begin{cases} x & \text{if } x \ge 0 \\ -x & \text{otherwise} \end{cases}")
        assert [_val(math, f"m:d/m:dPr/m:{name}") for name in ("begChr", "endChr")] == ["{", ""]
        matrix = _one(math, "m:d/m:e/m:m")
        assert _val(matrix, "m:mPr/m:mcs/m:mc/m:mcPr/m:mcJc") == "left"
        assert _val(matrix, "m:mPr/m:cGp") == "240"  # a quad (12 pt) between value and condition
        rows = [[_text(e) for e in row.findall(f"{_M}e")] for row in matrix.findall(f"{_M}mr")]
        assert rows == [["x", "if x≥0"], ["-x", "otherwise"]]
        text_run = matrix.find(f"{_M}mr").findall(f"{_M}e")[1].find(f"{_M}r")
        assert text_run.find(f"{_M}rPr/{_M}nor") is not None
        assert text_run.find(f"{_M}t").text == "if "

    def test_rcases_brace_is_on_the_right(self):
        math = _omml(r"\begin{rcases} a \\ b \end{rcases}")
        assert [_val(math, f"m:d/m:dPr/m:{name}") for name in ("begChr", "endChr")] == ["", "}"]

    def test_rows_at_the_top_level_align_at_the_ampersand(self):
        rows = _one(_omml(r"a &= b + c \\ d &= e", display=True), "m:oMath/m:eqArr").findall(f"{_M}e")
        assert [_text(row) for row in rows] == ["a&=b+c", "d&=e"]

    def test_aligned_environment(self):
        rows = _one(_omml(r"\begin{aligned} x &= 1 \\ y &= 2 \end{aligned}"), "m:eqArr").findall(f"{_M}e")
        assert [_text(row) for row in rows] == ["x&=1", "y&=2"]

    def test_fonts(self):
        assert _val(_omml(r"\mathbb{R}^n"), "m:sSup/m:e/m:r/m:rPr/m:scr") == "double-struck"
        assert _val(_omml(r"\mathbf{v}"), "m:r/m:rPr/m:sty") == "b"
        assert _val(_omml(r"\mathrm{d}x"), "m:r/m:rPr/m:sty") == "p"

    def test_accents_bars_and_braces(self):
        math = _omml(r"\hat{x} + \overline{AB} + \underbrace{a+b}_{n}")
        assert _val(math, "m:acc/m:accPr/m:chr") == chr(0x302)
        assert _val(math, "m:bar/m:barPr/m:pos") == "top"
        brace = _one(math, "m:limLow")
        assert _val(brace, "m:e/m:groupChr/m:groupChrPr/m:chr") == chr(0x23DF)
        assert _text(_one(brace, "m:lim")) == "n"

    def test_symbols_and_an_unknown_macro(self):
        assert _text(_omml(r"\alpha \leq \infty")) == "α≤∞"
        assert _text(_omml(r"\foo{x} + 1")) == r"\foo{x}+1"

    def test_display_is_an_equation_paragraph(self):
        assert _omml("x", display=True).tag == f"{_M}oMathPara"
        assert _omml("x").tag == f"{_M}oMath"

    def test_without_pylatexenc(self, monkeypatch):
        real_import = builtins.__import__

        def no_pylatexenc(name, *args, **kwargs):
            if name.startswith("pylatexenc"):
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_pylatexenc)
        assert latex_to_omml("x^2") is None


def _render(document: Document, options: DocxRendererOptions | None = None):
    buffer = BytesIO()
    DocxRenderer(options).render(document, buffer)
    return buffer.getvalue()


def _body(data: bytes):
    return docx.Document(BytesIO(data)).element.body


def _sample() -> Document:
    return Document(
        children=[
            Paragraph(content=[Text("Energy is "), MathInline(content="E = mc^2"), Text(" exactly.")]),
            MathBlock(content=r"\int_0^1 x^2\,dx = \frac{1}{3}"),
        ]
    )


class TestRenderer:
    def test_inline_math_sits_in_its_sentence(self):
        paragraph = _body(_render(_sample())).findall(f"{_W}p")[0]
        children = [child.tag.split("}")[1] for child in paragraph if child.tag.split("}")[1] in ("r", "oMath")]
        assert children == ["r", "oMath", "r"]

    def test_display_math_is_its_own_equation_paragraph(self):
        paragraph = _body(_render(_sample())).findall(f"{_W}p")[1]
        assert paragraph.find(f"{_M}oMathPara/{_M}oMath/{_M}nary") is not None
        assert paragraph.find(f"{_W}r") is None

    def test_latex_mode_keeps_the_source(self):
        data = _render(_sample(), DocxRendererOptions(math_mode="latex"))
        body = _body(data)
        assert body.find(f".//{_M}oMath") is None
        text = "".join(node.text or "" for node in body.iter(f"{_W}t"))
        assert "$E = mc^2$" in text
        assert r"\frac{1}{3}" in text

    def test_formula_that_does_not_convert_is_written_as_text(self, monkeypatch):
        monkeypatch.setattr("all2md.renderers.docx_math.latex_to_omml", lambda latex, display=False: None)
        body = _body(_render(_sample()))
        assert body.find(f".//{_M}oMath") is None
        assert "$E = mc^2$" in "".join(node.text or "" for node in body.iter(f"{_W}t"))

    def test_round_trip(self):
        document = DocxToAstConverter().parse(BytesIO(_render(_sample())))
        inline = [node for node in document.children[0].content if isinstance(node, MathInline)]
        assert [node.content for node in inline] == ["E=mc^{2}"]
        block = document.children[1]
        assert isinstance(block, MathBlock)
        assert r"\frac{1}{3}" in block.content
        assert "x^{2}" in block.content
