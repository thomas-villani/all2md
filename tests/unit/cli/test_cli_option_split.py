"""The CLI hands parser options to the parser and renderer options to the renderer.

``--outline``, ``--extract``, ``--slice`` and the line windows parse to an AST and
render it themselves. They used to pass every option to both steps, so each step
warned "Keyword arguments were ignored" about the options that belong to the other.
"""

from __future__ import annotations

import warnings

import pytest

from all2md.cli import main

HTML = (
    "<html><head><title>Guide</title></head><body>"
    "<h1>Guide</h1><p>Intro.</p>"
    "<h2>Install</h2><p>Step.</p>"
    "<h2>Usage</h2><p>Use it.</p>"
    "</body></html>"
)

MODES = [
    pytest.param(["--head", "6"], id="head"),
    pytest.param(["--lines", "1:6"], id="lines"),
    pytest.param(["--extract", "Install"], id="extract"),
    pytest.param(["--extract", "line:1-6"], id="extract-lines"),
    pytest.param(["--slice", "1/2"], id="slice"),
    pytest.param(["--outline"], id="outline"),
]


def _run(argv: list[str]) -> list[str]:
    """Run the CLI and return the messages of every 'ignored' warning it raised."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert main(argv) == 0
    return [str(w.message) for w in caught if "were ignored" in str(w.message)]


@pytest.mark.unit
@pytest.mark.parametrize("mode", MODES)
class TestNoIgnoredOptionWarnings:
    def test_stdout(self, tmp_path, capsys, mode):
        source = tmp_path / "guide.html"
        source.write_text(HTML, encoding="utf-8")
        argv = [str(source), "--html-extract-title", "--to", "man", "--man-renderer-section", "8", *mode]
        assert _run(argv) == []

    def test_output_file(self, tmp_path, mode):
        source = tmp_path / "guide.html"
        source.write_text(HTML, encoding="utf-8")
        out = tmp_path / "guide.8"
        argv = [str(source), "--html-extract-title", "--to", "man", "--man-renderer-section", "8", *mode]
        assert _run([*argv, "--out", str(out)]) == []

    def test_markdown_target(self, tmp_path, capsys, mode):
        source = tmp_path / "guide.html"
        source.write_text(HTML, encoding="utf-8")
        argv = [str(source), "--html-extract-title", "--markdown-emphasis-symbol", "_", *mode]
        assert _run(argv) == []


@pytest.mark.unit
class TestOptionsStillApply:
    """Splitting must not drop an option on the way to the step that wants it."""

    @pytest.mark.parametrize("mode", [["--head", "6"], ["--extract", "Install"], ["--slice", "1/2"]])
    def test_renderer_option_reaches_the_renderer(self, tmp_path, capsys, mode):
        source = tmp_path / "guide.html"
        source.write_text(HTML, encoding="utf-8")
        assert main([str(source), "--to", "man", "--man-renderer-section", "8", *mode]) == 0
        th = [line for line in capsys.readouterr().out.splitlines() if line.startswith(".TH")]
        assert th and th[0].split()[2] == "8"

    def test_parser_option_reaches_the_parser(self, tmp_path, capsys):
        source = tmp_path / "doc.html"
        source.write_text("<p>a&nbsp;b</p>", encoding="utf-8")
        assert main([str(source), "--html-convert-nbsp", "--head", "1"]) == 0
        assert "a b" in capsys.readouterr().out


@pytest.mark.unit
class TestMultiDocumentModes:
    """``--collate``, ``--split-by`` and ``--merge-from-list`` parse and render in separate steps too."""

    MAN = ["--html-extract-title", "--to", "man", "--man-renderer-section", "8"]

    def _sources(self, tmp_path):
        paths = []
        for name in ("a.html", "b.html"):
            path = tmp_path / name
            path.write_text(HTML, encoding="utf-8")
            paths.append(path)
        return paths

    def test_collate(self, tmp_path, capsys):
        a, b = self._sources(tmp_path)
        assert _run([str(a), str(b), "--collate", *self.MAN]) == []

    def test_split(self, tmp_path):
        a, _ = self._sources(tmp_path)
        assert _run([str(a), "--split-by", "h2", "--output-dir", str(tmp_path / "parts"), *self.MAN]) == []
        assert any((tmp_path / "parts").iterdir())

    def test_merge_from_list(self, tmp_path, capsys):
        a, b = self._sources(tmp_path)
        listing = tmp_path / "list.txt"
        listing.write_text(f"{a}\n{b}\n", encoding="utf-8")
        assert _run(["--merge-from-list", str(listing), *self.MAN]) == []
