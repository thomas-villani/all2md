#  Copyright (c) 2025 Tom Villani, Ph.D.
"""``grep`` and ``search`` skip a file they cannot read and search the rest.

One file whose format needs a missing optional dependency (a ``.chm`` without
pychm) used to end a recursive grep with exit 2 and no results at all. Like
``grep``, both commands now warn about that file on stderr and go on; a run in
which every input fails still fails.
"""

from __future__ import annotations

import pytest

import all2md.search.service as service_module
from all2md.cli.commands.search import handle_grep_command, handle_search_command
from all2md.exceptions import DependencyError
from all2md.search.service import SearchDocumentInput, SearchService

_real_to_ast = service_module.to_ast


def _fail_on_chm(source, **kwargs):
    if str(source).endswith(".chm"):
        raise DependencyError("chm", [("pychm", "")], message="CHM format requires the following packages: 'pychm'")
    return _real_to_ast(source, **kwargs)


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "to_ast", _fail_on_chm)
    (tmp_path / "notes.md").write_text("The deadline is Friday.\n", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "help.chm").write_bytes(b"ITSF not really")
    return tmp_path


@pytest.mark.unit
class TestSkipErrors:
    def test_service_records_the_skipped_document_and_indexes_the_rest(self, corpus):
        service = SearchService()
        documents = [
            SearchDocumentInput(source=corpus / "notes.md"),
            SearchDocumentInput(source=corpus / "sub" / "help.chm"),
        ]
        service.build_indexes(documents, skip_errors=True)
        assert [source.endswith("help.chm") for source, _ in service.skipped] == [True]
        assert service.state.chunks

    def test_service_raises_by_default(self, corpus):
        with pytest.raises(DependencyError):
            SearchService().build_indexes([SearchDocumentInput(source=corpus / "sub" / "help.chm")])

    def test_service_raises_when_every_document_fails(self, corpus):
        with pytest.raises(DependencyError):
            SearchService().build_indexes([SearchDocumentInput(source=corpus / "sub" / "help.chm")], skip_errors=True)


@pytest.mark.unit
class TestCommands:
    def test_recursive_grep_warns_and_finds_the_rest(self, corpus, capsys):
        assert handle_grep_command(["deadline", str(corpus), "-r"]) == 0
        captured = capsys.readouterr()
        assert "notes.md" in captured.out
        assert "help.chm: skipped: CHM format requires" in captured.err

    def test_grep_on_only_an_unreadable_file_still_fails(self, corpus, capsys):
        assert handle_grep_command(["deadline", str(corpus / "sub" / "help.chm")]) != 0
        assert "pychm" in capsys.readouterr().err

    def test_search_warns_and_finds_the_rest(self, corpus, capsys):
        assert handle_search_command(["deadline", str(corpus), "-r", "--mode", "grep"]) == 0
        captured = capsys.readouterr()
        assert "notes.md" in captured.out
        assert "help.chm: skipped" in captured.err
