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
content only, with repeated furniture excluded.

Getting that exclusion right took two corrections, both forced by measurement:

1. **Block-level deduplication is not enough.** The parser frequently glues a footer
   into an adjacent body block ("Page 1 of 2 | ACME CONFIDENTIAL Beta sentence
   B1 ..."). That block is unique, so no block comparison can ever see it. Furniture
   must be found as a repeated *word sequence* spanning blocks — :func:`find_furniture`.
2. **Furniture is a property of the document, not of one parse of it.** Deriving it
   per-candidate lets a candidate whose block segmentation happens to hide the
   repetition escape detection and bank its running header as recovered body text.
   The candidates then stop tying on text and keeping the boilerplate wins again.
   :func:`score_candidates` therefore pools what *every* candidate revealed and
   applies the union to all of them. This one bit differs between platforms and
   PyMuPDF versions, so a per-candidate rule can look perfectly correct locally and
   invert the ranking somewhere else.

With furniture excluded, a trimmed and an untrimmed conversion *tie* on text, which
frees the ``cleanliness`` dimension to break the tie in favour of the one that
actually removed it. On the same fixture that took the objective from r = -0.88 to
r = +1.00.

**It rewards an over-eager table detector**, because any junk region promoted to a
table adds cells. But scoring well-formedness *alone* — the obvious correction —
simply inverts the bias into rewarding an **under**-eager one: finding five clean
tables and missing the sixth then beats finding all six with one messy. That is not
theoretical; on a real arXiv paper ``table_detection_mode="ruling"`` scored 0.98 on
well-formedness against ``"pymupdf"``'s 0.68 while recovering *fewer* tables. Tables
are therefore scored on **quality-weighted recall** (:func:`_table_shape`): filled
cells, discounted by shape regularity. A hallucinated table is sparse and ragged and
contributes almost nothing; a missed real one costs its cells.

**And furniture must repeat like furniture.** A sequence counted as boilerplate if it
appeared in merely *two* blocks — correct only for the two-page fixture it was written
against. On a 21-page paper it fired on ordinary recurring academic phrasing and
flagged 746 words of real body text as boilerplate (against 131 with the corrected
rule). False furniture is not harmless: it makes body text look like clutter, so a
setting that *deletes* that text scores as if it had tidied up. The bar now scales
with page count — :func:`furniture_threshold`.

Body text is not a dimension at all
-----------------------------------
It **gates** the others. Losing a paragraph is data loss; leaving a running header in
is an annoyance, and no exchange rate between them is defensible. As a weighted
dimension the two were interchangeable at 0.45 versus 0.15, which means a setting
that destroyed 1% of the body could buy its way back with a 3% tidiness gain. That is
the wrong trade at any exchange rate, so retention instead *multiplies* the score,
raised to :data:`TEXT_RETENTION_EXPONENT`: shedding 1% of the body costs ~3% of
fitness and no amount of polish buys it back. This is a deliberately conservative
posture — the optimizer's advice is only worth taking if it cannot destroy content.

Fitness is *relative to the candidate pool*, not absolute: the best text recovery
observed across the candidates stands in for the reference we do not have. This is
deliberate. The job is to *rank* candidates, and inventing an absolute 0-100 quality
number would both duplicate :mod:`all2md.confidence` and imply a precision these
signals do not support.

Every correction above was forced by measurement, and several of them by documents
from the wild, which broke an objective that looked perfectly healthy on a synthetic
fixture. Changing the scoring without re-running that evaluation is not advisable.

"""

from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, NamedTuple

from all2md.ast.nodes import Document, Heading, Link, ListItem, Node, Table, Text, get_node_children

# One definition of "inline", shared with the round-trip scorer. A second copy here
# would be free to drift, and getting this set wrong silently corrupts word counts.
from all2md.roundtrip import _INLINE_TYPES

# Pin the public surface. Without this, autodoc also documents the names this
# module imports, and their docstrings are not valid reStructuredText.
__all__ = [
    "BOILERPLATE_NGRAM",
    "DIMENSION_WEIGHTS",
    "FORBIDDEN_KNOBS",
    "MINIMIZE_TOLERANCE",
    "MIN_STRUCTURE_ELEMENTS",
    "MIN_TABLE_CELLS",
    "TEXT_RETENTION_EXPONENT",
    "KNOBS",
    "Candidate",
    "DocumentMetrics",
    "Furniture",
    "OptimizationReport",
    "content_tokens",
    "extract_metrics",
    "find_furniture",
    "furniture_threshold",
    "score_candidates",
    "search",
    "tunable_knobs",
]

_unused_logger = logging.getLogger(__name__)

#: How the fitness dimensions are combined. Dimensions the candidate pool does not
#: exercise (no candidate found a table) are dropped and the rest renormalized, so a
#: table-free document is neither rewarded nor punished for the tables it lacks.
#:
#: Body text is deliberately **not** here. It is not a dimension to be traded against
#: the others; it is a multiplicative gate -- see :data:`TEXT_RETENTION_EXPONENT`.
DIMENSION_WEIGHTS: dict[str, float] = {
    "tables": 0.45,
    "structure": 0.25,
    "cleanliness": 0.30,
}

#: How steeply losing body text is punished. Retention (this candidate's body words
#: over the best candidate's) multiplies the whole score raised to this power, so
#: shedding 1% of the body costs roughly 3% of fitness.
#:
#: This exists because losing a paragraph and keeping a running header are not
#: commensurable defects. As a mere weighted dimension, body text was interchangeable
#: with tidiness, so a setting that destroyed content could buy its way back by
#: removing clutter. A conservative posture is the point: advice that can silently
#: delete text is not advice worth taking.
TEXT_RETENTION_EXPONENT = 3.0

#: How much fitness a recommended setting must be worth to survive the minimization
#: pass. Anything that can be removed without dropping below this is a passenger the
#: search happened to pick up, not a finding, and reporting it as advice is worse than
#: saying nothing: the user cannot tell the difference.
MINIMIZE_TOLERANCE = 1e-9

#: How much of a dimension the best candidate must actually find before that dimension
#: is allowed to influence the ranking.
#:
#: Every dimension is normalized against the best candidate in the pool, which turns a
#: *trivial* absolute difference into a *total* relative one. On a real arXiv paper
#: with no real tables at all, one setting happened to find a single two-column table
#: worth four cells while the default found none: the tables dimension read 1.0 against
#: 0.0 -- a maximal swing, worth its full weight -- and the optimizer reported a **45
#: point** gain for a change that measurably did nothing. A dimension the document
#: barely exercises carries no information about it, and must not be allowed to decide
#: the ranking. Below these floors it is dropped, exactly as it already is at zero.
MIN_TABLE_CELLS = 8.0
MIN_STRUCTURE_ELEMENTS = 3

#: Settings that must never be searched, and why. Enforced by a test, because every entry
#: here was added *after* the optimizer found and exploited it.
#:
#: A knob only belongs in :data:`KNOBS` if it is a genuine **fidelity trade-off** -- a
#: setting where the better value depends on the document and cannot be known in advance.
#: Two other kinds of setting look superficially tunable and are not:
#:
#: *Correctness settings*, where one value is simply right. ``merge_hyphenated_words``
#: repairs a word broken across a line break; leaving it off is a defect, not a trade-off.
#: The optimizer recommended disabling it on **17 of 17** real papers -- and ground truth
#: confirmed it made every one of them worse -- because the repair joins two tokens into
#: one and so *looks* like losing a word. (:func:`content_tokens` now removes that
#: incentive, but the setting still has no business being searched: there is no document
#: for which the broken word is the better answer.)
#:
#: *Content-inclusion preferences*, which change what the user asked for rather than how
#: well it was extracted. The objective rewards recovering more content, so it will always
#: say yes to ``include_comments`` -- not because leaking reviewer comments into the output
#: improves fidelity, but because comments are words and words score. That is a tautology
#: dressed up as a finding, and for comments specifically it is advice that leaks content
#: the author never meant to publish.
FORBIDDEN_KNOBS: dict[str, str] = {
    "merge_hyphenated_words": (
        "correctness, not a trade-off: the repair joins two tokens into one, so disabling it games a word count"
    ),
    "consolidate_inline_formatting": (
        "correctness, not a trade-off: disabling it fragments inline runs ('hello' -> 'hel' + 'lo')"
    ),
    "include_comments": (
        "a content-inclusion preference: more words always score, so this would always be recommended"
    ),
}

#: The option values worth searching, per format. Deliberately curated rather than
#: derived from the dataclass fields: most options are irrelevant to fidelity
#: (``password``), or are a security posture that an optimizer has no business
#: flipping (``strip_dangerous_elements``), or would explode the search space for no
#: gain. Only knobs that are a genuine fidelity **trade-off** belong here -- see
#: :data:`FORBIDDEN_KNOBS` for the two categories that are not.
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
    #: Filled cells discounted by shape regularity, summed over tables with 2+ columns.
    #: Quality-weighted *recall*: this, not ``table_quality``, is what the objective
    #: scores. Well-formedness alone rewards missing real tables; count alone rewards
    #: inventing them.
    good_cells: float = 0.0
    #: Fraction of table cells that are non-empty. A hallucinated table is sparse.
    table_fill: float = 0.0
    #: Fraction of table rows whose column count matches the table's modal count.
    #: A hallucinated table is ragged.
    table_regularity: float = 0.0
    #: ``100 - confidence.score``: how much real breakage the converter reported.
    breakage: float = 0.0

    #: The document's top-level block texts. Kept so the furniture found by *any*
    #: candidate can be re-applied to *this* one -- see :func:`score_candidates`.
    block_texts: list[str] = field(default_factory=list, repr=False, compare=False)
    #: The repeated content this parse revealed.
    furniture: Furniture = field(default_factory=lambda: Furniture(set(), set()), repr=False, compare=False)
    #: How many distinct blocks a sequence must span before it counts as furniture.
    #: Scales with page count: furniture repeats page after page, ordinary prose does not.
    min_furniture_blocks: int = 2

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
            "good_cells": round(self.good_cells, 2),
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

    Inline siblings are joined with **no separator**, because they are contiguous
    character runs, not separate words: a bolded middle of a word arrives as three
    runs and must come back as one word. Joining them with a space instead turns
    "hello" into "hel lo" and conjures a word out of nothing — which is not merely
    inaccurate, it is *exploitable*. The optimizer scores recovered text, so on real
    papers it learned to recommend ``consolidate_inline_formatting=False`` purely
    because leaving runs unmerged inflated the word count (2325 -> 2412 words on an
    arXiv paper, with no more text on the page). Blocks still get a separator: they
    are genuinely distinct runs of prose.
    """
    if isinstance(node, Text):
        return node.content

    result = ""
    for child in get_node_children(node):
        part = _node_text(child)
        if not part:
            continue
        if result and type(child).__name__ not in _INLINE_TYPES:
            result += " "
        result += part
    return result


_DIGITS = re.compile(r"\d+")

#: Length of the word window used to spot repeated furniture. Long enough that
#: ordinary prose does not collide by chance, short enough to catch a page footer.
BOILERPLATE_NGRAM = 5


def content_tokens(text: str) -> list[str]:
    """Split text into words in a way that cannot be gamed by *fragmenting* them.

    The objective's text signal is a word count, so any setting that chops one word into
    two makes the document look like it contains *more* text. That is not a hypothetical:
    it has now bitten this objective three separate times.

    * ``consolidate_inline_formatting=False`` split runs so that "hello" was counted as
      "hel" + "lo".
    * ``merge_hyphenated_words=False`` leaves a word broken across a line break, so
      repairing "hyphen-" + "ation" into "hyphenation" *reduces* the count by one -- and
      the optimizer learned to recommend switching the repair off. It did so on 17 of 17
      real papers, and ground truth confirmed the advice made every one of them worse.

    Patching each setting as it appears does not work, because the defect is in the
    *metric*, not in the settings: a count of whitespace-separated tokens rewards
    fragmentation, so there is always another door. The fix is to count words the same way
    no matter how the parse happened to break them up -- rejoin a token that ends in a
    hyphen with the one after it, and then drop hyphens entirely, so that

        "hyphen-" + "ation"   ->   "hyphenation"
        "hyphenation"         ->   "hyphenation"
        "Anglo-" + "Saxon"    ->   "anglosaxon"
        "Anglo-Saxon"         ->   "anglosaxon"

    all collapse to one identical token. A candidate that fragments text and one that does
    not now produce the *same* count, so the metric has no preference and cannot be gamed.

    Note this deliberately conflates "well-known" with "wellknown". That is fine: it does so
    for every candidate equally, and the count is only ever compared against other counts of
    the same document.
    """
    merged: list[str] = []
    carry = ""
    for token in text.lower().split():
        if carry:
            token = carry + token
            carry = ""
        # A token that is *only* punctuation ("-", "--") is not a word fragment.
        if len(token) > 1 and token.endswith("-"):
            carry = token[:-1]
            continue
        merged.append(token)
    if carry:
        merged.append(carry)
    return [stripped for token in merged if (stripped := token.replace("-", ""))]


def _boilerplate_key(text: str) -> str:
    """Normalize text so page-varying furniture still compares equal.

    A running footer is not byte-identical across pages -- "Page 1 of 12" and
    "Page 2 of 12" differ -- so digits are masked before comparing. Without this the
    header dedupes and the footer does not, and keeping the footer still pays.

    Uses :func:`content_tokens`, so furniture is recognized identically however the parse
    happened to break its words up.
    """
    return _DIGITS.sub("#", " ".join(content_tokens(text)))


class Furniture(NamedTuple):
    """The repeated content of a document: running headers, footers, watermarks.

    Two shapes, because one alone is not enough:

    * ``sequences`` -- word windows appearing in two or more distinct blocks. Needed
      because a header or footer is frequently *glued into an adjacent body block* by
      the parser ("Page 1 of 2 | ACME CONFIDENTIAL Beta sentence B1 ..."). Such a
      block is unique -- it contains body text -- so no block-level comparison can
      ever flag it, and its footer words would count as recovered body content.
    * ``blocks`` -- whole blocks that repeat. Needed because a short running heading
      ("Quarterly Report") is below the n-gram window and no sequence can catch it.
    """

    sequences: set[tuple[str, ...]]
    blocks: set[str]

    def union(self, other: Furniture) -> Furniture:
        """Combine what two parses each revealed about the document's furniture."""
        return Furniture(self.sequences | other.sequences, self.blocks | other.blocks)


def furniture_threshold(page_count: int | None) -> int:
    """How many distinct blocks a sequence must appear in before it is furniture.

    Furniture is content that repeats on *page after page*, so the bar has to scale
    with the document. A flat "appears twice" rule is only correct for a two-page
    document -- which is exactly the fixture it was written against. On a 21-page
    arXiv paper it fired on ordinary recurring academic phrasing and flagged 746 words
    of real body text as boilerplate, against 131 once the bar scaled with the page
    count. False furniture is not harmless: it makes body text look like clutter, so a
    setting that *deletes* that text scores as if it had tidied up.
    """
    if not page_count or page_count < 2:
        return 2
    return max(2, round(page_count / 2))


def find_furniture(texts: list[str], min_blocks: int = 2) -> Furniture:
    """Identify the repeated furniture in one parse of a document.

    A sequence must appear in at least ``min_blocks`` distinct blocks -- see
    :func:`furniture_threshold`. Counting *distinct blocks* (not occurrences) means a
    single block that repeats a phrase internally is never mistaken for furniture.

    Repetition is the only reference-free evidence that content is furniture, so a
    one-page document offers no signal and its header cannot be recognized. That is
    a real limit of the objective, not a bug.
    """
    tokens = [_boilerplate_key(text).split() for text in texts]

    counts: Counter[str] = Counter(_boilerplate_key(t) for t in texts if t.strip())
    blocks = {key for key, count in counts.items() if count >= min_blocks}

    where: dict[tuple[str, ...], set[int]] = {}
    for index, block in enumerate(tokens):
        for start in range(len(block) - BOILERPLATE_NGRAM + 1):
            where.setdefault(tuple(block[start : start + BOILERPLATE_NGRAM]), set()).add(index)

    sequences = {gram for gram, seen_in in where.items() if len(seen_in) >= min_blocks}
    return Furniture(sequences, blocks)


def _boilerplate_words(texts: list[str], furniture: Furniture) -> int:
    """Count how many of ``texts``' words belong to ``furniture``.

    ``furniture`` is passed in rather than derived here, because *what counts as
    furniture is a property of the document, not of one parse of it*. Deriving it
    per-candidate lets a candidate whose block segmentation happens to hide the
    repetition escape detection -- its furniture words then read as recovered body
    text, and keeping the boilerplate starts paying again. That is exactly how the
    over-detection trap came back on a document where every local run looked fine:
    the candidates stopped tying on text, and the untrimmed one won.
    """
    total = 0
    for text in texts:
        block = _boilerplate_key(text).split()
        if not block:
            continue
        if _boilerplate_key(text) in furniture.blocks:
            total += len(block)
            continue
        covered = [False] * len(block)
        for start in range(len(block) - BOILERPLATE_NGRAM + 1):
            if tuple(block[start : start + BOILERPLATE_NGRAM]) in furniture.sequences:
                for offset in range(start, start + BOILERPLATE_NGRAM):
                    covered[offset] = True
        total += sum(covered)
    return total


def _table_shape(table: Table) -> tuple[int, int, int, float]:
    """Return ``(cells, filled_cells, regular_rows, good_cells)`` for one table.

    ``good_cells`` is the table's contribution to the objective: its filled cells,
    discounted by how regular its shape is. It is *quality-weighted recall*, and both
    halves are load-bearing:

    * Scoring quality **alone** rewards under-detection — finding five clean tables
      and missing the sixth beats finding all six with one messy. Measured on a real
      arXiv paper, ``table_detection_mode="ruling"`` scored 0.98 on well-formedness
      against ``"pymupdf"``'s 0.68 while recovering *fewer* tables.
    * Scoring count **alone** rewards hallucination — any junk region promoted to a
      table adds cells.

    A single-column "table" is not tabular: it is a paragraph the detector captured,
    and counting it would let an aggressive detector bank body text as table content.
    """
    counts = [len(row.cells) for row in table.rows]
    if not counts:
        return 0, 0, 0, 0.0
    modal = Counter(counts).most_common(1)[0][0]
    cells = sum(counts)
    filled = sum(1 for row in table.rows for cell in row.cells if _node_text(cell).strip())
    regular = sum(1 for count in counts if count == modal)

    regularity = regular / len(counts)
    good = 0.0 if modal < 2 else filled * regularity
    return cells, filled, regular, good


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
    confidence = (document.metadata or {}).get("confidence") or {}
    signals = confidence.get("signals") or {} if isinstance(confidence, dict) else {}
    page_count = signals.get("page_count")
    metrics.min_furniture_blocks = furniture_threshold(page_count if isinstance(page_count, int) else None)

    texts = [_node_text(block).strip() for block in top_level]
    metrics.block_texts = texts
    metrics.furniture = find_furniture(texts, metrics.min_furniture_blocks)
    # content_tokens, not str.split: a whitespace token count rewards a parse that
    # fragments words, and the optimizer will find that and exploit it.
    metrics.words = sum(len(content_tokens(text)) for text in texts)
    metrics.boilerplate_words = _boilerplate_words(texts, metrics.furniture)
    metrics.unique_words = metrics.words - metrics.boilerplate_words

    repeats = Counter(_boilerplate_key(text) for text in texts if text)
    metrics.duplicate_blocks = sum(
        1 for text in texts if text and repeats[_boilerplate_key(text)] >= metrics.min_furniture_blocks
    )

    cells = filled = regular = rows = 0
    good = 0.0
    for node in _iter_nodes(document):
        if isinstance(node, Heading):
            metrics.headings += 1
        elif isinstance(node, ListItem):
            metrics.list_items += 1
        elif isinstance(node, Link):
            metrics.links += 1
        elif isinstance(node, Table):
            metrics.tables += 1
            table_cells, table_filled, table_regular, table_good = _table_shape(node)
            cells += table_cells
            filled += table_filled
            regular += table_regular
            rows += len(node.rows)
            good += table_good

    metrics.table_cells = cells
    metrics.good_cells = good
    metrics.table_fill = filled / cells if cells else 0.0
    metrics.table_regularity = regular / rows if rows else 0.0

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

    # What counts as furniture is a property of the DOCUMENT, not of one parse of it.
    # Pool every candidate's findings and re-apply the union to all of them, so a
    # candidate whose block segmentation happened to hide the repetition does not get
    # to bank its running header as recovered body text. Without this the candidates
    # stop tying on text and keeping the boilerplate wins again -- which is precisely
    # what happened on a document where every local run had looked correct.
    pooled = Furniture(set(), set())
    for candidate in candidates:
        pooled = pooled.union(candidate.metrics.furniture)

    for candidate in candidates:
        metrics = candidate.metrics
        if not metrics.block_texts:
            continue
        metrics.boilerplate_words = _boilerplate_words(metrics.block_texts, pooled)
        metrics.unique_words = metrics.words - metrics.boilerplate_words

    best_words = max(c.metrics.unique_words for c in candidates)
    best_structure = max(c.metrics.headings + c.metrics.list_items + c.metrics.links for c in candidates)
    best_cells = max(c.metrics.good_cells for c in candidates)

    # A dimension the document barely exercises says nothing about it. Because every
    # dimension is normalized against the pool's best, a trivial absolute difference
    # (four table cells against none, on a paper with no real tables) would otherwise
    # read as a total one -- 1.0 against 0.0 -- and swing the ranking by its full
    # weight. Drop it, exactly as we already do when it is entirely absent.
    active = dict(DIMENSION_WEIGHTS)
    if best_cells < MIN_TABLE_CELLS:
        active.pop("tables", None)
    if best_structure < MIN_STRUCTURE_ELEMENTS:
        active.pop("structure", None)
    total_weight = sum(active.values()) or 1.0

    for candidate in candidates:
        metrics = candidate.metrics
        dimensions: dict[str, float] = {}

        if "tables" in active:
            # Quality-weighted *recall*: filled cells discounted by shape regularity.
            # Quality alone rewards under-detection; count alone rewards hallucination.
            dimensions["tables"] = metrics.good_cells / best_cells

        if "structure" in active:
            structure = metrics.headings + metrics.list_items + metrics.links
            dimensions["structure"] = structure / best_structure

        # Furniture still sitting in the output is boilerplate the converter failed
        # to trim. Measured in words, not blocks, so a footer glued into a paragraph
        # counts just as much as one left in a block of its own.
        boilerplate_ratio = metrics.boilerplate_words / metrics.words if metrics.words else 0.0
        dimensions["cleanliness"] = 1.0 - boilerplate_ratio

        # Body text is not a dimension to be traded against the others -- it GATES
        # them. Losing a paragraph is data loss; leaving a running header in is an
        # annoyance, and the two must not be interchangeable at any exchange rate.
        # As a weighted dimension they were, so a candidate that destroyed body text
        # could buy its way back with a tidiness gain. Retention is therefore a
        # multiplier raised to TEXT_RETENTION_EXPONENT: shedding 1% of the body costs
        # ~3% of fitness and no amount of polish can buy it back.
        retention = metrics.unique_words / best_words if best_words else 1.0
        dimensions["retention"] = retention

        weighted = sum(dimensions[name] * active[name] for name in active if name in dimensions)
        gated = (weighted / total_weight) * (retention**TEXT_RETENTION_EXPONENT)
        # Breakage is a real defect the converter itself reported: subtract it.
        candidate.fitness = max(0.0, gated * 100.0 - metrics.breakage)
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
    best = max(seen.values(), key=lambda c: c.fitness)

    # Drop passengers. Coordinate descent accumulates whatever it walked through, so
    # the winner can carry settings that merely *tied* rather than won -- on a real
    # arXiv paper it reported ``table_detection_mode="none"`` for a document whose only
    # "table" was a one-column artifact, so the knob could not affect fitness at all.
    # A setting we have no evidence for is not a finding, and printing it as advice
    # invites the user to believe it matters. Try removing each one; if fitness does
    # not fall, it was never earning its place.
    #
    # This also makes the recommendation strictly more conservative -- everything
    # dropped reverts to the shipped default.
    shrinking = True
    while shrinking:
        shrinking = False
        for knob in list(best.options):
            trial = {name: value for name, value in best.options.items() if name != knob}
            candidate = consider(trial, f"minimize:{knob}")
            rank()
            if candidate.fitness >= best.fitness - MINIMIZE_TOLERANCE:
                best = candidate
                shrinking = True
                break

    rank()
    ranked = sorted(seen.values(), key=lambda c: -c.fitness)
    best = seen[signature(best.options)]

    return OptimizationReport(
        best_options=dict(best.options),
        best_fitness=best.fitness,
        baseline_fitness=baseline.fitness,
        candidates=ranked,
        evaluated=len(seen),
    )
