#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/chunking/tokenization.py
"""Token counting backends for chunking.

Chunking needs a notion of "token" to bound chunk sizes. Two backends are
provided:

- :class:`TiktokenCounter` — real BPE token counts via ``tiktoken`` (the same
  ``cl100k_base`` encoding used by recent OpenAI models). Required for any
  strategy that must split *on* token boundaries (``token``/``char`` and the
  default ``semantic`` strategy), because those need the encoder's
  ``encode``/``decode`` round-trip, not just a count.
- :class:`WhitespaceCounter` — a dependency-free approximation that counts
  whitespace-delimited runs. This mirrors the approximation used by the search
  subsystem (``all2md.search.chunking``) so count-only strategies behave
  consistently whether or not ``tiktoken`` is installed.

Use :func:`get_counter` to resolve a counter by name with graceful fallback.
"""

from __future__ import annotations

import re
from typing import Optional, Protocol, runtime_checkable

from all2md.constants import DEPS_CHUNK
from all2md.exceptions import DependencyError

_WHITESPACE_RE = re.compile(r"\s+")

#: Strategies that need the encoder's ``encode``/``decode`` round-trip (split on
#: real token boundaries), so the whitespace fallback cannot serve them.
_TIKTOKEN_REQUIRED_STRATEGIES = frozenset({"semantic", "token", "char"})


@runtime_checkable
class TokenCounter(Protocol):
    """Counts tokens in text. Optionally exposes a tiktoken ``encoding``."""

    name: str

    def count(self, text: str) -> int:
        """Return the number of tokens in ``text``."""
        ...


class WhitespaceCounter:
    """Approximate token count by whitespace-delimited runs (no dependency)."""

    name = "whitespace"
    #: No real encoder; strategies needing encode/decode must reject this.
    encoding = None

    def count(self, text: str) -> int:
        """Count whitespace-delimited tokens in ``text``."""
        return len([tok for tok in _WHITESPACE_RE.split(text) if tok])


class TiktokenCounter:
    """Real BPE token counts via ``tiktoken``.

    Exposes the underlying ``encoding`` so token-boundary chunkers can
    ``encode``/``decode``. Counting uses ``encode_ordinary`` to skip the
    special-token scan (pure overhead here, and it would raise on text that
    merely contains a special-token literal).
    """

    name = "tiktoken"

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        """Load the named ``tiktoken`` encoding (raising DependencyError if absent)."""
        try:
            import tiktoken
        except ImportError as exc:  # pragma: no cover - exercised via get_counter
            raise DependencyError(
                converter_name="chunk",
                missing_packages=[(name, spec) for name, _import, spec in DEPS_CHUNK],
                install_command="pip install all2md[chunk]",
                original_import_error=exc,
            ) from exc
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        """Count BPE tokens in ``text`` using ``encode_ordinary``."""
        return len(self.encoding.encode_ordinary(text))


def tiktoken_available() -> bool:
    """Return True when ``tiktoken`` can be imported."""
    try:
        import tiktoken  # noqa: F401
    except ImportError:
        return False
    return True


def get_counter(name: str = "auto", *, strategy: Optional[str] = None) -> TokenCounter:
    """Resolve a token counter by name.

    Parameters
    ----------
    name : {"auto", "tiktoken", "whitespace"}
        ``auto`` prefers ``tiktoken`` and falls back to whitespace counting when
        it is not installed (unless ``strategy`` requires real tokens, in which
        case a :class:`DependencyError` is raised). ``tiktoken`` forces the BPE
        backend (raising if unavailable). ``whitespace`` forces the
        approximation.
    strategy : str, optional
        The chunking strategy the counter is for. Used to decide whether the
        whitespace fallback is acceptable under ``auto``: strategies that split
        on token boundaries (``semantic``/``token``/``char``) cannot use it.

    Returns
    -------
    TokenCounter
        A ready-to-use counter.

    Raises
    ------
    DependencyError
        If ``tiktoken`` is required (explicitly, or implied by ``strategy``) but
        not installed.
    ValueError
        If ``name`` is not a recognized backend.

    """
    needs_real_tokens = strategy in _TIKTOKEN_REQUIRED_STRATEGIES

    if name == "whitespace":
        if needs_real_tokens:
            raise ValueError(
                f"Strategy '{strategy}' splits on real token boundaries and cannot use the "
                "whitespace token counter; use --token-counter tiktoken (pip install all2md[chunk])."
            )
        return WhitespaceCounter()

    if name == "tiktoken":
        return TiktokenCounter()

    if name == "auto":
        if tiktoken_available():
            return TiktokenCounter()
        if needs_real_tokens:
            # Surface a clean dependency error instead of silently degrading a
            # strategy that cannot work without real token boundaries.
            return TiktokenCounter()  # raises DependencyError
        return WhitespaceCounter()

    raise ValueError(f"Unknown token counter: {name!r}. Choose from auto, tiktoken, whitespace.")
