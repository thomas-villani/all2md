"""``--rich`` draws documents with the terminal renderer, in every mode.

The path before it rendered Markdown text and handed it to ``rich.markdown``,
which showed footnotes, task lists and GitHub alerts as Markdown source. The
whole-document view moved first; ``--outline``, ``--extract``, ``--slice`` and
the line windows followed. ``--line-numbers`` counts lines of the Markdown
source, so with it the source is printed as it is.
"""

from __future__ import annotations

import argparse
import re

import pytest

from all2md.ast.nodes import Document, Emphasis, Heading, Paragraph, Text
from all2md.cli import main
from all2md.cli.processors import _outline_document, _terminal_renderer_options
from all2md.options.terminal import TerminalRendererOptions
from all2md.renderers.terminal import TerminalRenderer

NL = chr(10)
ESC = chr(27)
_ANSI = re.compile(ESC + r"(\[[0-9;]*m|\]8;[^" + ESC + "]*" + ESC + chr(92) + chr(92) + ")")

SOURCE = NL.join(
    [
        "Text with a note[^1].",
        "",
        "- [x] done",
        "",
        "> [!WARNING]",
        "> Mind the gap.",
        "",
        "[^1]: The note.",
        "",
    ]
)

GUIDE = NL.join(
    [
        "# Guide",
        "",
        "Intro with a note[^1].",
        "",
        "## Install",
        "",
        "- [x] download",
        "- [ ] run",
        "",
        "## Usage",
        "",
        "> [!TIP]",
        "> Read the docs.",
        "",
        "[^1]: The note.",
        "",
    ]
)


def run(tmp_path, capsys, monkeypatch, source: str, *flags: str) -> str:
    """Run ``all2md FILE --rich --force-rich FLAGS`` and return stdout without escape codes."""
    monkeypatch.setenv("COLUMNS", "60")
    path = tmp_path / "doc.md"
    path.write_text(source, encoding="utf-8")
    assert main([str(path), "--rich", "--force-rich", *flags]) == 0
    out = capsys.readouterr().out
    return NL.join(line.rstrip() for line in _ANSI.sub("", out).splitlines())


@pytest.mark.unit
class TestRichUsesTheTerminalRenderer:
    def test_whole_document(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, SOURCE)
        assert "note[1]" in out
        assert "[^1]" not in out
        assert "☑ done" in out
        assert "Warning" in out and "[!WARNING]" not in out

    def test_outline_is_a_nested_list(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--outline")
        assert out.splitlines() == [" • Guide", "    • Install", "    • Usage"]

    def test_extract(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--extract", "Install")
        assert "☑ download" in out and "☐ run" in out
        assert "[x]" not in out

    def test_slice_ends_with_its_hint(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--slice", "1/2")
        assert out.splitlines()[-1].startswith("slice 1/2")
        assert "<!--" not in out
        assert "☑ download" in out

    def test_head(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--head", "8")
        assert "☑ download" in out
        assert "Usage" not in out

    def test_extract_by_line(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--extract", "line:5-8")
        assert out.splitlines()[0] == "Install"
        assert "☐ run" in out


@pytest.mark.unit
class TestLineNumbersPrintTheSource:
    """The numbers count Markdown lines, so the numbered source is printed verbatim."""

    def test_whole_document(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv("COLUMNS", "60")
        path = tmp_path / "doc.md"
        path.write_text(GUIDE, encoding="utf-8")
        assert main([str(path), "--rich", "--force-rich", "--line-numbers"]) == 0
        out = capsys.readouterr().out
        assert ESC not in out
        assert " 5: ## Install" in out.splitlines()

    def test_outline(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--outline", "--line-numbers")
        assert out.splitlines() == [" 1: * Guide", " 5:   * Install", "10:   * Usage"]


@pytest.mark.unit
class TestToTerminal:
    def test_rich_does_not_highlight_ansi_as_source(self, tmp_path, capsys, monkeypatch):
        """``--to terminal --rich`` used to wrap the ANSI text in a syntax highlighter."""
        from all2md.cli import processors

        def fail(*_args, **_kwargs):
            raise AssertionError("ANSI output went through the syntax highlighter")

        monkeypatch.setattr(processors, "_render_rich_text_output", fail)
        out = run(tmp_path, capsys, monkeypatch, SOURCE, "--to", "terminal")
        assert "note[1]" in out

    def test_slice_hint_is_last(self, tmp_path, capsys, monkeypatch):
        out = run(tmp_path, capsys, monkeypatch, GUIDE, "--to", "terminal", "--slice", "2/2")
        lines = out.splitlines()
        assert lines[-1].startswith("slice 2/2")
        assert "[1] The note." in lines


@pytest.mark.unit
class TestOutlineDocument:
    def _plain(self, doc: Document) -> list[str]:
        options = TerminalRendererOptions(width=60, color_system="none")
        output = TerminalRenderer(options).render_to_string(doc)
        return [line.rstrip() for line in output.splitlines()]

    def test_skipped_levels_nest_one_deeper(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="A")]),
                Heading(level=3, content=[Text(content="A.1.1")]),
                Heading(level=2, content=[Text(content="A.2")]),
                Heading(level=1, content=[Text(content="B")]),
            ]
        )
        assert self._plain(_outline_document(doc, 6)) == [" • A", "    • A.1.1", "    • A.2", " • B"]

    def test_a_document_that_starts_below_level_one(self):
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Two")]),
                Heading(level=1, content=[Text(content="One")]),
            ]
        )
        assert self._plain(_outline_document(doc, 6)) == [" • Two", " • One"]

    def test_heading_formatting_is_kept(self):
        heading = Heading(level=1, content=[Text(content="A "), Emphasis(content=[Text(content="styled")])])
        outline = _outline_document(Document(children=[heading]), 6)
        item = outline.children[0].items[0]
        assert isinstance(item.children[0], Paragraph)
        assert isinstance(item.children[0].content[1], Emphasis)

    def test_max_level(self):
        doc = Document(
            children=[Heading(level=1, content=[Text(content="A")]), Heading(level=2, content=[Text(content="B")])]
        )
        assert self._plain(_outline_document(doc, 1)) == [" • A"]

    def test_no_headings(self):
        doc = Document(children=[Paragraph(content=[Text(content="text")])])
        assert self._plain(_outline_document(doc, 6)) == ["No headings found in document"]


@pytest.mark.unit
class TestRichFlagsMapOntoOptions:
    def test_flags(self):
        args = argparse.Namespace(
            rich_code_theme="dracula",
            rich_inline_code_theme="native",
            rich_hyperlinks=False,
            rich_justify="full",
            rich_no_word_wrap=True,
            _rich_theme_styles={"h1": "bold red"},
        )
        options = _terminal_renderer_options(args)
        assert options.code_theme == "dracula"
        assert options.inline_code_theme == "native"
        assert options.hyperlinks is False
        assert options.justify == "full"
        assert options.word_wrap is False
        assert options.styles == {"h1": "bold red"}

    def test_defaults(self):
        options = _terminal_renderer_options(argparse.Namespace())
        assert options.code_theme == "monokai"
        assert options.hyperlinks is True
        assert options.word_wrap is True
        assert options.styles is None
