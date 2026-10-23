#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/docx_math.py
r"""Word equations (OMML) as LaTeX, for the DOCX parser.

Word stores an equation as Office Math Markup Language, a tree of structures --
``m:f`` for a fraction, ``m:nary`` for a large operator, ``m:d`` for a bracketed
group -- around runs of text. :func:`omml_to_latex` walks that tree and writes the
LaTeX a Markdown reader expects, so a fraction built in Word reads ``\frac{a}{b}``.

Covered: scripts (including ``m:sPre``), fractions (with ``\binom`` for a bar-less
fraction in parentheses), roots, large operators with their limits, named
functions, delimiters (``\left``/``\middle``/``\right`` when what they enclose is
tall), matrices, ``cases``, equation arrays (``aligned`` when a row has an ``&``,
``gathered`` otherwise), accents, bars, braces over and under, limits over and
under, boxes, font styles (``\mathbf``, ``\mathbb``, ...) and ``\text``. Symbols
are written as macros (``\alpha``, ``\le``, ``\to``) rather than left as Unicode,
which LaTeX itself does not read in math. An element this does not know keeps its
content.

The defaults are the schema's, which is what Word relies on when it leaves a
property out: an ``m:nary`` with no ``m:chr`` is an integral, an ``m:d`` with no
``m:begChr`` opens with a parenthesis, an ``m:acc`` with no ``m:chr`` is a hat,
and ``m:bar`` and ``m:groupChr`` sit underneath. The characters mirror the ones the
DOCX renderer writes (:mod:`all2md.renderers.docx_math`), so an equation survives a
round trip.
"""

from __future__ import annotations

import re
from typing import Any

MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_VAL = f"{{{MATH_NAMESPACE}}}val"

#: Large operators by their ``m:nary`` character. An ``m:nary`` without one is an integral.
_NARY = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∐": r"\coprod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "∯": r"\oiint",
    "⋃": r"\bigcup",
    "⋂": r"\bigcap",
    "⨁": r"\bigoplus",
    "⨂": r"\bigotimes",
    "⨀": r"\bigodot",
    "⨄": r"\biguplus",
    "⨆": r"\bigsqcup",
    "⋁": r"\bigvee",
    "⋀": r"\bigwedge",
}

#: Function names LaTeX has a macro for; any other name is ``\operatorname``.
_FUNCTIONS = frozenset(
    {"sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "coth", "arcsin", "arccos", "arctan"}
    | {"log", "ln", "lg", "exp", "arg", "deg", "dim", "hom", "ker"}
    | {"lim", "liminf", "limsup", "max", "min", "sup", "inf", "det", "gcd", "Pr"}
)

#: Accents by their ``m:acc`` character, as (one symbol, wider). An ``m:acc`` without one is a hat.
_ACCENTS = {
    chr(0x302): (r"\hat", r"\widehat"),
    chr(0x303): (r"\tilde", r"\widetilde"),
    chr(0x304): (r"\bar", r"\overline"),
    chr(0x305): (r"\bar", r"\overline"),
    chr(0x20D7): (r"\vec", r"\overrightarrow"),
    chr(0x20D6): (r"\overleftarrow", r"\overleftarrow"),
    chr(0x307): (r"\dot", r"\dot"),
    chr(0x308): (r"\ddot", r"\ddot"),
    chr(0x20DB): (r"\dddot", r"\dddot"),
    chr(0x301): (r"\acute", r"\acute"),
    chr(0x300): (r"\grave", r"\grave"),
    chr(0x306): (r"\breve", r"\breve"),
    chr(0x30C): (r"\check", r"\check"),
    chr(0x30A): (r"\mathring", r"\mathring"),
}
_BRACES = {chr(0x23DE): r"\overbrace", chr(0x23DF): r"\underbrace"}

#: Font macros by ``m:scr``, and by ``m:sty`` (``p`` upright, ``b`` bold, ``bi`` bold italic).
_SCRIPTS = {
    "double-struck": r"\mathbb",
    "fraktur": r"\mathfrak",
    "script": r"\mathcal",
    "sans-serif": r"\mathsf",
    "monospace": r"\mathtt",
}
_WEIGHTS = {"p": r"\mathrm", "b": r"\mathbf", "bi": r"\boldsymbol"}

#: Delimiters of ``m:d``, as written after ``\left`` and on their own.
_DELIMITERS = {
    "{": r"\{",
    "}": r"\}",
    "‖": r"\|",
    "⟨": r"\langle",
    "⟩": r"\rangle",
    chr(0x2329): r"\langle",
    chr(0x232A): r"\rangle",
    chr(0x3008): r"\langle",
    chr(0x3009): r"\rangle",
    "⌊": r"\lfloor",
    "⌋": r"\rfloor",
    "⌈": r"\lceil",
    "⌉": r"\rceil",
}
_MATRICES = {
    ("(", ")"): "pmatrix",
    ("[", "]"): "bmatrix",
    ("{", "}"): "Bmatrix",
    ("|", "|"): "vmatrix",
    ("‖", "‖"): "Vmatrix",
    ("{", ""): "cases",
    ("", "}"): "rcases",
}

#: What makes a bracketed group tall enough for ``\left`` and ``\right``.
_TALL = (r"\frac", r"\genfrac", r"\binom", r"\begin", r"\sqrt", r"\left", "brace{", "set{", *_NARY.values())

#: Characters written as macros. Plain spaces carry no meaning in math and are dropped.
_SYMBOLS = {
    # Greek
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ϵ": r"\epsilon",
    "ε": r"\varepsilon",
    "ζ": r"\zeta",
    "η": r"\eta",
    "θ": r"\theta",
    "ϑ": r"\vartheta",
    "ι": r"\iota",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "ξ": r"\xi",
    "π": r"\pi",
    "ϖ": r"\varpi",
    "ρ": r"\rho",
    "ϱ": r"\varrho",
    "σ": r"\sigma",
    "ς": r"\varsigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "ϕ": r"\phi",
    "φ": r"\varphi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Ξ": r"\Xi",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Υ": r"\Upsilon",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
    # Operators
    "±": r"\pm",
    "∓": r"\mp",
    "×": r"\times",
    "÷": r"\div",
    "·": r"\cdot",
    "⋅": r"\cdot",
    "∘": r"\circ",
    "∙": r"\bullet",
    "⊕": r"\oplus",
    "⊗": r"\otimes",
    "⊙": r"\odot",
    "∪": r"\cup",
    "∩": r"\cap",
    "∧": r"\wedge",
    "∨": r"\vee",
    "∖": r"\setminus",
    "⋆": r"\star",
    "∗": r"\ast",
    "†": r"\dagger",
    "−": "-",
    # Relations
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\neq",
    "≈": r"\approx",
    "≡": r"\equiv",
    "∼": r"\sim",
    "≃": r"\simeq",
    "≅": r"\cong",
    "∝": r"\propto",
    "≪": r"\ll",
    "≫": r"\gg",
    "∈": r"\in",
    "∉": r"\notin",
    "∋": r"\ni",
    "⊂": r"\subset",
    "⊃": r"\supset",
    "⊆": r"\subseteq",
    "⊇": r"\supseteq",
    "⊥": r"\perp",
    "∥": r"\parallel",
    "∣": r"\mid",
    "≺": r"\prec",
    "≻": r"\succ",
    "⊢": r"\vdash",
    "⊨": r"\models",
    # Arrows
    "→": r"\to",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "⇐": r"\Leftarrow",
    "⇔": r"\Leftrightarrow",
    "↦": r"\mapsto",
    "↑": r"\uparrow",
    "↓": r"\downarrow",
    "⟶": r"\longrightarrow",
    "⟹": r"\Longrightarrow",
    "⟺": r"\iff",
    "↪": r"\hookrightarrow",
    # Everything else
    "∞": r"\infty",
    "∂": r"\partial",
    "∇": r"\nabla",
    "∀": r"\forall",
    "∃": r"\exists",
    "∄": r"\nexists",
    "∅": r"\emptyset",
    "¬": r"\neg",
    "ħ": r"\hbar",
    "ℏ": r"\hbar",
    "ℓ": r"\ell",
    "ℜ": r"\Re",
    "ℑ": r"\Im",
    "ℵ": r"\aleph",
    "∠": r"\angle",
    "…": r"\ldots",
    "⋯": r"\cdots",
    "⋮": r"\vdots",
    "⋱": r"\ddots",
    # Word's differential d, Euler's e and the imaginary unit (double-struck italic)
    "ⅆ": r"\mathrm{d}",
    "ⅅ": r"\mathrm{D}",
    "ⅇ": "e",
    "ⅈ": "i",
    "ⅉ": "j",
    "′": "'",
    "″": "''",
    "‴": "'''",
    "⟨": r"\langle",
    "⟩": r"\rangle",
    "⌊": r"\lfloor",
    "⌋": r"\rfloor",
    "⌈": r"\lceil",
    "⌉": r"\rceil",
    "‖": r"\|",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "%": r"\%",
    "$": r"\$",
    "\\": r"\backslash",
    " ": "",
    **_NARY,
    # The spaces the renderer writes for \, \: \; \enspace \quad
    chr(0x2009): r"\,",
    chr(0x205F): r"\:",
    chr(0x2004): r"\;",
    chr(0x2002): r"\enspace",
    chr(0x2003): r"\quad",
}

#: Characters escaped inside ``\text``.
_TEXT_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "%": r"\%",
    "$": r"\$",
    "&": r"\&",
    "_": r"\_",
    "^": r"\^{}",
    "~": r"\~{}",
}

_OPERATOR_NAME = r"\operatorname"
#: Bases whose limit is a plain script (``\lim_{x \to 0}``, ``\sum_{i}``), not ``\underset``.
_LIMIT_BASES = frozenset({f"\\{name}" for name in _FUNCTIONS} | set(_NARY.values()))

_CONTROL_WORD_END = re.compile(r"\\[A-Za-z]+$")
_CONTROL_WORD = re.compile(r"\\[A-Za-z]+")
_ALIGNMENT = re.compile(r"(?<!\\)&")


def omml_local_name(tag: Any) -> str:
    """Return an element tag without its namespace, or ``""`` for a comment or processing instruction."""
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def omml_to_latex(element: Any) -> str:
    """Convert an OMML element (``m:oMath``, ``m:oMathPara`` or any part of one) to LaTeX.

    Parameters
    ----------
    element : Any
        The lxml element to convert, or None

    Returns
    -------
    str
        The LaTeX, or ``""`` for None

    """
    if element is None:
        return ""
    return _Reader().convert(element).strip()


def _join(parts: list[str]) -> str:
    r"""Concatenate LaTeX, with a space where a control word would run into a letter (``\alpha x``)."""
    out = ""
    for part in parts:
        if not part:
            continue
        if out and part[0].isalpha() and _CONTROL_WORD_END.search(out):
            out += " "
        out += part
    return out


def _children(element: Any) -> list[Any]:
    """Return the content children of an element, without its properties (``m:rPr``, ``m:naryPr``, ...)."""
    return [
        child
        for child in element
        if isinstance(getattr(child, "tag", None), str) and not omml_local_name(child.tag).endswith("Pr")
    ]


def _child(element: Any, name: str) -> Any | None:
    for child in element:
        if omml_local_name(getattr(child, "tag", None)) == name:
            return child
    return None


def _children_named(element: Any, name: str) -> list[Any]:
    return [child for child in element if omml_local_name(getattr(child, "tag", None)) == name]


def _property(element: Any, container: str, name: str) -> str | None:
    """Return the ``m:val`` of a property, ``""`` when it is present without one, or None when absent."""
    properties = _child(element, container)
    node = _child(properties, name) if properties is not None else None
    if node is None:
        return None
    return node.get(_VAL, "")


def _flag(element: Any, container: str, name: str) -> bool:
    value = _property(element, container, name)
    return value is not None and value.lower() not in {"0", "off", "false"}


def _unit_end(latex: str, index: int) -> int:
    r"""Return the index just past the unit of LaTeX starting at ``index``.

    A unit is a character, a braced group, a macro with its braced arguments, a
    ``\left`` ... ``\right`` pair, or a ``\begin`` ... ``\end`` environment.
    """
    if latex[index] == "{":
        return _group_end(latex, index)
    if latex[index] != "\\":
        return index + 1
    match = _CONTROL_WORD.match(latex, index)
    if match is None:
        return min(index + 2, len(latex))
    word, end = match.group(), match.end()
    if word in (r"\left", r"\begin"):
        closing = r"\right" if word == r"\left" else r"\end"
        depth = 0
        for token in _CONTROL_WORD.finditer(latex, index):
            if token.group() == word:
                depth += 1
            elif token.group() == closing:
                depth -= 1
                if depth == 0:
                    end = token.end()
                    break
        else:
            return len(latex)
        if word == r"\left":
            return _unit_end(latex, end) if end < len(latex) else end
    while end < len(latex) and latex[end] == "{":
        end = _group_end(latex, end)
    return end


def _group_end(latex: str, index: int) -> int:
    depth = 0
    position = index
    while position < len(latex):
        character = latex[position]
        if character == "\\":
            position += 2
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1
    return len(latex)


def _is_unit(latex: str) -> bool:
    return bool(latex) and (_unit_end(latex, 0) == len(latex) or _is_bracketed(latex))


def _is_bracketed(latex: str) -> bool:
    """Whether the LaTeX is one parenthesized or bracketed group, as ``(a+b)`` is."""
    pairs = {"(": ")", "[": "]"}
    if len(latex) < 2 or pairs.get(latex[0]) != latex[-1]:
        return False
    depth = 0
    for index, character in enumerate(latex):
        if character == latex[0]:
            depth += 1
        elif character == latex[-1]:
            depth -= 1
            if depth == 0 and index < len(latex) - 1:
                return False
    return depth == 0


def _base(latex: str) -> str:
    """Brace a script's base when it is more than one unit, so the script applies to all of it."""
    return latex if _is_unit(latex) or latex.isdigit() else f"{{{latex}}}"


def _function_macro(name: str) -> str:
    compact = name.replace(" ", "")
    return f"\\{compact}" if compact in _FUNCTIONS else f"\\operatorname{{{name}}}"


def _delimiter(character: str, sized: bool) -> str:
    if not character:
        return "." if sized else ""
    return _DELIMITERS.get(character, character)


class _Reader:
    """One conversion. It tracks whether it is inside a function name (``m:fName``)."""

    def __init__(self) -> None:
        self.naming = False

    def convert(self, element: Any) -> str:
        name = omml_local_name(getattr(element, "tag", None))
        if not name:
            return ""
        if name == "r":
            return self.sequence([element])
        if name == "t":
            return self._text(element.text or "", None)
        handler = self._HANDLERS.get(name)
        if handler is not None:
            return handler(self, element)
        return self.sequence(_children(element))

    def sequence(self, elements: list[Any]) -> str:
        """Convert siblings, merging adjacent runs of the same style so a word is styled as one."""
        parts: list[str] = []
        pending: list[str] = []
        pending_style: tuple[bool, str | None, str | None] | None = None
        for element in elements:
            if omml_local_name(element.tag) == "r":
                style = self._style(element)
                if style != pending_style and pending:
                    parts.append(self._text("".join(pending), pending_style))
                    pending = []
                pending_style = style
                pending.append("".join(t.text or "" for t in element.iter() if omml_local_name(t.tag) == "t"))
                continue
            if pending:
                parts.append(self._text("".join(pending), pending_style))
                pending = []
            parts.append(self.convert(element))
        if pending:
            parts.append(self._text("".join(pending), pending_style))
        return _join(parts)

    def _content(self, element: Any, name: str) -> str:
        """Convert the child ``name``. Only a base (``m:e``) can be part of a function's name."""
        child = _child(element, name)
        if child is None:
            return ""
        naming = self.naming
        self.naming = naming and name == "e"
        try:
            return self.sequence(_children(child))
        finally:
            self.naming = naming

    # ------------------------------------------------------------------ text
    @staticmethod
    def _style(run: Any) -> tuple[bool, str | None, str | None]:
        return (
            _flag(run, "rPr", "nor"),
            _property(run, "rPr", "sty"),
            _property(run, "rPr", "scr"),
        )

    @staticmethod
    def _symbol(raw: str, index: int) -> str:
        r"""Return the LaTeX for ``raw[index]``.

        A space Word kept between two words (``if a`` in a ``cases`` row) is ``\ ``;
        any other is spacing LaTeX does itself.
        """
        character = raw[index]
        if character == " " and 0 < index < len(raw) - 1 and raw[index - 1].isalnum() and raw[index + 1].isalnum():
            return "\\ "
        return _SYMBOLS.get(character, character)

    def _text(self, raw: str, style: tuple[bool, str | None, str | None] | None) -> str:
        normal, weight, script = style or (False, None, None)
        if normal:
            escaped = "".join(_TEXT_ESCAPES.get(character, character) for character in raw)
            return f"\\text{{{escaped}}}" if raw else ""
        latex = _join([self._symbol(raw, index) for index in range(len(raw))])
        if not latex:
            return ""
        word = raw.strip()
        if word.replace(" ", "").isalpha() and (self.naming or (weight == "p" and word.replace(" ", "") in _FUNCTIONS)):
            return _function_macro(word)
        if script in _SCRIPTS:
            return f"{_SCRIPTS[script]}{{{latex}}}"
        if weight in _WEIGHTS and (weight != "p" or any(c.isascii() and c.isalpha() for c in raw)):
            return f"{_WEIGHTS[weight]}{{{latex}}}"
        return latex

    # ------------------------------------------------------------ structures
    def _oMathPara(self, element: Any) -> str:
        return " ".join(part for part in (self.convert(child) for child in _children(element)) if part)

    def _f(self, element: Any) -> str:
        numerator = self._content(element, "num")
        denominator = self._content(element, "den")
        if not (numerator and denominator):
            return numerator or denominator
        kind = _property(element, "fPr", "type")
        if kind == "noBar":
            return f"\\genfrac{{}}{{}}{{0pt}}{{}}{{{numerator}}}{{{denominator}}}"
        if kind in ("lin", "skw"):
            return f"{_base(numerator)}/{_base(denominator)}"
        return f"\\frac{{{numerator}}}{{{denominator}}}"

    def _scripted(self, base: str, sub: str, sup: str) -> str:
        if not base:
            return sub or sup
        latex = _base(base)
        if sub:
            latex += f"_{{{sub}}}"
        if sup:
            latex += sup if re.fullmatch("'+", sup) else f"^{{{sup}}}"
        return latex

    def _sSup(self, element: Any) -> str:
        return self._scripted(self._content(element, "e"), "", self._content(element, "sup"))

    def _sSub(self, element: Any) -> str:
        return self._scripted(self._content(element, "e"), self._content(element, "sub"), "")

    def _sSubSup(self, element: Any) -> str:
        return self._scripted(self._content(element, "e"), self._content(element, "sub"), self._content(element, "sup"))

    def _sPre(self, element: Any) -> str:
        sub, sup = self._content(element, "sub"), self._content(element, "sup")
        scripts = "{}" + (f"_{{{sub}}}" if sub else "") + (f"^{{{sup}}}" if sup else "")
        return _join([scripts, self._content(element, "e")])

    def _rad(self, element: Any) -> str:
        radicand = self._content(element, "e")
        degree = "" if _flag(element, "radPr", "degHide") else self._content(element, "deg")
        if degree:
            return f"\\sqrt[{degree}]{{{radicand}}}"
        return f"\\sqrt{{{radicand}}}" if radicand else ""

    def _nary(self, element: Any) -> str:
        character = _property(element, "naryPr", "chr") or "∫"
        operator = _NARY.get(character) or _SYMBOLS.get(character) or character
        if not _flag(element, "naryPr", "subHide") and (sub := self._content(element, "sub")):
            operator += f"_{{{sub}}}"
        if not _flag(element, "naryPr", "supHide") and (sup := self._content(element, "sup")):
            operator += f"^{{{sup}}}"
        return _join([operator, self._content(element, "e")])

    def _func(self, element: Any) -> str:
        naming, self.naming = self.naming, True
        try:
            name_element = _child(element, "fName")
            name = self.sequence(_children(name_element)) if name_element is not None else ""
        finally:
            self.naming = naming
        return _join([name, self._content(element, "e")])

    def _limit(self, element: Any, script: str, brace: str, stack: str) -> str:
        base = self._content(element, "e")
        limit = self._content(element, "lim")
        if not limit:
            return base
        if base.startswith(_OPERATOR_NAME + "{") and _is_unit(base):
            return f"{_OPERATOR_NAME}*{base[len(_OPERATOR_NAME) :]}{script}{{{limit}}}"
        if (base.startswith(brace) and _is_unit(base)) or base in _LIMIT_BASES:
            return f"{base}{script}{{{limit}}}"
        return f"\\{stack}{{{limit}}}{{{base}}}"

    def _limLow(self, element: Any) -> str:
        return self._limit(element, "_", r"\underbrace", "underset")

    def _limUpp(self, element: Any) -> str:
        return self._limit(element, "^", r"\overbrace", "overset")

    def _d(self, element: Any) -> str:
        opening = _property(element, "dPr", "begChr")
        closing = _property(element, "dPr", "endChr")
        separator = _property(element, "dPr", "sepChr")
        opening = "(" if opening is None else opening
        closing = ")" if closing is None else closing
        separator = "|" if separator is None else separator

        cells = _children_named(element, "e")
        if len(cells) == 1:
            content = _children(cells[0])
            only = omml_local_name(content[0].tag) if len(content) == 1 else ""
            environment = _MATRICES.get((opening, closing))
            if environment and (only == "m" or (only == "eqArr" and environment in ("cases", "rcases"))):
                return self._environment(environment, self._rows(content[0]))
            if only == "f" and (opening, closing) == ("(", ")") and _property(content[0], "fPr", "type") == "noBar":
                numerator, denominator = self._content(content[0], "num"), self._content(content[0], "den")
                return f"\\binom{{{numerator}}}{{{denominator}}}"

        inner = [self.sequence(_children(cell)) for cell in cells]
        sized = any(marker in part for part in inner for marker in _TALL)
        parts = [rf"\left{_delimiter(opening, True)}" if sized else _delimiter(opening, False)]
        for index, part in enumerate(inner):
            if index:
                parts.append(rf"\middle{_delimiter(separator, True)}" if sized else _delimiter(separator, False))
            parts.append(part)
        parts.append(rf"\right{_delimiter(closing, True)}" if sized else _delimiter(closing, False))
        return _join(parts)

    def _rows(self, element: Any) -> list[str]:
        """Return the rows of an ``m:m`` (cells joined with ``&``) or an ``m:eqArr``."""
        if omml_local_name(element.tag) == "eqArr":
            return [self.sequence(_children(row)) for row in _children_named(element, "e")]
        return [
            " & ".join(self.sequence(_children(cell)) for cell in _children_named(row, "e"))
            for row in _children_named(element, "mr")
        ]

    @staticmethod
    def _environment(name: str, rows: list[str]) -> str:
        body = " \\\\ ".join(rows)
        return f"\\begin{{{name}}}{body}\\end{{{name}}}"

    def _m(self, element: Any) -> str:
        return self._environment("matrix", self._rows(element))

    def _eqArr(self, element: Any) -> str:
        rows = self._rows(element)
        return self._environment("aligned" if any(_ALIGNMENT.search(row) for row in rows) else "gathered", rows)

    def _acc(self, element: Any) -> str:
        base = self._content(element, "e")
        character = _property(element, "accPr", "chr")
        character = chr(0x302) if character is None else character
        if character in _ACCENTS:
            narrow, wide = _ACCENTS[character]
            single = len(base) == 1 or bool(_CONTROL_WORD.fullmatch(base))
            return f"{narrow if single else wide}{{{base}}}"
        return f"\\overset{{{_SYMBOLS.get(character, character)}}}{{{base}}}"

    def _bar(self, element: Any) -> str:
        macro = r"\overline" if _property(element, "barPr", "pos") == "top" else r"\underline"
        return f"{macro}{{{self._content(element, 'e')}}}"

    def _groupChr(self, element: Any) -> str:
        base = self._content(element, "e")
        character = _property(element, "groupChrPr", "chr")
        character = chr(0x23DF) if character is None else character
        if character in _BRACES:
            return f"{_BRACES[character]}{{{base}}}"
        stack = r"\overset" if _property(element, "groupChrPr", "pos") == "top" else r"\underset"
        return f"{stack}{{{_SYMBOLS.get(character, character)}}}{{{base}}}"

    def _borderBox(self, element: Any) -> str:
        return f"\\boxed{{{self._content(element, 'e')}}}"

    _HANDLERS: dict[str, Any] = {
        "oMathPara": _oMathPara,
        "f": _f,
        "sSup": _sSup,
        "sSub": _sSub,
        "sSubSup": _sSubSup,
        "sPre": _sPre,
        "rad": _rad,
        "nary": _nary,
        "func": _func,
        "limLow": _limLow,
        "limUpp": _limUpp,
        "d": _d,
        "m": _m,
        "eqArr": _eqArr,
        "acc": _acc,
        "bar": _bar,
        "groupChr": _groupChr,
        "borderBox": _borderBox,
    }
