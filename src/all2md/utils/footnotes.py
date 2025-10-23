"""Utilities for collecting and normalizing footnotes across converters."""

from __future__ import annotations

import itertools
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from all2md.ast import FootnoteDefinition, Node

_SANITIZE_PATTERN = re.compile(r"[^0-9A-Za-z_-]+")


def sanitize_footnote_identifier(identifier: str, *, fallback_prefix: str = "note") -> str:
    """Return a Markdown-safe footnote identifier.

    Parameters
    ----------
    identifier : str
        Raw identifier that may contain disallowed characters.
    fallback_prefix : str, default "note"
        Prefix used when the sanitized identifier would be empty.

    """
    candidate = identifier.strip()
    candidate = _SANITIZE_PATTERN.sub("-", candidate)
    candidate = candidate.strip("-")
    if not candidate:
        candidate = fallback_prefix
    return candidate


@dataclass
class FootnoteCollector:
    """Store footnote references and definitions with stable ordering."""

    auto_number_start: int = 1
    _next_auto_number: itertools.count = field(init=False, repr=False)
    _orders: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list), init=False, repr=False)
    _definitions: Dict[str, Dict[str, List[Node]]] = field(
        default_factory=lambda: defaultdict(dict), init=False, repr=False
    )
    _id_map: Dict[Tuple[str, str], str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the auto-number counter after dataclass initialization."""
        self._next_auto_number = itertools.count(self.auto_number_start)

    def register_reference(self, identifier: Optional[str], *, note_type: str = "footnote") -> str:
        """Record a reference and return the canonical identifier."""
        return self._ensure_identifier(identifier, note_type=note_type)

    def register_definition(
        self,
        identifier: Optional[str],
        content: List[Node],
        *,
        note_type: str = "footnote",
    ) -> str:
        """Record a definition and return the canonical identifier."""
        canonical_id = self._ensure_identifier(identifier, note_type=note_type)
        if content:
            self._definitions[note_type][canonical_id] = content
        return canonical_id

    def iter_definitions(self, *, note_type_priority: Sequence[str] | None = None) -> Iterator[FootnoteDefinition]:
        """Yield collected definitions in priority order."""
        priority = list(note_type_priority or self._orders.keys())
        seen: set[Tuple[str, str]] = set()

        for note_type in priority:
            for identifier in self._orders.get(note_type, []):
                key = (note_type, identifier)
                if key in seen:
                    continue
                seen.add(key)
                content = self._definitions.get(note_type, {}).get(identifier)
                if not content:
                    continue
                metadata = {"note_type": note_type} if note_type else {}
                yield FootnoteDefinition(identifier=identifier, content=content, metadata=metadata)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_identifier(self, identifier: Optional[str], *, note_type: str) -> str:
        raw = "" if identifier is None else str(identifier)
        key = (note_type, raw)
        if key in self._id_map:
            canonical = self._id_map[key]
        else:
            canonical = self._generate_identifier(raw, note_type)
            self._orders.setdefault(note_type, []).append(canonical)
            self._id_map[key] = canonical
        return canonical

    def _generate_identifier(self, raw: str, note_type: str) -> str:
        if raw.strip():
            base = sanitize_footnote_identifier(raw)
        else:
            next_value = next(self._next_auto_number)
            base = f"{note_type}{next_value}" if note_type != "footnote" else str(next_value)

        return self._dedupe_identifier(base, note_type)

    def _dedupe_identifier(self, identifier: str, note_type: str) -> str:
        existing = set(self._orders.get(note_type, []))
        if identifier not in existing:
            return identifier

        suffix = 2
        while f"{identifier}-{suffix}" in existing:
            suffix += 1
        return f"{identifier}-{suffix}"
