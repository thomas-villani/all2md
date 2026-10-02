#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for single-file gzip/bzip2/xz handling: the helpers, detection and the archive parser."""

from __future__ import annotations

import bz2
import gzip
import io
import lzma
import tarfile
from collections.abc import Callable
from pathlib import Path

import pytest

from all2md import to_markdown
from all2md.converter_registry import registry
from all2md.exceptions import ArchiveSecurityError, MalformedFileError
from all2md.utils.compression import (
    compression_kind,
    decompress_single,
    decompressed_prefix,
    gzip_original_name,
    looks_like_tar,
)

pytestmark = pytest.mark.unit

COMPRESSORS: dict[str, Callable[[bytes], bytes]] = {
    "gzip": gzip.compress,
    "bzip2": bz2.compress,
    "xz": lzma.compress,
}
MAN_PAGE = b".TH LS 1\n.SH NAME\nls \\- list directory contents\n"


def tar_bytes(compression: str = "gz") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=f"w:{compression}") as archive:
        info = tarfile.TarInfo("a.md")
        info.size = 7
        archive.addfile(info, io.BytesIO(b"# A\n\nx\n"))
    return buffer.getvalue()


def gzip_with_name(name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename=name, mode="wb", fileobj=buffer) as handle:
        handle.write(content)
    return buffer.getvalue()


class TestHelpers:
    """The stdlib-only helpers in all2md.utils.compression."""

    @pytest.mark.parametrize("kind", sorted(COMPRESSORS))
    def test_round_trip(self, kind: str) -> None:
        data = COMPRESSORS[kind](b"hello " * 1000)
        assert compression_kind(data) == kind
        assert decompress_single(data) == b"hello " * 1000
        assert decompressed_prefix(data, 5) == b"hello"

    def test_not_compressed(self) -> None:
        assert compression_kind(b"plain text") is None
        assert decompressed_prefix(b"plain text") is None
        with pytest.raises(MalformedFileError):
            decompress_single(b"plain text")

    def test_concatenated_members_are_joined(self) -> None:
        assert decompress_single(gzip.compress(b"one ") + gzip.compress(b"two")) == b"one two"

    def test_zero_padding_after_the_stream_is_ignored(self) -> None:
        assert decompress_single(gzip.compress(b"data") + b"\x00" * 64) == b"data"

    def test_trailing_garbage_is_rejected(self) -> None:
        with pytest.raises(MalformedFileError, match="after the end"):
            decompress_single(gzip.compress(b"data") + b"garbage")

    @pytest.mark.parametrize("kind", sorted(COMPRESSORS))
    def test_truncated_stream_is_rejected(self, kind: str) -> None:
        data = COMPRESSORS[kind](bytes(range(256)) * 400)
        with pytest.raises(MalformedFileError):
            decompress_single(data[: len(data) // 2])

    def test_corrupt_stream_is_rejected(self) -> None:
        data = bytearray(gzip.compress(b"some text that is long enough" * 10))
        data[20:30] = b"\xff" * 10
        with pytest.raises(MalformedFileError):
            decompress_single(bytes(data))

    def test_size_limit(self) -> None:
        with pytest.raises(ArchiveSecurityError, match="expands beyond"):
            decompress_single(gzip.compress(b"x" * 5000), max_size=4096)

    @pytest.mark.parametrize("kind", sorted(COMPRESSORS))
    def test_bomb_is_stopped_by_ratio(self, kind: str) -> None:
        bomb = COMPRESSORS[kind](bytes(32 * 1024 * 1024))
        with pytest.raises(ArchiveSecurityError, match="ratio"):
            decompress_single(bomb)

    def test_small_highly_compressible_file_is_allowed(self) -> None:
        # 1 MB of one byte compresses about 1000:1, but stays under the 10 MB ratio floor.
        assert len(decompress_single(gzip.compress(bytes(1024 * 1024)))) == 1024 * 1024

    def test_tar_headers(self) -> None:
        assert looks_like_tar(gzip.decompress(tar_bytes())[:512])
        v7 = io.BytesIO()
        with tarfile.open(fileobj=v7, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            info = tarfile.TarInfo("a")
            archive.addfile(info, io.BytesIO(b""))
        header = bytearray(v7.getvalue()[:512])
        header[257:265] = bytes(8)  # strip the ustar magic: an old-style header
        header[148:156] = b"        "
        header[148:155] = f"{sum(header):06o}\x00".encode()
        assert looks_like_tar(bytes(header))
        assert looks_like_tar(bytes(512))
        assert not looks_like_tar(MAN_PAGE.ljust(512, b"\n"))
        assert not looks_like_tar(b"short")

    def test_gzip_original_name(self) -> None:
        assert gzip_original_name(gzip_with_name("dir/ls.1", MAN_PAGE)) == "ls.1"
        assert gzip_original_name(gzip.compress(MAN_PAGE)) is None
        assert gzip_original_name(bz2.compress(MAN_PAGE)) is None


class TestDetection:
    """A compressed file reaches the archive parser, not the parser its inner MIME type names."""

    @pytest.mark.parametrize(
        ("name", "kind"),
        [
            ("notes.md.gz", "gzip"),
            ("page.html.bz2", "bzip2"),
            ("x.json.xz", "xz"),
            ("report.txt.gz", "gzip"),
            ("ls.1.gz", "gzip"),
        ],
    )
    def test_compressed_names_route_to_archive(self, tmp_path: Path, name: str, kind: str) -> None:
        path = tmp_path / name
        path.write_bytes(COMPRESSORS[kind](b"content\n"))
        assert registry.detect_format(str(path)) == "archive"

    def test_uncompressed_names_still_use_mime(self, tmp_path: Path) -> None:
        path = tmp_path / "page.htm"
        path.write_bytes(b"<p>x</p>")
        assert registry.detect_format(str(path)) == "html"


class TestSingleCompressedFile:
    """The archive parser converts a single compressed file as its inner format."""

    @pytest.mark.parametrize(
        ("name", "kind", "content", "expected"),
        [
            ("ls.1.gz", "gzip", MAN_PAGE, "# LS(1)"),
            ("notes.md.gz", "gzip", b"# Title\n\n*hi*\n", "# Title\n\n*hi*"),
            ("data.csv.gz", "gzip", b"a,b\n1,2\n", "| a | b |"),
            ("page.html.bz2", "bzip2", b"<h1>Hello</h1><p>x</p>", "# Hello"),
            # Repetitive, so xz really compresses it (a tiny input is stored verbatim).
            ("x.json.xz", "xz", b'{"words": "' + b"alpha " * 50 + b'"}', '"words"'),
            ("report.txt.gz", "gzip", b"plain words\n", "plain words"),
        ],
    )
    def test_converts_inner_file(self, tmp_path: Path, name: str, kind: str, content: bytes, expected: str) -> None:
        path = tmp_path / name
        path.write_bytes(COMPRESSORS[kind](content))
        assert expected in to_markdown(path)

    def test_bytes_use_the_name_in_the_gzip_header(self) -> None:
        assert "# LS(1)" in to_markdown(gzip_with_name("ls.1", MAN_PAGE))

    def test_unnamed_bytes_are_detected_by_content(self) -> None:
        assert "# LS(1)" in to_markdown(gzip.compress(MAN_PAGE))

    def test_named_stream(self) -> None:
        stream = io.BytesIO(gzip.compress(b"# Heading\n"))
        stream.name = "readme.md.gz"
        assert "# Heading" in to_markdown(stream)

    def test_misnamed_tar_gz_holding_one_file(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.tar.gz"
        path.write_bytes(gzip.compress(b"just text\n"))
        assert "just text" in to_markdown(path)

    @pytest.mark.parametrize("compression", ["gz", "bz2", "xz"])
    def test_real_tarballs_are_unchanged(self, tmp_path: Path, compression: str) -> None:
        path = tmp_path / f"bundle.tar.{compression}"
        path.write_bytes(tar_bytes(compression))
        result = to_markdown(path)
        assert "a.md" in result and "# A" in result

    def test_tarball_with_a_plain_gz_name(self, tmp_path: Path) -> None:
        path = tmp_path / "bundle.gz"
        path.write_bytes(tar_bytes("gz"))
        assert "a.md" in to_markdown(path)

    def test_double_compression_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.md.gz.gz"
        path.write_bytes(gzip.compress(gzip.compress(b"# x\n")))
        with pytest.raises(MalformedFileError, match="compressed twice"):
            to_markdown(path)

    def test_bomb_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "zeros.txt.gz"
        path.write_bytes(gzip.compress(b"a" * (32 * 1024 * 1024)))
        with pytest.raises(ArchiveSecurityError):
            to_markdown(path)
