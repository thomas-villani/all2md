#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/optimize.py
"""Auto-tune converter options against a reference-free fidelity objective.

Difficult documents — the scanned PDF, the three-column report, the table with no
ruling lines — rarely come with a reference to diff against, so the settings that
convert them well cannot be found by comparing to a known-good output. This module
searches the option space directly and ranks candidates by how much *well-formed*
structure each one recovers.

Why not reuse an existing score
-------------------------------
Neither shipped score works as a search objective:

* :mod:`all2md.confidence` is a saturating *breakage detector*
  (``100 - text_density - ocr_reliance - degraded_events``). It answers "can I
  trust this conversion?", and on any document that is not visibly broken it pins
  to ``100`` regardless of the settings used. Measured across 16 option
  combinations on a two-column fixture it produced **one** distinct score while
  the parsed AST produced **four** distinct outcomes: no gradient to climb.
* :mod:`all2md.roundtrip` needs a ground truth. It manufactures one by re-parsing
  rendered output, which measures the *renderer*, not the parser — a garbled table
  round-trips through Markdown perfectly. It is the right objective for tuning
  renderer options and the wrong one for tuning a PDF parser.

So the objective here is computed from the parsed AST, which is where the gradient
actually lives. The confidence report is still used, but for its *penalties* — the
degraded-content incidents it records are a genuine signal that a conversion broke.

The over-detection trap
-----------------------
"More structure is better" is the obvious objective and it is wrong twice over.

**It rewards keeping the boilerplate.** Leaving a running header and page footer in
yields strictly more text than trimming them, so a naive text-volume objective
prefers the worse conversion. Measured against a fixture whose correct parse is
known, that objective was *anti*-correlated with the truth (Pearson r = -0.88): it
picked the worst candidate nearly every time. Text is therefore scored over body
content only, with repeated furniture excluded — see :func:`_boilerplate_words`,
and note that block-level deduplication is *not* sufficient, because the parser
frequently glues a footer into an adjacent body block where no block comparison can
ever see it.

**It rewards an over-eager table detector**, because any junk region promoted to a
table adds cells. Tables are therefore scored on **well-formedness** — cell fill
density and column regularity — not on count. A hallucinated table is sparse and
ragged, and scores near zero.

With furniture excluded, a trimmed and an untrimmed conversion *tie* on text, which
frees the ``cleanliness`` dimension to break the tie in favour of the one that
actually removed it. On the same fixture that took the objective from r = -0.88 to
r = +1.00.

Fitness is *relative to the candidate pool*, not absolute: the best text recovery
observed across the candidates stands in for the reference we do not have. This is
deliberate. The job is to *rank* candidates, and inventing an absolute 0-100 quality
number would both duplicate :mod:`all2md.confidence` and imply a precision these
signals do not support.

"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from all2md.ast.nodes import Document, Heading, Link, ListItem, Node, Table, Text, get_node_children

# Pin the public surface. Without this, autodoc also documents the names this
# module imports, and their docstrings are not valid reStructuredText.
__all__ = [
    "BOILERPLATE_NGRAM",
    "DIMENSION_WEIGHTS",
    "KNOBS",
    "Candidate",
    "DocumentMetrics",
    "OptimizationReport",
    "extract_metrics",
    "score_candidates",
    "search",
    "tunable_knobs",
]

logger = logging.getLogger(__name__)

#: How the fitness dimensions are combined. Dimensions the candidate pool does not
#: exercise (no candidate found a table) are dropped and the rest renormalized, so a
#: table-free document is neither rewarded nor punished for the tables it lacks.
DIMENSION_WEIGHTS: dict[str, float] = {
    "text": 0.45,
    "tables": 0.25,
    "structure": 0.15,
    "cleanliness": 0.15,
}

#: The option values worth searching, per format. Deliberately curated rather than
#: derived from the dataclass fields: most options are irrelevant to fidelity
#: (``password``), or are a security posture that an optimizer has no business
#: flipping (``strip_dangerous_elements``), or would explode the search space for no
#: gain. Only knobs that plausibly change *what structure is recovered* belong here.
KNOBS: dict[str, dict[str, list[Any]]] = {
    "pdf": {
        "table_detection_mode": ["pymupdf", "ruling", "both", "none"],
        "detect_columns": [True, False],
        "column_detection_mode": ["auto", "force_single", "force_multi"],
        "enable_table_fallback_detection": [True, False],
        "table_fallback_extraction_mode": ["none", "grid", "text_clustering"],
        "detect_merged_cells": [True, False],
        "trim_headers_footers": [True, False],
        "auto_trim_headers_footers": [True, False],
        "dedup_running_headings": [True, False],
        "merge_hyphenated_words": [True, False],
        "consolidate_inline_formatting": [True, False],
    },
    "html": {
        "extract_readable": [True, False],
        "detect_table_alignment": [True, False],
        "collapse_whitespace": [True, False],
        "figures_parsing": ["figure", "image", "skip"],
        "details_parsing": ["details", "content", "skip"],
        "extract_microdata": [True, False],
    },
    "docx": {
        "preserve_tables": [True, False],
        "include_footnotes": [True, False],
        "include_endnotes": [True, False],
        "include_comments": [True, False],
        "include_image_captions": [True, False],
    },
}


@dataclass
class DocumentMetrics:
    """The reference-free structural yield of one conversion.

    Everything here is read off the parsed AST, except ``breakage``, which comes
    from the confidence report's degraded-content incidents.
    """

    blocks: int = 0
    #: Words in the document, counting every block.
    words: int = 0
    #: Words belonging to repeated furniture (running headers, page footers), whether
    #: they sit in their own block or were glued into a body block.
    boilerplate_words: int = 0
    #: ``words`` minus the furniture: the body content actually recovered. This, not
    #: ``words``, is what the text dimension scores.
    unique_words: int = 0
    #: Blocks whose text is entirely a repeat of another block.
    duplicate_blocks: int = 0
    headings: int = 0
    list_items: int = 0
    links: int = 0
    tables: int = 0
    table_cells: int = 0
    #: Fraction of table cells that are non-empty. A hallucinated table is sparse.
    table_fill: float = 0.0
    #: Fraction of table rows whose column count matches the table's modal count.
    #: A hallucinated table is ragged.
    table_regularity: float = 0.0
    #: ``100 - confidence.score``: how much real breakage the converter reported.
    breakage: float = 0.0

    @property
    def table_quality(self) -> float:
        """Well-formedness of the tables found, ``0.0``-``1.0``. Zero if there are none."""
        if not self.tables:
            return 0.0
        return self.table_fill * self.table_regularity

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view, including the derived table quality."""
        data = {
            "blocks": self.blocks,
            "words": self.words,
            "boilerplate_words": self.boilerplate_words,
            "unique_words": self.unique_words,
            "duplicate_blocks": self.duplicate_blocks,
            "headings": self.headings,
            "list_items": self.list_items,
            "links": self.links,
            "tables": self.tables,
            "table_cells": self.table_cells,
            "table_fill": round(self.table_fill, 4),
            "table_regularity": round(self.table_regularity, 4),
            "table_quality": round(self.table_quality, 4),
            "breakage": round(self.breakage, 2),
        }
        return data


@dataclass
class Candidate:
    """One point in the option space, with its measured yield and fitness."""

    #: The options that differ from the parser's defaults, e.g. ``{"detect_columns": True}``.
    options: dict[str, Any] = field(default_factory=dict)
    #: Where the candidate came from: ``"default"``, ``"preset:quality"``, ``"refine:detect_columns"``.
    origin: str = "default"
    metrics: DocumentMetrics = field(default_factory=DocumentMetrics)
    #: Pool-relative fitness, ``0``-``100``. Only comparable within one run.
    fitness: float = 0.0
    #: Per-dimension contributions, for explaining *why* a candidate won.
    dimensions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view."""
        return {
            "options": self.options,
            "origin": self.origin,
            "fitness": round(self.fitness, 2),
            "dimensions": {k: round(v, 4) for k, v in self.dimensions.items()},
            "metrics": self.metrics.to_dict(),
        }


@dataclass
class OptimizationReport:
    """The outcome of a search: what won, what it beat, and by how much."""

    source_format: str = ""
    #: The winning options, as a flat ``{option: value}`` diff from the defaults.
    best_options: dict[str, Any] = field(default_factory=dict)
    best_fitness: float = 0.0
    #: Fitness of the parser's stock defaults, so the gain is legible.
    baseline_fitness: float = 0.0
    #: Every candidate evaluated, best first.
    candidates: list[Candidate] = field(default_factory=list)
    evaluated: int = 0

    @property
    def gain(self) -> float:
        """How much fitness the winning options add over the stock defaults."""
        return self.best_fitness - self.baseline_fitness

    @property
    def improved(self) -> bool:
        """Whether the search beat the defaults at all."""
        return self.gain > 0.005

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view."""
        return {
            "source_format": self.source_format,
            "best_options": self.best_options,
            "best_fitness": round(self.best_fitness, 2),
            "baseline_fitness": round(self.baseline_fitness, 2),
            "gain": round(self.gain, 2),
            "improved": self.improved,
            "evaluated": self.evaluated,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def tunable_knobs(source_format: str) -> dict[str, list[Any]]:
    """Return the searchable option values for ``source_format`` (empty if untuned)."""
    return KNOBS.get(source_format, {})


def _iter_nodes(node: Node) -> list[Node]:
    """Walk every node in the tree.

    ``get_node_children`` already descends into table rows and cells, so this must
    not also walk them by hand or every cell would be counted twice.
    """
    found: list[Node] = [node]
    for child in get_node_children(node):
        found.extend(_iter_nodes(child))
    return found


def _node_text(node: Node) -> str:
    """Concatenate the text carried by a node and everything beneath it.

    Text lives in ``Text.content`` as a string, while every other node uses
    ``content``/``children``/``rows`` as a *container*. ``get_node_children``
    normalizes that difference; reading ``.content`` directly does not.
    """
    if isinstance(node, Text):
        return node.content
    parts = [_node_text(child) for child in get_node_children(node)]
    return " ".join(p for p in parts if p)


_DIGITS = re.compile(r"\d+")

#: Length of the word window used to spot repeated furniture. Long enough that
#: ordinary prose does not collide by chance, short enough to catch a page footer.
BOILERPLATE_NGRAM = 5


def _boilerplate_key(text: str) -> str:
    """Normalize text so page-varying furniture still compares equal.

    A running footer is not byte-identical across pages -- "Page 1 of 12" and
    "Page 2 of 12" differ -- so digits are masked before comparing. Without this the
    header dedupes and the footer does not, and keeping the footer still pays.
    """
    return _DIGITS.sub("#", " ".join(text.lower().split()))


def _boilerplate_words(texts: list[str]) -> int:
    """Count the words that are repeated furniture rather than body content.

    Furniture is detected two ways, because one alone is not enough:

    * **A whole block that repeats** -- a running heading, an unglued header.
    * **A repeated word sequence spanning blocks** -- because a header or footer is
      frequently *glued into an adjacent body block* by the parser, producing a
      block like "Page 1 of 2 | ACME CONFIDENTIAL Beta sentence B1 ...". That block
      is unique (it contains body text), so no amount of block-level comparison will
      ever flag it, and its footer words get counted as body. Measured against ground
      truth, that one leak was enough to make keeping the boilerplate outscore
      trimming it.

    Only sequences appearing in **two or more distinct blocks** count, so a single
    block that happens to repeat a phrase internally is not mistaken for furniture.

    Repetition is the only reference-free evidence that content is furniture, so a
    one-page document offers no signal and its header cannot be recognized. That is
    a real limit of the objective, not a bug.
    """
    tokens = [_boilerplate_key(text).split() for text in texts]

    whole_block: Counter[str] = Counter(_boilerplate_key(t) for t in texts if t.strip())
    covered = [[False] * len(block) for block in tokens]

    # Where does each n-gram appear? Furniture shows up in more than one block.
    seen: dict[tuple[str, ...], set[int]] = {}
    for index, block in enumerate(tokens):
        for start in range(len(block) - BOILERPLATE_NGRAM + 1):
            seen.setdefault(tuple(block[start : start + BOILERPLATE_NGRAM]), set()).add(index)

    for index, block in enumerate(tokens):
        # A short running heading ("Quarterly Report") is below the n-gram window,
        # so catch it as a whole-block repeat instead.
        if texts[index].strip() and whole_block[_boilerplate_key(texts[index])] > 1:
            covered[index] = [True] * len(block)
            continue
        for start in range(len(block) - BOILERPLATE_NGRAM + 1):
            if len(seen[tuple(block[start : start + BOILERPLATE_NGRAM])]) > 1:
                for offset in range(start, start + BOILERPLATE_NGRAM):
                    covered[index][offset] = True

    return sum(sum(block) for block in covered)


def _table_shape(table: Table) -> tuple[int, int, int]:
    """Return ``(cells, filled_cells, regular_rows)`` for one table."""
    counts = [len(row.cells) for row in table.rows]
    if not counts:
        return 0, 0, 0
    modal = Counter(counts).most_common(1)[0][0]
    cells = sum(counts)
    filled = sum(1 for row in table.rows for cell in row.cells if _node_text(cell).strip())
    regular = sum(1 for count in counts if count == modal)
    return cells, filled, regular


def extract_metrics(document: Document) -> DocumentMetrics:
    """Measure the structural yield of a parsed document.

    Reads the AST rather than the confidence report's signal vector: measured on a
    two-column fixture the signals collapsed 6 option combinations into 2 distinct
    vectors (and the score into 1), while the AST kept 4 distinct outcomes. The
    signals are a summary built for a different purpose; the AST is the evidence.
    """
    metrics = DocumentMetrics()

    top_level = list(document.children or [])
    metrics.blocks = len(top_level)

    # Boilerplate is text that *repeats*. Identify it, then exclude every occurrence
    # from the word count -- not just the second and later ones.
    #
    # This is load-bearing. Scoring text as "more is better" makes leaving the running
    # header in strictly better than trimming it, because the boilerplate is extra
    # words. Measured against ground truth that objective was anti-correlated
    # (r = -0.88): it reliably picked the *worst* conversion. Excluding furniture makes
    # a trimmed and an untrimmed conversion tie on text, so `cleanliness` -- which
    # counts the furniture still present -- decides, and the trimmed one wins.
    texts = [_node_text(block).strip() for block in top_level]
    metrics.words = sum(len(text.split()) for text in texts)
    metrics.boilerplate_words = _boilerplate_words(texts)
    metrics.unique_words = metrics.words - metrics.boilerplate_words

    repeats = Counter(_boilerplate_key(text) for text in texts if text)
    metrics.duplicate_blocks = sum(1 for text in texts if text and repeats[_boilerplate_key(text)] > 1)

    cells = filled = regular = rows = 0
    for node in _iter_nodes(document):
        if isinstance(node, Heading):
            metrics.headings += 1
        elif isinstance(node, ListItem):
            metrics.list_items += 1
        elif isinstance(node, Link):
            metrics.links += 1
        elif isinstance(node, Table):
            metrics.tables += 1
            table_cells, table_filled, table_regular = _table_shape(node)
            cells += table_cells
            filled += table_filled
            regular += table_regular
            rows += len(node.rows)

    metrics.table_cells = cells
    metrics.table_fill = filled / cells if cells else 0.0
    metrics.table_regularity = regular / rows if rows else 0.0

    confidence = (document.metadata or {}).get("confidence")
    if isinstance(confidence, dict):
        metrics.breakage = max(0.0, 100.0 - float(confidence.get("score", 100)))

    return metrics


def score_candidates(candidates: list[Candidate]) -> None:
    """Assign each candidate a pool-relative fitness, in place.

    Fitness is relative because the objective is reference-free: with no ground
    truth, the best text recovery *observed across the pool* is the closest thing to
    one. A candidate recovering fewer unique words than the best candidate lost text.

    Dimensions the pool does not exercise are dropped and the weights renormalized
    over the rest — if no candidate found a table, the ``tables`` dimension says
    nothing about this document and must not drag every score down.
    """
    if not candidates:
        return

    best_words = max(c.metrics.unique_words for c in candidates)
    best_structure = max(c.metrics.headings + c.metrics.list_items + c.metrics.links for c in candidates)
    any_tables = any(c.metrics.tables for c in candidates)

    active = dict(DIMENSION_WEIGHTS)
    if not any_tables:
        active.pop("tables")
    if not best_words:
        active.pop("text", None)
    if not best_structure:
        active.pop("structure", None)
    total_weight = sum(active.values()) or 1.0

    for candidate in candidates:
        metrics = candidate.metrics
        dimensions: dict[str, float] = {}

        if "text" in active:
            dimensions["text"] = metrics.unique_words / best_words

        if "tables" in active:
            # Well-formedness, not count: a junk table is sparse and ragged.
            dimensions["tables"] = metrics.table_quality

        if "structure" in active:
            structure = metrics.headings + metrics.list_items + metrics.links
            dimensions["structure"] = structure / best_structure

        # Furniture still sitting in the output is boilerplate the converter failed
        # to trim. Measured in words, not blocks, so a footer glued into a paragraph
        # counts just as much as one left in a block of its own.
        boilerplate_ratio = metrics.boilerplate_words / metrics.words if metrics.words else 0.0
        dimensions["cleanliness"] = 1.0 - boilerplate_ratio

        weighted = sum(dimensions[name] * active[name] for name in active if name in dimensions)
        # Breakage is a real defect the converter itself reported: subtract it.
        candidate.fitness = max(0.0, (weighted / total_weight) * 100.0 - metrics.breakage)
        candidate.dimensions = dimensions


def search(
    knobs: dict[str, list[Any]],
    evaluate: Callable[[dict[str, Any]], DocumentMetrics],
    *,
    presets: dict[str, dict[str, Any]] | None = None,
    rounds: int = 1,
) -> OptimizationReport:
    """Search ``knobs`` for the option set with the best fitness.

    Takes an ``evaluate`` callable rather than a document, so the search is pure and
    can be tested against a synthetic objective with no parsing at all.

    The shape is deliberately cheap. A full grid over the PDF knobs alone is tens of
    thousands of conversions; instead:

    1. Score the stock defaults, then each named preset. These are interpretable,
       few, and often already contain the answer.
    2. **Coordinate descent** from the best of those: walk one knob at a time, try
       each of its values holding the rest fixed, and keep any improvement. That is
       ``sum(len(values))`` conversions per round rather than ``prod(len(values))``.

    Coordinate descent finds a local optimum, not a global one — it cannot discover
    that two knobs only pay off when flipped *together*. That is an accepted trade:
    the alternative costs orders of magnitude more conversions, and the knobs here
    are largely independent in practice. ``rounds > 1`` re-walks the knobs from the
    new best point, which recovers some interactions.

    Every distinct option set is evaluated at most once.
    """
    seen: dict[tuple[tuple[str, Any], ...], Candidate] = {}

    def signature(options: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(sorted(options.items()))

    def consider(options: dict[str, Any], origin: str) -> Candidate:
        key = signature(options)
        if key not in seen:
            seen[key] = Candidate(options=dict(options), origin=origin, metrics=evaluate(options))
        return seen[key]

    def rank() -> None:
        """Fitness is pool-relative, so it must be recomputed as the pool grows."""
        score_candidates(list(seen.values()))

    baseline = consider({}, "default")
    rank()

    best = baseline
    for name, config in (presets or {}).items():
        # A preset that sets nothing for this format is the default under another
        # name; evaluating it would just be a duplicate.
        overrides = {k: v for k, v in config.items() if k in knobs}
        if not overrides:
            continue
        consider(overrides, f"preset:{name}")
    rank()
    best = max(seen.values(), key=lambda c: c.fitness)

    for _ in range(max(1, rounds)):
        improved = False
        for knob, values in knobs.items():
            for value in values:
                if best.options.get(knob) == value:
                    continue
                trial = dict(best.options)
                trial[knob] = value
                consider(trial, f"refine:{knob}")
            rank()
            leader = max(seen.values(), key=lambda c: c.fitness)
            if leader.fitness > best.fitness:
                best, improved = leader, True
        if not improved:
            break  # a full pass changed nothing; another one cannot either

    rank()
    ranked = sorted(seen.values(), key=lambda c: -c.fitness)
    best = ranked[0]

    return OptimizationReport(
        best_options=dict(best.options),
        best_fitness=best.fitness,
        baseline_fitness=baseline.fitness,
        candidates=ranked,
        evaluated=len(seen),
    )
