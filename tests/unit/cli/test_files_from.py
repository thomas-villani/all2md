"""``--files-from``: input paths from a list file or stdin, for every command that takes files."""

from __future__ import annotations

import argparse
import io

import pytest

from all2md.cli import builder, files_from, main
from all2md.cli.builder import EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.cli.files_from import apply_files_from, read_files_from

NL = chr(10)
NUL = chr(0)


@pytest.fixture
def docs(tmp_path):
    """Two Markdown files and a list naming them, the way a picker writes it."""
    first = tmp_path / "alpha.md"
    second = tmp_path / "beta notes.md"
    first.write_text("# Alpha" + NL * 2 + "quarterly invoice" + NL, encoding="utf-8")
    second.write_text("# Beta" + NL * 2 + "nothing to see" + NL, encoding="utf-8")
    return first, second


def _stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8"))


@pytest.mark.unit
@pytest.mark.cli
class TestReadFilesFrom:
    def test_lines_comments_and_blanks(self, docs, tmp_path):
        listing = tmp_path / "list.txt"
        listing.write_text(f"# picked{NL}{NL}alpha.md{NL}  beta notes.md  {NL}", encoding="utf-8")

        assert read_files_from(str(listing)) == [str(path) for path in docs]

    def test_relative_paths_resolve_against_the_list_files_folder(self, docs, tmp_path, monkeypatch):
        sub = tmp_path / "lists"
        sub.mkdir()
        (sub / "list.txt").write_text("../alpha.md" + NL, encoding="utf-8")
        monkeypatch.chdir(sub.parent.parent)

        assert read_files_from(str(sub / "list.txt")) == [str(sub / ".." / "alpha.md")]

    def test_stdin_resolves_against_the_current_folder(self, docs, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, "alpha.md" + NL)

        assert read_files_from("-") == [str(tmp_path / "alpha.md")]

    def test_null_separated_paths_are_taken_as_written(self, docs, tmp_path, monkeypatch):
        """No comment or whitespace handling: a NUL list is what find -print0 wrote."""
        monkeypatch.chdir(tmp_path)
        _stdin(monkeypatch, f"alpha.md{NUL}beta notes.md{NUL}")

        assert read_files_from("-", null=True) == [str(tmp_path / "alpha.md"), str(tmp_path / "beta notes.md")]

    def test_every_missing_path_is_named(self, docs, tmp_path):
        listing = tmp_path / "list.txt"
        listing.write_text(f"alpha.md{NL}gone.md{NL}also-gone.md{NL}", encoding="utf-8")

        with pytest.raises(argparse.ArgumentTypeError, match="gone.md") as raised:
            read_files_from(str(listing))
        assert "also-gone.md" in str(raised.value)

    def test_an_empty_list_is_an_error(self, monkeypatch):
        _stdin(monkeypatch, "# nothing" + NL)

        with pytest.raises(argparse.ArgumentTypeError, match="no paths"):
            read_files_from("-")

    def test_a_missing_list_file_is_an_error(self, tmp_path):
        with pytest.raises(argparse.ArgumentTypeError, match="list file not found"):
            read_files_from(str(tmp_path / "nope.txt"))


@pytest.mark.unit
@pytest.mark.cli
class TestApplyFilesFrom:
    def _ns(self, **kwargs) -> argparse.Namespace:
        return argparse.Namespace(**{"files_from": None, "null": False, **kwargs})

    def test_listed_paths_join_the_ones_on_the_command_line(self, docs, tmp_path):
        listing = tmp_path / "list.txt"
        listing.write_text("beta notes.md" + NL, encoding="utf-8")
        parsed = self._ns(inputs=[str(docs[0])], files_from=str(listing))

        assert apply_files_from(parsed, "inputs") is None
        assert parsed.inputs == [str(docs[0]), str(docs[1])]

    def test_a_single_input_command_takes_exactly_one(self, docs, tmp_path):
        listing = tmp_path / "list.txt"
        listing.write_text(f"alpha.md{NL}beta notes.md{NL}", encoding="utf-8")

        assert "listed 2" in apply_files_from(self._ns(input=None, files_from=str(listing)), "input", single=True)

    def test_stdin_cannot_be_both_the_list_and_the_document(self):
        assert "both" in apply_files_from(self._ns(inputs=["-"], files_from="-"), "inputs")

    def test_null_needs_files_from(self):
        assert "--null" in apply_files_from(self._ns(inputs=[], null=True), "inputs")

    def test_the_exit_code_mirrors_the_builders(self):
        assert files_from.EXIT_VALIDATION_ERROR == builder.EXIT_VALIDATION_ERROR


@pytest.mark.unit
@pytest.mark.cli
class TestCommands:
    def test_convert(self, docs, monkeypatch, capsys):
        _stdin(monkeypatch, str(docs[0]) + NL)

        assert main(["--files-from", "-"]) == EXIT_SUCCESS
        assert "quarterly invoice" in capsys.readouterr().out

    def test_convert_keeps_the_old_spelling(self, docs, monkeypatch, capsys):
        _stdin(monkeypatch, str(docs[0]) + NL)

        assert main(["--batch-from-list", "-"]) == EXIT_SUCCESS
        assert "quarterly invoice" in capsys.readouterr().out

    def test_convert_null(self, docs, monkeypatch, capsys):
        _stdin(monkeypatch, str(docs[0]) + NUL)

        assert main(["--files-from", "-", "--null"]) == EXIT_SUCCESS
        assert "quarterly invoice" in capsys.readouterr().out

    def test_grep(self, docs, monkeypatch, capsys):
        from all2md.cli.commands.search import handle_grep_command

        _stdin(monkeypatch, NUL.join(str(path) for path in docs) + NUL)

        assert handle_grep_command(["invoice", "--files-from", "-", "--null"]) == EXIT_SUCCESS
        out = capsys.readouterr().out
        assert "alpha.md" in out and "beta notes.md" not in out

    def test_grep_without_any_input(self, capsys):
        from all2md.cli.commands.search import handle_grep_command

        assert handle_grep_command(["invoice"]) == EXIT_VALIDATION_ERROR
        assert "--files-from" in capsys.readouterr().err

    def test_a_single_input_command(self, docs, monkeypatch, capsys):
        from all2md.cli.commands.llm_minify import handle_llm_minify_command

        _stdin(monkeypatch, str(docs[0]) + NL)

        assert handle_llm_minify_command(["--files-from", "-"]) == EXIT_SUCCESS
        assert "quarterly invoice" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "command", ["report", "chunk", "roundtrip", "optimize", "generate_site", "view", "lint", "search"]
    )
    def test_every_file_command_accepts_the_flag(self, command):
        """The parsers, not the work: each one knows --files-from and --null."""
        from all2md.cli.commands import chunk, generate_site, lint, optimize, report, roundtrip, search, view

        factories = {
            "report": report._create_report_parser,
            "chunk": chunk._create_chunk_parser,
            "roundtrip": roundtrip._create_roundtrip_parser,
            "optimize": optimize._create_optimize_parser,
            "generate_site": generate_site._create_generate_site_parser,
            "view": view._create_view_parser,
            "lint": lint._build_parser,
            "search": search._build_search_argument_parser,
        }
        options = {action.dest for action in factories[command]()._actions}

        assert {"files_from", "null"} <= options


@pytest.mark.unit
@pytest.mark.cli
class TestRead:
    @pytest.fixture
    def runs(self, monkeypatch):
        pytest.importorskip("wijjit")
        from all2md.tui import app

        started = []
        monkeypatch.setattr(app.Viewer, "run", lambda self: started.append(self))
        return started

    def test_a_picked_file_opens_and_the_keyboard_is_reattached(self, runs, docs, monkeypatch):
        from all2md.cli.commands import read

        reattached = []
        monkeypatch.setattr(read, "reattach_terminal_input", lambda: reattached.append(True) or True)
        _stdin(monkeypatch, str(docs[0]) + NL)

        assert read.handle_read_command(["--files-from", "-"]) == EXIT_SUCCESS
        assert reattached == [True]
        assert runs[0].title == "alpha.md"

    def test_several_picked_files_open_as_a_tree(self, runs, docs, monkeypatch):
        from all2md.cli.commands import read

        monkeypatch.setattr(read, "reattach_terminal_input", lambda: True)
        _stdin(monkeypatch, NL.join(str(path) for path in docs) + NL)

        assert read.handle_read_command(["--files-from", "-"]) == EXIT_SUCCESS
        assert set(runs[0].files.files) == set(docs)

    def test_no_keyboard_to_return_to(self, runs, docs, monkeypatch, capsys):
        from all2md.cli.builder import EXIT_ERROR
        from all2md.cli.commands import read

        monkeypatch.setattr(read, "reattach_terminal_input", lambda: False)
        _stdin(monkeypatch, str(docs[0]) + NL)

        assert read.handle_read_command(["--files-from", "-"]) == EXIT_ERROR
        assert "keyboard" in capsys.readouterr().err
        assert runs == []
