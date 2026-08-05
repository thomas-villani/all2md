"""Score all2md against PMC born-digital articles, page by page, with the controls attached.

This is the born-digital counterpart to `benchmarks.omnidocbench.benchmark`, and it scores
the same dimensions through the same oracle so the two are comparable. What differs is the
ground truth: JATS describes an *article*, so every page's truth is projected onto it by
`benchmarks.pmc.pages`, and the projection's failures are reported as an error budget rather
than folded into the parser's score.

Three controls ship inside the run, because each of them has already caught something:

* **Mismatch.** Every page is scored a second time against the *next page of the same
  article* -- the hardest confounder available, sharing running heads, vocabulary and
  sentences that continue across the break. A dimension whose own-page score does not
  clearly beat that is not measuring the page.
* **Mutation.** Every page is scored against deliberately damaged output. A dimension that
  does not move when the output is reversed, scrambled, or halved cannot detect that class
  of defect and must not be gated on. This is how `block_structure_similarity` was found to
  *rise* when half the content is deleted.
* **Input shape.** OCR is left enabled in auto mode. On a born-digital corpus it should
  never fire, and "never fired" is worth having as a measurement that could have failed.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from benchmarks.omnidocbench.oracles import PageProjection, project_ast, score_page
from benchmarks.pmc.alignment import TOKEN_PLACEMENT_MIN
from benchmarks.pmc.article import RECALL_MIN, RecallReport, measure_recall, summarize
from benchmarks.pmc.convert import convert_article, pdf_options
from benchmarks.pmc.oracles import coverage, project_jats, to_projection
from benchmarks.pmc.pages import ASSIGNMENTS, assign_pages, index_pages

SCHEMA_VERSION = 1
ORACLE_SCHEMA_VERSION = 1

#: Fixed seed: a control that scrambles differently every run cannot be compared across
#: runs, and a resolution change would be indistinguishable from a parser change.
SHUFFLE_SEED = 20260805

#: Dimensions this lane records but must not gate on, with the measurement that disqualified
#: each. Kept in the payload because a dimension nobody may gate on is still evidence.
UNGATEABLE: Mapping[str, str] = {
    "block_structure_similarity": (
        "cannot fail usefully: separates own-page from wrong-page output by only ~0.06, and "
        "rises when half the emitted content is deleted, so it rewards dropping blocks"
    ),
}


def _reorder(projection: PageProjection, order: Sequence[int]) -> PageProjection:
    return PageProjection(
        text_blocks=tuple(projection.text_blocks[index] for index in order),
        block_kinds=tuple(projection.block_kinds[index] for index in order),
        tables=projection.tables,
        formulas=projection.formulas,
    )


def _reversed(projection: PageProjection) -> PageProjection:
    return _reorder(projection, list(reversed(range(len(projection.text_blocks)))))


def _shuffled(projection: PageProjection) -> PageProjection:
    order = list(range(len(projection.text_blocks)))
    random.Random(SHUFFLE_SEED).shuffle(order)
    return _reorder(projection, order)


def _halved(projection: PageProjection) -> PageProjection:
    keep = list(range(0, len(projection.text_blocks), 2))
    return PageProjection(
        text_blocks=tuple(projection.text_blocks[index] for index in keep),
        block_kinds=tuple(projection.block_kinds[index] for index in keep),
        tables=projection.tables[: len(projection.tables) // 2],
        formulas=projection.formulas,
    )


#: Damage applied to emitted output, each asking a different question of the score.
MUTATIONS: Mapping[str, Callable[[PageProjection], PageProjection]] = {
    "reversed": _reversed,
    "shuffled": _shuffled,
    "halved": _halved,
}


@dataclass(frozen=True, slots=True)
class PageEvaluation:
    """One page scored against its projected ground truth."""

    article_id: str
    page: int
    scores: Mapping[str, float]
    control_scores: Mapping[str, float]
    mutated: Mapping[str, Mapping[str, float]]
    truth_blocks: int
    truth_tables: int
    emitted_blocks: int
    emitted_tables: int


@dataclass(frozen=True, slots=True)
class ArticleEvaluation:
    """One article's pages, its projection accounting, and its conversion evidence."""

    article_id: str
    pages: tuple[PageEvaluation, ...]
    assignments: Mapping[str, int]
    unsplit_spans: int
    excluded: Mapping[str, int]
    coverage: float
    ocr_page_fraction: float
    degraded_kinds: tuple[str, ...]
    duration_seconds: float
    ground_truth_blocks: int
    emitted_text: str = ""
    #: The PDF's own text layer, which bounds what any parser could recover.
    pdf_text: str = ""
    truth_blocks: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    error: str | None = None


def _pdf_facts(pdf_path: Path) -> tuple[int, int, str]:
    """Return the PDF's page count, word count, and its own text layer."""
    import fitz

    with fitz.open(pdf_path) as document:
        pages = [page.get_text() for page in document]
    text = " ".join(pages)
    return len(pages), len(text.split()), text


def evaluate_article(article: Any, *, options: Any = None) -> ArticleEvaluation:
    """Convert one article and score every page of it.

    Parameters
    ----------
    article : benchmarks.pmc.corpus.CorpusArticle
        Article with validated PDF and XML paths.
    options : PdfOptions or None
        Parser policy; defaults to `benchmarks.pmc.convert.pdf_options`.

    Returns
    -------
    ArticleEvaluation
        Page scores with the projection accounting that qualifies them.

    """
    from benchmarks.pmc.corpus import _parse_jats

    started = time.perf_counter()
    root, _ = _parse_jats(article.xml_path.read_bytes())
    blocks, whole = project_jats(root)
    page_count, pdf_words, pdf_text = _pdf_facts(article.pdf_path)
    indexed = index_pages(article.pdf_path)
    assignment = assign_pages(blocks, indexed)
    truth_pairs = tuple((block.kind, block.text) for block in blocks if block.text)

    try:
        converted = convert_article(article.pdf_path, page_count, options=options or pdf_options())
    except Exception as exc:  # noqa: BLE001 - a failed article stays in every denominator
        return ArticleEvaluation(
            article_id=article.article_id,
            pages=(),
            assignments=dict(assignment.assignments),
            unsplit_spans=assignment.unsplit_spans,
            excluded=dict(Counter(assignment.excluded)),
            coverage=coverage(whole, pdf_words),
            ocr_page_fraction=0.0,
            degraded_kinds=(),
            duration_seconds=time.perf_counter() - started,
            ground_truth_blocks=len(blocks),
            truth_blocks=truth_pairs,
            error=f"{type(exc).__name__}: {exc}",
        )

    emitted = [project_ast(page) for page in converted.pages]
    evaluations: list[PageEvaluation] = []
    for index, placed in enumerate(assignment.pages):
        truth = to_projection(tuple(item.block for item in placed))
        if not truth.text_blocks:
            # A page with no projected ground truth cannot be scored without inventing a
            # verdict. Counted in the payload's page accounting instead.
            continue
        actual = emitted[index]
        # The next page of the same article: a harder control than a different article,
        # because it shares the running head, the vocabulary, and a continuing sentence.
        control = emitted[(index + 1) % len(emitted)] if len(emitted) > 1 else PageProjection((), (), (), ())
        evaluations.append(
            PageEvaluation(
                article_id=article.article_id,
                page=index,
                scores=score_page(truth, actual),
                control_scores=score_page(truth, control),
                mutated={name: score_page(truth, mutate(actual)) for name, mutate in MUTATIONS.items()},
                truth_blocks=len(truth.text_blocks),
                truth_tables=len(truth.tables),
                emitted_blocks=len(actual.text_blocks),
                emitted_tables=len(actual.tables),
            )
        )

    return ArticleEvaluation(
        article_id=article.article_id,
        pages=tuple(evaluations),
        assignments=dict(assignment.assignments),
        unsplit_spans=assignment.unsplit_spans,
        excluded=dict(Counter(assignment.excluded)),
        coverage=coverage(whole, pdf_words),
        ocr_page_fraction=converted.ocr_page_fraction,
        degraded_kinds=converted.degraded_kinds,
        duration_seconds=time.perf_counter() - started,
        ground_truth_blocks=len(blocks),
        emitted_text=" ".join(block for page in emitted for block in page.text_blocks),
        pdf_text=pdf_text,
        truth_blocks=truth_pairs,
    )


def evaluate_corpus(articles: Sequence[Any], *, options: Any = None) -> list[ArticleEvaluation]:
    """Score every article in a corpus snapshot.

    Parameters
    ----------
    articles : Sequence
        `benchmarks.pmc.corpus.CorpusArticle` values.
    options : PdfOptions or None
        Parser policy.

    Returns
    -------
    list[ArticleEvaluation]
        One evaluation per article, in article-id order.

    """
    results = [evaluate_article(article, options=options) for article in articles]
    results.sort(key=lambda result: result.article_id)
    return results


def _dimension(pages: Sequence[PageEvaluation], name: str) -> dict[str, Any] | None:
    values = [page.scores[name] for page in pages if name in page.scores]
    if not values:
        return None
    control = [page.control_scores[name] for page in pages if name in page.control_scores]
    summary: dict[str, Any] = dict(summarize(values))
    summary["direction"] = "higher"
    if control:
        summary["control_mean"] = statistics.fmean(control)
        # The whole point of the control: how far the real score sits above scoring the
        # same ground truth against the wrong page.
        summary["discrimination"] = statistics.fmean(values) - statistics.fmean(control)
    drops: dict[str, float] = {}
    for mutation in MUTATIONS:
        deltas = [
            page.scores[name] - page.mutated[mutation][name]
            for page in pages
            if name in page.scores and mutation in page.mutated and name in page.mutated[mutation]
        ]
        if deltas:
            drops[mutation] = statistics.fmean(deltas)
    summary["mutation_drop"] = drops
    if name in UNGATEABLE:
        summary["ungateable"] = UNGATEABLE[name]
    return summary


def normalize_results(
    *,
    snapshot: Any,
    evaluations: Sequence[ArticleEvaluation],
    recall: RecallReport,
    all2md_commit: str,
    worktree_dirty: bool = False,
    parser_runtime: Mapping[str, str],
) -> dict[str, Any]:
    """Build the deterministic evidence payload for this lane.

    Parameters
    ----------
    snapshot : benchmarks.pmc.corpus.CorpusSnapshot
        The pinned corpus that was scored.
    evaluations : Sequence[ArticleEvaluation]
        Per-article results.
    recall : RecallReport
        Whole-article content recall with its control.
    all2md_commit : str
        Commit the parser was scored at.
    worktree_dirty : bool
        Whether the worktree had uncommitted changes.
    parser_runtime : Mapping[str, str]
        Versions of the libraries the parser used.

    Returns
    -------
    dict
        JSON-ready payload.

    """
    pages = [page for evaluation in evaluations for page in evaluation.pages]
    names = sorted({name for page in pages for name in page.scores})
    dimensions = {name: summary for name in names if (summary := _dimension(pages, name)) is not None}

    assignments: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    for evaluation in evaluations:
        assignments.update(evaluation.assignments)
        excluded.update(evaluation.excluded)
    placed = sum(count for name, count in assignments.items() if name != "excluded")
    total_blocks = placed + assignments.get("excluded", 0)

    failures = {result.article_id: result.error for result in evaluations if result.error is not None}
    ocr_articles = [result.article_id for result in evaluations if result.ocr_page_fraction > 0]
    coverages = [result.coverage for result in evaluations]

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "corpus_pin": snapshot.manifest_sha256,
            "bucket": snapshot.bucket,
            "complete_corpus": snapshot.complete,
            "oracle_schema_version": ORACLE_SCHEMA_VERSION,
            "all2md_commit": all2md_commit,
            "worktree_dirty": worktree_dirty,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "platform": sys.platform,
            "parser_runtime": dict(sorted(parser_runtime.items())),
            "parser_config": {
                "layout_analysis_mode": "enabled",
                "include_page_numbers": True,
                "ocr": {"enabled": True, "mode": "auto", "engine": "tesseract", "dpi": 200},
            },
            "placement_config": {
                "token_placement_min": TOKEN_PLACEMENT_MIN,
                "recall_min": RECALL_MIN,
            },
        },
        "corpus": {
            "articles_expected": snapshot.expected_articles,
            "articles_scored": len(evaluations),
            "articles_converted": sum(1 for result in evaluations if result.error is None),
            "pages_scored": len(pages),
            "ground_truth_blocks": total_blocks,
            # Ground-truth words over PDF words. Far from 1 in either direction means the
            # ground truth does not describe what the page renders, and every content score
            # carries an unearned penalty.
            "coverage": summarize(coverages),
        },
        # The error budget, stated rather than absorbed. These blocks are excluded from every
        # per-page score; article-level recall still counts them.
        "projection": {
            "assignments": {name: assignments.get(name, 0) for name in ASSIGNMENTS},
            "excluded_reasons": dict(sorted(excluded.items())),
            "error_budget": assignments.get("excluded", 0) / total_blocks if total_blocks else 0.0,
            "unsplit_spans": sum(result.unsplit_spans for result in evaluations),
        },
        "article_recall": {
            "recall": recall.recall,
            "recovered": recall.recovered,
            "scored": recall.scored,
            "too_short": recall.too_short,
            # The share of blocks the PDF's own text layer reproduces. Everything above it
            # is unreachable for any parser, so raw recall alone reads as parser loss when
            # it is mostly JATS recording words in an order the page never prints.
            "ceiling": recall.ceiling,
            "attainable": recall.attainable,
            "attainable_recall": recall.attainable_recall,
            "by_kind": {
                kind: {
                    "recovered": counts.recovered,
                    "attainable": counts.attainable,
                    "scored": counts.scored,
                    "attainable_recall": counts.attainable_recall,
                }
                for kind, counts in recall.by_kind.items()
            },
            "control_recall": recall.control_recall,
            "discrimination": recall.recall - recall.control_recall,
        },
        "dimensions": dimensions,
        "conversion_failures": failures,
        # Expected to be empty: this corpus was characterized as 0.0% scan-shaped. A
        # non-empty list means the corpus is not what the characterization says it is.
        "ocr_articles": ocr_articles,
        "degraded_events": dict(
            sorted(Counter(kind for result in evaluations for kind in result.degraded_kinds).items())
        ),
    }


def run(snapshot: Any, *, all2md_commit: str = "unknown", worktree_dirty: bool = False) -> dict[str, Any]:
    """Score a corpus snapshot end to end.

    Parameters
    ----------
    snapshot : benchmarks.pmc.corpus.CorpusSnapshot
        Pinned corpus to score.
    all2md_commit : str
        Commit the parser is being scored at.
    worktree_dirty : bool
        Whether the worktree had uncommitted changes.

    Returns
    -------
    dict
        JSON-ready payload.

    """
    import fitz

    evaluations = evaluate_corpus(snapshot.articles)
    recall = measure_recall(
        [
            (result.article_id, result.truth_blocks, result.emitted_text, result.pdf_text)
            for result in evaluations
            if result.error is None
        ]
    )
    return normalize_results(
        snapshot=snapshot,
        evaluations=evaluations,
        recall=recall,
        all2md_commit=all2md_commit,
        worktree_dirty=worktree_dirty,
        parser_runtime={"pymupdf": getattr(fitz, "__doc__", "") or "", "python": sys.version.split()[0]},
    )


def write_result(payload: Mapping[str, Any], path: Path) -> Path:
    """Write the evidence payload as strict JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return path
