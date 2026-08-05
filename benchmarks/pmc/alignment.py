"""Locate JATS article blocks on PDF pages, and measure how well that can be done.

This is the feasibility probe behind the page-alignment decision, not the oracle. It
answers one question with evidence: *can article-level ground truth be projected onto
pages cleanly enough to score per page?*

Two properties are deliberate and load-bearing.

**Order-free.** Placement never consults the reading order all2md extracts -- only whether
a page's text contains a block's n-grams. Aligning by extracted order would make page
assignment depend on the very thing the lane grades, and the reading-order metric would
partly be marking its own homework.

**Self-validating.** `measure` scores every block a second time against a *different*
article's pages. A placement rate that does not collapse on that control is measuring
nothing, so the control ships with the tool rather than being a thing someone remembers to
do. Two earlier versions of this probe reported confident, wholly wrong numbers:

- bag-of-words overlap made every page score highly on stopwords alone, reporting 57% of
  blocks as ambiguous;
- joining JATS element text without a separator fused ``<label>Table 2</label>`` onto its
  caption as the token ``2obtained``, corrupting an n-gram at every element boundary and
  making tables look 32% unlocatable when the real figure is 1.4%.

Neither was a property of the corpus. Both looked plausible.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Token n-gram width. Five is long enough that ordinary prose cannot collide by chance --
#: the mismatch control puts the false-placement rate under 1% -- and short enough to
#: survive a line break or a hyphenation fix inside a paragraph.
NGRAM = 5

#: Below this share of a block's n-grams, the best page is not considered a match at all.
PLACEMENT_MIN = 0.30

#: A runner-up page holding at least this share means the block is genuinely on two pages.
#: Adjacent runner-up is an ordinary page break; non-adjacent is a real ambiguity.
RUNNER_UP_MIN = 0.15

#: A page holding at least this share of a block holds the *whole* block, so the block
#: cannot be split across pages no matter what a runner-up scores. Checking the runner-up
#: first was a real defect: body text reusing a figure caption's wording made 71% of
#: "split" blocks -- and 88% of split figures -- ambiguous when their top page already held
#: 100% of them. Not 1.0, because normalization and de-hyphenation can cost an n-gram or
#: two on a legitimate whole-block match.
COMPLETE_MIN = 0.95

#: Blocks with fewer n-grams than this carry too little text to place, and are reported
#: separately rather than counted as failures.
MIN_NGRAMS = 4

#: Share of a block's distinct tokens a page must hold for `place_by_tokens` to place it.
#: N-gram containment assumes the page renders a block's words in the order JATS declares
#: them, and structured markup breaks that assumption without changing a single word: an
#: ``<element-citation>`` lists source before authors while the page prints authors first,
#: and ``<surname>``/``<given-names>`` invert against the rendered byline. Those blocks are
#: fully present on their page and score zero n-gram containment.
#:
#: Calibrated on 8 articles, not chosen: at 0.65 the fallback recovers 89.1% of the blocks
#: n-gram containment reports as missing, agrees with n-gram placement on 99.0% of the
#: blocks where that method already gives a confident answer, and places only 0.6% of blocks
#: onto a *different article's* pages. Raising it to 0.85 buys nothing -- false placement is
#: already under 1% -- and gives up half the recovered blocks.
TOKEN_PLACEMENT_MIN = 0.65

#: Below this many distinct tokens a bag of words is not distinctive enough to identify a
#: page, whatever share of it matches.
TOKEN_MIN_DISTINCT = 5

#: JATS elements worth placing on a page.
PLACEABLE_TAGS = ("p", "table-wrap", "fig")

VERDICTS = ("clean", "spans", "split", "missing", "too_short")

_WORD = re.compile(r"[a-z0-9]+")
_SOFT_HYPHEN = "­"
_LINE_HYPHEN = re.compile(r"-\s*\n\s*")


@dataclass(frozen=True, slots=True)
class BlockPlacement:
    """Where one JATS block was found in a PDF.

    Attributes
    ----------
    kind : str
        JATS tag, one of `PLACEABLE_TAGS`.
    verdict : str
        ``clean`` (one page wins), ``spans`` (two adjacent pages), ``split`` (two
        non-adjacent pages), ``missing``, or ``too_short``.
    page : int or None
        Zero-based best page; for ``spans``, the earlier of the two.
    runner_up_page : int or None
        Second-best page when one scored above `RUNNER_UP_MIN`.
    top_share : float
        Share of the block's n-grams found on the best page.

    """

    kind: str
    verdict: str
    page: int | None
    runner_up_page: int | None
    top_share: float


@dataclass(frozen=True, slots=True)
class AlignmentReport:
    """Corpus-wide placement measurement, with its own control.

    Attributes
    ----------
    verdicts : dict[str, int]
        Verdict counts over every scored block.
    by_kind : dict[str, dict[str, int]]
        Verdict counts per JATS tag.
    control_verdicts : dict[str, int]
        Verdict counts for the same blocks scored against a different article's pages.
    articles : int
        Articles measured.

    """

    verdicts: dict[str, int]
    by_kind: dict[str, dict[str, int]]
    control_verdicts: dict[str, int]
    articles: int

    @property
    def scored(self) -> int:
        """Blocks that carried enough text to place."""
        return sum(count for verdict, count in self.verdicts.items() if verdict != "too_short")

    @property
    def placeable(self) -> int:
        """Blocks resolved to a page or to an identifiable adjacent pair."""
        return self.verdicts.get("clean", 0) + self.verdicts.get("spans", 0)

    @property
    def control_false_placement(self) -> float:
        """Share of blocks 'placed' against the wrong article -- the instrument's noise floor."""
        scored = sum(count for verdict, count in self.control_verdicts.items() if verdict != "too_short")
        if not scored:
            return 0.0
        placed = self.control_verdicts.get("clean", 0) + self.control_verdicts.get("spans", 0)
        return placed / scored

    def share(self, count: int) -> float:
        """Return ``count`` as a share of scored blocks.

        Parameters
        ----------
        count : int
            Block count to express as a share.

        Returns
        -------
        float
            Fraction in ``[0, 1]``, or ``0.0`` when nothing was scored.

        """
        return count / self.scored if self.scored else 0.0


def normalize(text: str) -> list[str]:
    """Reduce text to comparable lowercase alphanumeric tokens.

    De-hyphenates across line breaks and drops soft hyphens, so a word broken by the
    typesetter still matches the JATS spelling.

    Parameters
    ----------
    text : str
        Raw text from either side of the comparison.

    Returns
    -------
    list[str]
        Token sequence.

    """
    folded = unicodedata.normalize("NFKD", text).lower().replace(_SOFT_HYPHEN, "")
    return _WORD.findall(_LINE_HYPHEN.sub("", folded))


def ngrams(tokens: Sequence[str]) -> set[tuple[str, ...]]:
    """Return the set of token `NGRAM`-grams.

    Parameters
    ----------
    tokens : Sequence[str]
        Normalized tokens.

    Returns
    -------
    set[tuple[str, ...]]
        Distinct n-grams; a set because repetition carries no placement information.

    """
    return {tuple(tokens[index : index + NGRAM]) for index in range(len(tokens) - NGRAM + 1)}


def page_ngrams(pdf_path: Path) -> list[set[tuple[str, ...]]]:
    """Index each PDF page by its token n-grams.

    Parameters
    ----------
    pdf_path : pathlib.Path
        PDF to index.

    Returns
    -------
    list[set[tuple[str, ...]]]
        One n-gram set per page, in page order.

    """
    import fitz

    with fitz.open(pdf_path) as document:
        return [ngrams(normalize(page.get_text())) for page in document]


def jats_blocks(root: Any) -> list[tuple[str, str]]:
    """Extract placeable blocks from a parsed JATS tree.

    Element text is joined with a **space**, never concatenated. Concatenation fuses
    ``<label>Table 2</label>`` onto the following caption into a single bogus token and
    corrupts an n-gram at every element boundary -- which made tables look unlocatable
    when they are not.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        Parsed JATS article.

    Returns
    -------
    list[tuple[str, str]]
        ``(tag, text)`` pairs in document order.

    """
    blocks: list[tuple[str, str]] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
        if tag in PLACEABLE_TAGS:
            blocks.append((tag, " ".join(element.itertext())))
    return blocks


def place_block(block: set[tuple[str, ...]], pages: Sequence[set[tuple[str, ...]]]) -> BlockPlacement:
    """Decide which page a block sits on, using content overlap only.

    Parameters
    ----------
    block : set[tuple[str, ...]]
        The block's n-grams.
    pages : Sequence[set[tuple[str, ...]]]
        Per-page n-gram sets, in page order.

    Returns
    -------
    BlockPlacement
        Verdict and supporting shares. ``kind`` is left empty for the caller to fill.

    """
    if len(block) < MIN_NGRAMS or not pages:
        return BlockPlacement("", "too_short", None, None, 0.0)
    # Negate the index so that equal shares break toward the *earliest* page. Without it
    # the sort silently preferred the last page, which is arbitrary; first occurrence is
    # both deterministic and the conventional reading of a duplicated block.
    ranked = sorted(
        ((len(block & page) / len(block), -index) for index, page in enumerate(pages)),
        reverse=True,
    )
    shares = [(share, -negated_index) for share, negated_index in ranked]
    top_share, top_page = shares[0]
    second_share, second_page = shares[1] if len(shares) > 1 else (0.0, None)
    if top_share < PLACEMENT_MIN:
        return BlockPlacement("", "missing", None, None, top_share)
    # Completeness before ambiguity. A page holding essentially all of a block holds the
    # block; another page echoing its wording -- body text restating a figure caption, a
    # running header, a repeated table label -- does not make it two-paged.
    if top_share >= COMPLETE_MIN:
        return BlockPlacement("", "clean", top_page, None, top_share)
    if second_share >= RUNNER_UP_MIN and second_page is not None:
        if abs(top_page - second_page) == 1:
            return BlockPlacement("", "spans", min(top_page, second_page), max(top_page, second_page), top_share)
        return BlockPlacement("", "split", top_page, second_page, top_share)
    return BlockPlacement("", "clean", top_page, None, top_share)


def place_by_tokens(tokens: Sequence[str], pages: Sequence[set[str]]) -> int | None:
    """Place a block by unordered token containment, for blocks whose word order is not the page's.

    Deliberately kept apart from `place_block` rather than folded into it as a fallback: the
    published feasibility numbers describe n-gram containment, and quietly widening the rule
    they were measured with would leave them describing something else. Callers compose the
    two and report which rule placed what.

    Parameters
    ----------
    tokens : Sequence[str]
        The block's normalized tokens.
    pages : Sequence[set[str]]
        Per-page distinct token sets, in page order.

    Returns
    -------
    int or None
        Zero-based page index, or ``None`` when no page holds enough of the block. Ties
        break toward the earliest page, as in `place_block`.

    """
    distinct = set(tokens)
    if len(distinct) < TOKEN_MIN_DISTINCT or not pages:
        return None
    share, negated_index = max((len(distinct & page) / len(distinct), -index) for index, page in enumerate(pages))
    return -negated_index if share >= TOKEN_PLACEMENT_MIN else None


def measure(articles: Iterable[Any]) -> AlignmentReport:
    """Measure placement across a corpus, including the mismatch control.

    Parameters
    ----------
    articles : Iterable
        `benchmarks.pmc.corpus.CorpusArticle` values with readable PDF and XML paths.

    Returns
    -------
    AlignmentReport
        Verdict counts, per-kind breakdown, and the control's false-placement rate.

    """
    from benchmarks.pmc.corpus import _parse_jats

    indexed: list[tuple[str, list[set[tuple[str, ...]]], list[tuple[str, set[tuple[str, ...]]]]]] = []
    for article in articles:
        root, _ = _parse_jats(article.xml_path.read_bytes())
        pages = page_ngrams(article.pdf_path)
        blocks = [(kind, ngrams(normalize(text))) for kind, text in jats_blocks(root)]
        indexed.append((article.article_id, pages, blocks))

    verdicts: Counter[str] = Counter()
    control: Counter[str] = Counter()
    by_kind: dict[str, Counter[str]] = {tag: Counter() for tag in PLACEABLE_TAGS}

    for position, (_article_id, pages, blocks) in enumerate(indexed):
        if not pages:
            continue
        # Pair each article with its neighbour rather than a random one, so the control is
        # deterministic and reproduces exactly on a re-run.
        _, other_pages, _ = indexed[(position + 1) % len(indexed)]
        for kind, block in blocks:
            placement = place_block(block, pages)
            verdicts[placement.verdict] += 1
            by_kind[kind][placement.verdict] += 1
            if other_pages:
                control[place_block(block, other_pages).verdict] += 1

    return AlignmentReport(
        verdicts={verdict: verdicts.get(verdict, 0) for verdict in VERDICTS},
        by_kind={kind: {verdict: counts.get(verdict, 0) for verdict in VERDICTS} for kind, counts in by_kind.items()},
        control_verdicts={verdict: control.get(verdict, 0) for verdict in VERDICTS},
        articles=len(indexed),
    )
