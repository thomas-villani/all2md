"""Document text printed to a terminal carries no control characters.

A document is untrusted input. Printed to a terminal, an ESC in it is executed, not
shown, so the CLI removes control characters from document output that goes to a
terminal or the pager. Output to a file or a pipe is left exactly as converted.
"""

from __future__ import annotations

import io

import pytest

from all2md.cli import main

ESC = chr(0x1B)
BEL = chr(0x07)
RESET = f"{ESC}c"
TITLE = f"{ESC}]0;PWNED{BEL}"


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def hostile(tmp_path):
    path = tmp_path / "doc.html"
    path.write_text(f"<h1>Head {TITLE}</h1><p>hello {RESET}{TITLE} world</p>", encoding="utf-8")
    return path


def _run(monkeypatch, stream, *argv) -> str:
    monkeypatch.setattr("sys.stdout", stream)
    assert main([*argv]) == 0
    return stream.getvalue()


@pytest.mark.unit
@pytest.mark.parametrize(
    "flags",
    [
        [],
        ["--line-numbers"],
        ["--to", "html"],
        ["--head", "3"],
        ["--extract", "Head*"],
        ["--outline"],
    ],
)
def test_terminal_output_has_no_control_characters(monkeypatch, hostile, flags):
    out = _run(monkeypatch, _Terminal(), str(hostile), *flags)
    assert ESC not in out
    assert BEL not in out


@pytest.mark.unit
def test_visible_text_survives(monkeypatch, hostile):
    out = _run(monkeypatch, _Terminal(), str(hostile))
    assert "hello" in out and "world" in out
    assert "PWNED" in out


@pytest.mark.unit
def test_piped_output_is_left_as_converted(monkeypatch, hostile):
    out = _run(monkeypatch, io.StringIO(), str(hostile))
    assert ESC in out


@pytest.mark.unit
def test_file_output_is_left_as_converted(hostile, tmp_path):
    target = tmp_path / "out.md"
    assert main([str(hostile), "--out", str(target)]) == 0
    assert ESC in target.read_text(encoding="utf-8")
