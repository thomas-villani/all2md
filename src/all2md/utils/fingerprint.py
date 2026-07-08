"""Content/identity fingerprinting for cache invalidation.

A small, dependency-free primitive shared by any subsystem that persists an
artifact derived from a set of input files and wants to reuse it *only* while
those inputs are unchanged. Today it guards the persistent search index
(:mod:`all2md.search.service`); the same digest is intended to key the broader
conversion cache (converted ASTs/output reused by ``view``/``serve`` and the
conversion optimizer).

The default signature is ``(size, mtime_ns)`` — an ``os.stat`` with no read —
because the decision "may I reuse this artifact?" must be cheap on the hot path
(the whole point is to avoid re-reading/re-parsing the corpus). ``content_hash``
is available for callers that need robustness against mtime-preserving copies
and can afford to read the bytes.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

__all__ = ["file_signature", "bytes_signature", "corpus_fingerprint"]

_HASH_READ_CHUNK = 1 << 20  # 1 MiB


def _hash_file(path: Path, *, chunk_size: int = _HASH_READ_CHUNK) -> str:
    """Return the hex SHA-256 of a file's bytes, read in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def file_signature(path: str | Path, *, content_hash: bool = False) -> dict[str, object]:
    """Return a change-signature for a single file.

    Parameters
    ----------
    path : str | Path
        File to signature. Resolved to an absolute path so the identity is
        stable regardless of the working directory.
    content_hash : bool, default False
        When True, also hash the file bytes (SHA-256). Robust against
        mtime-preserving copies at the cost of a full read. When False, only
        ``(size, mtime_ns)`` is captured — an O(1) stat that still changes
        whenever the file is rewritten.

    Returns
    -------
    dict[str, object]
        JSON-serializable signature (``path``, ``size``, ``mtime_ns`` and,
        optionally, ``sha256``).

    Raises
    ------
    OSError
        If the file cannot be stat-ed (missing, permission denied, ...).

    """
    resolved = Path(path).resolve()
    stat = resolved.stat()
    signature: dict[str, object] = {
        "path": str(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if content_hash:
        signature["sha256"] = _hash_file(resolved)
    return signature


def bytes_signature(data: bytes) -> dict[str, object]:
    """Return a content signature for an in-memory bytes source (e.g. stdin)."""
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _normalize_extra(mapping: Mapping[str, object]) -> dict[str, object]:
    """Coerce a parameter mapping into a deterministic, JSON-safe dict."""
    normalized: dict[str, object] = {}
    for key, value in mapping.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


def corpus_fingerprint(
    sources: Iterable[str | Path | bytes],
    *,
    extra: Mapping[str, object] | None = None,
    content_hash: bool = False,
) -> str:
    """Return a stable hex digest over a set of sources plus parameters.

    The digest is **order-independent** (entries are sorted before hashing), so
    the same set of documents supplied in a different order reuses a cached
    artifact. Missing / unstat-able files contribute a sentinel entry so their
    disappearance still changes the digest (a removed file must invalidate).

    Parameters
    ----------
    sources : Iterable[str | Path | bytes]
        The input documents the artifact was built from. ``bytes`` sources are
        always content-hashed; path sources use :func:`file_signature`.
    extra : Mapping[str, object] | None
        Parameters that affect the derived artifact (e.g. chunking / scoring
        options). Included in the digest so a settings change invalidates too.
    content_hash : bool, default False
        Forwarded to :func:`file_signature` for path sources.

    Returns
    -------
    str
        Hex SHA-256 digest of the normalized ``(entries, extra)`` payload.

    """
    entries: list[dict[str, object]] = []
    for source in sources:
        if isinstance(source, (bytes, bytearray)):
            entries.append(bytes_signature(bytes(source)))
            continue
        try:
            entries.append(file_signature(source, content_hash=content_hash))
        except OSError:
            entries.append({"path": str(source), "missing": True})

    # Sort by a canonical rendering so ordering of ``sources`` is irrelevant.
    entries.sort(key=lambda entry: json.dumps(entry, sort_keys=True))

    payload = {"entries": entries, "extra": _normalize_extra(extra or {})}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
