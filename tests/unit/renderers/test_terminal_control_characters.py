"""The terminal renderer never passes a document's control characters to the terminal.

A document is untrusted input, and a terminal acts on control characters: ESC
starts a sequence that can set the window title, clear the screen, forge an
OSC 8 hyperlink or, in some terminals, write the clipboard. Text, headings,
alt text and link targets all reached the output raw.
"""

from __future__ import annotations

import re

import pytest

from all2md import from_ast
from all2md.ast.nodes import (
    CodeBlock,
    Document,
    Heading,
    Image,
    Link,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast.transforms import TERMINAL_UNSAFE_CHARACTERS, remove_terminal_unsafe_characters

ESC = chr(0x1B)
BEL = chr(0x07)
CSI_C1 = chr(0x9B)
TITLE = f"{ESC}]0;PWNED{BEL}"
CLEAR = f"{ESC}[2J"


def _render(*children) -> str:
    return from_ast(Document(children=list(children)), "terminal", clickable_links="all", color_system="truecolor")


def _text(content: str) -> Paragraph:
    return Paragraph(content=[Text(content=content)])


CASES = {
    "text": lambda: _text(f"before {TITLE} {CLEAR} after"),
    "heading": lambda: Heading(level=2, content=[Text(content=f"Title {TITLE}")]),
    "link_target": lambda: Paragraph(content=[Link(url=f"http://example.com/{TITLE}", content=[Text(content="x")])]),
    "link_text": lambda: Paragraph(content=[Link(url="http://example.com/", content=[Text(content=f"x {TITLE}")])]),
    "image": lambda: Paragraph(content=[Image(url=f"http://example.com/{TITLE}.png", alt_text=f"alt {TITLE}")]),
    "table": lambda: Table(
        header=TableRow(cells=[TableCell(content=[Text(content=f"h {TITLE}")])]),
        rows=[TableRow(cells=[TableCell(content=[Text(content=f"c {CLEAR}")])])],
    ),
    "code": lambda: CodeBlock(content=f"x = 1  # {TITLE}", language="python"),
    "c1_csi": lambda: _text(f"c1 {CSI_C1}2J here"),
}


@pytest.mark.unit
@pytest.mark.parametrize("case", sorted(CASES))
def test_no_injected_sequence_reaches_the_output(case):
    out = _render(CASES[case]())
    assert f"{ESC}]0;" not in out
    assert CLEAR not in out
    assert CSI_C1 not in out
    assert BEL not in out.replace(f"{ESC}]8;", "")  # OSC 8 is closed with ST, never BEL


@pytest.mark.unit
def test_every_hyperlink_target_is_clean():
    out = _render(CASES["link_target"](), CASES["image"]())
    targets = re.findall(f"{ESC}]8;[^;]*;([^{ESC}]*){ESC}", out)
    assert targets, "hyperlinks are still written"
    for target in targets:
        assert not TERMINAL_UNSAFE_CHARACTERS.search(target)


@pytest.mark.unit
def test_visible_text_survives():
    out = _render(_text(f"before {TITLE} after"))
    plain = re.sub(f"{ESC}\\[[0-9;]*m", "", out)
    assert "before ]0;PWNED after" in plain


@pytest.mark.unit
def test_tabs_and_newlines_are_kept():
    doc = Document(children=[CodeBlock(content="a\tb\nc", language="text")])
    cleaned, removed = remove_terminal_unsafe_characters(doc)
    assert removed == 0
    assert cleaned is doc


@pytest.mark.unit
def test_the_input_document_is_not_changed():
    paragraph = _text(f"x {TITLE}")
    doc = Document(children=[paragraph])
    cleaned, removed = remove_terminal_unsafe_characters(doc)
    assert removed == 2
    assert paragraph.content[0].content == f"x {TITLE}"
    assert cleaned.children[0].content[0].content == "x ]0;PWNED"


@pytest.mark.unit
def test_the_renderer_still_styles():
    assert f"{ESC}[" in _render(Heading(level=1, content=[Text(content="Styled")]))


@pytest.mark.unit
def test_the_pattern_is_exactly_the_c0_c1_controls_but_tab_and_newline():
    expected = {code for code in range(0x20) if code not in (0x09, 0x0A)} | set(range(0x7F, 0xA0))
    matched = {code for code in range(0x110000) if TERMINAL_UNSAFE_CHARACTERS.match(chr(code))}
    assert matched == expected
