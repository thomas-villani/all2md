#  Copyright (c) 2025 Tom Villani, Ph.D.
# src/all2md/roundtrip.py
"""Round-trip fidelity scoring — how much structure survives a conversion.

Where :mod:`all2md.confidence` asks "how much should I trust this conversion?"
*without* a reference, this module asks a question that *has* one: convert a
document to another format, parse it straight back, and measure what changed.
The source AST is the ground truth; the re-parsed AST is the candidate::

    original --render--> via-format --parse--> round-tripped
       |                                             |
       +--------------- compared -------------------+

That makes the score a genuine regression guard: a clean Markdown document
round-trips through Markdown at exactly ``100``, so any drift is a real defect
rather than measurement noise. It is also the second half of the substrate the
``optimize`` capstone consumes -- :mod:`all2md.confidence` scores conversions
where no reference exists (gnarly PDFs), this module scores the ones where a
reference can be manufactured.

The comparison is deliberately *structural* rather than textual. Two documents
that serialize to different bytes may carry identical structure (Markdown is
happy to write a bullet as ``*`` or ``-``), while two documents with identical
text may have lost every heading. Five dimensions are scored independently and
combined:

* ``structure`` (weight 0.40) -- the block skeleton: heading levels, list
  nesting and ordering, table placement, code blocks, quotes.
* ``text`` (0.30) -- the document-wide word stream, in order.
* ``inline`` (0.15) -- inline formatting: bold, italic, code, links, images.
* ``tables`` (0.10) -- table dimensions and cell text.
* ``references`` (0.05) -- hyperlink and image targets (URLs).

Dimensions absent from the source are dropped and the remaining weights are
renormalized, so a document with no tables is neither rewarded nor punished for
the tables it does not have.

``structure`` and ``text`` are scored against *independent* alignments, and that
separation is load-bearing. An earlier design aligned blocks by shape and then
compared the text of each aligned pair, which meant two paragraphs could pair up
merely because both were paragraphs -- a demoted heading would shift every
subsequent pairing and crater the text score for a document that had not lost a
single word. Scoring the word stream document-wide keeps a structural change
from being punished twice.

Alongside the score, the report lists concrete :class:`StructuralDelta` incidents
("2 headings became paragraphs", "table 1: 4x3 -> 4x2") so a low score is
actionable rather than merely alarming.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from all2md.ast.nodes import (
    Code,
    CodeBlock,
    Document,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Table,
    Text,
    get_node_children,
)
from all2md.confidence import Band, Severity, band_for_score

# Pin the public surface. Without this, autodoc also documents the names this
# module imports -- including ``difflib.SequenceMatcher``, whose docstring is not
# valid reStructuredText and fails the ``-W`` docs build.
__all__ = [
    "DIMENSION_WEIGHTS",
    "TEXT_INTACT_THRESHOLD",
    "TEXT_MANGLED_THRESHOLD",
    "TEXT_SIMILARITY_TOKEN_CAP",
    "RoundTripReport",
    "StructuralDelta",
    "build_report",
    "coalesce_deltas",
    "net_block_deltas",
    "score_roundtrip",
]

# --- Scoring model -----------------------------------------------------------
#
# Weights are exposed as module constants so tests (and the ``optimize`` capstone)
# can reason about them. They are renormalized over the dimensions the source
# document actually exercises -- see ``score_roundtrip``.

#: Relative weight of each fidelity dimension in the composite score.
DIMENSION_WEIGHTS: dict[str, float] = {
    "structure": 0.40,
    "text": 0.30,
    "inline": 0.15,
    "tables": 0.10,
    "references": 0.05,
}

#: Text similarity at or above which the word stream is considered intact.
#: Whitespace normalization can nudge a faithful document a hair under 1.0, so
#: this is not exactly 1.
TEXT_INTACT_THRESHOLD = 0.995

#: Text similarity below which lost words are a ``warn`` rather than an ``info``.
TEXT_MANGLED_THRESHOLD = 0.75

#: Combined word count (original + round-tripped) above which the order-sensitive
#: text comparison is abandoned for an order-insensitive multiset overlap.
#:
#: ``SequenceMatcher`` is quadratic in the worst case, and its worst case is not
#: hypothetical: 10k+10k words drawn from a small vocabulary (an OCR-garbled
#: page, a table of repeated cells) takes seconds, and 20k+20k takes half a
#: minute. Word *order* is already the ``structure`` dimension's concern, so
#: degrading to a bag-of-words overlap above the cap costs little and bounds the
#: runtime of ``all2md roundtrip`` on a large corpus.
TEXT_SIMILARITY_TOKEN_CAP = 20_000

#: Inline node types. Everything else reachable from a Document is a block and
#: contributes to the structural skeleton.
_INLINE_TYPES: frozenset[str] = frozenset(
    {
        "Text",
        "Emphasis",
        "Strong",
        "Code",
        "Link",
        "Image",
        "LineBreak",
        "Strikethrough",
        "Mark",
        "Underline",
        "Superscript",
        "Subscript",
        "HTMLInline",
        "FootnoteReference",
        "MathInline",
        "CommentInline",
    }
)

#: Inline types whose presence is incidental to formatting fidelity. ``Text`` is
#: scored by the ``text`` dimension; a ``LineBreak`` is a rendering artifact that
#: most formats are free to add or drop.
_UNSCORED_INLINE_TYPES: frozenset[str] = frozenset({"Text", "LineBreak"})


@dataclass
class StructuralDelta:
    """A single concrete difference between the original and the round trip.

    Parameters
    ----------
    kind : str
        Machine-readable category (e.g. ``"block_lost"``, ``"block_changed"``,
        ``"inline_lost"``, ``"table_changed"``, ``"reference_lost"``).
    detail : str or None, default = None
        Human-readable qualifier, e.g. ``"heading(h2) -> paragraph"``.
    count : int, default = 1
        How many times this delta occurred. Deltas sharing
        ``(kind, detail, severity)`` are coalesced with their counts summed.
    severity : {"info", "warn", "error"}, default = "warn"
        How serious the difference is. Purely descriptive: the score comes from
        the dimension metrics, not from summing delta penalties.

    """

    kind: str
    detail: str | None = None
    count: int = 1
    severity: Severity = "warn"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict, omitting ``detail`` when unset."""
        data: dict[str, Any] = {"kind": self.kind, "count": self.count, "severity": self.severity}
        if self.detail is not None:
            data["detail"] = self.detail
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuralDelta":
        """Reconstruct a :class:`StructuralDelta` from its :meth:`to_dict` form."""
        return cls(
            kind=str(data.get("kind", "")),
            detail=data.get("detail"),
            count=int(data.get("count", 1)),
            severity=data.get("severity", "warn"),
        )


@dataclass
class RoundTripReport:
    """Structural fidelity of a ``parse -> render(via) -> parse`` round trip.

    Parameters
    ----------
    score : int
        Overall fidelity, ``0`` (nothing survived) to ``100`` (structurally identical).
    band : {"high", "medium", "low"}
        Coarse bucket derived from ``score``, using the same thresholds as
        :class:`~all2md.confidence.ConfidenceReport`.
    source_format : str
        Format the original was parsed from (e.g. ``"docx"``).
    via : str
        Format the document was round-tripped through (e.g. ``"markdown"``).
    metrics : dict
        Per-dimension scores in ``0-100``, keyed by :data:`DIMENSION_WEIGHTS`.
        Dimensions the source does not exercise are omitted entirely.
    deltas : list of StructuralDelta
        Concrete differences found, most severe and most structural first.

    """

    score: int
    band: Band
    source_format: str
    via: str
    metrics: dict[str, int] = field(default_factory=dict)
    deltas: list[StructuralDelta] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict."""
        return {
            "score": self.score,
            "band": self.band,
            "source_format": self.source_format,
            "via": self.via,
            "metrics": dict(self.metrics),
            "deltas": [delta.to_dict() for delta in self.deltas],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoundTripReport":
        """Reconstruct a :class:`RoundTripReport` from its :meth:`to_dict` form."""
        return cls(
            score=int(data.get("score", 0)),
            band=data.get("band", "low"),
            source_format=str(data.get("source_format", "")),
            via=str(data.get("via", "")),
            metrics={str(key): int(value) for key, value in (data.get("metrics") or {}).items()},
            deltas=[StructuralDelta.from_dict(delta) for delta in data.get("deltas", []) or []],
        )


def net_block_deltas(deltas: list[StructuralDelta]) -> list[StructuralDelta]:
    """Cancel ``block_lost`` against ``block_added`` for the same block description.

    Sequence alignment reports a moved block as one deleted and one inserted, so a
    document that merely *gained* a paragraph can be described as having lost one
    too. Netting the pair leaves the honest multiset statement -- "one heading
    became a paragraph" -- and lets block *ordering* be judged by the ``structure``
    score, which is what actually measures it.

    Expects already-coalesced deltas, and drops any whose count nets to zero.
    """
    lost = {delta.detail: delta for delta in deltas if delta.kind == "block_lost"}
    added = {delta.detail: delta for delta in deltas if delta.kind == "block_added"}
    for detail in set(lost) & set(added):
        overlap = min(lost[detail].count, added[detail].count)
        lost[detail].count -= overlap
        added[detail].count -= overlap
    return [delta for delta in deltas if delta.count > 0]


def coalesce_deltas(deltas: list[StructuralDelta]) -> list[StructuralDelta]:
    """Merge deltas sharing ``(kind, detail, severity)``, summing counts.

    Keeps first-seen order, which puts document-order structural findings first.
    """
    merged: dict[tuple[str, str | None, str], StructuralDelta] = {}
    for delta in deltas:
        key = (delta.kind, delta.detail, delta.severity)
        existing = merged.get(key)
        if existing is None:
            merged[key] = StructuralDelta(
                kind=delta.kind, detail=delta.detail, count=delta.count, severity=delta.severity
            )
        else:
            existing.count += delta.count
    return list(merged.values())


# --- Feature extraction ------------------------------------------------------

#: A block's structural signature: its kind plus whatever distinguishes it
#: (heading level, list ordering, table dimensions, code language) and its
#: nesting depth.
Shape = tuple[Any, ...]


def _is_inline(node: Node) -> bool:
    return type(node).__name__ in _INLINE_TYPES


def _own_words(node: Node) -> list[str]:
    """Words from this node's inline content, ignoring nested blocks.

    Descends through inline wrappers (``Strong``, ``Link``, ...) to reach ``Text``
    but stops at any block child, whose words belong to that block instead.
    """
    if isinstance(node, Text):
        return node.content.split()

    words: list[str] = []

    def walk(current: Node) -> None:
        for child in get_node_children(current):
            if isinstance(child, Text):
                words.extend(child.content.split())
            elif _is_inline(child):
                walk(child)

    walk(node)
    return words


#: Leaf nodes whose textual payload is a bare ``content`` string rather than
#: ``Text`` children. ``get_node_children`` returns nothing for them, so a naive
#: ``Text``-only walk never sees their words -- and a round trip that dropped or
#: mangled a code block, a math expression, or a raw HTML span would score a
#: false 100 on the text dimension.
_CONTENT_STRING_TYPES = (CodeBlock, MathBlock, HTMLBlock, Code, MathInline, HTMLInline)


def _payload_words(node: Node) -> list[str]:
    """Words carried by a leaf whose content is a plain string, not ``Text``.

    Covers code, math and raw-HTML payloads (block and inline) and an image's
    alt text. Returns ``[]`` for every other node, so callers can add it
    unconditionally alongside the ordinary ``Text`` walk.
    """
    if isinstance(node, _CONTENT_STRING_TYPES):
        return node.content.split()
    if isinstance(node, Image):
        return (node.alt_text or "").split()
    return []


def _all_words(node: Node) -> list[str]:
    """Words from every ``Text`` descendant, crossing block boundaries.

    Unlike :func:`_own_words` this does not stop at nested blocks, because a
    table cell is free to wrap its content in a paragraph in one format and not
    in another -- and a cell whose text vanished must not read as an empty cell
    faithfully preserved.

    Also folds in :func:`_payload_words`: code, math, raw-HTML and image-alt
    payloads live in a ``str`` attribute with no ``Text`` children, so a
    ``Text``-only walk would let a mangled code block round-trip as a perfect
    score.
    """
    words: list[str] = []

    def walk(current: Node) -> None:
        for child in get_node_children(current):
            if isinstance(child, Text):
                words.extend(child.content.split())
            else:
                words.extend(_payload_words(child))
                walk(child)

    if isinstance(node, Text):
        return node.content.split()
    words.extend(_payload_words(node))
    walk(node)
    return words


def _unwrap(node: Node) -> Node:
    """Collapse a ``Paragraph`` whose sole child is another ``Paragraph``.

    Nested paragraphs are meaningless -- no format represents a paragraph inside
    a paragraph -- so they are always a parser or renderer artifact rather than
    content. Treating the chain as one paragraph keeps the artifact from reading
    as an added block.
    """
    while isinstance(node, Paragraph):
        blocks = [child for child in get_node_children(node) if not _is_inline(child)]
        if len(blocks) == 1 and isinstance(blocks[0], Paragraph) and not _own_words(node):
            node = blocks[0]
        else:
            break
    return node


def _table_dimensions(table: Table) -> tuple[int, int]:
    """Return ``(rows, cols)``, counting the header as a row."""
    rows = ([table.header] if table.header is not None else []) + list(table.rows)
    cols = max((len(row.cells) for row in rows), default=0)
    return len(rows), cols


def _block_shape(node: Node, depth: int) -> Shape:
    """Return the hashable structural signature of a block.

    Depth is included so that a flattened nested list registers as a structural
    change rather than passing as an equivalent flat one.
    """
    if isinstance(node, Heading):
        return ("heading", node.level, depth)
    if isinstance(node, List):
        return ("list", node.ordered, depth)
    if isinstance(node, ListItem):
        return ("listitem", depth)
    if isinstance(node, Table):
        rows, cols = _table_dimensions(node)
        return ("table", rows, cols)
    if isinstance(node, CodeBlock):
        return ("code", node.language or "")
    if isinstance(node, Paragraph):
        return ("paragraph", depth)
    # Remaining blocks (BlockQuote, ThematicBreak, MathBlock, HTMLBlock,
    # DefinitionList, FootnoteDefinition, Comment, ...) are identified by type
    # and nesting alone.
    return (type(node).__name__.lower(), depth)


def _skeleton(doc: Document) -> list[Shape]:
    """Flatten a document into a depth-annotated sequence of block shapes.

    Two normalizations keep format-legal spelling differences from reading as
    structural loss:

    * A ``ListItem`` holding a single ``Paragraph`` is emitted as one block --
      Markdown writes tight lists without the wrapping paragraph and HTML writes
      loose ones with it, and neither has lost anything. A chain of singly-nested
      paragraphs collapses the same way (see :func:`_unwrap`).
    * ``TableRow`` / ``TableCell`` are not emitted; the ``Table`` shape already
      carries its dimensions and the ``tables`` dimension scores cell text.
    """
    shapes: list[Shape] = []

    def walk(node: Node, depth: int) -> None:
        for raw_child in get_node_children(node):
            if _is_inline(raw_child):
                continue
            child = _unwrap(raw_child)
            if isinstance(child, Table):
                shapes.append(_block_shape(child, depth))
                continue  # do not descend: rows and cells are folded into the shape
            if isinstance(child, ListItem):
                shapes.append(("listitem", depth))
                inner = [_unwrap(c) for c in get_node_children(child) if not _is_inline(c)]
                if len(inner) == 1 and isinstance(inner[0], Paragraph):
                    continue  # tight/loose equivalence: the lone paragraph is the item
                walk(child, depth + 1)
                continue
            shapes.append(_block_shape(child, depth))
            walk(child, depth + 1)

    walk(doc, 0)
    return shapes


def _tables(doc: Document) -> list[tuple[int, int, list[str]]]:
    """Every table as ``(rows, cols, cell_words)`` in document order."""
    found: list[tuple[int, int, list[str]]] = []

    def walk(node: Node) -> None:
        for child in get_node_children(node):
            if isinstance(child, Table):
                rows, cols = _table_dimensions(child)
                found.append((rows, cols, _all_words(child)))
                continue
            walk(child)

    walk(doc)
    return found


def _inline_counts(doc: Document) -> Counter[str]:
    """Multiset of scored inline node types across the whole document."""
    counts: Counter[str] = Counter()

    def walk(node: Node) -> None:
        for child in get_node_children(node):
            name = type(child).__name__
            if name in _INLINE_TYPES and name not in _UNSCORED_INLINE_TYPES:
                counts[name] += 1
            walk(child)

    walk(doc)
    return counts


def _references(doc: Document) -> Counter[str]:
    """Multiset of hyperlink and image targets."""
    refs: Counter[str] = Counter()

    def walk(node: Node) -> None:
        for child in get_node_children(node):
            if isinstance(child, (Link, Image)):
                url = (getattr(child, "url", "") or "").strip()
                if url:
                    refs[url] += 1
            walk(child)

    walk(doc)
    return refs


# --- Similarity primitives ---------------------------------------------------


def _bag_similarity(left: Counter[str], right: Counter[str]) -> float:
    """Multiset overlap in ``[0, 1]`` (Bray-Curtis), ``1.0`` when both are empty."""
    total = sum(left.values()) + sum(right.values())
    if total == 0:
        return 1.0
    overlap = sum((left & right).values())
    return 2.0 * overlap / total


def _sequence_similarity(left: list[Any], right: list[Any]) -> float:
    """Order-sensitive similarity in ``[0, 1]``, ``1.0`` when both are empty.

    ``autojunk`` is disabled: its heuristic treats any element appearing in more
    than 1% of a 200+ element sequence as noise, which would silently discard the
    most common block shape (``paragraph``) in exactly the long documents whose
    structure we most want to check.
    """
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def _word_similarity(left: list[str], right: list[str]) -> float:
    """Similarity of two word streams, order-sensitive below the token cap.

    Above :data:`TEXT_SIMILARITY_TOKEN_CAP` combined words this degrades to an
    order-insensitive multiset overlap to bound the quadratic worst case.
    """
    if len(left) + len(right) > TEXT_SIMILARITY_TOKEN_CAP:
        return _bag_similarity(Counter(left), Counter(right))
    return _sequence_similarity(left, right)


def _table_similarity(left: tuple[int, int, list[str]], right: tuple[int, int, list[str]]) -> float:
    """Similarity of two tables: half their dimensions, half their cell text."""
    rows_sim = min(left[0], right[0]) / max(left[0], right[0]) if max(left[0], right[0]) else 1.0
    cols_sim = min(left[1], right[1]) / max(left[1], right[1]) if max(left[1], right[1]) else 1.0
    return 0.5 * (rows_sim * cols_sim) + 0.5 * _word_similarity(left[2], right[2])


def _describe(shape: Shape) -> str:
    """Render a block shape as a compact human-readable label."""
    kind = str(shape[0])
    if kind == "heading":
        return f"heading(h{shape[1]})"
    if kind == "list":
        return "ordered list" if shape[1] else "bullet list"
    if kind == "table":
        return f"table({shape[1]}x{shape[2]})"
    if kind == "code":
        return f"code({shape[1]})" if shape[1] else "code"
    return kind


# --- Dimension scoring -------------------------------------------------------


def _score_structure(original: list[Shape], roundtripped: list[Shape], deltas: list[StructuralDelta]) -> float:
    """Score the block skeleton and record which blocks were lost or reshaped."""
    matcher = SequenceMatcher(None, original, roundtripped, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            # Pair positionally as far as both runs go: the shapes differ, but it
            # is almost certainly the same content, reshaped.
            paired = min(i2 - i1, j2 - j1)
            for offset in range(paired):
                deltas.append(
                    StructuralDelta(
                        "block_changed",
                        f"{_describe(original[i1 + offset])} -> {_describe(roundtripped[j1 + offset])}",
                        severity="warn",
                    )
                )
            for offset in range(paired, i2 - i1):
                deltas.append(StructuralDelta("block_lost", _describe(original[i1 + offset]), severity="warn"))
            for offset in range(paired, j2 - j1):
                deltas.append(StructuralDelta("block_added", _describe(roundtripped[j1 + offset]), severity="info"))
        elif tag == "delete":
            for offset in range(i2 - i1):
                deltas.append(StructuralDelta("block_lost", _describe(original[i1 + offset]), severity="warn"))
        elif tag == "insert":
            for offset in range(j2 - j1):
                deltas.append(StructuralDelta("block_added", _describe(roundtripped[j1 + offset]), severity="info"))

    return _sequence_similarity(original, roundtripped)


def _score_text(original: list[str], roundtripped: list[str], deltas: list[StructuralDelta]) -> float:
    """Score the document-wide word stream and report how many words went missing."""
    similarity = _word_similarity(original, roundtripped)
    missing = sum((Counter(original) - Counter(roundtripped)).values())
    if missing:
        deltas.append(
            StructuralDelta(
                "text_lost",
                f"{missing:,} of {len(original):,} words",
                severity="warn" if similarity < TEXT_MANGLED_THRESHOLD else "info",
            )
        )
    elif similarity < TEXT_INTACT_THRESHOLD:
        # Every original word survived, so the shortfall is words the round trip
        # invented (a rendered caption, a footnote marker) or words it moved.
        added = sum((Counter(roundtripped) - Counter(original)).values())
        if added:
            deltas.append(StructuralDelta("text_added", f"{added:,} words", severity="info"))
        else:
            deltas.append(StructuralDelta("text_reordered", severity="info"))
    return similarity


def _score_inline(original: Counter[str], roundtripped: Counter[str], deltas: list[StructuralDelta]) -> float:
    """Score inline-formatting preservation and record what went missing."""
    for name, count in original.items():
        lost = count - roundtripped.get(name, 0)
        if lost > 0:
            deltas.append(StructuralDelta("inline_lost", name.lower(), count=lost, severity="warn"))
    return _bag_similarity(original, roundtripped)


def _score_tables(
    original: list[tuple[int, int, list[str]]],
    roundtripped: list[tuple[int, int, list[str]]],
    deltas: list[StructuralDelta],
) -> float:
    """Score table preservation pairwise in document order."""
    if not original:
        return 1.0
    total = 0.0
    for index, table_a in enumerate(original):
        if index >= len(roundtripped):
            deltas.append(
                StructuralDelta("table_lost", f"table {index + 1} ({table_a[0]}x{table_a[1]})", severity="error")
            )
            continue
        table_b = roundtripped[index]
        if (table_a[0], table_a[1]) != (table_b[0], table_b[1]):
            deltas.append(
                StructuralDelta(
                    "table_changed",
                    f"table {index + 1}: {table_a[0]}x{table_a[1]} -> {table_b[0]}x{table_b[1]}",
                    severity="warn",
                )
            )
        total += _table_similarity(table_a, table_b)
    return total / len(original)


def _score_references(original: Counter[str], roundtripped: Counter[str], deltas: list[StructuralDelta]) -> float:
    """Score hyperlink/image target preservation."""
    for url, count in original.items():
        lost = count - roundtripped.get(url, 0)
        if lost > 0:
            deltas.append(StructuralDelta("reference_lost", url, count=lost, severity="warn"))
    return _bag_similarity(original, roundtripped)


# --- Public entry point ------------------------------------------------------

_KIND_RANK: dict[str, int] = {
    "table_lost": 0,
    "block_lost": 1,
    "block_changed": 2,
    "table_changed": 3,
    "text_lost": 4,
    "inline_lost": 5,
    "reference_lost": 6,
    "text_reordered": 7,
    "text_added": 8,
    "block_added": 9,
}
_SEVERITY_RANK: dict[str, int] = {"error": 0, "warn": 1, "info": 2}


def _rank(delta: StructuralDelta) -> tuple[int, int]:
    """Sort key putting the most severe, most structural findings first."""
    return (_SEVERITY_RANK.get(delta.severity, 1), _KIND_RANK.get(delta.kind, 9))


def score_roundtrip(original: Document, roundtripped: Document) -> tuple[int, dict[str, int], list[StructuralDelta]]:
    """Compare two ASTs and return ``(score, per-dimension metrics, deltas)``.

    Only the dimensions the *original* actually exercises are scored; their
    weights are renormalized to sum to 1. A document with no tables therefore
    neither gains nor loses points for its (absent) tables, and an empty document
    scores a vacuous ``100``.

    Parameters
    ----------
    original : Document
        The ground-truth AST, parsed from the source document.
    roundtripped : Document
        The AST re-parsed after rendering ``original`` to the intermediate format.

    Returns
    -------
    tuple of (int, dict, list)
        The ``0-100`` score, the per-dimension ``0-100`` metrics, and the
        coalesced, severity-ranked structural deltas.

    """
    deltas: list[StructuralDelta] = []

    shapes_a, shapes_b = _skeleton(original), _skeleton(roundtripped)
    words_a, words_b = _all_words(original), _all_words(roundtripped)
    inline_a, inline_b = _inline_counts(original), _inline_counts(roundtripped)
    tables_a, tables_b = _tables(original), _tables(roundtripped)
    refs_a, refs_b = _references(original), _references(roundtripped)

    raw = {
        "structure": _score_structure(shapes_a, shapes_b, deltas),
        "text": _score_text(words_a, words_b, deltas),
        "inline": _score_inline(inline_a, inline_b, deltas),
        "tables": _score_tables(tables_a, tables_b, deltas),
        "references": _score_references(refs_a, refs_b, deltas),
    }
    # A dimension is "exercised" only if the source has something to lose there.
    present = {
        "structure": bool(shapes_a),
        "text": bool(words_a),
        "inline": bool(inline_a),
        "tables": bool(tables_a),
        "references": bool(refs_a),
    }

    active = {name: value for name, value in raw.items() if present[name]}
    if not active:
        return 100, {}, []

    total_weight = sum(DIMENSION_WEIGHTS[name] for name in active)
    composite = sum(DIMENSION_WEIGHTS[name] * value for name, value in active.items()) / total_weight
    score = int(round(max(0.0, min(1.0, composite)) * 100))

    metrics = {name: int(round(value * 100)) for name, value in active.items()}
    ranked = sorted(net_block_deltas(coalesce_deltas(deltas)), key=_rank)
    return score, metrics, ranked


def build_report(original: Document, roundtripped: Document, *, source_format: str, via: str) -> RoundTripReport:
    """Assemble a scored :class:`RoundTripReport` from two ASTs."""
    score, metrics, deltas = score_roundtrip(original, roundtripped)
    return RoundTripReport(
        score=score,
        band=band_for_score(score),
        source_format=source_format,
        via=via,
        metrics=metrics,
        deltas=deltas,
    )
