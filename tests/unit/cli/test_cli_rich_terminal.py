"""``--rich`` draws a whole document with the terminal renderer.

The path before it rendered Markdown text and handed it to ``rich.markdown``,
which showed footnotes, task lists and GitHub alerts as Markdown source.
"""

from __future__ import annotations

import argparse

import pytest

from all2md.cli import main
from all2md.cli.processors import _terminal_renderer_options

NL = chr(10)

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


@pytest.mark.unit
class TestRichUsesTheTerminalRenderer:
    def test_whole_document(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setenv("COLUMNS", "60")
        path = tmp_path / "doc.md"
        path.write_text(SOURCE, encoding="utf-8")
        assert main([str(path), "--rich", "--force-rich"]) == 0
        out = capsys.readouterr().out
        assert "note" in out and "[1]" in out
        assert "[^1]" not in out
        assert "☑" in out
        assert "Warning" in out and "[!WARNING]" not in out

    def test_line_numbers_keep_the_markdown_path(self, tmp_path, capsys):
        path = tmp_path / "doc.md"
        path.write_text(SOURCE, encoding="utf-8")
        assert main([str(path), "--rich", "--force-rich", "--line-numbers"]) == 0
        assert "[^1]" in capsys.readouterr().out


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
