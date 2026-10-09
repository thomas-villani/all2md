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
        args = [str(doc), "--keys", "vim", "--no-outline", "--clickable-links", "web", "--code-theme", "dracula"]
        assert handle_read_command(args) == EXIT_SUCCESS
        (viewer,) = runs
        assert viewer.preset == "vim" and viewer.app.state["panel"] == ""
        assert viewer.layout.options.clickable_links == "web"
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

    def test_no_input_on_a_terminal_browses_the_current_folder(self, runs, monkeypatch, doc):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
        monkeypatch.chdir(doc.parent)
        assert handle_read_command([]) == EXIT_SUCCESS
        (viewer,) = runs
        assert viewer.files.files == (doc,)
        assert viewer.app.state["panel"] == "files"

    def test_no_stdin_at_all_browses_the_current_folder(self, monkeypatch, doc):
        pytest.importorskip("wijjit")
        from all2md.tui import app

        # A stub: Wijjit itself reads sys.stdin when it is built on Linux.
        made = []

        class Viewer:
            def __init__(self, layout, title, **kwargs):
                made.append(kwargs["files"])

            def run(self):
                pass

        monkeypatch.setattr(app, "Viewer", Viewer)
        monkeypatch.setattr("sys.stdin", None)
        monkeypatch.chdir(doc.parent)
        assert handle_read_command([]) == EXIT_SUCCESS
        assert made[0].files == (doc,)

    def test_files_with_no_folder_in_common(self, runs, monkeypatch, doc, capsys):
        from all2md.tui import files

        def no_common_folder(inputs):
            raise ValueError("the files have no folder in common")

        monkeypatch.setattr(files, "collect", no_common_folder)
        assert handle_read_command([str(doc), str(doc.parent)]) == EXIT_ERROR
        assert "no folder in common" in capsys.readouterr().err
        assert runs == []

    def test_a_folder_opens_the_file_tree(self, runs, doc):
        (doc.parent / "sub").mkdir()
        (doc.parent / "sub" / "more.html").write_text("<h1>More</h1>", encoding="utf-8")
        (doc.parent / "skip.unknownext").write_text("x", encoding="utf-8")
        assert handle_read_command([str(doc.parent)]) == EXIT_SUCCESS
        (viewer,) = runs
        assert viewer.title == doc.parent.name
        assert [p.name for p in viewer.files.files] == ["notes.md", "more.html"]

    def test_several_files_open_the_file_tree(self, runs, doc):
        other = doc.parent / "other.md"
        other.write_text("# Other" + NL, encoding="utf-8")
        assert handle_read_command([str(doc), str(other)]) == EXIT_SUCCESS
        assert sorted(p.name for p in runs[0].files.files) == ["notes.md", "other.md"]

    def test_the_tree_opens_files_with_the_options(self, runs, doc):
        assert handle_read_command([str(doc.parent), "--clickable-links", "all"]) == EXIT_SUCCESS
        layout = runs[0].opener(doc)
        assert [h.text for h in layout.headings] == ["Notes"]
        assert layout.options.clickable_links == "all"

    def test_a_folder_without_documents(self, runs, tmp_path, capsys):
        assert handle_read_command([str(tmp_path)]) == EXIT_FILE_ERROR
        assert "no documents" in capsys.readouterr().err
        assert runs == []

    def test_stdin_with_other_inputs(self, runs, doc, capsys):
        assert handle_read_command(["-", str(doc)]) == EXIT_ERROR
        assert "stdin" in capsys.readouterr().err

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

    def test_rcat_help_mentions_the_viewer(self, capsys):
        with pytest.raises(SystemExit):
            rcat_main(["--help"])
        out = capsys.readouterr().out
        assert out.startswith("rcat FILE is all2md FILE --rich") and "rcat -i FILE" in out and "usage: all2md" in out

    def test_parser_factory(self):
        parsed = _create_read_parser().parse_args(["x.md"])
        assert (parsed.input, parsed.keys, parsed.no_outline, parsed.format) == (["x.md"], "default", False, "auto")


@pytest.mark.unit
@pytest.mark.cli
def test_help_lists_the_keys():
    text = _create_read_parser().format_help()
    assert "keys:" in text and "--keys vim adds:" in text
    assert "PgDn, Space      Scroll down a page" in text
    assert "  j          Scroll down a line" in text
