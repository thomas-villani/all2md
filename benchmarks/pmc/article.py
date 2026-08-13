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

What remains is recall and its converse, both measured with n-gram containment -- the one
instrument on this corpus with a published false-positive rate, 0.8% against a mismatched
article.

**Recall is reported with precision because recall alone is gameable.** The highest recall
available here comes from emitting the raw text layer with no structure whatsoever, so a
recall figure rising is not by itself good news. `measure_precision` asks the opposite
question -- does the output contain anything the document does not -- against the PDF's own
text layer rather than JATS, and reports duplication separately because a block emitted
twice leaves every set-based measure unmoved.

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

from benchmarks.pmc.alignment import MIN_NGRAMS, ngram_counts, ngrams, normalize

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


@dataclass(frozen=True, slots=True)
class PrecisionReport:
    """Whether the output says anything the document does not, with its mismatch control.

    Attributes
    ----------
    supported : int
        Distinct emitted n-grams the PDF's own text layer also holds.
    resequenced : int
        Unsupported n-grams every one of whose *words* the layer holds. The adjacency is new,
        not the text: all2md orders columns and joins blocks, and the layer is extracted in
        PyMuPDF's own order, so every place the two disagree mints n-grams that are nobody's
        defect. Measured rather than assumed -- it is 4.8% of emitted n-grams against 0.5%
        genuinely novel, so folding it into the failure would have made the headline number
        nine times worse than the parser deserves.
    novel : int
        Unsupported n-grams containing a word the layer never has anywhere. The residue that
        actually indicts the parser.
    emitted : int
        Distinct emitted n-grams.
    excess : int
        Occurrences of *supported* n-grams emitted more often than the text layer holds
        them. Restricted to supported n-grams on purpose: an unsupported n-gram is already
        counted by `precision`, and letting it score here too would make one defect move two
        numbers.
    occurrences : int
        Total emitted n-gram occurrences -- the denominator `excess` is a share of.
    control_supported : int
        Emitted n-grams "supported" by a *different* article's text layer. The noise floor:
        without it a high precision may only mean that English n-grams are common.
    control_emitted : int
        Distinct emitted n-grams scored against the mismatched article.

    """

    supported: int
    resequenced: int
    novel: int
    emitted: int
    excess: int
    occurrences: int
    control_supported: int
    control_emitted: int

    @property
    def precision(self) -> float:
        """Share of emitted n-grams the document itself accounts for, phrase for phrase."""
        return self.supported / self.emitted if self.emitted else 0.0

    @property
    def novel_share(self) -> float:
        """Share of emitted n-grams containing a word the document does not have.

        The number worth reading, and the counterpart of `RecallReport.attainable_recall`:
        both exist because the raw figure is dominated by something that is not the parser's
        doing.
        """
        return self.novel / self.emitted if self.emitted else 0.0

    @property
    def duplication(self) -> float:
        """Share of emitted n-gram occurrences that repeat text the page prints once."""
        return self.excess / self.occurrences if self.occurrences else 0.0

    @property
    def control_precision(self) -> float:
        """Share of emitted n-grams the *wrong* article's text layer appears to account for."""
        return self.control_supported / self.control_emitted if self.control_emitted else 0.0


def measure_precision(
    articles: Iterable[tuple[str, Sequence[tuple[str, str]], str, str]],
) -> PrecisionReport:
    """Measure whether the output contains text the document does not.

    The converse of `measure_recall`, and it exists because recall alone cannot be trusted:
    the highest recall on this corpus is obtained by emitting the raw text layer with no
    structure at all, which is exactly how a 99% page-level text recall coexisted with less
    than half of section titles becoming headings. A pair of numbers that fail in opposite
    directions is readable; either one alone is not.

    **The reference is the PDF's own text layer, not JATS.** JATS is not what the page
    prints -- it omits running heads and folios the parser legitimately sees, and orders
    citation and byline text the way the markup declares it rather than the way it is
    typeset. Scoring against it would charge the parser for reproducing the document. The
    text layer is what the file actually contains, so anything outside it is unexplained.

    Two defects, two numbers, because the set-based one cannot see the second:

    * **Invented text** lowers `precision`. The proven case on this corpus is auto-OCR
      firing on a page that already had a good text layer and substituting its own guesses.
    * **Duplicated text** raises `duplication` and leaves `precision` untouched, because a
      block emitted twice is an unchanged set and a doubled multiset.

    **Raw precision is not readable on its own either, so the split ships with it.** Most of
    what a correct conversion emits "unsupported" is the document's own words in an adjacency
    the text layer does not have: all2md orders columns and joins blocks, while the layer
    comes out in PyMuPDF's order, and every disagreement mints n-grams at the seam. On the
    first five articles that accounted for 4.8% of emitted n-grams against 0.5% carrying a
    word the layer never has. `novel_share` is therefore the figure to read, exactly as
    `attainable_recall` rather than raw recall is on the other side.

    Parameters
    ----------
    articles : Iterable
        ``(article_id, blocks, emitted_text, pdf_text)`` tuples, as `measure_recall` takes.
        ``blocks`` is accepted and unused, so both instruments can be driven from one
        sequence rather than two that could drift apart.

    Returns
    -------
    PrecisionReport
        Precision, duplication and the mismatched-article control.

    """
    indexed = []
    for _article_id, _blocks, emitted, pdf_text in articles:
        layer_tokens = normalize(pdf_text)
        indexed.append((ngram_counts(normalize(emitted)), ngram_counts(layer_tokens), set(layer_tokens)))

    supported = resequenced = novel = emitted_total = excess = occurrences = 0
    control_supported = control_emitted = 0
    for position, (emitted_counts, layer, words) in enumerate(indexed):
        other = indexed[(position + 1) % len(indexed)][1]
        for gram, count in emitted_counts.items():
            emitted_total += 1
            occurrences += count
            held = layer.get(gram, 0)
            if held:
                supported += 1
                excess += max(0, count - held)
            elif all(token in words for token in gram):
                resequenced += 1
            else:
                novel += 1
            if other is not layer:
                control_emitted += 1
                control_supported += other.get(gram, 0) > 0

    return PrecisionReport(
        supported=supported,
        resequenced=resequenced,
        novel=novel,
        emitted=emitted_total,
        excess=excess,
        occurrences=occurrences,
        control_supported=control_supported,
        control_emitted=control_emitted,
    )


@dataclass(frozen=True, slots=True)
class BindingReport:
    """Whether a figure's caption reached the figure, rather than merely reaching the output.

    This lane already reports that figure caption *text* survives at close to 100%, because
    `benchmarks.pmc.oracles.walk` yields each ``<fig>``'s caption as an ordinary text block
    and the parser does emit those words. That number is true and it is not the question:
    a caption emitted as free-floating prose scores exactly like one attached to its image.
    What is missing is the binding, and nothing measured it.

    Three counts, because the interesting failures are distinguishable and a single ratio
    would hide which one is happening:

    * ``bound`` -- the caption is carried by an emitted figure. The number to move.
    * ``misfiled`` -- the caption was *found* by the parser and written into the image's
      ``alt_text`` instead. Alt text substitutes for an image for a reader who cannot see
      it; a caption sits beside one. Counting these apart separates "the detector failed"
      from "the detector worked and the AST had nowhere to put the result" (#338), which
      are opposite kinds of defect with opposite fixes.
    * ``present`` -- the caption's words are somewhere in the output. Expected to stay near
      the top whatever the other two do, and reported so that a low ``bound`` cannot be
      misread as lost text.

    Attributes
    ----------
    bound : int
        Ground-truth figures whose caption is carried by an emitted figure.
    misfiled : int
        Ground-truth figures whose caption reached an emitted figure's alt text instead.
    present : int
        Ground-truth figures whose caption text appears anywhere in the output.
    scored : int
        Ground-truth figures with enough n-grams to look for.
    too_short : int
        Figures whose caption is too short to test, reported rather than counted either way.
    images_emitted : int
        `Image` nodes emitted across the corpus. Compared against ``scored``, this is the
        granularity gap: a tiled or multi-panel figure emits several images under one
        caption, measured at 345 rasters for 231 figures on this corpus.
    captioned_emitted : int
        Emitted images carrying a caption at all -- the converse denominator. A parser that
        captioned every image with the same string would score well on ``bound`` alone.
    control_bound : int
        Captions "bound" to a *different* article's figures. The instrument's noise floor.
    control_scored : int
        Captions scored against the mismatched article.

    """

    bound: int
    misfiled: int
    present: int
    scored: int
    too_short: int
    images_emitted: int
    captioned_emitted: int
    control_bound: int
    control_scored: int

    @property
    def binding_rate(self) -> float:
        """Share of testable figures whose caption is attached to a figure in the output."""
        return self.bound / self.scored if self.scored else 0.0

    @property
    def misfiled_rate(self) -> float:
        """Share whose caption was detected but written to alt text instead."""
        return self.misfiled / self.scored if self.scored else 0.0

    @property
    def caption_recall(self) -> float:
        """Share whose caption text survived anywhere -- the number that is already high."""
        return self.present / self.scored if self.scored else 0.0

    @property
    def control_binding_rate(self) -> float:
        """Share of captions 'bound' to the wrong article's figures."""
        return self.control_bound / self.control_scored if self.control_scored else 0.0


def measure_binding(
    articles: Iterable[tuple[str, Sequence[str], Sequence[tuple[str, str]], str]],
) -> BindingReport:
    """Measure whether figure captions are bound to figures.

    Matching is n-gram containment at `RECALL_MIN`, the same rule and threshold
    `measure_recall` uses, so a caption that counts as recovered there and as unbound here
    differs only in where it ended up -- not in how generously it was matched.

    **Scored per ground-truth figure, never per emitted image.** A figure tiled into fifteen
    rasters that all carry the correct caption is one binding, not fifteen; scoring the
    emitted side would report that article as a triumph and an article whose single image
    carries no caption as an equal failure.

    Parameters
    ----------
    articles : Iterable
        ``(article_id, truth_captions, emitted_figures, emitted_text)`` tuples, where
        ``emitted_figures`` are ``(caption, alt_text)`` pairs from the converted AST.

    Returns
    -------
    BindingReport
        Binding, misfiling and caption survival, with the mismatched-article control.

    """
    indexed = [
        (
            [ngrams(normalize(caption)) for caption in truth],
            [(ngrams(normalize(caption)), ngrams(normalize(alt))) for caption, alt in figures],
            ngrams(normalize(emitted_text)),
            len(figures),
            sum(1 for caption, _alt in figures if caption.strip()),
        )
        for _article_id, truth, figures, emitted_text in articles
    ]

    bound = misfiled = present = scored = too_short = 0
    images = captioned = control_bound = control_scored = 0
    for position, (truth, figures, haystack, image_count, captioned_count) in enumerate(indexed):
        images += image_count
        captioned += captioned_count
        # Pair with the neighbour rather than a random article, so the control reproduces
        # exactly on a re-run -- as `measure_recall` does.
        other = indexed[(position + 1) % len(indexed)][1]
        for caption in truth:
            if len(caption) < MIN_NGRAMS:
                too_short += 1
                continue
            scored += 1
            bound += any(emitted and _contained(caption, emitted) for emitted, _alt in figures)
            misfiled += any(alt and _contained(caption, alt) for _emitted, alt in figures)
            present += _contained(caption, haystack)
            if other is not figures:
                control_scored += 1
                control_bound += any(emitted and _contained(caption, emitted) for emitted, _alt in other)

    return BindingReport(
        bound=bound,
        misfiled=misfiled,
        present=present,
        scored=scored,
        too_short=too_short,
        images_emitted=images,
        captioned_emitted=captioned,
        control_bound=control_bound,
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
