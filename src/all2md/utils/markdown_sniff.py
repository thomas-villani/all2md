#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/markdown_sniff.py
r"""Recognize Markdown from its content alone.

Detection by filename never needs this: a ``.md`` is Markdown. Content without
a name does, most often a document piped to stdin (``cat notes.md | rcat``),
which used to fall through to plain text and come out with its syntax escaped
(``\# Heading``).

Markdown's marks are common outside Markdown: ``#`` begins a comment in shell,
Python, YAML and INI files, ``- item`` is a YAML list, and reStructuredText has
lists and ``**strong**`` too. So the test asks for two different kinds of mark,
reads a ``#`` line as a heading only when blank lines set it apart as Markdown
headings are and comments are not, and says no outright to text that shows
another language's own syntax: a program's statements, an reST directive or
role, an Org keyword. Code inside fenced blocks is set aside first, since a
README full of shell examples is still Markdown.

A front matter block (YAML between ``---`` lines, or TOML between ``+++``)
opening the text is set aside the same way, and is itself a sign: it is how
static-site and note-taking tools write Markdown, and the YAML detector would
otherwise read the whole document as a YAML stream.
"""

from __future__ import annotations

import re

_SAMPLE_CHARS = 64 * 1024

_FRONT_MATTER = re.compile(r"\A(?:---|\+\+\+)[ \t]*\n.*?\n(?:---|\+\+\+|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL)
_FENCED_BLOCK = re.compile(r"^[ ]{0,3}(```|~~~)[^\n]*\n.*?^[ ]{0,3}\1[ \t]*$", re.DOTALL | re.MULTILINE)
_YAML_KEY_LINE = re.compile(r"^[\w.\"'-]+[ \t]*:(?:[ \t]|$)")

_MARKS: dict[str, re.Pattern[str]] = {
    # A heading has a blank line (or the start) above and a blank line (or the end) below.
    "heading": re.compile(r"(?:\A|\n[ \t]*\n)#{1,6}[ \t]+\S[^\n]*(?:\n[ \t]*\n|\n?\Z)"),
    "fence": re.compile(r"^[ ]{0,3}(?:```|~~~)", re.MULTILINE),
    "list": re.compile(
        r"^[ ]{0,3}(?:[-*+]|\d{1,9}[.)])[ \t]+\S.*\n[ ]{0,3}(?:[-*+]|\d{1,9}[.)])[ \t]+\S", re.MULTILINE
    ),
    "link": re.compile(r"!?\[[^\]\n]+\]\([^)\s]+(?:[ \t]+\"[^\"\n]*\")?\)"),
    # Strong emphasis around words, not ``**/*.pyc``-style globs.
    "emphasis": re.compile(r"(?<![\w*/])\*\*(?=[^\s*/])[^*\n/]*[A-Za-z][^*\n/]*(?<=[^\s*/])\*\*(?![\w*/])"),
    "table": re.compile(r"^[ ]{0,3}\|?[ \t]*:?-{3,}:?[ \t]*\|", re.MULTILINE),
    "quote": re.compile(r"^[ ]{0,3}>[ \t]?\S", re.MULTILINE),
    "inline_code": re.compile(r"(?<![`:\w])`[^`\n]+`(?![`_\w])"),
}

# Another language's own syntax: source code statements, reST directives and roles, Org keywords.
_NOT_MARKDOWN = re.compile(
    r"^(?:#!|#include\b|#\+\w+:|\.\. [\w:-]+::|[ \t]*(?:def \w+\(|class \w+[(:]|import [\w.]+(?: as \w+)?[ \t]*$|"
    r"from [\w.]+ import \w|package [\w.]+;?[ \t]*$|function \w+[ \t]*\(|(?:const|let|var) \w+[ \t]*=|"
    r"public (?:static )?[\w<>\[\]]+ \w+[ \t]*\())|:\w+:`|\bfunction[ \t]*\(|\)[ \t]*=>[ \t]*\{|\}[ \t]*;",
    re.MULTILINE,
)


def _sample(content: bytes) -> str | None:
    if b"\x00" in content[:_SAMPLE_CHARS]:
        return None
    return content[:_SAMPLE_CHARS].decode("utf-8", errors="ignore").replace("\r\n", "\n")


def _body_is_markdown(text: str) -> bool:
    prose = _FENCED_BLOCK.sub("", text)
    if _NOT_MARKDOWN.search(prose):
        return False
    kinds = {name for name, pattern in _MARKS.items() if pattern.search(text if name == "fence" else prose)}
    return len(kinds) >= 2


def looks_like_markdown(content: bytes) -> bool:
    """Return whether ``content`` reads as Markdown rather than plain text.

    Parameters
    ----------
    content : bytes
        The start of the input; only the first 64 KB are examined.

    Returns
    -------
    bool
        True when, outside fenced code and front matter, the text carries two
        kinds of Markdown mark and nothing that belongs to another language.

    """
    text = _sample(content)
    if text is None:
        return False
    front_matter = _FRONT_MATTER.match(text)
    if front_matter:
        return has_markdown_front_matter(content)
    return _body_is_markdown(text)


def has_markdown_front_matter(content: bytes) -> bool:
    """Return whether ``content`` is a front matter block followed by a Markdown body.

    The body counts as Markdown when it carries Markdown's marks, or when it
    starts with prose rather than another ``key: value`` line, which would make
    the whole a YAML stream of several documents instead.

    Parameters
    ----------
    content : bytes
        The start of the input.

    Returns
    -------
    bool
        True when the text opens with ``---``/``+++`` front matter and the rest
        reads as a Markdown document.

    """
    text = _sample(content)
    if text is None:
        return False
    front_matter = _FRONT_MATTER.match(text)
    if not front_matter:
        return False
    body = text[front_matter.end() :]
    first_line = next((line.strip() for line in body.split("\n") if line.strip()), "")
    if not first_line:
        return False
    if _body_is_markdown(body):
        return True
    return not (_YAML_KEY_LINE.match(first_line) or first_line.startswith(("- ", "---", "+++")))
