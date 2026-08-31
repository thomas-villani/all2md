#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Audit the ground-truth oracle itself, rather than the parser it scores.

Every figure this lane publishes rests on the JATS projection being a faithful account of
what the page prints.  That assumption went unexamined for months and was wrong: the
projection joined every element's text with a space, so the ground truth read ``bla CTX-M``
where the page prints ``blaCTX-M``, and the penalty that produced was several times larger
than the structural defect it was hiding (#470).  These checks exist so that the next such
error is found by running something rather than by noticing.

They read only the cached corpus -- JATS and the PDF's own text layer -- so none of them
convert anything, and each takes about a minute over a development corpus.

Usage, from the repository root::

    python -m benchmarks.pmc.audit ceiling
    python -m benchmarks.pmc.audit unscored --manifest benchmarks/pmc/manifest-tuned.json

``--manifest`` defaults to the development corpus and ``--cache`` to the lane's own cache
directory; the corpus must already be materialized (``python -m benchmarks.pmc load``).

**Do not point these at the sealed holdout while developing.**  Reading it is a scoring act,
not a development one -- see :file:`benchmarks/pmc/README.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import fitz  # noqa: E402

from benchmarks.pmc import oracles  # noqa: E402
from benchmarks.pmc.alignment import MIN_NGRAMS, ngrams, normalize  # noqa: E402
from benchmarks.pmc.article import RECALL_MIN  # noqa: E402
from benchmarks.pmc.corpus import DEFAULT_MANIFEST, _parse_jats, read_manifest  # noqa: E402

DEFAULT_CACHE = HERE / ".cache"

#: Where a block's containment against the PDF text layer is reported.  The bands narrow
#: around ``RECALL_MIN`` because the question that matters is whether that bar slices
#: through a crowd or separates two clear populations.
BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 0.2),
    (0.2, 0.5),
    (0.5, 0.7),
    (0.7, 0.75),
    (0.75, 0.8),
    (0.8, 0.85),
    (0.85, 0.9),
    (0.9, 0.95),
    (0.95, 1.0),
    (1.0, 1.01),
)


class Article(NamedTuple):
    """One cached article: its id and the two files these instruments read."""

    article_id: str
    xml: Path
    pdf: Path


def articles(manifest: Path, cache: Path) -> list[Article]:
    """Return the cached articles a manifest pins, in id order.

    The cache root is keyed by the manifest's own digest, exactly as `corpus.load_corpus`
    keys it, so a manifest edit reads a different directory rather than silently reusing
    the articles selected under the old one.

    Parameters
    ----------
    manifest : Path
        Committed manifest naming the corpus.
    cache : Path
        Cache directory the corpus was materialized into.

    Returns
    -------
    list[Article]
        Every article directory holding both a JATS file and a PDF.

    """
    root = cache / read_manifest(manifest).sha256[:16] / "articles"
    if not root.is_dir():
        raise SystemExit(
            f"corpus not materialized at {root}\n"
            f"run: python -m benchmarks.pmc load --manifest {manifest} --cache {cache}"
        )
    found: list[Article] = []
    for directory in sorted(root.iterdir()):
        xml = next(directory.glob("*.xml"), None)
        pdf = next(directory.glob("*.pdf"), None)
        if xml is not None and pdf is not None:
            found.append(Article(directory.name, xml, pdf))
    return found


def _projected(article: Article) -> tuple[tuple[Any, ...], Any]:
    root, _ = _parse_jats(article.xml.read_bytes())
    return oracles.project_jats(root)


def _page_text(article: Article) -> str:
    with fitz.open(article.pdf) as document:
        return " ".join(page.get_text() for page in document)


def _title_sources(node: Any, ancestors: frozenset[str] = frozenset()) -> Iterator[tuple[str, str]]:
    """Yield ``(what produced it, text)`` for every ``title``-kind block under a node."""
    tag = oracles._tag(node)
    if tag in oracles.SKIPPED:
        return
    if oracles.BLOCKS.get(tag) == "title":
        text = oracles._own_text(node)
        if text:
            if {"ref", "ref-list"} & ancestors:
                where = "a reference-list entry"
            elif {"front", "article-meta"} & ancestors:
                where = "the article's own title"
            elif {"table-wrap", "fig"} & ancestors:
                where = "a float's label"
            elif {"sec", "abstract", "body"} & ancestors:
                where = "a section heading"
            else:
                where = "elsewhere"
            yield where, text
        return
    for child in node:
        yield from _title_sources(child, ancestors | {tag})


def ceiling(corpus: list[Article]) -> None:
    """Report where blocks sit against the attainable bar, per kind.

    ``RECALL_MIN`` is all-or-nothing, so a crowd sitting just either side of it would mean
    the published attainable-recall figures turn on the threshold rather than on the
    output.  A sharply bimodal distribution means they do not.

    Parameters
    ----------
    corpus : list[Article]
        Articles to read.

    """
    shares: dict[str, list[float]] = {}
    for article in corpus:
        blocks, _ = _projected(article)
        page = ngrams(normalize(_page_text(article)))
        for block in blocks:
            grams = ngrams(normalize(block.text))
            if len(grams) >= MIN_NGRAMS:
                shares.setdefault(block.kind, []).append(len(grams & page) / len(grams))

    for kind in sorted(shares):
        values = shares[kind]
        attainable = sum(1 for value in values if value >= RECALL_MIN)
        print(f"\n{kind}: {len(values):,} scored, {attainable:,} attainable ({attainable / len(values):.1%})")
        for low, high in BANDS:
            count = sum(1 for value in values if low <= value < high)
            if not count:
                continue
            label = "exactly 1.0" if low >= 1.0 else f"{low:.2f}-{high:.2f}"
            if low == RECALL_MIN:
                mark = "  <- just over the bar"
            elif high == RECALL_MIN:
                mark = "  <- just under"
            else:
                mark = ""
            print(f"   {label:>12s} {count:6,d} {count / len(values):6.1%}{mark}")


def unscored(corpus: list[Article]) -> None:
    """Report what the ``MIN_NGRAMS`` floor removes, per kind.

    A block under about eight words is never scored, because a two-word block matches by
    accident.  The artifact records the count as ``too_short`` and says nothing about what
    it is.  It is mostly section headings -- the one structure a Markdown converter is most
    obviously judged on.

    Parameters
    ----------
    corpus : list[Article]
        Articles to read.

    """
    total: Counter[str] = Counter()
    short: Counter[str] = Counter()
    words: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for article in corpus:
        blocks, _ = _projected(article)
        for block in blocks:
            total[block.kind] += 1
            if len(ngrams(normalize(block.text))) < MIN_NGRAMS:
                short[block.kind] += 1
                words[block.kind] += len(normalize(block.text))
                examples.setdefault(block.kind, []).append(block.text[:44])

    print(f"{'kind':12s} {'total':>8s} {'unscored':>9s} {'share':>8s} {'mean words':>11s}")
    for kind in sorted(total):
        count = short[kind]
        mean = words[kind] / count if count else 0.0
        print(f"{kind:12s} {total[kind]:8,d} {count:9,d} {count / total[kind]:8.1%} {mean:11.1f}")
    scored_total = sum(total.values())
    print(f"{'ALL':12s} {scored_total:8,d} {sum(short.values()):9,d} {sum(short.values()) / scored_total:8.1%}")
    for kind, rows in sorted(examples.items()):
        print(f"\n{kind}: {' | '.join(rows[:8])}")


def titles(corpus: list[Article]) -> None:
    """Attribute every ``title`` block to the ancestor that produced it.

    The published by-kind table has one ``title`` row.  A section heading and a
    reference-list entry both land in it, the floor removes them at very different rates,
    and the row reads as a claim about heading structure.  This says what it is made of.

    Parameters
    ----------
    corpus : list[Article]
        Articles to read.

    """
    scored: Counter[str] = Counter()
    short: Counter[str] = Counter()
    for article in corpus:
        root, _ = _parse_jats(article.xml.read_bytes())
        for where, text in _title_sources(root):
            if len(ngrams(normalize(text))) < MIN_NGRAMS:
                short[where] += 1
            else:
                scored[where] += 1

    print(f"{'title blocks come from':26s} {'scored':>8s} {'unscored':>9s} {'unscored share':>15s}")
    for where in sorted(set(scored) | set(short)):
        seen, missed = scored[where], short[where]
        print(f"{where:26s} {seen:8,d} {missed:9,d} {missed / (seen + missed):15.1%}")
    print(f"{'ALL':26s} {sum(scored.values()):8,d} {sum(short.values()):9,d}")


def duplicates(corpus: list[Article]) -> None:
    """Count truth blocks repeating another block's exact text in the same article.

    Scoring is set containment per block, so a repeat is checked twice against the same
    output and gets the same verdict both times: it double-weights rather than distorts.
    Reported so that stays a measured claim rather than an assumption.

    Parameters
    ----------
    corpus : list[Article]
        Articles to read.

    """
    scored = repeats = 0
    pairs: Counter[str] = Counter()
    for article in corpus:
        blocks, _ = _projected(article)
        seen: dict[str, str] = {}
        for block in blocks:
            if len(ngrams(normalize(block.text))) < MIN_NGRAMS:
                continue
            scored += 1
            key = " ".join(normalize(block.text))
            if key in seen:
                repeats += 1
                pairs[" + ".join(sorted((seen[key], block.kind)))] += 1
            else:
                seen[key] = block.kind

    print(
        f"{repeats} of {scored:,} scored blocks ({repeats / scored:.2%}) repeat another "
        f"block's exact text in the same article"
    )
    for kinds, count in pairs.most_common():
        print(f"   {kinds}: {count}")


def unprintable(corpus: list[Article]) -> None:
    """Report projected words the PDF's own text layer never holds.

    ``coverage`` is reported rather than asserted, so a projection claiming words the page
    does not show is invisible in the published figures and only deflates every tool's
    recall.  Most of what this finds -- ORCID digits, institution identifiers, licence URLs
    -- sits in blocks that fail the ceiling anyway, which is what the ceiling is for.

    Parameters
    ----------
    corpus : list[Article]
        Articles to read.

    """
    rows: list[tuple[str, int, int, list[str]]] = []
    for article in corpus:
        _, projection = _projected(article)
        page = set(normalize(_page_text(article)))
        truth = normalize(" ".join(projection.text_blocks))
        missing = [word for word in truth if word not in page]
        rows.append((article.article_id, len(truth), len(missing), missing))

    rows.sort(key=lambda row: -row[2] / max(row[1], 1))
    print(f"{'article':18s} {'truth':>8s} {'absent':>7s} {'share':>7s}   examples")
    for name, truth_words, absent, missing in rows[:15]:
        sample = " ".join(dict.fromkeys(missing))[:82]
        print(f"{name:18s} {truth_words:8,d} {absent:7,d} {absent / max(truth_words, 1):7.1%}   {sample}")

    total_truth = sum(row[1] for row in rows)
    total_absent = sum(row[2] for row in rows)
    print(
        f"\n{len(rows)} articles: {total_absent:,} of {total_truth:,} projected words "
        f"({total_absent / total_truth:.3%}) are absent from the PDF's own text layer"
    )

    shape: Counter[str] = Counter()
    for _name, _truth_words, _absent, missing in rows:
        for word in missing:
            if re.fullmatch(r"\d+", word):
                shape["a bare number"] += 1
            elif len(word) == 1:
                shape["a single character"] += 1
            elif re.search(r"\d", word):
                shape["mixed letters and digits"] += 1
            else:
                shape["a word"] += 1
    print("\nshape of the absent words:")
    for kind, count in shape.most_common():
        print(f"   {kind:26s} {count:8,d} {count / total_absent:7.1%}")


CHECKS: dict[str, Callable[[list[Article]], None]] = {
    "ceiling": ceiling,
    "duplicates": duplicates,
    "titles": titles,
    "unprintable": unprintable,
    "unscored": unscored,
}


def main(argv: list[str] | None = None) -> int:
    """Run one audit over a materialized corpus."""
    parser = argparse.ArgumentParser(prog="python -m benchmarks.pmc.audit", description=__doc__)
    parser.add_argument("check", choices=sorted(CHECKS), help="which audit to run")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="corpus manifest")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="cache directory")
    args = parser.parse_args(argv)

    corpus = articles(args.manifest, args.cache)
    print(f"{args.check}: {len(corpus)} articles from {args.manifest.name}\n", flush=True)
    CHECKS[args.check](corpus)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
