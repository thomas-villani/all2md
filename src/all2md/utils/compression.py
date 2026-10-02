#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/compression.py
"""Bounded decompression of single gzip, bzip2 and xz streams.

A ``.gz``, ``.bz2`` or ``.xz`` file is either a compressed tar archive or one
compressed file (``ls.1.gz``, ``data.csv.gz``). The helpers here tell the two
apart from the first decompressed tar block, and decompress a single file with
the same size limits the archive validators apply, so a small input cannot
expand without bound.

"""

from __future__ import annotations

import bz2
import lzma
import zlib
from typing import Literal

from all2md.constants import DEFAULT_MAX_COMPRESSION_RATIO, DEFAULT_MAX_UNCOMPRESSED_SIZE
from all2md.exceptions import ArchiveSecurityError, MalformedFileError

CompressionKind = Literal["gzip", "bzip2", "xz"]

TAR_BLOCK_SIZE = 512
_CHUNK_SIZE = 1024 * 1024
# The ratio limit applies only once the output is this large: a small text file
# can legitimately compress 200:1, and a bomb is defined by what it expands to.
_RATIO_CHECK_FLOOR = 10 * 1024 * 1024

_SIGNATURES: tuple[tuple[bytes, CompressionKind], ...] = (
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
)

_GZIP_FEXTRA = 0x04
_GZIP_FNAME = 0x08


def compression_kind(data: bytes) -> CompressionKind | None:
    """Return the compression a byte string starts with, or None.

    Parameters
    ----------
    data : bytes
        The start of the input.

    Returns
    -------
    {"gzip", "bzip2", "xz"} or None
        The compression format.

    """
    for signature, kind in _SIGNATURES:
        if data.startswith(signature):
            return kind
    return None


def _decompress_member(kind: CompressionKind, data: bytes, limit: int) -> tuple[bytes, bytes, bool]:
    """Decompress one member of a stream, stopping once ``limit`` bytes are out.

    Returns
    -------
    tuple[bytes, bytes, bool]
        The output, the input after this member, and whether the member ended.

    """
    out = bytearray()
    try:
        if kind == "gzip":
            gz = zlib.decompressobj(16 + zlib.MAX_WBITS)
            pending = data
            while not gz.eof and len(out) < limit:
                piece = gz.decompress(pending, min(_CHUNK_SIZE, limit - len(out)))
                pending = gz.unconsumed_tail
                out += piece
                if not piece and not pending:
                    break  # input used up and nothing buffered: the stream is cut short
            return bytes(out), gz.unused_data, gz.eof
        other = bz2.BZ2Decompressor() if kind == "bzip2" else lzma.LZMADecompressor()
        out += other.decompress(data, max_length=min(_CHUNK_SIZE, limit))
        while not other.eof and not other.needs_input and len(out) < limit:
            out += other.decompress(b"", max_length=min(_CHUNK_SIZE, limit - len(out)))
        return bytes(out), other.unused_data, other.eof
    except (zlib.error, OSError, EOFError, lzma.LZMAError) as error:
        raise MalformedFileError(f"Invalid {kind} data: {error}") from error


def decompressed_prefix(data: bytes, size: int = TAR_BLOCK_SIZE) -> bytes | None:
    """Return the first ``size`` decompressed bytes, or None if they cannot be read.

    Parameters
    ----------
    data : bytes
        The compressed input (its start is enough).
    size : int, default 512
        How many decompressed bytes to return.

    Returns
    -------
    bytes or None
        Up to ``size`` bytes, or None for input that is not compressed or is corrupt.

    """
    kind = compression_kind(data)
    if kind is None:
        return None
    try:
        out, _rest, _ended = _decompress_member(kind, data, size)
    except MalformedFileError:
        return None
    return out[:size]


def looks_like_tar(block: bytes) -> bool:
    """Return True when ``block`` is the first header block of a tar archive.

    The POSIX ``ustar`` magic is accepted, and so is an old-style (v7) header
    whose checksum adds up, which is how ``tarfile`` itself recognizes one. An
    all-zero block is an empty archive.

    Parameters
    ----------
    block : bytes
        The first 512 decompressed bytes.

    Returns
    -------
    bool
        True if the block is a tar header.

    """
    if len(block) < TAR_BLOCK_SIZE:
        return False
    block = block[:TAR_BLOCK_SIZE]
    if block[257:262] == b"ustar" or block == bytes(TAR_BLOCK_SIZE):
        return True
    field = block[148:156].replace(b"\x00", b" ").strip()
    try:
        stored = int(field, 8)
    except ValueError:
        return False
    unsigned = sum(block[:148]) + 8 * 0x20 + sum(block[156:])
    return stored == unsigned


def decompress_single(
    data: bytes,
    *,
    max_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> bytes:
    """Decompress a whole gzip, bzip2 or xz stream within size limits.

    Concatenated members (``cat a.gz b.gz``) are joined, as ``gzip -d`` does;
    zero padding after the last member is ignored.

    Parameters
    ----------
    data : bytes
        The compressed input.
    max_size : int
        Largest decompressed size allowed.
    max_ratio : float
        Largest decompressed/compressed ratio allowed once the output passes 10 MB.

    Returns
    -------
    bytes
        The decompressed content.

    Raises
    ------
    ArchiveSecurityError
        If the output would exceed ``max_size`` or the ratio limit.
    MalformedFileError
        If the input is not compressed, or is truncated or corrupt.

    """
    kind = compression_kind(data)
    if kind is None:
        raise MalformedFileError("Input is not gzip, bzip2 or xz compressed")
    out = bytearray()
    remaining = data
    while remaining:
        piece, rest, ended = _decompress_member(kind, remaining, max_size + 1 - len(out))
        out += piece
        if len(out) > max_size:
            raise ArchiveSecurityError(
                f"Compressed file expands beyond {max_size / (1024 * 1024):.1f}MB; refusing to decompress it"
            )
        ratio = len(out) / len(data)
        if len(out) > _RATIO_CHECK_FLOOR and ratio > max_ratio:
            raise ArchiveSecurityError(f"Compressed file has a suspicious compression ratio: {ratio:.1f}:1")
        if not ended:
            raise MalformedFileError(f"Truncated {kind} data: the stream ends before its last member does")
        remaining = rest if compression_kind(rest) == kind else b""
        if rest and not remaining and rest.strip(b"\x00"):
            raise MalformedFileError(f"Unexpected data after the end of the {kind} stream")
    return bytes(out)


def gzip_original_name(data: bytes) -> str | None:
    """Return the file name a gzip header stores (``gzip`` writes it by default).

    Parameters
    ----------
    data : bytes
        The gzip input (its start is enough).

    Returns
    -------
    str or None
        The stored name, or None when the header has none.

    """
    if len(data) < 10 or not data.startswith(b"\x1f\x8b") or not data[3] & _GZIP_FNAME:
        return None
    pos = 10
    if data[3] & _GZIP_FEXTRA:
        if len(data) < pos + 2:
            return None
        pos += 2 + int.from_bytes(data[pos : pos + 2], "little")
    end = data.find(b"\x00", pos)
    if end == -1:
        return None
    name = data[pos:end].decode("latin-1").replace("\\", "/").rsplit("/", 1)[-1]
    return name or None
