"""Project article-level JATS ground truth onto the PDF pages that render it.

`benchmarks.pmc.alignment` established that this is possible -- 95.7% of blocks resolve to
a page or an adjacent pair, measured with a mismatch control that puts false placement below
1%. This module does the projection for real, and handles the three cases the probe only
counted.

**Blocks that cross a page break are split, not double-counted.** The decided policy is that
a spanning block belongs to both its pages, but *belonging* to a page and *being scored
whole against* it are different things: a paragraph broken across a break has half its text
on each side, so scoring the whole paragraph against both pages would guarantee a mismatch
on both. The split point comes from the same n-gram evidence as the placement -- the last
token whose n-gram is still on the earlier page -- and when the token stream cannot be
mapped back onto the raw text the block falls back to counting whole on both pages, which
is counted rather than hidden.

**Blocks too short to place inherit a page.** A section heading is three words; it has no
five-grams, so containment cannot place it. It is first looked for as an exact phrase, which
resolves the distinctive ones, and otherwise takes the page of the next block that *was*
placed. Typesetting supports that fallback: a heading is kept with the text it introduces,
so the next block's page is the heading's page except in the rare orphan.

**Blocks that do not resolve are excluded and counted.** They are the lane's error budget.
Dropping them silently would let the alignment's failures read as the parser's.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from benchmarks.pmc.alignment import NGRAM, ngrams, normalize, place_block, place_by_tokens
from benchmarks.pmc.oracles import JatsBlock

#: Word pattern used to map a token index back to a character offset in the raw text. It
#: must agree with `benchmarks.pmc.alignment.normalize` on token *count*; when it does not,
#: the split is abandoned rather than applied at the wrong place.
_RAW_WORD = re.compile(r"[A-Za-z0-9]+")

#: How a block came to sit on a page, plus the bucket for those that never did.
ASSIGNMENTS = ("clean", "spans", "tokens", "phrase", "inherited", "excluded")


@dataclass(frozen=True, slots=True)
class PageText:
    """One PDF page indexed both ways placement needs it.

    Attributes
    ----------
    grams : set[tuple[str, ...]]
        The page's token n-grams, for containment scoring.
    phrase : str
        The page's tokens joined by spaces, for exact-phrase search of blocks too short to
        have n-grams.
    tokens : set[str]
        The page's distinct tokens, for the order-free fallback.

    """

    grams: set[tuple[str, ...]]
    phrase: str
    tokens: set[str]


@dataclass(frozen=True, slots=True)
class PlacedBlock:
    """One ground-truth block assigned to one page.

    Attributes
    ----------
    block : JatsBlock
        The block, with ``text`` narrowed to the portion this page renders when it was split
        across a page break.
    order : int
        Index in JATS document order, so a page's blocks can be restored to article order.
    assignment : str
        One of `ASSIGNMENTS`, never ``excluded``.

    """

    block: JatsBlock
    order: int
    assignment: str


@dataclass(frozen=True, slots=True)
class PageAssignment:
    """Ground truth projected onto a PDF's pages.

    Attributes
    ----------
    pages : tuple[tuple[PlacedBlock, ...], ...]
        Blocks per page in JATS document order, one entry per PDF page.
    assignments : Mapping[str, int]
        Counts per `ASSIGNMENTS` category.
    excluded : tuple[str, ...]
        Placement verdicts of the blocks that could not be placed, in document order.
    unsplit_spans : int
        Spanning blocks counted whole on both pages because the split point could not be
        mapped back onto the raw text.

    """

    pages: tuple[tuple[PlacedBlock, ...], ...]
    assignments: Mapping[str, int]
    excluded: tuple[str, ...]
    unsplit_spans: int

    @property
    def placed(self) -> int:
        """Blocks that reached at least one page."""
        return sum(count for name, count in self.assignments.items() if name != "excluded")

    @property
    def error_budget(self) -> float:
        """Share of blocks excluded because they would not resolve to a page."""
        total = self.placed + self.assignments.get("excluded", 0)
        return self.assignments.get("excluded", 0) / total if total else 0.0


def index_pages(pdf_path: Path) -> tuple[PageText, ...]:
    """Index every page of a PDF for placement.

    Read with PyMuPDF directly rather than through all2md, so that what a page is held to
    contain can never be changed by a parser change.

    Parameters
    ----------
    pdf_path : pathlib.Path
        PDF to index.

    Returns
    -------
    tuple[PageText, ...]
        One entry per page, in page order.

    """
    import fitz

    with fitz.open(pdf_path) as document:
        indexed = []
        for page in document:
            tokens = normalize(page.get_text())
            indexed.append(PageText(grams=ngrams(tokens), phrase=" ".join(tokens), tokens=set(tokens)))
        return tuple(indexed)


def _split_at_token(text: str, token_index: int) -> tuple[str, str] | None:
    """Split raw text after its ``token_index``-th word, or ``None`` if that cannot be found.

    Parameters
    ----------
    text : str
        Raw block text.
    token_index : int
        Number of leading tokens that belong to the earlier page.

    Returns
    -------
    tuple[str, str] or None
        Earlier and later portions, or ``None`` when the raw word count disagrees with the
        normalized token count, which would put the offset in the wrong place.

    """
    matches = list(_RAW_WORD.finditer(text))
    if len(matches) != len(normalize(text)) or not 0 < token_index < len(matches):
        return None
    cut = matches[token_index - 1].end()
    return text[:cut].strip(), text[cut:].strip()


def _spanning_split(block: JatsBlock, early: set[tuple[str, ...]]) -> tuple[str, str] | None:
    """Find where a spanning block leaves the earlier page.

    Parameters
    ----------
    block : JatsBlock
        Block whose placement verdict was ``spans``.
    early : set[tuple[str, ...]]
        N-grams of the earlier of its two pages.

    Returns
    -------
    tuple[str, str] or None
        Text rendered on the earlier and on the later page, or ``None`` if the block cannot
        be split reliably.

    """
    tokens = normalize(block.text)
    last_on_early = -1
    for index in range(len(tokens) - NGRAM + 1):
        if tuple(tokens[index : index + NGRAM]) in early:
            last_on_early = index
    if last_on_early < 0:
        return None
    return _split_at_token(block.text, min(last_on_early + NGRAM, len(tokens)))


def _phrase_page(block: JatsBlock, pages: Sequence[PageText]) -> int | None:
    """Return the only page containing a short block verbatim, if exactly one does."""
    phrase = " ".join(normalize(block.text))
    if not phrase:
        return None
    hits = [index for index, page in enumerate(pages) if phrase in page.phrase]
    return hits[0] if len(hits) == 1 else None


def assign_pages(blocks: Sequence[JatsBlock], pages: Sequence[PageText]) -> PageAssignment:
    """Project ground-truth blocks onto the pages that render them.

    Parameters
    ----------
    blocks : Sequence[JatsBlock]
        Ground-truth blocks in JATS document order.
    pages : Sequence[PageText]
        Indexed pages from `index_pages`.

    Returns
    -------
    PageAssignment
        Blocks per page, with the accounting for everything that did not place.

    """
    grams = [page.grams for page in pages]
    buckets: list[list[PlacedBlock]] = [[] for _ in pages]
    counts: Counter[str] = Counter()
    excluded: list[str] = []
    unsplit = 0
    #: Short blocks waiting for the next placed block to tell them which page they are on.
    pending: list[tuple[int, JatsBlock]] = []

    def flush(page: int | None) -> None:
        nonlocal pending
        for order, block in pending:
            if page is None:
                counts["excluded"] += 1
                excluded.append("too_short")
            else:
                buckets[page].append(PlacedBlock(block, order, "inherited"))
                counts["inherited"] += 1
        pending = []

    token_sets = [page.tokens for page in pages]
    for order, block in enumerate(blocks):
        tokens = normalize(block.text)
        placement = place_block(ngrams(tokens), grams)
        if placement.verdict == "too_short":
            page = _phrase_page(block, pages)
            if page is None:
                pending.append((order, block))
                continue
            buckets[page].append(PlacedBlock(block, order, "phrase"))
            counts["phrase"] += 1
            continue
        if placement.verdict == "missing":
            # Word order, not presence: a structured citation lists its fields in an order
            # the page does not print, so it holds no n-gram in common with a page that
            # renders every one of its words.
            page = place_by_tokens(tokens, token_sets)
            if page is not None:
                flush(page)
                buckets[page].append(PlacedBlock(block, order, "tokens"))
                counts["tokens"] += 1
                continue
        if placement.page is None or placement.verdict in {"missing", "split"}:
            counts["excluded"] += 1
            excluded.append(placement.verdict)
            continue
        if placement.verdict == "spans" and placement.runner_up_page is not None:
            flush(placement.page)
            early, late = placement.page, placement.runner_up_page
            split = _spanning_split(block, grams[early])
            if split is None:
                unsplit += 1
                buckets[early].append(PlacedBlock(block, order, "spans"))
                buckets[late].append(PlacedBlock(block, order, "spans"))
            else:
                head, tail = split
                # The table's structure stays with the earlier page: splitting a
                # TableProjection would invent a shape that neither page renders.
                buckets[early].append(
                    PlacedBlock(JatsBlock(block.kind, head, block.caption, block.table), order, "spans")
                )
                buckets[late].append(PlacedBlock(JatsBlock("text_block", tail, "", None), order, "spans"))
            counts["spans"] += 1
            continue
        flush(placement.page)
        buckets[placement.page].append(PlacedBlock(block, order, "clean"))
        counts["clean"] += 1

    # Short blocks trailing the last placed block have no successor to inherit from.
    flush(None)
    for bucket in buckets:
        bucket.sort(key=lambda placed: placed.order)
    return PageAssignment(
        pages=tuple(tuple(bucket) for bucket in buckets),
        assignments={name: counts.get(name, 0) for name in ASSIGNMENTS},
        excluded=tuple(excluded),
        unsplit_spans=unsplit,
    )
