#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/terminal_math.py
r"""LaTeX math as Unicode text, for the terminal renderer's ``math_mode="unicode"``.

A terminal cannot typeset, so the renderer shows math as its LaTeX source by
default. This module offers a readable alternative made of ordinary characters:
``\alpha^2 + x_i`` becomes ``α² + xᵢ``, ``\frac{a+b}{2}`` becomes ``(a+b)/2``
and ``\int_0^\infty`` becomes ``∫₀^∞``. Nothing is dropped: a script with a
character Unicode has no superscript or subscript for keeps its ``^``/``_``
and gains parentheses where its extent would be unclear, and a macro the
converter does not know is kept as written.

Display math with rows (``aligned``, ``cases``, the ``matrix`` family, or
``\\`` at the top level) is laid out on several lines, with its columns lined
up; inline math puts rows on one line, separated by ``;``.

The LaTeX is parsed with ``pylatexenc`` (the ``latex`` extra), which also
names the symbols (``\leq`` is ``≤``). Without it, or when a formula cannot be
converted, :func:`latex_to_unicode` returns ``None`` and the caller shows the
LaTeX source.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

_SUPERSCRIPTS = dict(
    zip(
        "0123456789+-=()abcdefghijklmnoprstuvwxyzABDEGHIJKLMNOPRTUVWαβγδθφχ",
        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂᵅᵝᵞᵟᶿᵠᵡ",
        strict=True,
    )
)
_SUBSCRIPTS = dict(
    zip(
        "0123456789+-=()aehijklmnoprstuvxβγρφχ",
        "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓᵦᵧᵨᵩᵪ",
        strict=True,
    )
)
_VULGAR_FRACTIONS = {
    ("1", "2"): "½",
    ("1", "3"): "⅓",
    ("2", "3"): "⅔",
    ("1", "4"): "¼",
    ("3", "4"): "¾",
    ("1", "5"): "⅕",
    ("1", "6"): "⅙",
    ("1", "8"): "⅛",
}
_PRIMES = {"'": "′", "''": "″", "'''": "‴"}
_SCRIPT_CHARS = frozenset(_SUPERSCRIPTS.values()) | frozenset(_SUBSCRIPTS.values()) | frozenset("′″‴")

#: Combining marks for accents on a single character (overline and underline go on every character).
_ACCENTS = {
    "hat": chr(0x302),
    "widehat": chr(0x302),
    "tilde": chr(0x303),
    "widetilde": chr(0x303),
    "bar": chr(0x305),
    "overline": chr(0x305),
    "underline": chr(0x332),
    "vec": chr(0x20D7),
    "dot": chr(0x307),
    "ddot": chr(0x308),
    "acute": chr(0x301),
    "grave": chr(0x300),
    "breve": chr(0x306),
    "check": chr(0x30C),
}
_SPREAD_ACCENTS = frozenset({"overline", "underline"})

#: Macros whose argument is shown as it is (the font changes a terminal cannot show).
_PLAIN_STYLE = frozenset(
    {"mathrm", "mathit", "mathbf", "mathsf", "mathtt", "boldsymbol", "bm", "mathnormal", "operatorname", "displaystyle"}
)
_TEXT = frozenset({"text", "textrm", "textit", "textbf", "textsf", "texttt", "mbox", "emph"})
_FRACTIONS = frozenset({"frac", "dfrac", "tfrac", "cfrac"})
_BINOMIALS = frozenset({"binom", "dbinom", "tbinom"})
_DELIMITER_SIZES = frozenset(
    {"left", "right", "middle", "big", "Big", "bigg", "Bigg"}
    | {f"{size}{side}" for size in ("big", "Big", "bigg", "Bigg") for side in ("l", "r", "m")}
)
_DROPPED = frozenset({"label", "nonumber", "notag", "limits", "nolimits", "displaystyle", "textstyle"})
_SPACES = {",": " ", ":": " ", ";": " ", " ": " ", "!": "", "quad": "  ", "qquad": "    ", "enspace": " "}
#: How many arguments a macro takes when pylatexenc does not know it.
_ARITY = dict.fromkeys(_FRACTIONS | _BINOMIALS, 2) | dict.fromkeys(
    (*_ACCENTS, *_PLAIN_STYLE, *_TEXT, "sqrt", "tag", "label", "boxed", "pmod"), 1
)

_MATRICES = {
    "matrix": ("", ""),
    "smallmatrix": ("", ""),
    "array": ("", ""),
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("‖", "‖"),
}
_GATHERED = frozenset({"gathered", "gather", "gather*", "multline", "multline*", "equation", "equation*"})
_CASES = frozenset({"cases", "dcases", "rcases"})

#: Tall delimiters: (top, middle, bottom, fill) for a delimiter several lines high.
_TALL = {
    "(": ("⎛", "⎜", "⎝", "⎜"),
    ")": ("⎞", "⎟", "⎠", "⎟"),
    "[": ("⎡", "⎢", "⎣", "⎢"),
    "]": ("⎤", "⎥", "⎦", "⎥"),
    "{": ("⎧", "⎨", "⎩", "⎪"),
    "}": ("⎫", "⎬", "⎭", "⎪"),
    "|": ("│", "│", "│", "│"),
    "‖": ("‖", "‖", "‖", "‖"),
}

#: Stands for a space that must survive whitespace collapsing (``\quad``, spaces inside ``\text``).
_HARD_SPACE = "\x00"
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"[^\W\d_]+")
_ROOTS = "√∛∜"


def latex_to_unicode(latex: str, inline: bool = False) -> Optional[str]:
    r"""Return LaTeX math as Unicode text, or ``None`` when it cannot be converted.

    Parameters
    ----------
    latex : str
        The formula, without ``$`` delimiters.
    inline : bool, default False
        Keep the result on one line. Display math (the default) puts the rows
        of ``aligned``, ``cases`` and matrices on lines of their own.

    Returns
    -------
    str or None
        The text, or ``None`` when ``pylatexenc`` is not installed or the
        formula does not parse.

    Examples
    --------
        >>> latex_to_unicode(r"\alpha^2 + x_i")  # doctest: +SKIP
        'α² + xᵢ'

    """
    try:
        from pylatexenc.latex2text import LatexNodes2Text
        from pylatexenc.latexwalker import LatexWalker
    except ImportError:
        return None
    try:
        nodes, _, _ = LatexWalker(latex, tolerant_parsing=True).get_latex_nodes()
        converter = _Converter(LatexNodes2Text(math_mode="text"), inline)
        box = converter.top(nodes)
    except Exception as e:  # noqa: BLE001 - any failure falls back to the LaTeX source
        logger.debug("Could not convert math to Unicode: %s", e)
        return None
    lines = [line.rstrip() for line in box.lines]
    text = lines[0].strip() if len(lines) == 1 else "\n".join(lines).strip("\n")
    return text or None


def text_width(text: str) -> int:
    """Return the number of terminal cells ``text`` takes (combining marks take none)."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


@dataclass
class _Box:
    """Lines of text, laid out together, with the row that lines up with the text around it."""

    lines: list[str]
    baseline: int = 0

    @property
    def width(self) -> int:
        return max((text_width(line) for line in self.lines), default=0)


Fragment = Union[str, _Box]


def _collapse(text: str) -> str:
    """Collapse runs of whitespace (LaTeX math ignores it) and turn hard spaces back into spaces."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([(\[{]) ", r"\1", text)
    text = re.sub(r" ([)\]}])", r"\1", text)
    return text.replace(_HARD_SPACE, " ")


def _pad(text: str, width: int, align: str = "l") -> str:
    gap = max(0, width - text_width(text))
    if align == "r":
        return " " * gap + text
    if align == "c":
        return " " * (gap // 2) + text + " " * (gap - gap // 2)
    return text + " " * gap


def _hjoin(fragments: list[Fragment]) -> _Box:
    """Lay fragments side by side, lining up their baselines."""
    boxes: list[_Box] = []
    run: list[str] = []
    for fragment in fragments:
        if isinstance(fragment, str):
            run.append(fragment)
            continue
        if run:
            boxes.append(_Box([_collapse("".join(run))]))
            run = []
        boxes.append(fragment)
    if run:
        boxes.append(_Box([_collapse("".join(run))]))
    if len(boxes) == 1:
        return boxes[0]
    above = max((box.baseline for box in boxes), default=0)
    below = max((len(box.lines) - box.baseline - 1 for box in boxes), default=0)
    lines = [""] * (above + below + 1)
    for box in boxes:
        width = box.width
        top = above - box.baseline
        for row in range(len(lines)):
            index = row - top
            line = box.lines[index] if 0 <= index < len(box.lines) else ""
            lines[row] += _pad(line, width)
    return _Box(lines, above)


def _flatten(fragments: list[Fragment]) -> str:
    """Return fragments as one line: the rows of a box are joined with ``; ``."""
    return _collapse(
        "".join(
            fragment if isinstance(fragment, str) else "; ".join(line.strip() for line in fragment.lines)
            for fragment in fragments
        )
    ).strip()


def _tall(delimiter: str, height: int) -> list[str]:
    """Return a delimiter drawn ``height`` lines high."""
    if not delimiter:
        return [""] * height
    if height == 1 or delimiter not in _TALL:
        return [delimiter] * height
    top, middle, bottom, fill = _TALL[delimiter]
    lines = [fill] * height
    lines[0], lines[-1] = top, bottom
    if delimiter in "{}" and height > 2:
        lines[(height - 1) // 2] = middle
    return lines


def _script(text: str, superscript: bool) -> str:
    """Return ``text`` as a superscript or subscript, with ``^``/``_`` when Unicode cannot."""
    compact = text.replace(" ", "")
    if superscript and compact and set(compact) <= set("′″‴"):
        return compact
    table = _SUPERSCRIPTS if superscript else _SUBSCRIPTS
    if compact and all(char in table for char in compact):
        return "".join(table[char] for char in compact)
    mark = "^" if superscript else "_"
    if _is_term(compact):
        return mark + compact
    return f"{mark}({text.strip()})"


def _is_term(text: str) -> bool:
    """Return whether ``text`` reads as one term beside ``/`` or ``^``: a number, a word, a symbol or a group.

    A symbol may carry accents, scripts and a root sign (``√x²``); a word is
    letters only (``dx``), so ``2a`` is not a term.
    """
    if _NUMBER.fullmatch(text) or _WORD.fullmatch(text) or _is_group(text):
        return True
    core = "".join(c for c in text.lstrip(_ROOTS) if c not in _SCRIPT_CHARS and not unicodedata.combining(c))
    return len(core) <= 1 or _is_group(core)


def _is_group(text: str) -> bool:
    """Return whether ``text`` is one bracketed group, such as ``(a+b)`` (not ``(a)+(b)``)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    if len(text) < 2 or text[0] not in pairs or text[-1] != pairs[text[0]]:
        return False
    depth = 0
    for position, char in enumerate(text):
        depth += char == text[0]
        depth -= char == pairs[text[0]]
        if depth == 0 and position < len(text) - 1:
            return False
    return True


def _operand(text: str) -> str:
    """Return ``text`` as a fraction's numerator or denominator, in parentheses unless it is one term."""
    text = text.strip()
    return text if _is_term(text) else f"({text})"


class _Converter:
    """Turn a pylatexenc node list into fragments of text."""

    def __init__(self, l2t: Any, inline: bool) -> None:
        self.l2t = l2t
        self.inline = inline

    # Tokens ---------------------------------------------------------------

    @staticmethod
    def _tokens(nodes: list[Any]) -> list[Any]:
        """Split character nodes into single characters; other nodes stay as they are."""
        tokens: list[Any] = []
        for node in nodes or []:
            if node is None:
                continue
            if _is_node(node, "LatexCharsNode"):
                tokens.extend(node.chars)
            elif _is_node(node, "LatexCommentNode"):
                continue
            else:
                tokens.append(node)
        return tokens

    @staticmethod
    def _take_argument(tokens: list[Any], index: int) -> tuple[Any, int]:
        """Return the argument starting at ``tokens[index]`` (spaces skipped) and the index after it."""
        while index < len(tokens) and isinstance(tokens[index], str) and tokens[index].isspace():
            index += 1
        if index >= len(tokens):
            return None, index
        return tokens[index], index + 1

    def _text(self, argument: Any) -> str:
        """Return a macro or script argument as one line of text."""
        if argument is None:
            return ""
        if isinstance(argument, str):
            return argument
        if _is_node(argument, "LatexGroupNode"):
            return _flatten(self.fragments(argument.nodelist))
        return _flatten(self.fragments([argument]))

    def _verbatim_text(self, argument: Any) -> str:
        r"""Return the argument of ``\text`` and friends: text mode, its spaces kept."""
        if argument is None:
            return ""
        if isinstance(argument, str):
            return argument
        nodes = argument.nodelist if _is_node(argument, "LatexGroupNode") else [argument]
        return str(self.l2t.nodelist_to_text(nodes)).replace(" ", _HARD_SPACE)

    # Conversion -----------------------------------------------------------

    def top(self, nodes: list[Any]) -> _Box:
        r"""Convert a whole formula; ``\\`` and ``&`` at the top level make rows, as in ``gather``."""
        tokens = self._tokens(nodes)
        if any(_is_row_break(token) or _is_cell_break(token) for token in tokens):
            has_cells = any(_is_cell_break(token) for token in tokens)
            laid_out = self._environment("aligned" if has_cells else "gathered", nodes)
            return laid_out if isinstance(laid_out, _Box) else _Box([laid_out])
        fragments = self.fragments(nodes)
        if self.inline:
            return _Box([_flatten(fragments)])
        return _hjoin(fragments)

    def fragments(self, nodes: list[Any]) -> list[Fragment]:
        """Convert a node list to fragments: strings, and boxes for anything with rows."""
        tokens = self._tokens(nodes)
        out: list[Fragment] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if isinstance(token, str):
                if token in "^_":
                    argument, index = self._take_argument(tokens, index)
                    out.append(_script(self._text(argument), token == "^"))
                    if getattr(argument, "macro_post_space", ""):
                        # ``^\infty e``: the space that ended the macro keeps ``^∞`` off the ``e``.
                        out.append(" ")
                elif token == "'":
                    count = 1
                    while index < len(tokens) and _is_char(tokens[index], "'") and count < 3:
                        count += 1
                        index += 1
                    out.append(_PRIMES["'" * count])
                elif token in "{}":
                    continue
                else:
                    out.append(token)
            elif _is_node(token, "LatexGroupNode"):
                out.extend(self.fragments(token.nodelist))
            elif _is_node(token, "LatexMacroNode"):
                index = self._macro(token, tokens, index, out)
            elif _is_node(token, "LatexEnvironmentNode"):
                out.append(self._environment(token.environmentname, token.nodelist))
            elif _is_node(token, "LatexMathNode"):
                out.extend(self.fragments(token.nodelist))
            elif _is_node(token, "LatexSpecialsNode"):
                if token.specials_chars == "~":
                    out.append(_HARD_SPACE)
                elif token.specials_chars in _PRIMES:
                    # pylatexenc reads ``''`` as a closing quote; in math it is a double prime.
                    out.append(_PRIMES[token.specials_chars])
                elif token.specials_chars != "&":
                    out.append(str(self.l2t.nodelist_to_text([token])))
            else:
                out.append(token.latex_verbatim())
        return out

    def _arguments(self, node: Any, tokens: list[Any], index: int, count: int) -> tuple[list[Any], Any, int]:
        """Return ``count`` mandatory arguments, the optional one, and the index after them.

        pylatexenc parses the arguments of the macros it knows; for the others
        they are the next tokens.
        """
        parsed = list(getattr(getattr(node, "nodeargd", None), "argnlist", None) or [])
        optional = None
        mandatory: list[Any] = []
        for argument in parsed:
            if argument is None:
                continue
            if _is_node(argument, "LatexGroupNode") and argument.delimiters == ("[", "]"):
                optional = argument
            else:
                mandatory.append(argument)
        if not parsed and count and index < len(tokens) and _is_char(tokens[index], "["):
            close = next((i for i in range(index, len(tokens)) if _is_char(tokens[i], "]")), None)
            if close is not None:
                optional = "".join(t if isinstance(t, str) else t.latex_verbatim() for t in tokens[index + 1 : close])
                index = close + 1
        while len(mandatory) < count:
            argument, index = self._take_argument(tokens, index)
            if argument is None:
                break
            mandatory.append(argument)
        return mandatory, optional, index

    def _macro(self, node: Any, tokens: list[Any], index: int, out: list[Fragment]) -> int:  # noqa: C901
        """Convert one macro, appending to ``out``; return the index of the next token."""
        name = node.macroname
        trailing = " " if node.macro_post_space else ""
        count = _ARITY.get(name, 0)
        args, optional, index = self._arguments(node, tokens, index, count)

        if name in _SPACES:
            space = _SPACES[name]
            out.append(space.replace(" ", _HARD_SPACE) if len(space) > 1 else space)
        elif name in _DELIMITER_SIZES:
            if index < len(tokens) and _is_char(tokens[index], "."):
                index += 1
        elif name in _DROPPED:
            pass
        elif name == "\\":
            out.append("; ")
        elif name in _FRACTIONS and len(args) == 2:
            numerator, denominator = self._text(args[0]).strip(), self._text(args[1]).strip()
            vulgar = _VULGAR_FRACTIONS.get((numerator, denominator))
            if vulgar:
                out.append(vulgar)
            elif numerator.isdigit() and denominator.isdigit():
                out.append(_script(numerator, True) + "⁄" + _script(denominator, False))
            else:
                out.append(f"{_operand(numerator)}/{_operand(denominator)}")
        elif name in _BINOMIALS and len(args) == 2:
            out.append(f"C({self._text(args[0]).strip()}, {self._text(args[1]).strip()})")
        elif name == "sqrt" and args:
            radicand = _operand(self._text(args[0]))
            degree = (optional if isinstance(optional, str) else self._text(optional)).strip() if optional else ""
            root = {"": "√", "2": "√", "3": "∛", "4": "∜"}.get(degree)
            out.append((root or _script(degree, True) + "√") + radicand)
        elif name in _ACCENTS and args:
            out.append(_accent(self._text(args[0]), name))
        elif name in _TEXT and args:
            out.append(self._verbatim_text(args[0]))
        elif name in _PLAIN_STYLE and args:
            out.append(self._text(args[0]))
        elif name == "boxed" and args:
            out.append(f"[{self._text(args[0])}]")
        elif name == "tag" and args:
            out.append(f"{_HARD_SPACE * 4}({self._text(args[0]).strip()})")
        elif name == "pmod" and args:
            out.append(f" (mod {self._text(args[0]).strip()})")
        else:
            text = str(self.l2t.nodelist_to_text([node])).strip()
            if not text:
                # A macro pylatexenc does not know: keep it as written, with the groups after it.
                text = node.latex_verbatim().rstrip()
                while index < len(tokens) and _is_node(tokens[index], "LatexGroupNode"):
                    text += tokens[index].latex_verbatim()
                    index += 1
            out.append(text)
        out.append(trailing)
        return index

    # Environments ---------------------------------------------------------

    def _rows(self, nodes: list[Any]) -> list[list[str]]:
        """Split an environment's body into rows of cells (one line of text each)."""
        rows: list[list[str]] = []
        cells: list[str] = []
        current: list[Any] = []
        for node in nodes or []:
            if _is_cell_break(node):
                cells.append(_flatten(self.fragments(current)))
                current = []
            elif _is_row_break(node):
                cells.append(_flatten(self.fragments(current)))
                rows.append(cells)
                cells, current = [], []
            else:
                current.append(node)
        last = _flatten(self.fragments(current))
        if last or cells:
            cells.append(last)
            rows.append(cells)
        return [row for row in rows if any(cell for cell in row)]

    def _environment(self, name: str, nodes: list[Any]) -> Fragment:
        """Lay an environment out: rows on lines of their own, columns lined up.

        Matrices center their columns between tall brackets; ``cases`` puts a
        brace on the left; ``gather`` and its kin center each row; anything
        else (``aligned``, ``split``, an unknown environment) lines its columns
        up as ``align`` does, right then left, so the rows meet at the ``&``.
        """
        body = nodes
        if name == "array" or name.startswith("alignat"):
            # The column spec ({cc} or {2}) is the first argument; pylatexenc may leave it in the body.
            tokens = list(nodes or [])
            if tokens and _is_node(tokens[0], "LatexGroupNode"):
                body = tokens[1:]
        rows = self._rows(body)
        if not rows:
            return ""
        columns = max(len(row) for row in rows)
        for row in rows:
            row.extend([""] * (columns - len(row)))

        if name in _MATRICES:
            left, right = _MATRICES[name]
            if self.inline:
                inner = "; ".join(", ".join(row) for row in rows)
                return f"{left or '['}{inner}{right or ']'}" if left or len(rows) > 1 else inner
            widths = [max(text_width(row[c]) for row in rows) for c in range(columns)]
            lines = ["  ".join(_pad(cell, widths[c], "c") for c, cell in enumerate(row)) for row in rows]
            return _bracket(lines, left, right)
        if name in _CASES:
            if self.inline:
                return "{" + "; ".join(" ".join(cell for cell in row if cell) for row in rows) + "}"
            widths = [max(text_width(row[c]) for row in rows) for c in range(columns)]
            lines = ["  ".join(_pad(cell, widths[c]) for c, cell in enumerate(row)).rstrip() for row in rows]
            return _bracket(lines, "" if name == "rcases" else "{", "}" if name == "rcases" else "")
        if self.inline:
            return "; ".join(" ".join(cell for cell in row if cell) for row in rows)
        if name in _GATHERED or columns == 1:
            width = max(text_width(" ".join(row).strip()) for row in rows)
            return _Box([_pad(" ".join(row).strip(), width, "c") for row in rows], (len(rows) - 1) // 2)
        widths = [max(text_width(row[c]) for row in rows) for c in range(columns)]
        lines = []
        for row in rows:
            parts = [_pad(cell, widths[c], "r" if c % 2 == 0 else "l") for c, cell in enumerate(row)]
            lines.append(" ".join(parts).rstrip())
        return _Box(lines, (len(lines) - 1) // 2)


def _bracket(lines: list[str], left: str, right: str) -> _Box:
    """Put tall delimiters around lines of text."""
    height = len(lines)
    width = max((text_width(line) for line in lines), default=0)
    lefts, rights = _tall(left, height), _tall(right, height)
    pad_left = " " if left else ""
    pad_right = " " if right else ""
    rows = [f"{lefts[i]}{pad_left}{_pad(line, width)}{pad_right}{rights[i]}" for i, line in enumerate(lines)]
    return _Box(rows, (height - 1) // 2)


def _accent(text: str, name: str) -> str:
    """Put an accent on ``text``: a combining mark on one character, on every character for over/underline."""
    mark = _ACCENTS[name]
    stripped = text.strip()
    if name in _SPREAD_ACCENTS and stripped:
        return "".join(char + mark if not char.isspace() else char for char in stripped)
    if len(stripped) == 1:
        return stripped + mark
    return f"{name}({stripped})"


def _is_cell_break(token: Any) -> bool:
    return _is_node(token, "LatexSpecialsNode") and token.specials_chars == "&"


def _is_row_break(token: Any) -> bool:
    return _is_node(token, "LatexMacroNode") and token.macroname == "\\"


def _is_char(token: Any, char: str) -> bool:
    """Return whether a token is the character ``char`` (a pylatexenc node cannot be compared with a string)."""
    return isinstance(token, str) and token == char


def _is_node(token: Any, node_type: str) -> bool:
    """Return whether a token is a pylatexenc node of the given type."""
    from pylatexenc import latexwalker

    return not isinstance(token, str) and bool(token.isNodeType(getattr(latexwalker, node_type)))
