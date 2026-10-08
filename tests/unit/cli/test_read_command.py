"""``all2md read`` and ``rcat -i``: argument handling, without running the viewer."""

from __future__ import annotations

import io

import pytest

from all2md.cli import rcat_main
from all2md.cli.builder import EXIT_DEPENDENCY_ERROR, EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.commands import dispatch_command
from all2md.cli.commands.read import _create_read_parser, handle_read_command

NL = chr(10)


@pytest.fixture
def runs(monkeypatch):
    """Record each viewer the command would run, instead of running it."""
    pytest.importorskip("wijjit")
    from all2md.tui import app

    started = []
    monkeypatch.setattr(app.Viewer, "run", lambda self: started.append(self))
    return started


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Notes" + NL * 2 + "See [x](#notes)." + NL, encoding="utf-8")
    return path


@pytest.mark.unit
@pytest.mark.cli
class TestReadCommand:
    def test_opens_the_viewer(self, runs, doc):
        assert handle_read_command([str(doc)]) == EXIT_SUCCESS
        (viewer,) = runs
        assert viewer.title == "notes.md"
        assert viewer.preset == "default"
        assert viewer.app.state["panel"] == "outline"
        assert [h.text for h in viewer.layout.headings] == ["Notes"]

    def test_options(self, runs, doc):
        args = [str(doc), "--keys", "vim", "--no-outline", "--no-hyperlinks", "--code-theme", "dracula"]
        assert handle_read_command(args) == EXIT_SUCCESS
        (viewer,) = runs
        assert viewer.preset == "vim" and viewer.app.state["panel"] == ""
        assert viewer.layout.options.hyperlinks is False
        assert viewer.layout.options.code_theme == "dracula"

    def test_format_hint(self, runs, tmp_path):
        path = tmp_path / "notes.data"
        path.write_text("# Heading" + NL * 2 + "text" + NL, encoding="utf-8")
        assert handle_read_command([str(path), "--format", "markdown"]) == EXIT_SUCCESS
        assert [h.text for h in runs[0].layout.headings] == ["Heading"]

    def test_missing_file(self, runs, tmp_path):
        assert handle_read_command([str(tmp_path / "nope.md")]) == EXIT_FILE_ERROR
        assert runs == []

    def test_bad_preset(self, runs, doc):
        assert handle_read_command([str(doc), "--keys", "emacs"]) != EXIT_SUCCESS
        assert runs == []

    def test_no_input_on_a_terminal(self, runs, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
        assert handle_read_command([]) == EXIT_ERROR
        assert "give a file" in capsys.readouterr().err

    def test_empty_stdin(self, runs, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"")))
        assert handle_read_command(["-"]) == EXIT_FILE_ERROR

    def test_stdin_without_a_terminal_to_return_to(self, runs, monkeypatch, capsys):
        from all2md.cli.commands import read

        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"# From stdin" + NL.encode())))
        monkeypatch.setattr(read, "reattach_terminal_input", lambda: False)
        assert handle_read_command(["-"]) == EXIT_ERROR
        assert "save it to a file" in capsys.readouterr().err
        assert runs == []

    def test_stdin(self, runs, monkeypatch):
        from all2md.cli.commands import read

        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"# From stdin" + NL.encode())))
        monkeypatch.setattr(read, "reattach_terminal_input", lambda: True)
        assert handle_read_command(["-"]) == EXIT_SUCCESS
        assert runs[0].title == "stdin"

    def test_without_wijjit(self, monkeypatch, doc, capsys):
        from all2md.tui import app

        monkeypatch.setattr(app, "wijjit_available", lambda: False)
        assert handle_read_command([str(doc)]) == EXIT_DEPENDENCY_ERROR
        assert "all2md[tui]" in capsys.readouterr().err


@pytest.mark.unit
@pytest.mark.cli
class TestEntryPoints:
    def test_dispatched_as_a_subcommand(self, runs, doc):
        assert dispatch_command(["read", str(doc)]) == EXIT_SUCCESS
        assert len(runs) == 1

    @pytest.mark.parametrize("flag", ["-i", "--interactive"])
    def test_rcat_interactive(self, runs, doc, flag):
        assert rcat_main([flag, str(doc), "--keys", "vim"]) == EXIT_SUCCESS
        assert runs[0].preset == "vim"

    def test_rcat_without_i_does_not_open_the_viewer(self, runs, doc, capsys):
        assert rcat_main([str(doc)]) == EXIT_SUCCESS
        assert runs == []
        assert "Notes" in capsys.readouterr().out

    def test_parser_factory(self):
        parsed = _create_read_parser().parse_args(["x.md"])
        assert (parsed.keys, parsed.no_outline, parsed.format) == ("default", False, "auto")
