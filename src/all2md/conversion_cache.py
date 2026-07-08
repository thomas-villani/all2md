"""Opt-in persistent conversion cache.

Stashes parsed ASTs on disk so repeated conversions of an unchanged file can
skip the expensive parse step. Shared by the CLI conversion commands (grep,
search, chunk, view, serve) whenever caching is enabled.

The cache is **opt-in**: nothing is read or written unless a caller activates it
(the CLI ``--cache`` flag, or ``ALL2MD_CACHE=1``). Entries are keyed by a
fingerprint over the source file (path + size + mtime), the resolved format and
parser options, and the all2md version + AST schema — so a changed file, changed
options, or a version bump all miss cleanly rather than serving a stale AST.

Activation is process-scoped via a context manager, so the many call sites that
funnel through :func:`all2md.to_ast` need no per-call plumbing::

    with use_conversion_cache(enabled=True):   # or honor ALL2MD_CACHE
        ...                                    # to_ast() transparently caches

A module-global (not a ``ContextVar``) holds the active cache so it is visible
from ``all2md serve``'s per-request worker threads, which a context variable set
on the main thread would not reach.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from all2md.utils.fingerprint import corpus_fingerprint

if TYPE_CHECKING:
    from all2md.ast.nodes import Document

logger = logging.getLogger(__name__)

_ENV_ENABLE = "ALL2MD_CACHE"
_ENV_DIR = "ALL2MD_CACHE_DIR"
_APP_NAME = "all2md"

# AST serialization schema the cache stores; bump-invalidation is handled by
# folding the all2md version into every key, but this is an extra guard.
_AST_SCHEMA = 1

__all__ = [
    "ConversionCache",
    "default_cache_dir",
    "use_conversion_cache",
    "get_active_cache",
    "cache_enabled_by_env",
    "make_cache_key",
]


def default_cache_dir() -> Path:
    """Return the conversion-cache directory.

    Honors ``ALL2MD_CACHE_DIR`` when set; otherwise uses the per-OS user cache
    directory (via ``platformdirs``) with a ``conversions`` subdirectory — e.g.
    ``~/.cache/all2md/conversions`` on Linux, or the ``all2md/Cache/conversions``
    folder under ``%LOCALAPPDATA%`` on Windows.
    """
    override = os.environ.get(_ENV_DIR)
    if override:
        return Path(override).expanduser()
    import platformdirs

    return Path(platformdirs.user_cache_dir(_APP_NAME, appauthor=False)) / "conversions"


def cache_enabled_by_env() -> bool:
    """Return True if ``ALL2MD_CACHE`` requests caching (1/true/yes/on)."""
    return os.environ.get(_ENV_ENABLE, "").strip().lower() in {"1", "true", "yes", "on"}


def make_cache_key(source_path: str, *, source_format: str, options_repr: str) -> str:
    """Build the cache key for a parsed AST.

    Combines the file's change-signature (via :func:`corpus_fingerprint`) with
    everything else that affects the parse: the resolved format, a stable repr of
    the resolved parser options, the all2md version, and the AST schema version.
    """
    from all2md import __version__

    return corpus_fingerprint(
        [source_path],
        extra={
            "format": source_format,
            "options": options_repr,
            "all2md_version": __version__,
            "ast_schema": _AST_SCHEMA,
        },
    )


class ConversionCache:
    """Directory-backed store of parsed ASTs, serialized as AST-JSON.

    All I/O is best-effort: a corrupt or unreadable entry is treated as a miss,
    and a failed write is swallowed — caching must never break a conversion.
    """

    def __init__(self, directory: Path) -> None:
        """Create a cache rooted at ``directory`` (created lazily on first write)."""
        self.directory = Path(directory)

    def _entry_path(self, key: str) -> Path:
        # Shard by the first two hex chars to avoid one enormous flat directory.
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> "Document | None":
        """Return the cached ``Document`` for ``key``, or None on any miss/error."""
        path = self._entry_path(key)
        if not path.exists():
            return None
        try:
            from all2md.ast.nodes import Document
            from all2md.ast.serialization import json_to_ast

            node = json_to_ast(path.read_text(encoding="utf-8"))
        except Exception as exc:  # corrupt / schema-incompatible entry → treat as miss
            logger.debug("Conversion cache: ignoring unreadable entry %s: %s", path, exc)
            return None
        if not isinstance(node, Document):
            return None
        return node

    def put(self, key: str, document: "Document") -> None:
        """Store ``document`` under ``key`` (best-effort; never raises)."""
        from all2md.ast.serialization import ast_to_json

        path = self._entry_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write to a temp sibling then atomically replace, so a crash mid-write
            # can't leave a truncated entry that later reads as corrupt.
            tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            tmp.write_text(ast_to_json(document), encoding="utf-8")
            os.replace(tmp, path)
        except Exception as exc:  # a cache write must never break the conversion
            logger.debug("Conversion cache: failed to store entry %s: %s", path, exc)


# Process-global active cache (see module docstring for why not a ContextVar).
_active_cache: "ConversionCache | None" = None


def get_active_cache() -> "ConversionCache | None":
    """Return the currently active conversion cache, or None if disabled."""
    return _active_cache


@contextmanager
def use_conversion_cache(
    *, enabled: bool | None = None, cache_dir: str | Path | None = None
) -> Iterator["ConversionCache | None"]:
    """Activate the conversion cache for the duration of the ``with`` block.

    Parameters
    ----------
    enabled : bool | None
        Force caching on (True) or off (False). When None, falls back to the
        ``ALL2MD_CACHE`` environment variable. This lets a per-command
        ``--cache`` flag force-enable while the env var provides a global default.
    cache_dir : str | Path | None
        Override the cache directory; otherwise ``ALL2MD_CACHE_DIR`` or the
        per-OS default (:func:`default_cache_dir`) is used.

    Yields
    ------
    ConversionCache | None
        The active cache, or None when caching is disabled.

    """
    global _active_cache
    if enabled is None:
        enabled = cache_enabled_by_env()
    if not enabled:
        yield None
        return

    directory = Path(cache_dir).expanduser() if cache_dir else default_cache_dir()
    cache = ConversionCache(directory)
    previous = _active_cache
    _active_cache = cache
    try:
        yield cache
    finally:
        _active_cache = previous
