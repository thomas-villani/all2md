#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/man.py
"""Unix man page (man(7)) to AST converter.

Man pages are roff source written with the man(7) macro package. This parser
reads the macros directly rather than emulating roff: it understands the
structural macros (``.TH``, ``.SH``, ``.SS``, paragraphs, tagged and indented
paragraphs, ``.RS``/``.RE`` nesting, no-fill regions, links and simple ``tbl``
tables), the font macros and escapes, and enough of the roff request language
(conditionals, string definitions, skipped macro definitions) to read the
preamble pod2man writes at the top of every Perl manual page.

Anything else is ignored, as roff itself ignores an undefined macro. The mdoc(7)
macro package (``.Dd``/``.Sh``, used by BSD manuals) is a different language
and is not read here.

"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Callable, Literal, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    Heading,
    LineBreak,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast.nodes import Alignment
from all2md.converter_metadata import ConverterMetadata
from all2md.options.man import ManParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)

# Fonts a run of text can carry. "C" is any constant-width font (CW, CR, ...);
# "CB", "CI" and "CBI" are constant width inside bold and/or italic text.
_Font = Literal["R", "B", "I", "BI", "C", "CB", "CI", "CBI"]
_LINE_BREAK = "\n"  # text of the sentinel run that stands for .br

_FONT_NAMES: dict[str, _Font] = {
    "R": "R",
    "1": "R",
    "I": "I",
    "2": "I",
    "B": "B",
    "3": "B",
    "BI": "BI",
    "4": "BI",
    "C": "C",
    "CW": "C",
    "CR": "C",
    "CB": "CB",
    "CI": "CI",
    "CBI": "CBI",
    "CO": "C",
    "TT": "C",
}

# Special characters (\(xx and \[name]) that man pages actually use.
_SPECIAL_CHARS: dict[str, str] = {
    "em": "\u2014",
    "en": "\u2013",
    "hy": "-",
    "mi": "-",
    "pl": "+",
    "mu": "\u00d7",
    "di": "\u00f7",
    "+-": "\u00b1",
    "eq": "=",
    "==": "\u2261",
    ">=": "\u2265",
    "<=": "\u2264",
    "!=": "\u2260",
    "->": "\u2192",
    "<-": "\u2190",
    "<>": "\u2194",
    "rA": "\u21d2",
    "lA": "\u21d0",
    "ua": "\u2191",
    "da": "\u2193",
    "bu": "\u2022",
    "ci": "\u25cb",
    "sq": "\u25a1",
    "lq": "\u201c",
    "rq": "\u201d",
    "oq": "\u2018",
    "cq": "\u2019",
    "aq": "'",
    "dq": '"',
    "Fo": "\u00ab",
    "Fc": "\u00bb",
    "fo": "\u2039",
    "fc": "\u203a",
    "ga": "`",
    "aa": "\u00b4",
    "ti": "~",
    "a~": "~",
    "ha": "^",
    "a^": "^",
    "rs": "\\",
    "sl": "/",
    "ba": "|",
    "or": "|",
    "br": "\u2502",
    "rn": "\u203e",
    "ul": "_",
    "co": "\u00a9",
    "rg": "\u00ae",
    "tm": "\u2122",
    "de": "\u00b0",
    "ss": "\u00df",
    "sc": "\u00a7",
    "ps": "\u00b6",
    "dg": "\u2020",
    "dd": "\u2021",
    "ct": "\u00a2",
    "Po": "\u00a3",
    "Eu": "\u20ac",
    "eu": "\u20ac",
    "Ye": "\u00a5",
    "at": "@",
    "sh": "#",
    "Do": "$",
    "lB": "[",
    "rB": "]",
    "lC": "{",
    "rC": "}",
    "la": "\u27e8",
    "ra": "\u27e9",
    "%0": "\u2030",
    "12": "\u00bd",
    "14": "\u00bc",
    "34": "\u00be",
    "if": "\u221e",
}

# Strings (\*x, \*(xx) defined by the man macros themselves; .ds adds more.
_PREDEFINED_STRINGS: dict[str, str] = {
    "R": "\u00ae",
    "S": "",
    "Tm": "\u2122",
    "lq": "\u201c",
    "rq": "\u201d",
    "Aq": "'",
}

# Escapes that take a delimited argument ('...'), and escapes that take a name.
_DELIMITED_ESCAPES = frozenset("hvwoXZbBlLDRNASx")
_NAMED_ESCAPES = frozenset("nmMFYVgk$")
_EMPTY_ESCAPES = frozenset("&|^,/:%){}!pdurtac")  # those that print nothing here

_BULLET_TAGS = frozenset({"\u2022", "\u00b7", "*", "-", "+", "o", "\u2013", "\u2014", "\u25cb", "\u25e6", "\u2023"})
_NUMBERED_TAG = re.compile(r"^\(?(\d+)[.)]?$")

# Requests and macros with no visible effect here; listed so they are not
# reported as unknown.
_IGNORED_MACROS = frozenset(
    {
        "PD",
        "ad",
        "na",
        "hy",
        "nh",
        "ne",
        "in",
        "ti",
        "ll",
        "ps",
        "vs",
        "ta",
        "bp",
        "ns",
        "rs",
        "nr",
        "rr",
        "rm",
        "rn",
        "tr",
        "cc",
        "c2",
        "ec",
        "eo",
        "lf",
        "mso",
        "do",
        "pc",
        "lg",
        "ss",
        "cs",
        "fam",
        "ev",
        "DT",
        "UC",
        "AT",
        "IX",
        "ul",
        "cu",
        "ce",
        "pl",
        "po",
        "pn",
        "nm",
        "nn",
        "mk",
        "rt",
        "fl",
        "hc",
        "hw",
        "hla",
        "hlm",
        "hym",
        "hys",
        "char",
        "fchar",
        "schar",
        "tm",
        "ab",
        "so",
        "blm",
        "lsm",
        "warn",
        "cp",
        "sy",
        "pso",
        "open",
        "close",
        "write",
        "ch",
        "wh",
        "it",
        "itc",
        "em",
        "kern",
        "ftr",
        "fspecial",
        "special",
        "sizes",
        "fp",
        "fzoom",
        "pm",
        "pev",
        "pnr",
        "ptr",
        "als",
        "aln",
        "chop",
        "substring",
        "length",
        "nop",
        "BT",
        "PT",
        "YS",
    }
)

_MAX_STRING_DEPTH = 8

# Requests a page may issue before .TH (pod2man's preamble is made of these).
_PREAMBLE_REQUESTS = frozenset(
    {
        "de",
        "de1",
        "am",
        "ig",
        "ds",
        "as",
        "nr",
        "rr",
        "if",
        "ie",
        "el",
        "br",
        "ad",
        "na",
        "nh",
        "hy",
        "ss",
        "ll",
        "rm",
        "tr",
        "IX",
    }
)


def _is_man_content(data: bytes) -> bool:
    r"""Return True when the sample is roff source that opens with ``.TH``.

    Comment lines (``.\"``), blank lines, the ``'\" t`` preprocessor hint and a
    preamble of roff requests (macro and string definitions, conditionals, as
    pod2man writes) are skipped; the first macro after them must be ``.TH``. A
    sample that ends before any macro counts too when it held a comment or a
    definition, because license headers and preambles often fill the first
    kilobyte that detection reads.

    Parameters
    ----------
    data : bytes
        The start of the input.

    Returns
    -------
    bool
        True if the content looks like a man(7) page.

    """
    if not data or b"\x00" in data[:1024]:
        return False
    text = data[:4096].decode("latin-1")
    lines = text.splitlines()
    if len(data) > 4096 or (lines and not text.endswith(("\n", "\r"))):
        lines = lines[:-1]  # the last line may be cut short
    saw_roff = False
    in_definition = False
    for line in lines:
        stripped = line.strip()
        if in_definition:
            in_definition = re.match(r"^[.']\s*\.(\s|$)", stripped) is None
            continue
        if not stripped:
            continue
        if re.match(r"^[.']\s*\\[\"#{}]", stripped) or stripped in (".", "'"):
            saw_roff = True
            continue
        request = re.match(r"^[.']\s*([^\s\\]+)", stripped)
        if request is None:
            return False
        name = request.group(1)
        if name == "TH":
            return True
        if name in _PREAMBLE_REQUESTS:
            saw_roff = True
            in_definition = name in ("de", "de1", "am", "ig")
            continue
        return False
    return saw_roff


def _split_args(text: str) -> list[str]:
    r"""Split macro arguments the way roff does: on spaces, honoring double quotes.

    Inside a quoted argument ``""`` stands for one literal quote. Escapes are kept
    as written; an escaped space (``\ ``) does not split.

    """
    args: list[str] = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " \t":
            i += 1
        if i >= n:
            break
        buf: list[str] = []
        if text[i] == '"':
            i += 1
            while i < n:
                ch = text[i]
                if ch == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                if ch == "\\" and i + 1 < n:
                    buf.append(text[i : i + 2])
                    i += 2
                    continue
                buf.append(ch)
                i += 1
        else:
            while i < n and text[i] not in " \t":
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i : i + 2])
                    i += 2
                    continue
                buf.append(text[i])
                i += 1
        args.append("".join(buf))
    return args


def _strip_comment(line: str) -> tuple[str, bool]:
    r"""Remove a ``\"`` or ``\#`` comment from a line.

    Returns
    -------
    tuple[str, bool]
        The line without its comment, and True when the comment was ``\#``,
        which also joins the line to the next one.

    """
    i, n = 0, len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            nxt = line[i + 1]
            if nxt == '"':
                return line[:i], False
            if nxt == "#":
                return line[:i], True
            i += 2
            continue
        i += 1
    return line, False


def _logical_lines(text: str) -> list[str]:
    r"""Split source into lines, dropping comments and joining ``\``-continued lines."""
    out: list[str] = []
    pending = ""
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        had_comment = "\\" in raw and ('\\"' in raw or "\\#" in raw)
        line, joins = _strip_comment(raw)
        trailing = len(line) - len(line.rstrip("\\"))
        if trailing % 2 == 1:
            line, joins = line[:-1], True
        line = pending + line
        if joins:
            pending = line
            continue
        pending = ""
        stripped = line.strip()
        # A request line that held only a comment (.\" ...) is not a blank line.
        if had_comment and (not stripped or stripped in (".", "'")):
            continue
        out.append(line)
    if pending:
        out.append(pending)
    return out


@dataclass
class _Frame:
    """One indentation level (the document, or the inside of ``.RS``)."""

    blocks: list[Node] = field(default_factory=list)
    list_kind: Optional[str] = None  # "dl", "ul" or "ol"
    list_start: int = 1
    dl_items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = field(default_factory=list)
    list_items: list[ListItem] = field(default_factory=list)
    item_term: Optional[list[Node]] = None
    item_blocks: Optional[list[Node]] = None


class ManParser(BaseParser):
    r"""Convert man(7) pages to AST representation.

    Parameters
    ----------
    options : ManParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
        >>> parser = ManParser()
        >>> doc = parser.parse('.TH LS 1\n.SH NAME\nls \\- list directory contents\n')

    """

    def __init__(self, options: ManParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the man page parser with options and progress callback."""
        BaseParser._validate_options_type(options, ManParserOptions, "man")
        options = options or ManParserOptions()
        super().__init__(options, progress_callback)
        self.options: ManParserOptions = options
        self._reset()

    def _reset(self) -> None:
        self._frames: list[_Frame] = [_Frame()]
        self._runs: list[tuple[str, _Font, Optional[str]]] = []
        self._font: _Font = "R"
        self._prev_font: _Font = "R"
        self._no_space = False  # previous line ended with \c
        self._pending_font: Optional[_Font] = None  # .B with no arguments
        self._capture: Optional[str] = None  # "tp", "tq", "sh" or "ss"
        self._capture_runs: list[tuple[str, _Font, Optional[str]]] = []
        self._nofill = False
        self._code_lines: list[str] = []
        self._link: Optional[str] = None
        self._link_start = 0
        self._strings: dict[str, str] = dict(_PREDEFINED_STRINGS)
        self._string_depth = 0
        self._skip_until: Optional[str] = None  # end marker of a .de/.ig block
        self._skip_depth = 0  # brace depth of a false conditional block
        self._last_condition = True
        self._table_lines: Optional[list[str]] = None
        self._metadata = DocumentMetadata()
        self._in_name_section = False
        self._warned: set[str] = set()

    # ------------------------------------------------------------------ parse

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse a man page into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The man page: a file path, raw bytes, a binary stream or roff source text.

        Returns
        -------
        Document
            AST document node

        """
        self._emit_progress("started", "Parsing man page", current=0, total=100)
        source = self._load_text_content(input_data)
        self._reset()
        for line in _logical_lines(source):
            self._process_line(line)
        self._finish()
        self._emit_progress("finished", "Parsing complete", current=100, total=100)
        return Document(children=self._frames[0].blocks, metadata=self._metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Return the metadata read from ``.TH`` and the NAME section.

        Parameters
        ----------
        document : Any
            Unused; the metadata is gathered while parsing.

        Returns
        -------
        DocumentMetadata
            Title, date, section, source, manual and one-line description.

        """
        return self._metadata

    # ------------------------------------------------------------ line level

    def _process_line(self, line: str) -> None:
        if self._skip_until is not None:
            if re.match(r"^[.']\s*" + re.escape(self._skip_until) + r"(\s|$)", line):
                self._skip_until = None
            return
        if self._skip_depth:
            self._skip_depth = max(0, self._skip_depth + line.count("\\{") - line.count("\\}"))
            return
        if "\\}" in line:
            line = line.replace("\\}", "")
        if self._table_lines is not None:
            if re.match(r"^[.']\s*TE(\s|$)", line):
                self._end_table()
            else:
                self._table_lines.append(line)
            return
        if line[:1] in (".", "'"):
            self._process_control(line[1:])
        else:
            self._process_text(line)

    def _process_control(self, body: str) -> None:
        body = body.lstrip(" \t")
        match = re.match(r"([^\s\\]*)(.*)$", body)
        name, rest = (match.group(1), match.group(2)) if match else ("", body)
        if not name:
            return
        handler = getattr(self, f"_m_{name}", None)
        if handler is None and name in _FONT_MACROS:
            self._font_macro(name, _split_args(rest))
            return
        if handler is not None:
            handler(rest)
            return
        if name in _IGNORED_MACROS:
            if name == "so":
                self._warn_once("so", "Man page includes another file (.so %s); the included text is not read", rest)
            return
        if name in ("Dd", "Dt", "Sh", "Nm"):
            self._warn_once("mdoc", "This looks like an mdoc(7) page, which all2md does not read yet")
            return
        logger.debug("Ignoring unknown man macro .%s", name)

    def _process_text(self, line: str) -> None:
        if self._nofill:
            self._code_lines.append(self._plain(line))
            return
        if not line.strip():
            if self._capture is None:
                self._flush_paragraph()
            return
        if line[:1] in (" ", "\t") and self._capture is None:
            # An indented text line starts a new output line; the indent itself has
            # no Markdown equivalent.
            if self._runs and self._runs[-1][0] != _LINE_BREAK:
                self._runs.append((_LINE_BREAK, "R", self._link))
                self._no_space = True
            line = line.lstrip(" \t")
        runs, continued = self._expand(line)
        if self._pending_font is not None:
            runs = [(text, self._pending_font, link) for text, _font, link in runs]
            self._pending_font = None
        self._add_runs(runs, continued)

    # -------------------------------------------------------------- escapes

    def _expand(self, text: str, font: Optional[_Font] = None) -> tuple[list[tuple[str, _Font, Optional[str]]], bool]:
        r"""Expand escapes in ``text`` into runs of (text, font, link).

        Font escapes (``\fB``) change the running font unless ``font`` forces one.

        Returns
        -------
        tuple
            The runs and whether the text ended with ``\c`` (join the next line).

        """
        runs: list[tuple[str, _Font, Optional[str]]] = []
        buf: list[str] = []
        continued = False

        def flush() -> None:
            if buf:
                runs.append(("".join(buf), font or self._font, self._link))
                buf.clear()

        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch != "\\":
                buf.append("\t" if ch == "\t" else ch)
                i += 1
                continue
            i += 1
            if i >= n:
                break
            esc = text[i]
            i += 1
            if esc == "f":
                fname, i = self._read_name(text, i)
                flush()
                if font is None:
                    self._set_font(fname)
            elif esc == "(":
                buf.append(self._special(text[i : i + 2]))
                i += 2
            elif esc == "[":
                end = text.find("]", i)
                end = n if end == -1 else end
                buf.append(self._special(text[i:end]))
                i = end + 1
            elif esc == "*":
                sname, i = self._read_name(text, i)
                buf.append(self._string(sname))
            elif esc == "-":
                buf.append("-")
            elif esc in ("e", "\\"):
                buf.append("\\")
            elif esc == ".":
                buf.append(".")
            elif esc in (" ", "~", "0"):
                buf.append(" ")
            elif esc == "t":
                buf.append("\t")
            elif esc == "'":
                buf.append("'")
            elif esc == "`":
                buf.append("`")
            elif esc == "c":
                if i >= n:
                    continued = True
            elif esc in ("s", "S"):
                i = self._skip_size(text, i)
            elif esc == "N":
                arg, i = self._read_delimited(text, i)
                buf.append(chr(int(arg)) if arg.isdigit() else "")
            elif esc in _DELIMITED_ESCAPES:
                _arg, i = self._read_delimited(text, i)
            elif esc in _NAMED_ESCAPES:
                if esc == "n" and i < n and text[i] in "+-":
                    i += 1
                _name, i = self._read_name(text, i)
            elif esc == "z":
                continue
            elif esc in _EMPTY_ESCAPES:
                continue
            else:
                buf.append(esc)
        flush()
        return runs, continued

    def _plain(self, text: str) -> str:
        """Expand escapes and return the text without fonts (for code and tables)."""
        saved = (self._font, self._prev_font, self._link)
        runs, _continued = self._expand(text)
        self._font, self._prev_font, self._link = saved
        return "".join(r[0] for r in runs)

    @staticmethod
    def _read_name(text: str, i: int) -> tuple[str, int]:
        """Read an escape name: one character, ``(xx`` or ``[name]``."""
        if i >= len(text):
            return "", i
        if text[i] == "(":
            return text[i + 1 : i + 3], i + 3
        if text[i] == "[":
            end = text.find("]", i)
            end = len(text) if end == -1 else end
            return text[i + 1 : end], end + 1
        return text[i], i + 1

    @staticmethod
    def _read_delimited(text: str, i: int) -> tuple[str, int]:
        """Read a delimited escape argument such as ``'2n'`` or ``[...]``."""
        if i >= len(text):
            return "", i
        delim = text[i]
        close = "]" if delim == "[" else delim
        end = text.find(close, i + 1)
        if end == -1:
            return "", len(text)
        return text[i + 1 : end], end + 1

    @staticmethod
    def _skip_size(text: str, i: int) -> int:
        r"""Skip the argument of a size escape (``\s+2``, ``\s(12``, ``\s[10]``, ``\s0``)."""
        n = len(text)
        if i < n and text[i] in "+-":
            i += 1
        if i < n and text[i] == "(":
            return i + 3
        if i < n and text[i] in "['":
            close = "]" if text[i] == "[" else "'"
            end = text.find(close, i + 1)
            return n if end == -1 else end + 1
        if i < n and text[i].isdigit():
            i += 1
            if i < n and text[i].isdigit() and text[i - 1] in "123":
                i += 1
        return i

    def _special(self, name: str) -> str:
        if name in _SPECIAL_CHARS:
            return _SPECIAL_CHARS[name]
        unicode = re.fullmatch(r"u([0-9A-Fa-f]{4,6})(?:_[0-9A-Fa-f]{4,6})*", name)
        if unicode:
            return chr(int(unicode.group(1), 16))
        number = re.fullmatch(r"char(\d+)", name)
        if number:
            return chr(int(number.group(1)))
        if len(name) == 2 and name[0] in "'`^~:," and name[1].isalpha():
            return name[1]  # accented letter, e.g. \('e; keep the base letter
        logger.debug("Unknown man special character %r", name)
        return ""

    def _string(self, name: str) -> str:
        value = self._strings.get(name, "")
        if "\\" not in value or self._string_depth >= _MAX_STRING_DEPTH:
            return value
        self._string_depth += 1
        try:
            return self._plain(value)
        finally:
            self._string_depth -= 1

    def _set_font(self, name: str) -> None:
        if name in ("P", ""):
            self._font, self._prev_font = self._prev_font, self._font
            return
        font = _FONT_NAMES.get(name)
        if font is None:
            return
        self._prev_font, self._font = self._font, font

    # ------------------------------------------------------------- inlines

    def _add_runs(self, runs: list[tuple[str, _Font, Optional[str]]], continued: bool) -> None:
        """Append one input line's runs to the paragraph or the pending capture."""
        target = self._capture_runs if self._capture is not None else self._runs
        if runs and target and not self._no_space and target[-1][0] != _LINE_BREAK:
            last = target[-1]
            target.append((" ", last[1], last[2] if last[2] == self._link else None))
        target.extend(runs)
        self._no_space = continued
        if self._capture is not None and not continued and runs:
            self._finish_capture()

    def _font_macro(self, name: str, args: list[str]) -> None:
        """Handle .B, .I, .BR and the other font macros."""
        fonts = _FONT_MACROS[name]
        if not args:
            if len(fonts) == 1:
                self._pending_font = fonts[0]
            return
        if self._nofill:
            joined = "".join(args) if len(fonts) > 1 else " ".join(args)
            self._code_lines.append(self._plain(joined))
            return
        runs: list[tuple[str, _Font, Optional[str]]] = []
        continued = False
        if len(fonts) == 1:
            runs, continued = self._expand(" ".join(args), font=fonts[0])
        else:
            for index, arg in enumerate(args):
                arg_runs, continued = self._expand(arg, font=fonts[index % 2])
                runs.extend(arg_runs)
        self._add_runs(runs, continued)

    def _inline_nodes(self, runs: list[tuple[str, _Font, Optional[str]]]) -> list[Node]:
        """Group runs into inline nodes, keeping edge whitespace outside formatting."""
        merged: list[list[Any]] = []
        for text, font, link in runs:
            if not text:
                continue
            if text == _LINE_BREAK:
                merged.append([_LINE_BREAK, "R", link])
                continue
            if merged and merged[-1][1] == font and merged[-1][2] == link and merged[-1][0] != _LINE_BREAK:
                merged[-1][0] += text
            else:
                merged.append([text, font, link])

        nodes: list[Node] = []
        link_nodes: list[Node] = []
        current_link: Optional[str] = None
        # Runs of the current stretch (same link, no line break), nested on flush.
        pending: list[tuple[str, frozenset[str]]] = []

        def flush() -> None:
            out = link_nodes if current_link is not None else nodes
            out.extend(_nest_runs(pending, frozenset()))
            pending.clear()

        def close_link() -> None:
            nonlocal current_link
            flush()
            if current_link is not None:
                content = link_nodes[:] or [Text(content=current_link)]
                nodes.append(Link(url=current_link, content=_merge_text(content)))
                link_nodes.clear()
                current_link = None

        for text, font, link in merged:
            if link != current_link:
                close_link()
                current_link = link
            if text == _LINE_BREAK:
                flush()
                (link_nodes if link is not None else nodes).append(LineBreak())
                continue
            pending.append((re.sub(r"[ \t]+", " ", text), _FONT_ATTRIBUTES[font]))
        close_link()
        return _trim(_merge_text(nodes))

    # -------------------------------------------------------------- blocks

    @property
    def _frame(self) -> _Frame:
        return self._frames[-1]

    def _target(self) -> list[Node]:
        frame = self._frame
        return frame.item_blocks if frame.item_blocks is not None else frame.blocks

    def _flush_paragraph(self) -> None:
        self._flush_code()
        if not self._runs:
            return
        nodes = self._inline_nodes(self._runs)
        self._runs = []
        self._no_space = False
        if not nodes:
            return
        if self._in_name_section and self._metadata.subject is None:
            plain = "".join(node.content for node in nodes if isinstance(node, Text))
            parts = re.split(r"\s+[-\u2013\u2014]\s+", plain, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                self._metadata.subject = parts[1].strip()
        self._target().append(Paragraph(content=nodes))

    def _flush_code(self) -> None:
        if not self._code_lines:
            return
        lines = self._code_lines
        self._code_lines = []
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            self._target().append(CodeBlock(content="\n".join(lines)))

    def _finish_item(self, frame: _Frame) -> None:
        if frame.item_blocks is None:
            return
        if frame.list_kind == "dl":
            descriptions = [DefinitionDescription(content=frame.item_blocks)] if frame.item_blocks else []
            frame.dl_items.append((DefinitionTerm(content=frame.item_term or []), descriptions))
        else:
            frame.list_items.append(ListItem(children=frame.item_blocks))
        frame.item_term = None
        frame.item_blocks = None

    def _close_list(self, frame: Optional[_Frame] = None) -> None:
        frame = frame or self._frame
        if frame is self._frame:
            self._flush_paragraph()
        self._finish_item(frame)
        if frame.list_kind == "dl" and frame.dl_items:
            frame.blocks.append(DefinitionList(items=frame.dl_items))
        elif frame.list_kind in ("ul", "ol") and frame.list_items:
            # A nested list does not loosen its item (Markdown's "- a" + "  - b" is
            # tight); any other second block, a paragraph or code, does.
            tight = all(sum(not isinstance(child, List) for child in item.children) <= 1 for item in frame.list_items)
            frame.blocks.append(
                List(ordered=frame.list_kind == "ol", items=frame.list_items, start=frame.list_start, tight=tight)
            )
        frame.list_kind = None
        frame.list_start = 1
        frame.dl_items = []
        frame.list_items = []

    def _open_item(self, kind: str, term: Optional[list[Node]] = None, start: int = 1) -> None:
        self._flush_paragraph()
        frame = self._frame
        if frame.list_kind != kind:
            self._close_list()
            frame.list_kind = kind
            frame.list_start = start
        else:
            self._finish_item(frame)
        frame.item_term = term
        frame.item_blocks = []

    def _close_all_frames(self) -> None:
        self._flush_paragraph()
        while len(self._frames) > 1:
            self._m_RE("")
        self._close_list()

    def _begin_capture(self, kind: str) -> None:
        self._flush_paragraph()
        self._capture = kind
        self._capture_runs = []
        self._no_space = False

    def _finish_capture(self) -> None:
        kind = self._capture
        runs = self._capture_runs
        self._capture = None
        self._capture_runs = []
        self._no_space = False
        nodes = self._inline_nodes(runs)
        if kind in ("sh", "ss"):
            self._add_heading(kind, nodes)
        elif kind == "tq" and self._frame.list_kind == "dl" and self._frame.item_term is not None:
            # .TQ adds another term to the item .TP opened (--verbose, -v); Markdown
            # definition lists give each description one term, so join them.
            if nodes:
                self._frame.item_term = [*self._frame.item_term, Text(content=", "), *nodes]
        else:
            self._open_item("dl", nodes)

    def _add_heading(self, kind: str, nodes: list[Node]) -> None:
        if not nodes:
            return
        plain = "".join(node.content for node in nodes if isinstance(node, Text))
        self._in_name_section = kind == "sh" and plain.strip().upper() == "NAME"
        if self.options.normalize_heading_case:
            nodes = [_title_case_node(node) for node in nodes]
        level = 1 if kind == "sh" else 2
        if self.options.title_heading:
            level += 1
        self._frames[0].blocks.append(Heading(level=level, content=nodes))

    def _finish(self) -> None:
        if self._table_lines is not None:
            self._end_table()
        if self._capture is not None:
            self._finish_capture()
        self._close_all_frames()

    def _warn_once(self, key: str, message: str, *args: Any) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message, *args)

    # ---------------------------------------------------- structural macros

    def _m_TH(self, rest: str) -> None:
        args = [self._plain(arg) for arg in _split_args(rest)]
        if not args:
            return
        name = args[0]
        section = args[1] if len(args) > 1 else ""
        title = f"{name}({section})" if section else name
        self._metadata.title = title
        if len(args) > 2 and args[2]:
            self._metadata.modification_date = args[2]
        if section:
            self._metadata.custom["section"] = section
        if len(args) > 3 and args[3]:
            self._metadata.custom["source"] = args[3]
        if len(args) > 4 and args[4]:
            self._metadata.custom["manual"] = args[4]
        if self.options.title_heading:
            self._close_all_frames()
            self._frames[0].blocks.append(Heading(level=1, content=[Text(content=title)]))

    def _section(self, kind: str, rest: str) -> None:
        self._close_all_frames()
        self._nofill = False
        self._font = self._prev_font = "R"
        args = _split_args(rest)
        self._begin_capture(kind)
        if args:
            runs, _continued = self._expand(" ".join(args))
            self._capture_runs = runs
            self._finish_capture()

    def _m_SH(self, rest: str) -> None:
        self._section("sh", rest)

    def _m_SS(self, rest: str) -> None:
        self._section("ss", rest)

    def _paragraph(self, _rest: str = "") -> None:
        self._end_nofill_for_structure()
        self._close_list()
        self._font = "R"

    _m_PP = _paragraph
    _m_LP = _paragraph
    _m_P = _paragraph
    _m_HP = _paragraph

    def _end_nofill_for_structure(self) -> None:
        self._flush_paragraph()
        self._nofill = False

    def _m_TP(self, _rest: str) -> None:
        self._end_nofill_for_structure()
        self._begin_capture("tp")

    def _m_TQ(self, _rest: str) -> None:
        self._end_nofill_for_structure()
        self._begin_capture("tq")

    def _m_IP(self, rest: str) -> None:
        self._end_nofill_for_structure()
        args = _split_args(rest)
        tag_runs, _continued = self._expand(args[0]) if args else ([], False)
        tag_text = "".join(r[0] for r in tag_runs).strip()
        frame = self._frame
        if not tag_text:
            if frame.item_blocks is None:
                self._close_list()
            return
        if tag_text in _BULLET_TAGS:
            self._open_item("ul")
            return
        numbered = _NUMBERED_TAG.match(tag_text)
        if numbered:
            self._open_item("ol", start=int(numbered.group(1)))
            return
        self._open_item("dl", self._inline_nodes(tag_runs))

    def _m_RS(self, _rest: str) -> None:
        self._flush_paragraph()
        self._frames.append(_Frame())

    def _m_RE(self, _rest: str) -> None:
        if len(self._frames) == 1:
            return
        self._flush_paragraph()
        self._close_list()
        inner = self._frames.pop()
        if not inner.blocks:
            return
        parent = self._frame
        if parent.item_blocks is not None:
            parent.item_blocks.extend(inner.blocks)
        else:
            parent.blocks.append(BlockQuote(children=inner.blocks))

    def _m_br(self, _rest: str) -> None:
        if self._nofill or self._capture is not None:
            return
        if self._runs:
            self._runs.append((_LINE_BREAK, "R", self._link))
            self._no_space = True

    def _m_sp(self, _rest: str) -> None:
        if self._nofill:
            self._code_lines.append("")
        else:
            self._flush_paragraph()

    _m_Sp = _m_sp

    def _m_nf(self, _rest: str) -> None:
        self._flush_paragraph()
        self._nofill = True

    def _m_fi(self, _rest: str) -> None:
        self._flush_code()
        self._nofill = False

    _m_EX = _m_nf
    _m_EE = _m_fi
    _m_Vb = _m_nf  # pod2man verbatim block
    _m_Ve = _m_fi

    def _m_ft(self, rest: str) -> None:
        args = _split_args(rest)
        self._set_font(args[0] if args else "P")

    def _m_UR(self, rest: str) -> None:
        args = _split_args(rest)
        self._link = self._plain(args[0]) if args else None

    def _m_MT(self, rest: str) -> None:
        args = _split_args(rest)
        self._link = f"mailto:{self._plain(args[0])}" if args else None

    def _end_link(self, rest: str) -> None:
        url = self._link
        if url is not None and not self._link_has_text():
            text = url[len("mailto:") :] if url.startswith("mailto:") else url
            self._add_runs([(text, "R", url)], continued=False)
        self._link = None
        args = _split_args(rest)
        if args:
            # Trailing punctuation (.UE ,) attaches to the link without a space.
            runs, continued = self._expand(" ".join(args))
            self._no_space = True
            self._add_runs(runs, continued)

    def _link_has_text(self) -> bool:
        target = self._capture_runs if self._capture is not None else self._runs
        return any(link == self._link and text.strip() for text, _font, link in target)

    _m_UE = _end_link
    _m_ME = _end_link

    def _m_SY(self, rest: str) -> None:
        self._paragraph()
        args = _split_args(rest)
        if args:
            runs, continued = self._expand(args[0], font="B")
            self._add_runs(runs, continued)

    def _m_OP(self, rest: str) -> None:
        args = _split_args(rest)
        if not args:
            return
        runs: list[tuple[str, _Font, Optional[str]]] = [("[", "R", self._link)]
        flag_runs, _ = self._expand(args[0], font="B")
        runs.extend(flag_runs)
        if len(args) > 1:
            runs.append((" ", "R", self._link))
            arg_runs, _ = self._expand(" ".join(args[1:]), font="I")
            runs.extend(arg_runs)
        runs.append(("]", "R", self._link))
        self._add_runs(runs, False)

    def _m_MR(self, rest: str) -> None:
        args = _split_args(rest)
        if not args:
            return
        runs, _ = self._expand(args[0], font="I")
        if len(args) > 1:
            runs.append((f"({self._plain(args[1])})", "R", self._link))
        if len(args) > 2:
            runs.append((self._plain(args[2]), "R", self._link))
        self._add_runs(runs, False)

    def _m_TS(self, _rest: str) -> None:
        self._flush_paragraph()
        self._table_lines = []

    # ------------------------------------------------- roff request language

    def _m_de(self, rest: str) -> None:
        args = _split_args(rest)
        self._skip_until = args[1] if len(args) > 1 else "."

    _m_de1 = _m_de
    _m_am = _m_de
    _m_ig = _m_de

    def _m_ds(self, rest: str) -> None:
        match = re.match(r"\s*(\S+)\s?(.*)$", rest)
        if match:
            value = match.group(2)
            self._strings[match.group(1)] = value[1:] if value.startswith('"') else value

    _m_ds1 = _m_ds

    def _m_as(self, rest: str) -> None:
        match = re.match(r"\s*(\S+)\s?(.*)$", rest)
        if match:
            value = match.group(2)
            value = value[1:] if value.startswith('"') else value
            self._strings[match.group(1)] = self._strings.get(match.group(1), "") + value

    def _m_if(self, rest: str) -> None:
        self._conditional(rest, is_ie=False)

    def _m_ie(self, rest: str) -> None:
        self._conditional(rest, is_ie=True)

    def _m_el(self, rest: str) -> None:
        self._run_branch(not self._last_condition, rest.lstrip())

    def _conditional(self, rest: str, is_ie: bool) -> None:
        rest = rest.lstrip()
        result, body = _evaluate_condition(rest)
        if is_ie:
            self._last_condition = result
        self._run_branch(result, body)

    def _run_branch(self, result: bool, body: str) -> None:
        opened = body.startswith("\\{")
        if opened:
            body = body[2:]
        if not result:
            if opened:
                self._skip_depth = max(0, 1 + body.count("\\{") - body.count("\\}"))
            return
        body = body.lstrip()
        if body:
            self._process_line(body)

    def _end_table(self) -> None:
        lines = self._table_lines or []
        self._table_lines = None
        table = self._build_table(lines)
        if table is not None:
            self._target().append(table)

    def _build_table(self, lines: list[str]) -> Optional[Node]:
        """Turn a simple tbl(1) table into a Table, or a code block when it is not simple."""
        if not lines:
            return None
        index = 0
        tab = "\t"
        if lines[0].rstrip().endswith(";"):
            tab_match = re.search(r"tab\s*\((.)\)", lines[0])
            if tab_match:
                tab = tab_match.group(1)
            index = 1
        formats: list[str] = []
        while index < len(lines):
            formats.append(lines[index])
            index += 1
            if formats[-1].rstrip().endswith("."):
                break
        data = lines[index:]
        if any(line.strip().startswith(("T{", ".T&")) or "T{" in line for line in data):
            return CodeBlock(content="\n".join(self._plain(line) for line in data if line.strip() not in ("_", "=")))

        rows: list[list[list[Node]]] = []
        for line in data:
            stripped = line.strip()
            if stripped in ("_", "=", "") or line[:1] in (".", "'"):
                continue
            cells = []
            for cell in line.split(tab):
                runs, _continued = self._expand(cell.strip())
                cells.append(self._inline_nodes(runs))
            self._font = self._prev_font = "R"
            rows.append(cells)
        if not rows:
            return None
        width = max(len(row) for row in rows)
        for row in rows:
            row.extend([] for _ in range(width - len(row)))

        first_format = formats[0] if formats else ""
        keys = re.findall(r"[lrcnaLRCNA]", first_format)
        align_map: dict[str, Alignment] = {"l": "left", "r": "right", "c": "center", "n": "right", "a": "left"}
        alignments: list[Alignment | None] = [align_map.get(key.lower()) for key in keys[:width]]
        alignments.extend([None] * (width - len(alignments)))
        # tbl has no header row as such; man pages put the column titles first
        # (usually bold, or ruled off with _), and a Markdown table needs a header.
        table_rows = [TableRow(cells=[TableCell(content=cell) for cell in row]) for row in rows]
        header = table_rows[0]
        header.is_header = True
        return Table(header=header, rows=table_rows[1:], alignments=alignments)


_FONT_MACROS: dict[str, tuple[_Font, ...]] = {
    "B": ("B",),
    "I": ("I",),
    "SB": ("B",),
    "SM": ("R",),
    "BI": ("B", "I"),
    "BR": ("B", "R"),
    "IB": ("I", "B"),
    "IR": ("I", "R"),
    "RB": ("R", "B"),
    "RI": ("R", "I"),
}


def _evaluate_condition(text: str) -> tuple[bool, str]:
    r"""Evaluate the condition at the start of a ``.if``/``.ie`` line.

    Only the conditions man pages use to pick between output devices are
    understood: ``n`` (true; this is a terminal-style reader), ``t`` (false),
    ``\n(.g`` (true; groff extensions are fine), each optionally negated with
    ``!``. Anything else is false, so its branch is skipped.

    Returns
    -------
    tuple[bool, str]
        The result and the rest of the line (the body).

    """
    negate = False
    if text.startswith("!"):
        negate, text = True, text[1:]
    match = re.match(r"(n|t|o|e|v)(?![A-Za-z0-9(\[])\s*(.*)$", text)
    if match:
        result = match.group(1) == "n" or match.group(1) == "o"
        return result != negate, match.group(2)
    match = re.match(r"\\n(?:\(\.g|\[\.g\])\s*(.*)$", text)
    if match:
        return not negate, match.group(1)
    # d/r/m/c/F/S NAME ask whether something is defined; say yes, so a page's
    # fallback definitions (.if !d UR ...) are skipped.
    match = re.match(r"[drmcFS]\s+\S+\s*(.*)$", text)
    if match:
        return not negate, match.group(1)
    # Unknown condition: skip one token (a quoted comparison or a word) and treat as false.
    match = re.match(r"('[^']*'[^']*'|\S+)\s*(.*)$", text)
    body = match.group(2) if match else ""
    return negate, body


# What each font contributes when runs are nested: bold, italic, or constant width.
_FONT_ATTRIBUTES: dict[_Font, frozenset[str]] = {
    "R": frozenset(),
    "B": frozenset("B"),
    "I": frozenset("I"),
    "BI": frozenset("BI"),
    "C": frozenset("C"),
    "CB": frozenset("CB"),
    "CI": frozenset("CI"),
    "CBI": frozenset("CBI"),
}


def _nest_runs(runs: list[tuple[str, frozenset[str]]], active: frozenset[str]) -> list[Node]:
    r"""Build nested inline nodes from font runs.

    ``\fBbold \f(BIboth\fB bold\fR`` is one Strong holding an Emphasis, not
    three siblings: at each level the attribute (bold or italic) whose stretch
    from the current run is longest becomes the outer node, and the runs inside
    it are nested the same way, down to constant-width runs, which become Code.
    Whitespace at the edges of a stretch stays outside the formatting.
    """
    out: list[Node] = []
    index = 0
    while index < len(runs):
        text, attributes = runs[index]
        extra = attributes - active
        if not extra or not text.strip(" "):
            out.append(Text(content=text))
            index += 1
            continue
        styles = extra - {"C"}
        if not styles:
            out.extend(_edge_split(text, lambda core: Code(content=core)))
            index += 1
            continue
        best, end = "", index
        # On a tie italic goes outside, as CommonMark nests ***x*** (<em><strong>).
        for attribute in sorted(styles, reverse=True):
            stop = index
            while stop < len(runs) and attribute in runs[stop][1]:
                stop += 1
            if stop > end:
                best, end = attribute, stop
        stretch = list(runs[index:end])
        first_text, first_attributes = stretch[0]
        lead = first_text[: len(first_text) - len(first_text.lstrip(" "))]
        stretch[0] = (first_text[len(lead) :], first_attributes)
        last_text, last_attributes = stretch[-1]
        trail = last_text[len(last_text.rstrip(" ")) :]
        stretch[-1] = (last_text[: len(last_text) - len(trail)], last_attributes)
        if lead:
            out.append(Text(content=lead))
        inner = _merge_text(_nest_runs(stretch, active | {best}))
        out.append(Strong(content=inner) if best == "B" else Emphasis(content=inner))
        if trail:
            out.append(Text(content=trail))
        index = end
    return out


def _edge_split(text: str, wrap: Callable[[str], Node]) -> list[Node]:
    """Wrap the core of ``text``, keeping its edge spaces outside as plain text."""
    core = text.strip(" ")
    lead = text[: len(text) - len(text.lstrip(" "))]
    trail = text[len(text.rstrip(" ")) :]
    nodes = [Text(content=lead), wrap(core), Text(content=trail)]
    return [node for node in nodes if not isinstance(node, Text) or node.content]


def _merge_text(nodes: list[Node]) -> list[Node]:
    merged: list[Node] = []
    for node in nodes:
        if isinstance(node, Text) and merged and isinstance(merged[-1], Text):
            merged[-1] = Text(content=merged[-1].content + node.content)
        else:
            merged.append(node)
    return [node for node in merged if not (isinstance(node, Text) and not node.content)]


def _trim(nodes: list[Node]) -> list[Node]:
    """Strip whitespace at the edges of an inline sequence, and leading/trailing line breaks."""
    while nodes and isinstance(nodes[0], LineBreak):
        nodes.pop(0)
    while nodes and isinstance(nodes[-1], LineBreak):
        nodes.pop()
    if nodes and isinstance(nodes[0], Text):
        nodes[0] = Text(content=nodes[0].content.lstrip())
    if nodes and isinstance(nodes[-1], Text):
        nodes[-1] = Text(content=nodes[-1].content.rstrip())
    return [node for node in nodes if not (isinstance(node, Text) and not node.content)]


def _title_case(text: str) -> str:
    if not text.isupper():
        return text
    return re.sub(r"(^|\s)(\S)(\S*)", lambda m: m.group(1) + m.group(2).upper() + m.group(3).lower(), text)


def _title_case_node(node: Node) -> Node:
    if isinstance(node, Text):
        return Text(content=_title_case(node.content))
    return node


CONVERTER_METADATA = ConverterMetadata(
    format_name="man",
    extensions=[".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9", ".man"],
    mime_types=["text/troff", "text/x-troff-man", "application/x-troff-man"],
    magic_bytes=[],
    content_detector=_is_man_content,
    parser_class=ManParser,
    renderer_class="all2md.renderers.man.ManRenderer",
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=ManParserOptions,
    renderer_options_class="all2md.options.man.ManRendererOptions",
    description="Parse and render Unix manual pages written with the man(7) macros",
    priority=10,
)
