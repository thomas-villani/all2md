"""Unit tests for shared CLI input-collection helpers.

Covers glob pattern splitting, hidden-component detection, and the
dot-file/dot-folder skipping behaviour of ``collect_input_files``.
"""

from pathlib import Path

import pytest

from all2md.cli.commands.shared import (
    collect_input_files,
    has_hidden_component,
    split_glob_pattern,
)
from all2md.converter_registry import registry


@pytest.mark.unit
class TestSplitGlobPattern:
    """Test ``split_glob_pattern`` anchor/pattern/recursive extraction."""

    def test_simple_pattern(self):
        anchor, pattern, recursive = split_glob_pattern("subdir/*.docx")
        assert anchor == Path("subdir")
        assert pattern == "*.docx"
        assert recursive is False

    def test_recursive_pattern(self):
        anchor, pattern, recursive = split_glob_pattern("subdir/**/*.docx")
        assert anchor == Path("subdir")
        assert pattern == "*.docx"
        assert recursive is True

    def test_no_directory_prefix(self):
        anchor, pattern, recursive = split_glob_pattern("*.docx")
        assert anchor == Path(".")
        assert pattern == "*.docx"
        assert recursive is False

    def test_explicit_hidden_anchor_preserved(self):
        # A literal dot-folder in the anchor is not treated as a wildcard part.
        anchor, pattern, _ = split_glob_pattern(".config/*.md")
        assert anchor == Path(".config")
        assert pattern == "*.md"


@pytest.mark.unit
class TestHasHiddenComponent:
    """Test ``has_hidden_component`` relative-to-root semantics."""

    def test_hidden_file(self):
        assert has_hidden_component(Path("root/.hidden.md"), Path("root")) is True

    def test_hidden_folder(self):
        assert has_hidden_component(Path("root/.git/x.md"), Path("root")) is True

    def test_plain_file(self):
        assert has_hidden_component(Path("root/sub/x.md"), Path("root")) is False

    def test_hidden_root_itself_not_counted(self):
        # Components at or above ``root`` are not considered hidden.
        assert has_hidden_component(Path(".config/x.md"), Path(".config")) is False


@pytest.mark.unit
class TestCollectInputFilesHidden:
    """Test that collect_input_files skips dot-paths by default."""

    def _build_tree(self, tmp_path):
        (tmp_path / "a.md").write_text("# a")
        (tmp_path / ".hidden.md").write_text("# h")
        hidden_dir = tmp_path / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "c.md").write_text("# c")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("# n")

    def test_directory_skips_hidden_by_default(self, tmp_path):
        self._build_tree(tmp_path)
        items = collect_input_files([str(tmp_path)], recursive=True, extensions=[".md"])
        names = sorted(Path(i.display_name).name for i in items)
        assert names == ["a.md", "nested.md"]

    def test_directory_include_hidden(self, tmp_path):
        self._build_tree(tmp_path)
        items = collect_input_files([str(tmp_path)], recursive=True, extensions=[".md"], include_hidden=True)
        names = sorted(Path(i.display_name).name for i in items)
        assert names == [".hidden.md", "a.md", "c.md", "nested.md"]

    def test_explicit_hidden_file_is_included(self, tmp_path):
        # An explicitly named dot-file is always converted.
        hidden = tmp_path / ".hidden.md"
        hidden.write_text("# h")
        items = collect_input_files([str(hidden)], extensions=[".md"])
        names = [Path(i.display_name).name for i in items]
        assert names == [".hidden.md"]


@pytest.mark.unit
class TestCollectInputFilesMultiPartExtensions:
    """Two-part extensions must survive collection (#306).

    ``Path("a.tar.gz").suffix`` is ``".gz"``, which no converter declares, so the
    default extension filter used to drop every ``.tar.gz`` before any converter
    saw it -- while the Python API opened the same file fine.
    """

    def test_every_registered_extension_is_accepted(self, tmp_path):
        # Parity with the registry rather than a hand-listed set: if a format
        # declares an extension, naming a file with it must be collectable.
        known = sorted(registry.get_all_extensions())
        for ext in known:
            (tmp_path / f"sample{ext}").write_bytes(b"x")

        items = collect_input_files([str(tmp_path)])
        collected = {Path(i.display_name).name for i in items}
        missing = sorted(f"sample{ext}" for ext in known if f"sample{ext}" not in collected)
        assert missing == []

    @pytest.mark.parametrize("name", ["bundle.tar.gz", "bundle.tar.bz2", "bundle.tar.xz"])
    def test_explicitly_named_archive_is_collected(self, tmp_path, name):
        archive = tmp_path / name
        archive.write_bytes(b"x")
        items = collect_input_files([str(archive)])
        assert [Path(i.display_name).name for i in items] == [name]

    def test_explicit_multi_part_extension_filter(self, tmp_path):
        (tmp_path / "a.tar.gz").write_bytes(b"x")
        (tmp_path / "b.md").write_text("# b")
        items = collect_input_files([str(tmp_path)], extensions=[".tar.gz"])
        assert [Path(i.display_name).name for i in items] == ["a.tar.gz"]

    def test_dotted_stem_still_resolves_to_its_real_extension(self, tmp_path):
        # Trying shorter tails is what keeps this working: the suffixes of
        # "report.2024.md" are ['.2024', '.md'] and only the last is an extension.
        (tmp_path / "report.2024.md").write_text("# r")
        items = collect_input_files([str(tmp_path)], extensions=[".md"])
        assert [Path(i.display_name).name for i in items] == ["report.2024.md"]

    def test_unknown_double_extension_is_still_rejected(self, tmp_path):
        (tmp_path / "a.tar.gz.bak").write_bytes(b"x")
        assert collect_input_files([str(tmp_path)], extensions=[".tar.gz"]) == []
