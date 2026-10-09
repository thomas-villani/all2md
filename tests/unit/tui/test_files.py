"""Collecting the documents the viewer's file tree offers."""

from __future__ import annotations

import os

import pytest

from all2md.tui.files import FileTree, collect


def touch(root, *names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")


@pytest.fixture
def tree(tmp_path):
    touch(
        tmp_path,
        "README.md",
        "guide/intro.md",
        "guide/Setup.docx",
        "guide/deep/notes.html",
        "data.unknownext",
        ".hidden.md",
        ".git/config.md",
        "node_modules/pkg/readme.md",
        "__pycache__/x.md",
    )
    return tmp_path


def names(files: FileTree) -> list[str]:
    return [path.relative_to(files.root).as_posix() for path in files.files]


@pytest.mark.unit
class TestCollect:
    def test_a_folder(self, tree):
        files = collect([str(tree)])
        assert files.root == tree
        assert names(files) == ["guide/deep/notes.html", "guide/intro.md", "guide/Setup.docx", "README.md"]
        assert not files.truncated

    def test_the_current_folder_by_default(self, tree, monkeypatch):
        monkeypatch.chdir(tree)
        assert collect([]).root == tree

    def test_a_glob(self, tree, monkeypatch):
        monkeypatch.chdir(tree)
        files = collect(["guide/**/*.*"])
        assert files.root == tree / "guide"
        assert names(files) == ["deep/notes.html", "intro.md", "Setup.docx"]

    def test_several_files_root_at_their_common_folder(self, tree):
        files = collect([str(tree / "guide" / "deep" / "notes.html"), str(tree / "guide" / "intro.md")])
        assert files.root == tree / "guide"

    def test_a_named_file_is_kept_whatever_its_extension(self, tree):
        files = collect([str(tree / "data.unknownext"), str(tree / "README.md")])
        assert names(files) == ["data.unknownext", "README.md"]

    def test_duplicates_once(self, tree):
        files = collect([str(tree / "README.md"), str(tree)])
        assert names(files).count("README.md") == 1

    def test_missing(self, tree):
        with pytest.raises(FileNotFoundError):
            collect([str(tree / "nope")])

    def test_formats_missing_a_parser_package_are_left_out(self, tree, monkeypatch):
        from all2md.converter_registry import registry

        monkeypatch.setattr(registry, "check_dependencies", lambda **kwargs: {"docx": ["python-docx"]})
        assert "guide/Setup.docx" not in names(collect([str(tree)]))
        assert "guide/Setup.docx" in names(collect([str(tree / "guide" / "Setup.docx"), str(tree / "README.md")]))

    def test_limit(self, tree):
        files = collect([str(tree)], limit=2)
        assert len(files.files) == 2 and files.truncated

    @pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
    def test_symlinked_folders_are_not_entered(self, tree, tmp_path_factory):
        outside = tmp_path_factory.mktemp("outside")
        touch(outside, "secret.md")
        try:
            os.symlink(outside, tree / "link", target_is_directory=True)
        except OSError:
            pytest.skip("symlinks need privileges here")
        assert "link/secret.md" not in names(collect([str(tree)]))


@pytest.mark.unit
class TestNodes:
    def test_folders_first_then_files_by_name(self, tree):
        files = collect([str(tree)])
        nodes = files.nodes()
        assert [node["label"] for node in nodes] == ["guide/", "README.md"]
        guide = nodes[0]
        assert guide["id"] == "d:guide"
        assert [node["label"] for node in guide["children"]] == ["deep/", "intro.md", "Setup.docx"]
        assert guide["children"][1]["id"] == "f:guide/intro.md"

    def test_ids_round_trip(self, tree):
        files = collect([str(tree)])
        for path in files.files:
            assert files.path_of(files.node_id(path)) == path
        assert files.path_of("d:guide") is None
        assert files.path_of("f:../../etc/passwd") is None

    def test_folder_ids(self, tree):
        files = collect([str(tree)])
        assert files.folder_ids(tree / "guide" / "deep" / "notes.html") == ["d:guide", "d:guide/deep"]
        assert files.folder_ids() == ["d:guide", "d:guide/deep"]
