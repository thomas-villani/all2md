"""Unit tests for CLIInputItem class and related functionality."""

from pathlib import Path

import pytest

from all2md.cli.input_items import CLIInputItem


@pytest.mark.unit
class TestCLIInputItem:
    """Test CLIInputItem dataclass."""

    def test_local_file_creation(self, tmp_path: Path):
        """Test creating a local file input item."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        item = CLIInputItem(
            raw_input=file_path,
            kind="local_file",
            display_name="test.txt",
            path_hint=file_path,
        )

        assert item.is_local_file()
        assert not item.is_remote()
        assert not item.is_stdin()
        assert item.kind == "local_file"

    def test_remote_uri_creation(self):
        """Test creating a remote URI input item."""
        item = CLIInputItem(
            raw_input="https://example.com/doc.pdf",
            kind="remote_uri",
            display_name="doc.pdf",
            path_hint=Path("doc.pdf"),
            metadata={"remote_host": "example.com"},
        )

        assert not item.is_local_file()
        assert item.is_remote()
        assert not item.is_stdin()
        assert item.kind == "remote_uri"

    def test_stdin_creation(self):
        """Test creating a stdin input item."""
        item = CLIInputItem(
            raw_input=b"some stdin content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert not item.is_local_file()
        assert not item.is_remote()
        assert item.is_stdin()
        assert item.kind == "stdin_bytes"

    def test_best_path_local_file(self, tmp_path: Path):
        """Test best_path returns path for local file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        item = CLIInputItem(
            raw_input=file_path,
            kind="local_file",
            display_name="test.txt",
            path_hint=file_path,
        )

        assert item.best_path() == file_path

    def test_best_path_remote(self):
        """Test best_path returns path_hint for remote."""
        hint = Path("doc.pdf")
        item = CLIInputItem(
            raw_input="https://example.com/doc.pdf",
            kind="remote_uri",
            display_name="doc.pdf",
            path_hint=hint,
        )

        assert item.best_path() == hint

    def test_best_path_stdin_none(self):
        """Test best_path returns None for stdin without hint."""
        item = CLIInputItem(
            raw_input=b"content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert item.best_path() is None

    def test_name_from_path_hint(self, tmp_path: Path):
        """Test name property uses path_hint name."""
        hint = tmp_path / "document.pdf"
        item = CLIInputItem(
            raw_input="https://example.com/path/document.pdf",
            kind="remote_uri",
            display_name="remote document",
            path_hint=hint,
        )

        assert item.name == "document.pdf"

    def test_name_stdin(self):
        """Test name property returns 'stdin' for stdin input."""
        item = CLIInputItem(
            raw_input=b"content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert item.name == "stdin"

    def test_name_fallback_display_name(self):
        """Test name falls back to display_name."""
        item = CLIInputItem(
            raw_input="some input",
            kind="remote_uri",
            display_name="my document",
        )

        assert item.name == "my document"

    def test_stem_from_path_hint(self, tmp_path: Path):
        """Test stem property uses path_hint stem."""
        hint = tmp_path / "document.pdf"
        item = CLIInputItem(
            raw_input="https://example.com/document.pdf",
            kind="remote_uri",
            display_name="document",
            path_hint=hint,
        )

        assert item.stem == "document"

    def test_stem_stdin(self):
        """Test stem returns 'stdin' for stdin input."""
        item = CLIInputItem(
            raw_input=b"content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert item.stem == "stdin"

    def test_stem_remote_fallback(self):
        """Test stem falls back to remote_host for remote without hint."""
        item = CLIInputItem(
            raw_input="https://example.com/path",
            kind="remote_uri",
            display_name="remote",
            metadata={"remote_host": "example.com"},
        )

        assert item.stem == "example.com"

    def test_suffix_from_path_hint(self, tmp_path: Path):
        """Test suffix property uses path_hint suffix."""
        hint = tmp_path / "document.pdf"
        item = CLIInputItem(
            raw_input="https://example.com/document.pdf",
            kind="remote_uri",
            display_name="document",
            path_hint=hint,
        )

        assert item.suffix == ".pdf"

    def test_suffix_empty_when_no_hint(self):
        """Test suffix returns empty string without hint."""
        item = CLIInputItem(
            raw_input="content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert item.suffix == ""

    def test_derive_output_stem_from_hint(self, tmp_path: Path):
        """Test derive_output_stem uses path_hint."""
        hint = tmp_path / "document.pdf"
        item = CLIInputItem(
            raw_input=hint,
            kind="local_file",
            display_name="document.pdf",
            path_hint=hint,
        )

        assert item.derive_output_stem(1) == "document"

    def test_derive_output_stem_remote_with_host(self):
        """Test derive_output_stem for remote with host."""
        item = CLIInputItem(
            raw_input="https://example.com/page",
            kind="remote_uri",
            display_name="page",
            metadata={"remote_host": "example.com"},
        )

        stem = item.derive_output_stem(1)
        assert "example" in stem or "remote" in stem

    def test_derive_output_stem_stdin(self):
        """Test derive_output_stem returns 'stdin' for stdin."""
        item = CLIInputItem(
            raw_input=b"content",
            kind="stdin_bytes",
            display_name="stdin",
        )

        assert item.derive_output_stem(1) == "stdin"

    def test_derive_output_stem_fallback_with_index(self):
        """Test derive_output_stem includes index in fallback."""
        item = CLIInputItem(
            raw_input="https://example.com/",
            kind="remote_uri",
            display_name="remote",
            metadata={"remote_host": "example.com"},
        )

        stem = item.derive_output_stem(42)
        # Should include formatted index or host
        assert "example" in stem or "0042" in stem

    def test_frozen_dataclass(self, tmp_path: Path):
        """Test CLIInputItem is immutable (frozen)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        item = CLIInputItem(
            raw_input=file_path,
            kind="local_file",
            display_name="test.txt",
        )

        with pytest.raises(AttributeError):
            item.kind = "remote_uri"  # type: ignore

    def test_original_argument_preserved(self):
        """Test original_argument is preserved."""
        item = CLIInputItem(
            raw_input="processed_path",
            kind="local_file",
            display_name="file.txt",
            original_argument="./relative/file.txt",
        )

        assert item.original_argument == "./relative/file.txt"

    def test_metadata_preserved(self):
        """Test metadata dict is preserved."""
        item = CLIInputItem(
            raw_input="https://example.com/doc.pdf",
            kind="remote_uri",
            display_name="doc.pdf",
            metadata={"remote_host": "example.com", "custom_key": "custom_value"},
        )

        assert item.metadata["remote_host"] == "example.com"
        assert item.metadata["custom_key"] == "custom_value"

    def test_slots_efficiency(self):
        """Test CLIInputItem uses __slots__ for memory efficiency."""
        # __slots__ is specified in the dataclass decorator
        item = CLIInputItem(
            raw_input="test",
            kind="local_file",
            display_name="test",
        )
        # Slots-based classes don't have __dict__
        assert not hasattr(item, "__dict__") or len(item.__dict__) == 0
