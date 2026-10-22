#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/docx_math.py
r"""LaTeX math as Word equations (OMML), for the DOCX renderer.

Word stores an equation as Office Math Markup Language: ``m:oMath`` for math
inside a paragraph and ``m:oMathPara`` for a display equation. This module
writes it from LaTeX, so ``$\frac{a}{b}$`` arrives in Word as a fraction that
Word's equation tools can edit, not as the LaTeX source between dollar signs.

Covered: scripts, fractions and binomials, roots, accents, bars and braces over
and under, large operators with their limits (``\sum``, ``\int``, ...), named
functions (``\sin``, ``\lim``), ``\left``/``\middle``/``\right`` delimiters,
matrices, ``cases``, rows aligned at ``&`` (``aligned``, ``align``,
``gathered``, and ``\\`` at the top level), font styles (``\mathbf``,
``\mathbb``, ...) and ``\text``. A macro the converter does not know is kept as
written, inside the equation, so nothing is dropped.

The LaTeX is parsed with ``pylatexenc``, as the terminal renderer's Unicode math
is (:mod:`all2md.renderers.terminal_math`, whose token helpers this shares).
Without it, or when a formula does not parse, :func:`latex_to_omml` returns
``None`` and the renderer writes the LaTeX source as text.

The encodings follow what Word writes itself, read back from equations built in
Word: an alignment point in ``m:eqArr`` is an ``&`` in the text (which Word
honors before an operator, so ``cases`` is laid out as columns instead); and an
``m:nary`` without ``m:chr`` is an integral, so every operator names its
character.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, cast

from lxml import etree

from all2md.renderers.terminal_math import (
    _BINOMIALS,
    _CASES,
    _DROPPED,
    _FRACTIONS,
    _MATRICES,
    _TEXT,
    _is_cell_break,
    _is_char,
    _is_node,
    _is_row_break,
    latex_tokens,
    macro_arguments,
    take_argument,
)

logger = logging.getLogger(__name__)

MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

#: Large operators, as ``m:nary`` characters. Integrals put their limits beside the sign, the rest above and below.
_NARY = {
    "sum": "∑",
    "prod": "∏",
    "coprod": "∐",
    "int": "∫",
    "iint": "∬",
    "iiint": "∭",
    "oint": "∮",
    "oiint": "∯",
    "bigcup": "⋃",
    "bigcap": "⋂",
    "bigoplus": "⨁",
    "bigotimes": "⨂",
    "bigodot": "⨀",
    "biguplus": "⨄",
    "bigsqcup": "⨆",
    "bigvee": "⋁",
    "bigwedge": "⋀",
}
_INTEGRALS = frozenset("∫∬∭∮∯")

#: Named functions, written upright; the ones with limits take a subscript underneath (``\lim_{x\to 0}``).
_FUNCTIONS = frozenset(
    {"sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "coth", "arcsin", "arccos", "arctan"}
    | {"log", "ln", "lg", "exp", "arg", "deg", "dim", "hom", "ker"}
)
_LIMIT_FUNCTIONS = frozenset({"lim", "liminf", "limsup", "max", "min", "sup", "inf", "det", "gcd", "Pr"})
_FUNCTION_NAMES = {"liminf": "lim inf", "limsup": "lim sup"}

#: Accents on their argument, as ``m:acc`` characters (combining marks).
_ACCENTS = {
    "hat": chr(0x302),
    "widehat": chr(0x302),
    "tilde": chr(0x303),
    "widetilde": chr(0x303),
    "bar": chr(0x305),
    "vec": chr(0x20D7),
    "overrightarrow": chr(0x20D7),
    "overleftarrow": chr(0x20D6),
    "dot": chr(0x307),
    "ddot": chr(0x308),
    "dddot": chr(0x20DB),
    "acute": chr(0x301),
    "grave": chr(0x300),
    "breve": chr(0x306),
    "check": chr(0x30C),
    "mathring": chr(0x30A),
}
_BARS = {"overline": "top", "underline": "bot"}
_GROUP_CHARACTERS = {"overbrace": (chr(0x23DE), "top"), "underbrace": (chr(0x23DF), "bot")}

#: Font macros as (``m:sty``, ``m:scr``): ``p`` is upright, ``b`` bold, ``i`` italic, ``bi`` both.
_STYLES: dict[str, tuple[str | None, str | None]] = {
    "mathrm": ("p", None),
    "mathup": ("p", None),
    "mathbf": ("b", None),
    "mathit": ("i", None),
    "boldsymbol": ("bi", None),
    "bm": ("bi", None),
    "mathnormal": (None, None),
    "mathbb": (None, "double-struck"),
    "mathcal": (None, "script"),
    "mathscr": (None, "script"),
    "mathfrak": (None, "fraktur"),
    "mathsf": (None, "sans-serif"),
    "mathtt": (None, "monospace"),
}

_SPACES = {
    ",": chr(0x2009),
    ":": chr(0x205F),
    ";": chr(0x2004),
    " ": " ",
    "!": "",
    "enspace": chr(0x2002),
    "quad": chr(0x2003),
    "qquad": chr(0x2003) * 2,
}

#: Delimiters written as macros after ``\left``, ``\right`` and the ``\big`` family.
_DELIMITERS = {
    "{": "{",
    "}": "}",
    "|": "‖",
    "langle": "⟨",
    "rangle": "⟩",
    "lvert": "|",
    "rvert": "|",
    "vert": "|",
    "lVert": "‖",
    "rVert": "‖",
    "Vert": "‖",
    "lfloor": "⌊",
    "rfloor": "⌋",
    "lceil": "⌈",
    "rceil": "⌉",
    "backslash": "\\",
}
_SIZED = frozenset(
    {"big", "Big", "bigg", "Bigg"} | {f"{size}{side}" for size in ("big", "Big", "bigg", "Bigg") for side in "lrm"}
)

#: Where the body of a large operator ends (a relation or a comma), and also a function's (any operator).
_RELATIONS = frozenset("=<>≤≥≠≈≡∼≃≅∝→←↔⇒⇐⇔∈∉⊂⊃⊆⊇,;")
_OPERATORS = _RELATIONS | frozenset("+-−±∓·×÷*/")
_OPENING, _CLOSING = frozenset("([{⟨⌊⌈"), frozenset(")]}⟩⌋⌉")

#: How many arguments a macro takes when pylatexenc does not know it.
_ARITY = dict.fromkeys(_FRACTIONS | _BINOMIALS, 2) | dict.fromkeys(
    (*_ACCENTS, *_BARS, *_GROUP_CHARACTERS, *_STYLES, *_TEXT, "sqrt", "boxed", "tag", "label", "pmod", "operatorname"),
    1,
)


@dataclass
class _Run:
    r"""Text in one run of math, with its font (``style``, ``script``), or ordinary text (``normal``, ``\text``)."""

    text: str
    style: str | None = None
    script: str | None = None
    normal: bool = False

    def props(self) -> tuple[str | None, str | None, bool]:
        return self.style, self.script, self.normal


@dataclass
class _Group:
    """A braced group: one base for a script that follows it, its items otherwise."""

    items: list[Item]


@dataclass
class _Operator:
    """A large operator (``kind="nary"``) or a named function (``"func"``), with its limits.

    Its body is what follows it in the formula, up to a relation (or, for a
    function, any operator), so it is settled when the items are assembled.
    """

    kind: str
    text: str
    limits: bool = False
    sub: list[Item] | None = None
    sup: list[Item] | None = None


Item = _Run | _Group | _Operator | etree._Element


def latex_to_omml(latex: str, display: bool = False) -> etree._Element | None:
    r"""Return LaTeX math as a Word equation, or ``None`` when it cannot be converted.

    Parameters
    ----------
    latex : str
        The formula, without ``$`` delimiters.
    display : bool, default False
        Return a display equation (``m:oMathPara``, a paragraph of its own)
        instead of math that sits in a line of text (``m:oMath``).

    Returns
    -------
    lxml.etree._Element or None
        The equation, or ``None`` when ``pylatexenc`` is not installed or the
        formula does not parse.

    Examples
    --------
        >>> etree.tostring(latex_to_omml(r"x^2"))  # doctest: +SKIP
        b'<m:oMath xmlns:m="..."><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>...'

    """
    try:
        from pylatexenc.latex2text import LatexNodes2Text
        from pylatexenc.latexwalker import LatexWalker
    except ImportError:
        return None
    try:
        nodes, _, _ = LatexWalker(latex, tolerant_parsing=True).get_latex_nodes()
        elements = _Converter(LatexNodes2Text(math_mode="text")).top(nodes)
    except Exception as e:  # noqa: BLE001 - any failure falls back to the LaTeX source
        logger.debug("Could not convert math to OMML: %s", e)
        return None
    if not elements:
        return None
    math = _element("oMath", *elements)
    return _element("oMathPara", math) if display else math


# OMML elements ---------------------------------------------------------------


def _element(tag: str, *children: etree._Element, **values: str) -> etree._Element:
    """Return an ``m:`` element with ``m:``-namespaced attributes and the given children."""
    element = etree.Element(f"{{{MATH_NAMESPACE}}}{tag}", nsmap={"m": MATH_NAMESPACE})
    for name, value in values.items():
        element.set(f"{{{MATH_NAMESPACE}}}{name}", value)
    for child in children:
        element.append(child)
    return element


def _value(tag: str, value: str) -> etree._Element:
    """Return a property element such as ``<m:chr m:val="∑"/>``."""
    return _element(tag, val=value)


def _run_element(run: _Run) -> etree._Element:
    element = _element("r")
    if run.normal:
        element.append(_element("rPr", _element("nor")))
    elif run.style or run.script:
        properties = _element("rPr")
        if run.script:
            properties.append(_value("scr", run.script))
        if run.style:
            properties.append(_value("sty", run.style))
        element.append(properties)
    text = _element("t")
    text.text = run.text
    if run.normal or run.text != run.text.strip():
        text.set(_XML_SPACE, "preserve")
    element.append(text)
    return element


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def _scripts_element(base: list[Item], sub: list[Item] | None, sup: list[Item] | None) -> etree._Element:
    """Return ``base`` with a subscript, a superscript or both."""
    if (
        len(base) == 1
        and isinstance(base[0], etree._Element)
        and _local_name(base[0]) == "groupChr"
        and (sub is None) != (sup is None)
    ):
        # A brace over or under an expression takes its label on the brace's side.
        under = sub is not None
        return _element(
            "limLow" if under else "limUpp", _element("e", base[0]), _element("lim", *_assemble(sub or sup or []))
        )
    e = _element("e", *_assemble(base))
    if sub is not None and sup is not None:
        return _element("sSubSup", e, _element("sub", *_assemble(sub)), _element("sup", *_assemble(sup)))
    if sup is not None:
        return _element("sSup", e, _element("sup", *_assemble(sup)))
    return _element("sSub", e, _element("sub", *_assemble(sub or [])))


def _operator_element(operator: _Operator, body: list[Item]) -> etree._Element:
    if operator.kind == "nary":
        properties = _element(
            "naryPr",
            _value("chr", operator.text),
            _value("limLoc", "subSup" if operator.text in _INTEGRALS else "undOvr"),
        )
        if operator.sub is None:
            properties.append(_value("subHide", "1"))
        if operator.sup is None:
            properties.append(_value("supHide", "1"))
        return _element(
            "nary",
            properties,
            _element("sub", *_assemble(operator.sub or [])),
            _element("sup", *_assemble(operator.sup or [])),
            _element("e", *_assemble(body)),
        )
    label = _Run(operator.text, style="p")
    name: Item = label
    if operator.limits and (operator.sub is None) != (operator.sup is None):
        under = operator.sub is not None
        name = _element(
            "limLow" if under else "limUpp",
            _element("e", _run_element(label)),
            _element("lim", *_assemble(operator.sub or operator.sup or [])),
        )
    elif operator.sub is not None or operator.sup is not None:
        name = _scripts_element([name], operator.sub, operator.sup)
    return _element("func", _element("fName", *_assemble([name])), _element("e", *_assemble(body)))


def _take_body(items: list[Item], index: int, kind: str) -> tuple[list[Item], int]:
    """Return the body of the operator before ``items[index]``, and the index after it.

    It runs to the next relation (a function's, to the next operator of any
    kind, or another function) outside brackets, to a bracket that closes one
    opened before the operator, or to the end.
    """
    stops = _RELATIONS if kind == "nary" else _OPERATORS
    depth = 0
    body: list[Item] = []
    while index < len(items):
        item = items[index]
        if isinstance(item, _Run) and not item.normal:
            if depth == 0 and item.text in _CLOSING:
                break
            if depth == 0 and item.text in stops and (body or item.text not in "+-−"):
                break
            depth += item.text in _OPENING
            depth -= item.text in _CLOSING and depth > 0
        elif isinstance(item, _Operator) and kind == "func" and item.kind == "func" and depth == 0 and body:
            break
        body.append(item)
        index += 1
    return body, index


def _assemble(items: list[Item]) -> list[etree._Element]:
    """Turn items into OMML elements: runs with the same font merged, groups opened, operators given bodies."""
    items = list(items)
    out: list[etree._Element] = []
    pending: _Run | None = None
    index = 0
    while index < len(items):
        item = items[index]
        index += 1
        if isinstance(item, _Run):
            if pending is not None and pending.props() == item.props():
                pending = replace(pending, text=pending.text + item.text)
            else:
                if pending is not None:
                    out.append(_run_element(pending))
                pending = item
            continue
        if pending is not None:
            out.append(_run_element(pending))
            pending = None
        if isinstance(item, _Group):
            items[index:index] = item.items
        elif isinstance(item, _Operator):
            body, index = _take_body(items, index, item.kind)
            out.append(_operator_element(item, body))
        else:
            out.append(item)
    if pending is not None:
        out.append(_run_element(pending))
    return out


def _pop_base(out: list[Item]) -> list[Item]:
    """Remove and return what a script attaches to: the last item, or the whole number it ends."""
    if not out:
        return []
    last = out.pop()
    if not isinstance(last, _Run) or not last.text.isdigit():
        return [last]
    digits: list[_Run] = [last]
    while out and isinstance(out[-1], _Run) and out[-1].props() == last.props():
        previous = out[-1].text
        if previous.isdigit() or (previous == "." and digits[0].text.isdigit() and len(out) > 1):
            digits.insert(0, cast(_Run, out.pop()))
        else:
            break
    if digits[0].text == ".":
        out.append(digits.pop(0))
    return [_Run("".join(run.text for run in digits), last.style, last.script, last.normal)]


# Conversion ------------------------------------------------------------------


class _Converter:
    """Turn a pylatexenc node list into OMML items."""

    def __init__(self, l2t: Any) -> None:
        self.l2t = l2t
        self.style: str | None = None
        self.script: str | None = None

    @contextmanager
    def _font(self, style: str | None, script: str | None) -> Iterator[None]:
        saved = self.style, self.script
        self.style, self.script = style, script
        try:
            yield
        finally:
            self.style, self.script = saved

    def _run(self, text: str) -> _Run:
        return _Run(text, self.style, self.script)

    def _argument(self, argument: Any) -> list[Item]:
        """Return a macro or script argument as items."""
        if argument is None:
            return []
        if isinstance(argument, str):
            return [] if argument.isspace() else [self._run(argument)]
        if _is_node(argument, "LatexGroupNode"):
            return self.items(argument.nodelist)
        return self.items([argument])

    def _plain_text(self, argument: Any) -> str:
        r"""Return the argument of ``\text`` and friends as text, its spaces kept."""
        if argument is None:
            return ""
        if isinstance(argument, str):
            return argument
        nodes = argument.nodelist if _is_node(argument, "LatexGroupNode") else [argument]
        return str(self.l2t.nodelist_to_text(nodes))

    def top(self, nodes: list[Any]) -> list[etree._Element]:
        r"""Convert a whole formula; ``\\`` and ``&`` at the top level make aligned rows."""
        tokens = latex_tokens(nodes)
        if any(_is_row_break(token) or _is_cell_break(token) for token in tokens):
            has_cells = any(_is_cell_break(token) for token in tokens)
            return _assemble([self._environment("aligned" if has_cells else "gathered", nodes)])
        return _assemble(self.items(nodes))

    def items(self, nodes: list[Any]) -> list[Item]:
        """Convert a node list (or a list of tokens) to items."""
        tokens = latex_tokens(nodes)
        out: list[Item] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if isinstance(token, str):
                if token in "^_":
                    index = self._scripts(token, tokens, index, out)
                elif token == "'":
                    count = 1
                    while index < len(tokens) and _is_char(tokens[index], "'") and count < 3:
                        count += 1
                        index += 1
                    out.append(self._run("′″‴"[count - 1]))
                elif token not in "{}" and not token.isspace():
                    out.append(self._run(token))
            elif _is_node(token, "LatexGroupNode"):
                out.append(_Group(self.items(token.nodelist)))
            elif _is_node(token, "LatexMacroNode"):
                index = self._macro(token, tokens, index, out)
            elif _is_node(token, "LatexEnvironmentNode"):
                out.append(self._environment(token.environmentname, token.nodelist))
            elif _is_node(token, "LatexMathNode"):
                out.extend(self.items(token.nodelist))
            elif _is_node(token, "LatexSpecialsNode"):
                chars = token.specials_chars
                if chars == "~":
                    out.append(self._run(chr(0xA0)))
                elif chars in ("''", "'''"):
                    # pylatexenc reads ``''`` as a closing quote; in math it is a double prime.
                    out.append(self._run("″" if chars == "''" else "‴"))
                elif chars.startswith("-"):
                    out.extend(self._run("-") for _ in chars)
                elif chars != "&":
                    out.append(self._run(str(self.l2t.nodelist_to_text([token]))))
            else:
                out.append(self._run(token.latex_verbatim()))
        return out

    def _scripts(self, mark: str, tokens: list[Any], index: int, out: list[Item]) -> int:
        """Attach a subscript or superscript (and the other one, when it follows) to the item before it."""
        argument, index = take_argument(tokens, index)
        scripts = {mark: self._argument(argument)}
        following = index
        while following < len(tokens) and isinstance(tokens[following], str) and tokens[following].isspace():
            following += 1
        if following < len(tokens) and isinstance(tokens[following], str) and tokens[following] in "^_":
            if tokens[following] != mark:
                argument, index = take_argument(tokens, following + 1)
                scripts[tokens[following]] = self._argument(argument)
        sub, sup = scripts.get("_"), scripts.get("^")
        if out and isinstance(out[-1], _Operator):
            operator = out[-1]
            operator.sub = sub if sub is not None else operator.sub
            operator.sup = sup if sup is not None else operator.sup
            return index
        out.append(_scripts_element(_pop_base(out), sub, sup))
        return index

    def _delimiter(self, tokens: list[Any], index: int) -> tuple[str, int]:
        r"""Return the delimiter after ``\left`` and its kin (``.`` is none), and the index after it."""
        token, index = take_argument(tokens, index)
        if token is None or _is_char(token, "."):
            return "", index
        if isinstance(token, str):
            return token, index
        if _is_node(token, "LatexMacroNode"):
            return _DELIMITERS.get(token.macroname) or str(self.l2t.nodelist_to_text([token])), index
        return token.latex_verbatim(), index

    def _delimited(self, tokens: list[Any], index: int) -> tuple[etree._Element, int]:
        r"""Convert ``\left( ... \middle| ... \right)``, which starts at ``tokens[index]``."""
        opening, index = self._delimiter(tokens, index)
        segments: list[list[Any]] = [[]]
        separator = None
        closing = ""
        depth = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            name = token.macroname if _is_node(token, "LatexMacroNode") else None
            if name == "left":
                depth += 1
            elif name == "right" and depth:
                depth -= 1
            elif name == "right":
                closing, index = self._delimiter(tokens, index)
                break
            elif name == "middle" and not depth:
                character, index = self._delimiter(tokens, index)
                separator = separator or character
                segments.append([])
                continue
            segments[-1].append(token)
        properties = _element("dPr", _value("begChr", opening))
        if separator:
            properties.append(_value("sepChr", separator))
        properties.append(_value("endChr", closing))
        parts = [_element("e", *_assemble(self.items(segment))) for segment in segments]
        return _element("d", properties, *parts), index

    def _macro(self, node: Any, tokens: list[Any], index: int, out: list[Item]) -> int:  # noqa: C901
        """Convert one macro, appending to ``out``; return the index of the next token."""
        name = node.macroname
        args, optional, index = macro_arguments(node, tokens, index, _ARITY.get(name, 0))

        if name in _SPACES:
            if _SPACES[name]:
                out.append(self._run(_SPACES[name]))
        elif name == "left":
            delimited, index = self._delimited(tokens, index)
            out.append(delimited)
        elif name in ("right", "middle") or name in _SIZED:
            character, index = self._delimiter(tokens, index)
            if character:
                out.append(self._run(character))
        elif name in _DROPPED:
            pass
        elif name == "\\":
            out.append(self._run(chr(0x2003)))
        elif name in _NARY:
            out.append(_Operator("nary", _NARY[name]))
        elif name in _FUNCTIONS or name in _LIMIT_FUNCTIONS:
            out.append(_Operator("func", _FUNCTION_NAMES.get(name, name), limits=name in _LIMIT_FUNCTIONS))
        elif name == "operatorname" and args:
            starred = False
            if _is_char(args[0], "*"):
                # pylatexenc does not know \operatorname*, so the star is the first "argument".
                starred = True
                args[0], index = take_argument(tokens, index)
            out.append(_Operator("func", self._plain_text(args[0]).strip(), limits=starred))
        elif name in _FRACTIONS and len(args) == 2:
            out.append(_element("f", self._in("num", args[0]), self._in("den", args[1])))
        elif name in _BINOMIALS and len(args) == 2:
            fraction = _element(
                "f", _element("fPr", _value("type", "noBar")), self._in("num", args[0]), self._in("den", args[1])
            )
            out.append(_element("d", _element("e", fraction)))
        elif name == "sqrt" and args:
            degree = self._argument(optional) if optional is not None else []
            properties = _element("radPr")
            if not degree:
                properties.append(_value("degHide", "1"))
            out.append(_element("rad", properties, _element("deg", *_assemble(degree)), self._in("e", args[0])))
        elif name in _ACCENTS and args:
            out.append(_element("acc", _element("accPr", _value("chr", _ACCENTS[name])), self._in("e", args[0])))
        elif name in _BARS and args:
            out.append(_element("bar", _element("barPr", _value("pos", _BARS[name])), self._in("e", args[0])))
        elif name in _GROUP_CHARACTERS and args:
            character, position = _GROUP_CHARACTERS[name]
            properties = _element(
                "groupChrPr",
                _value("chr", character),
                _value("pos", position),
                _value("vertJc", "bot" if position == "top" else "top"),
            )
            out.append(_element("groupChr", properties, self._in("e", args[0])))
        elif name in _TEXT and args:
            out.append(_Run(self._plain_text(args[0]), normal=True))
        elif name in _STYLES and args:
            with self._font(*_STYLES[name]):
                out.append(_Group(self._argument(args[0])))
        elif name == "boxed" and args:
            out.append(_element("borderBox", self._in("e", args[0])))
        elif name == "tag" and args:
            out.append(_Run(f"{chr(0x2003) * 2}({self._plain_text(args[0]).strip()})", normal=True))
        elif name == "pmod" and args:
            out.extend([self._run(chr(0x2003) + "("), _Run("mod", style="p"), self._run(chr(0x2004))])
            out.extend(self._argument(args[0]))
            out.append(self._run(")"))
        else:
            text = str(self.l2t.nodelist_to_text([node])).strip()
            if not text:
                # A macro pylatexenc does not know: keep it as written, with the groups after it.
                text = node.latex_verbatim().rstrip()
                while index < len(tokens) and _is_node(tokens[index], "LatexGroupNode"):
                    text += tokens[index].latex_verbatim()
                    index += 1
            out.append(self._run(text))
        return index

    def _in(self, tag: str, argument: Any) -> etree._Element:
        """Return an argument converted and wrapped in ``m:<tag>`` (``m:num``, ``m:e``, ...)."""
        return _element(tag, *_assemble(self._argument(argument)))

    # Environments ---------------------------------------------------------

    def _rows(self, nodes: list[Any]) -> list[list[list[Item]]]:
        """Split an environment's body into rows of cells."""
        rows: list[list[list[Item]]] = []
        cells: list[list[Item]] = []
        current: list[Any] = []
        for node in nodes or []:
            if _is_cell_break(node):
                cells.append(self.items(current))
                current = []
            elif _is_row_break(node):
                cells.append(self.items(current))
                rows.append(cells)
                cells, current = [], []
            else:
                current.append(node)
        last = self.items(current)
        if last or cells:
            cells.append(last)
            rows.append(cells)
        return [row for row in rows if any(row)]

    def _environment(self, name: str, nodes: list[Any]) -> Item:
        """Lay an environment out: a matrix (``m:m``) for the matrix family and ``cases``, an equation array otherwise.

        ``cases`` is a brace on the left (``rcases``, on the right) of
        left-aligned columns. In an equation array, each ``&`` stays in the
        row as an alignment point, which is how Word aligns ``aligned`` at its
        relations.
        """
        body = nodes
        if name == "array" or name.startswith("alignat"):
            # The column spec ({cc} or {2}) is the first argument; pylatexenc may leave it in the body.
            tokens = list(nodes or [])
            if tokens and _is_node(tokens[0], "LatexGroupNode"):
                body = tokens[1:]
        rows = self._rows(body)
        if not rows:
            return _Group([])
        if name in _MATRICES or name in _CASES:
            if name in _CASES:
                # Word aligns an equation array at an ``&`` only before an operator, and a
                # condition rarely starts with one, so cases are left-aligned columns.
                left, right = ("", "}") if name == "rcases" else ("{", "")
                matrix = _matrix(rows, "left", gap="240")
            else:
                left, right = _MATRICES[name]
                matrix = _matrix(rows, "center")
            if not left and not right:
                return matrix
            return _element(
                "d", _element("dPr", _value("begChr", left), _value("endChr", right)), _element("e", matrix)
            )
        array = _element("eqArr")
        for row in rows:
            content: list[Item] = []
            for position, cell in enumerate(row):
                if position:
                    content.append(_Run("&"))
                content.extend(cell)
            array.append(_element("e", *_assemble(content)))
        return array


def _matrix(rows: list[list[list[Item]]], justification: str, gap: str | None = None) -> etree._Element:
    """Return rows of cells as an ``m:m``, its columns justified alike; ``gap`` widens the space between them."""
    columns = max(len(row) for row in rows)
    properties = _element("mPr")
    if gap:
        properties.append(_value("cGpRule", "3"))
        properties.append(_value("cGp", gap))
    column = _element("mcPr", _value("count", str(columns)), _value("mcJc", justification))
    properties.append(_element("mcs", _element("mc", column)))
    matrix = _element("m", properties)
    for row in rows:
        cells = [_element("e", *_assemble(cell)) for cell in row]
        cells.extend(_element("e") for _ in range(columns - len(row)))
        matrix.append(_element("mr", *cells))
    return matrix
