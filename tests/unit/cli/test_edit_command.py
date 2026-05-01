"""Unit tests for the edit CLI command."""

from pathlib import Path
from unittest.mock import patch

import pytest

from all2md.cli.builder import EXIT_FILE_ERROR, EXIT_VALIDATION_ERROR
from all2md.cli.commands.edit import (
    _available_target_formats,
    _build_save_defaults,
    handle_edit_command,
)
from all2md.utils.io_utils import backup_file


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "notes.md"
    path.write_text("# Hello\n\nWorld\n", encoding="utf-8")
    return path


@pytest.mark.unit
class TestArgValidation:
    def test_stdin_input_rejected(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = handle_edit_command(["-"])
        assert rc == EXIT_VALIDATION_ERROR
        assert "stdin" in capsys.readouterr().err.lower()

    def test_missing_file_rejected(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = handle_edit_command([str(tmp_path / "no_such_file.md")])
        assert rc == EXIT_FILE_ERROR
        assert "not found" in capsys.readouterr().err.lower()

    def test_directory_rejected(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = handle_edit_command([str(tmp_path)])
        assert rc == EXIT_FILE_ERROR
        assert "directory" in capsys.readouterr().err.lower()


@pytest.mark.unit
class TestAvailableFormats:
    def test_markdown_is_always_first(self) -> None:
        formats = _available_target_formats()
        assert len(formats) > 0
        assert formats[0]["value"] == "markdown"
        assert formats[0]["extension"] == "md"

    def test_each_format_has_value_label_extension(self) -> None:
        for fmt in _available_target_formats():
            assert set(fmt.keys()) == {"value", "label", "extension"}

    def test_unloadable_formats_are_filtered(self) -> None:
        from all2md.cli.commands import edit as edit_module

        def fake_get_renderer(fmt: str):  # type: ignore[no-untyped-def]
            if fmt == "html":
                raise ImportError("not installed")
            return object()

        with patch.object(edit_module.registry, "get_renderer", side_effect=fake_get_renderer):
            with patch.object(edit_module.registry, "list_formats", return_value=["html", "rst", "markdown"]):
                formats = _available_target_formats()

        values = [f["value"] for f in formats]
        assert "html" not in values
        assert "rst" in values
        assert values[0] == "markdown"


@pytest.mark.unit
class TestSaveDefaults:
    def test_markdown_source_overwrites_original(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        target_format, target_path, overwrite = _build_save_defaults(path, "markdown")
        assert target_format == "markdown"
        assert Path(target_path) == path
        assert overwrite is True

    def test_non_markdown_source_writes_sibling_md(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.docx"
        target_format, target_path, overwrite = _build_save_defaults(path, "docx")
        assert target_format == "markdown"
        assert Path(target_path) == tmp_path / "doc.md"
        assert overwrite is False


@pytest.mark.unit
class TestBackupFile:
    def test_no_backup_when_target_missing(self, tmp_path: Path) -> None:
        result = backup_file(tmp_path / "ghost.txt")
        assert result is None

    def test_creates_bak_for_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.txt"
        path.write_text("v1", encoding="utf-8")
        backup = backup_file(path)
        assert backup is not None
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "v1"
        assert backup.name == "data.txt.bak"

    def test_collisions_use_numbered_suffix(self, tmp_path: Path) -> None:
        path = tmp_path / "data.txt"
        path.write_text("v1", encoding="utf-8")
        b1 = backup_file(path)
        path.write_text("v2", encoding="utf-8")
        b2 = backup_file(path)
        path.write_text("v3", encoding="utf-8")
        b3 = backup_file(path)
        assert b1 is not None and b2 is not None and b3 is not None
        names = {b.name for b in (b1, b2, b3)}
        assert names == {"data.txt.bak", "data.txt.bak.1", "data.txt.bak.2"}
