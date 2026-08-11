"""Measure whether anything was lost, over the whole article rather than page by page.

The per-page instrument excludes the blocks that will not resolve to a page -- about 5% --
and those are not a random 5%: they are structured citations, bylines and float captions,
the material most likely to be mishandled. An instrument that silently drops the hard cases
and reports on the rest is flattering itself. This one pays no alignment tax, so its
denominator is every ground-truth block.

**It asks a narrower question than the page instrument, on purpose: did this block's text
survive anywhere in the output?** Not "in the right place" -- that is the page instrument's
job, and at article scale it is not answerable with these tools. Two measurements settled
that.

*The shared oracle's block-locating threshold does not survive an article-length haystack.*
``_IDENTIFIED_MATCH`` admits a block once half its characters align monotonically, which is
sound over one page. Over a whole article, 77-86% of one article's ground-truth blocks
"locate" inside a **completely different article's** output, at a median alignment of
0.62-0.72. The safeguard that is supposed to stop absent content from earning order credit
is inoperative at this length, so reading order is scored per page, where its calibration
holds.

*Page order cannot fail here, so it is not scored.* Page attribution comes from the parser's
own per-page loop, which emits a separator per PDF page. Content cannot migrate between page
groups, and a dropped page raises `benchmarks.pmc.convert.PageBoundaryError` instead of
scoring. A page-sequence metric would report a perfect score by construction.

What remains is recall, measured with n-gram containment -- the one instrument on this
corpus with a published false-positive rate, 0.8% against a mismatched article.

**Raw recall is not readable on its own, so the ceiling ships with it.** Much of a JATS
article cannot be recovered from the PDF by *any* parser, because the markup does not record
the words in the order the page prints them: ``<element-citation>`` lists the journal before
the authors, ``<surname>`` precedes ``<given-names>`` against the rendered byline. Measured
against the PDF's own text layer, only 61.1% of blocks are recoverable at all -- so a raw
54.6% is 89% of what was available, not a parser losing half the document. The ceiling is
computed per run rather than pinned, because it is a property of the corpus and the
extraction, both of which can change.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from benchmarks.pmc.alignment import MIN_NGRAMS, ngrams, normalize

#: Share of a block's n-grams that must appear in the output for the block to count as
#: recovered. Not 1.0: de-hyphenation, ligature folding and a dropped soft hyphen each cost
#: an n-gram or two on text that is otherwise reproduced exactly.
RECALL_MIN = 0.80


@dataclass(frozen=True, slots=True)
class RecallReport:
    """Whole-article content recall with its mismatch control.

    Attributes
    ----------
    recovered : int
        Blocks whose text was found in the article's own output.
    attainable : int
        Blocks recoverable at all, measured against the PDF's own text layer. The honest
        denominator: everything above this is unreachable for any parser.
    recovered_attainable : int
        Blocks that were both attainable and recovered.
    scored : int
        Blocks long enough to look for.
    too_short : int
        Blocks with too few n-grams to test, reported rather than counted either way.
    by_kind : Mapping[str, KindRecall]
        The same counts per block kind.
    control_recovered : int
        Blocks "recovered" from a *different* article's output. The instrument's noise
        floor: a recall figure means nothing without it.
    control_scored : int
        Blocks scored against the mismatched article.

    """

    recovered: int
    attainable: int
    recovered_attainable: int
    scored: int
    too_short: int
    by_kind: Mapping[str, "KindRecall"]
    control_recovered: int
    control_scored: int

    @property
    def recall(self) -> float:
        """Share of testable blocks whose text survived into the output."""
        return self.recovered / self.scored if self.scored else 0.0

    @property
    def ceiling(self) -> float:
        """Share of blocks the PDF's own text layer reproduces -- the best any parser could do."""
        return self.attainable / self.scored if self.scored else 0.0

    @property
    def attainable_recall(self) -> float:
        """Share of the *recoverable* blocks that were recovered. The number worth reading."""
        return self.recovered_attainable / self.attainable if self.attainable else 0.0

    @property
    def control_recall(self) -> float:
        """Share of blocks 'recovered' from the wrong article."""
        return self.control_recovered / self.control_scored if self.control_scored else 0.0


@dataclass(frozen=True, slots=True)
class KindRecall:
    """Recall counts for one block kind.

    Attributes
    ----------
    recovered, attainable, recovered_attainable, scored : int
        As on `RecallReport`, restricted to this kind.

    """

    recovered: int
    attainable: int
    recovered_attainable: int
    scored: int

    @property
    def attainable_recall(self) -> float:
        """Share of this kind's recoverable blocks that were recovered."""
        return self.recovered_attainable / self.attainable if self.attainable else 0.0


def _contained(block: set[tuple[str, ...]], haystack: set[tuple[str, ...]]) -> bool:
    return len(block & haystack) / len(block) >= RECALL_MIN


def measure_recall(
    articles: Iterable[tuple[str, Sequence[tuple[str, str]], str, str]],
) -> RecallReport:
    """Measure article-level content recall against both the output and the attainable ceiling.

    Parameters
    ----------
    articles : Iterable
        ``(article_id, blocks, emitted_text, pdf_text)`` tuples, where ``blocks`` are
        ``(kind, text)`` ground-truth pairs, ``emitted_text`` is all2md's whole output and
        ``pdf_text`` is the PDF's own text layer.

    Returns
    -------
    RecallReport
        Recall, ceiling and the mismatched-article control, overall and per kind.

    """
    indexed = [
        (
            article_id,
            [(kind, ngrams(normalize(text))) for kind, text in blocks],
            ngrams(normalize(emitted)),
            ngrams(normalize(pdf_text)),
        )
        for article_id, blocks, emitted, pdf_text in articles
    ]

    totals = [0, 0, 0, 0]  # recovered, attainable, both, scored
    too_short = control_recovered = control_scored = 0
    by_kind: dict[str, list[int]] = {}
    for position, (_article_id, blocks, haystack, ceiling) in enumerate(indexed):
        # Pair with the neighbour rather than a random article, so the control reproduces
        # exactly on a re-run.
        other = indexed[(position + 1) % len(indexed)][2]
        for kind, block in blocks:
            if len(block) < MIN_NGRAMS:
                too_short += 1
                continue
            found = _contained(block, haystack)
            reachable = _contained(block, ceiling)
            counts = by_kind.setdefault(kind, [0, 0, 0, 0])
            for bucket in (totals, counts):
                bucket[0] += found
                bucket[1] += reachable
                bucket[2] += found and reachable
                bucket[3] += 1
            if other is not haystack:
                control_scored += 1
                control_recovered += _contained(block, other)

    return RecallReport(
        recovered=totals[0],
        attainable=totals[1],
        recovered_attainable=totals[2],
        scored=totals[3],
        too_short=too_short,
        by_kind={kind: KindRecall(*counts) for kind, counts in sorted(by_kind.items())},
        control_recovered=control_recovered,
        control_scored=control_scored,
    )


def summarize(values: Sequence[float]) -> dict[str, float]:
    """Summarize a dimension's distribution, so a gate can see whether it discriminates.

    Parameters
    ----------
    values : Sequence[float]
        Per-item scores.

    Returns
    -------
    dict[str, float]
        ``count``, ``mean``, ``median``, ``minimum``, ``maximum`` and ``stdev``. A dimension
        whose minimum, median and maximum coincide cannot fail, whatever its value.

    """
    if not values:
        return {"count": 0.0}
    return {
        "count": float(len(values)),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def tally(counter: Counter[str], names: Sequence[str]) -> dict[str, int]:
    """Return a counter as a dict with every expected name present, zero-filled."""
    return {name: counter.get(name, 0) for name in names}
