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

from benchmarks.omnidocbench.dimensions import UNGATEABLE as SHARED_UNGATEABLE
from benchmarks.omnidocbench.oracles import PageProjection, project_ast, score_page
from benchmarks.pmc.alignment import MIN_NGRAMS, TOKEN_PLACEMENT_MIN, ngrams, normalize
from benchmarks.pmc.article import (
    RECALL_MIN,
    BindingReport,
    PrecisionReport,
    RecallReport,
    measure_binding,
    measure_precision,
    measure_recall,
    summarize,
)
from benchmarks.pmc.convert import DegradedFact, convert_article, pdf_options
from benchmarks.pmc.oracles import coverage, project_jats, to_projection, walk_figures
from benchmarks.pmc.pages import ASSIGNMENTS, assign_pages, index_pages

#: 2 adds ``article_precision``. A reader that expects 1 would silently see recall with no
#: converse and read it as the whole story, which is the misreading this lane just fixed.
#: 3 adds ``corpus.articles_unavailable``. Under 2 a run that lost pinned articles was
#: indistinguishable from one that scored them all, so every payload without this key has
#: an unknown denominator rather than a complete one.
#: 4 reshapes ``degraded_events`` from a flat count of coalesced event *objects* to
#: occurrences broken down by reason and by how many articles each reached. Under 3 an
#: article rejecting twelve regions counted the same as one rejecting a single region, and
#: the nine reasons behind ``table_rejected`` were indistinguishable -- so the number could
#: not tell an improvement from a regression, because some of those reasons are the parser
#: correctly refusing to grid a page of prose.
#: 5 adds ``figure_binding`` and turns image extraction on. Under 4 the lane inherited the
#: default ``alt_text`` attachment mode, which returns before extraction runs, so it emitted
#: no figures at all and no figure defect was observable -- and the ~100% caption text recall
#: it did report was being read as though it said something about figures, which it does not.
#: 6 records the caption-aware oracle (shared ``project_ast``, oracle schema 2). Under 5 a
#: caption the parser bound to its figure left the projected text stream for a string
#: attribute the oracle never read, so recall *fell* as figure binding improved -- 101 of
#: the 103 "lost" captions on the held-out corpus were in the output the whole time (#406).
#: No payload key changes shape; the measurement underneath every recall figure does.
#: 7 projects every ``<table>`` a ``<table-wrap>`` carries. Under 6 only the first was read,
#: so a wide table the publisher split for the page contributed half its columns to the
#: ground truth and the other half went unasked-for -- 5.3% of this corpus's table text,
#: and every tool that did extract it was charged with emitting text nothing could match.
#: Rows nested inside a cell's own table are no longer counted twice either. A ground-truth
#: change must bump this even though no payload key moves: the artifact is only meaningful
#: against the truth that produced it, and `test_the_reference_was_produced_by_the_current_payload_shape`
#: is what stops a projection edit from landing while the recorded figures quietly describe
#: an older one.
SCHEMA_VERSION = 7
#: 3 = the shared projection admits any container of inline text, by shape rather than by
#: type name, so a node holding inline content with no ``Paragraph`` wrapper is no longer
#: invisible to measurement (#443). ``SCHEMA_VERSION`` deliberately does *not* move with
#: it: this lane projects the PDF parser's AST, which emits no definition lists and wraps
#: every list item in a ``Paragraph``, so no figure in the payload can change. The oracle
#: version tracks the oracle; the lane version tracks what the lane measures.
#: 2 = the shared projection reads caption attributes (see schema 6 above and
#: ``benchmarks.omnidocbench.oracles._semantic_blocks``).
ORACLE_SCHEMA_VERSION = 3

#: Fixed seed: a control that scrambles differently every run cannot be compared across
#: runs, and a resolution change would be indistinguishable from a parser change.
SHUFFLE_SEED = 20260805

#: Dimensions this lane records but must not gate on. Re-exported from the shared declaration
#: rather than restated: this lane refused to gate on `block_structure_similarity` while the
#: scanned-page gate went on comparing it every month, because each decided locally. Kept in
#: the payload because a dimension nobody may gate on is still evidence.
UNGATEABLE: Mapping[str, str] = SHARED_UNGATEABLE


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
    degraded: tuple[DegradedFact, ...]
    duration_seconds: float
    ground_truth_blocks: int
    #: ``<table-wrap>`` elements the publisher deposited as a graphic rather than as markup.
    image_tables: int = 0
    #: What the tables on over-emitting pages are, by `SURPLUS_VERDICTS`.
    surplus_verdicts: Mapping[str, int] = field(default_factory=dict)
    surplus_examined: int = 0
    surplus_in_text_layer: int = 0
    surplus_words_in_text_layer: int = 0
    emitted_text: str = ""
    #: The PDF's own text layer, which bounds what any parser could recover.
    pdf_text: str = ""
    truth_blocks: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    #: Ground-truth ``<fig>`` captions, and the ``(caption, alt_text)`` of every emitted image.
    truth_captions: tuple[str, ...] = field(default_factory=tuple)
    emitted_figures: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    error: str | None = None


def _degraded_summary(evaluations: Sequence[Any]) -> dict[str, Any]:
    """Total each degraded-event kind by occurrence, and break it down by reason.

    ``articles`` is reported beside ``occurrences`` because the two answer different
    questions and diverge sharply here: one article contributed twelve
    ``text_grid_splits_words`` rejections out of twenty-nine measured across twelve
    articles, so a corpus total alone reads as a widespread failure when it can be a
    single pathological document.
    """
    totals: Counter[str] = Counter()
    articles: Counter[str] = Counter()
    reasons: dict[str, Counter[str]] = {}
    reason_articles: dict[str, Counter[str]] = {}
    for result in evaluations:
        for kind in {fact.kind for fact in result.degraded}:
            articles[kind] += 1
        for kind, reason in {(fact.kind, fact.reason) for fact in result.degraded}:
            if reason is not None:
                reason_articles.setdefault(kind, Counter())[reason] += 1
        for fact in result.degraded:
            totals[fact.kind] += fact.occurrences
            if fact.reason is not None:
                reasons.setdefault(fact.kind, Counter())[fact.reason] += fact.occurrences

    summary: dict[str, Any] = {}
    for kind in sorted(totals):
        entry: dict[str, Any] = {"occurrences": totals[kind], "articles": articles[kind]}
        if kind in reasons:
            entry["by_reason"] = {
                reason: {"occurrences": count, "articles": reason_articles[kind][reason]}
                for reason, count in sorted(reasons[kind].items(), key=lambda item: (-item[1], item[0]))
            }
        summary[kind] = entry
    return summary


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
    truth_captions = tuple(figure.caption for figure in walk_figures(root))
    page_count, pdf_words, pdf_text = _pdf_facts(article.pdf_path)
    indexed = index_pages(article.pdf_path)
    assignment = assign_pages(blocks, indexed)
    truth_pairs = tuple((block.kind, block.text) for block in blocks if block.text)
    image_tables = sum(1 for block in blocks if block.image_table)

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
            degraded=(),
            duration_seconds=time.perf_counter() - started,
            ground_truth_blocks=len(blocks),
            image_tables=image_tables,
            truth_blocks=truth_pairs,
            truth_captions=truth_captions,
            error=f"{type(exc).__name__}: {exc}",
        )

    emitted = [project_ast(page) for page in converted.pages]
    evaluations: list[PageEvaluation] = []
    scored_pages: list[tuple[Any, Any]] = []
    for index, placed in enumerate(assignment.pages):
        truth = to_projection(tuple(item.block for item in placed))
        if not truth.text_blocks:
            # A page with no projected ground truth cannot be scored without inventing a
            # verdict. Counted in the payload's page accounting instead.
            continue
        actual = emitted[index]
        scored_pages.append((truth, actual))
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

    surplus_verdicts, surplus_examined, surplus_in_layer, surplus_layer_words = _classify_surplus_tables(
        blocks, pdf_text, scored_pages
    )

    return ArticleEvaluation(
        article_id=article.article_id,
        pages=tuple(evaluations),
        assignments=dict(assignment.assignments),
        unsplit_spans=assignment.unsplit_spans,
        excluded=dict(Counter(assignment.excluded)),
        coverage=coverage(whole, pdf_words),
        ocr_page_fraction=converted.ocr_page_fraction,
        degraded=converted.degraded,
        duration_seconds=time.perf_counter() - started,
        ground_truth_blocks=len(blocks),
        image_tables=image_tables,
        surplus_verdicts=dict(surplus_verdicts),
        surplus_examined=surplus_examined,
        surplus_in_text_layer=surplus_in_layer,
        surplus_words_in_text_layer=surplus_layer_words,
        emitted_text=" ".join(block for page in emitted for block in page.text_blocks),
        pdf_text=pdf_text,
        truth_blocks=truth_pairs,
        truth_captions=truth_captions,
        emitted_figures=tuple((figure.caption, figure.alt_text) for figure in converted.figures),
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


#: Where a surplus table's text sits in the ground truth, by 5-gram containment at
#: `RECALL_MIN` -- the same rule and the same threshold the recall instrument places blocks
#: with, so a verdict here and a verdict there differ only in where the text was looked for.
#:
#: Deliberately *not* extended with an unordered-token fallback, though the alignment module
#: has one. That rule answers "which page of this article holds this block", discriminating
#: among that article's own pages, and it is calibrated for that question. The question here
#: is whether a grid holds table text or prose -- and an article's tables and its prose share
#: a vocabulary by construction, so a bag of words cannot separate them at any threshold. An
#: earlier draft borrowed `TOKEN_PLACEMENT_MIN` anyway and filed 21 of 58 surplus tables as
#: resequenced prose, none of which were prose.
SURPLUS_VERDICTS = ("jats_table", "jats_prose", "outside_jats")


def _share(needle: set, haystack: set) -> float:
    return len(needle & haystack) / len(needle) if needle else 0.0


def _classify_surplus_tables(
    blocks: Sequence[Any],
    pdf_text: str,
    pages: Sequence[tuple[Any, Any]],
) -> tuple[Counter, int, int, int]:
    """Ask what the tables on over-emitting pages actually are.

    The lane publishes `tables_emitted` beside `tables_expected`, and the gap between them
    reads as invention unless something says otherwise. This says otherwise, or fails to.

    Every table emitted on a page carrying more tables than the ground truth expects is
    put to two questions. First, and independently of JATS: does the PDF's own text layer
    hold this table's words? Text in the layer was printed on the page, so a table that
    fails here is the only kind that could have been invented. Second: where does the text
    sit in the ground truth -- inside a ``<table>``, inside prose, or nowhere? Prose
    committed to a grid is the defect this was built to find.

    Only the first question has an unordered form, and only there does it mean anything.
    A grid re-cuts the page's words into cells, so a real table can hold every word the
    text layer holds while sharing few of its 5-grams -- which is why `words_in_text_layer`
    is the invention test and `in_text_layer` is a statement about adjacency. Against JATS
    the same fallback would be worthless: prose committed to a grid keeps its word order
    *inside* the cells, so ordered containment is what detects it, while a bag of words
    cannot tell an article's table vocabulary from its prose vocabulary at all.

    Returns
    -------
    tuple[Counter, int, int, int]
        Verdict counts, tables examined, how many the text layer holds by n-gram
        containment, and how many by word containment. Both are reported because they
        answer different questions: a grid re-cuts the page's words into cells, so a
        real table can hold every word the layer holds while sharing few of its
        5-grams. The word figure is the invention test; the n-gram figure is adjacency.

    """
    truth_table_grams: set = set()
    truth_prose_grams: set = set()
    for block in blocks:
        if not block.text:
            continue
        tokens = normalize(block.text)
        if block.kind == "table":
            truth_table_grams |= ngrams(tokens)
        else:
            truth_prose_grams |= ngrams(tokens)
    layer_tokens = normalize(pdf_text)
    layer_grams, layer_words = ngrams(layer_tokens), set(layer_tokens)

    verdicts: Counter = Counter()
    examined = layer_supported = layer_words_supported = 0
    for truth, actual in pages:
        if len(actual.tables) <= len(truth.tables):
            continue
        for table in actual.tables:
            tokens = normalize(table.text)
            grams, words = ngrams(tokens), set(tokens)
            if len(grams) < MIN_NGRAMS:
                continue
            examined += 1
            if _share(grams, layer_grams) >= RECALL_MIN:
                layer_supported += 1
            if _share(words, layer_words) >= TOKEN_PLACEMENT_MIN:
                layer_words_supported += 1
            if _share(grams, truth_table_grams) >= RECALL_MIN:
                verdicts["jats_table"] += 1
            elif _share(grams, truth_prose_grams) >= RECALL_MIN:
                verdicts["jats_prose"] += 1
            else:
                verdicts["outside_jats"] += 1
    return verdicts, examined, layer_supported, layer_words_supported


def normalize_results(
    *,
    snapshot: Any,
    evaluations: Sequence[ArticleEvaluation],
    recall: RecallReport,
    precision: PrecisionReport,
    binding: BindingReport,
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
    precision : PrecisionReport
        Whether the output says anything the document does not, with its control.
    binding : BindingReport
        Whether figure captions reached the figures they belong to.
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
                # Part of the measurement, not an incidental: under the default `alt_text`
                # the parser emits no images and `figure_binding` is zero by construction.
                "attachment_mode": "base64",
            },
            "placement_config": {
                "token_placement_min": TOKEN_PLACEMENT_MIN,
                "recall_min": RECALL_MIN,
            },
        },
        "corpus": {
            "articles_expected": snapshot.expected_articles,
            # Named separately from `articles_expected - articles_scored`, which a `--limit`
            # produces too: one is a sample the operator asked for, the other is corpus the
            # run was denied.
            "articles_unavailable": sorted(snapshot.unavailable),
            "articles_scored": len(evaluations),
            "articles_converted": sum(1 for result in evaluations if result.error is None),
            "pages_scored": len(pages),
            "ground_truth_blocks": total_blocks,
            # Ground-truth words over PDF words. Far from 1 in either direction means the
            # ground truth does not describe what the page renders, and every content score
            # carries an unearned penalty.
            "coverage": summarize(coverages),
            # Both sides of the table count, because the score alone cannot tell "found
            # nothing" from "found something wrong" -- and the parser's own
            # `table_rejected` events say it often finds a candidate and then rejects it.
            "tables_expected": sum(page.truth_tables for page in pages),
            "tables_emitted": sum(page.emitted_tables for page in pages),
            # Reported beside them because it is a share of the gap between them that no
            # parser change can close: a `<table-wrap>` deposited as a graphic carries no
            # cell text, so it is absent from `tables_expected` while the table it prints is
            # extracted from the page and counted in `tables_emitted`.
            "tables_deposited_as_images": sum(result.image_tables for result in evaluations),
            # What the surplus *is*. Without this the gap between the two counts above can
            # only be read as invention or explained away in prose; here it is measured
            # every run, against the document's own text layer and against JATS.
            "table_surplus": {
                "examined": sum(result.surplus_examined for result in evaluations),
                "in_text_layer": sum(result.surplus_in_text_layer for result in evaluations),
                "words_in_text_layer": sum(result.surplus_words_in_text_layer for result in evaluations),
                "by_source": {
                    verdict: sum(result.surplus_verdicts.get(verdict, 0) for result in evaluations)
                    for verdict in SURPLUS_VERDICTS
                },
            },
            "pages_with_expected_table": sum(1 for page in pages if page.truth_tables),
            "pages_with_emitted_table": sum(1 for page in pages if page.emitted_tables),
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
            # `attainable_recall` is recovered_attainable / attainable, NOT recovered /
            # attainable: a block can be recovered from the output while the PDF's own text
            # layer does not reproduce it, and that block belongs in neither side of the
            # share. Publishing the numerator is what makes the ratio checkable from the
            # artifact alone -- without it a reader divides the two counts that *are*
            # published, gets a different number, and has no way to tell which is wrong.
            "recovered_attainable": recall.recovered_attainable,
            "attainable_recall": recall.attainable_recall,
            "by_kind": {
                kind: {
                    "recovered": counts.recovered,
                    "attainable": counts.attainable,
                    "recovered_attainable": counts.recovered_attainable,
                    "scored": counts.scored,
                    "attainable_recall": counts.attainable_recall,
                }
                for kind, counts in recall.by_kind.items()
            },
            "control_recall": recall.control_recall,
            # Reported so a zero cannot be read as a passing control: with one article there
            # is no other article to score against, and the rate is 0.0% for want of a
            # denominator rather than because nothing false was placed.
            "control_scored": recall.control_scored,
            "discrimination": recall.recall - recall.control_recall,
        },
        # Recall's converse, and it ships beside it rather than somewhere else because either
        # number alone is gameable: the highest recall on this corpus comes from emitting the
        # raw text layer with no structure at all, and the highest precision from emitting
        # almost nothing.
        "article_precision": {
            "precision": precision.precision,
            "supported": precision.supported,
            "emitted": precision.emitted,
            # Unsupported splits two ways, and only one of them is the parser's doing: a
            # resequenced n-gram is the document's own words in an order the text layer does
            # not have, which column ordering and block joins produce by design.
            "resequenced": precision.resequenced,
            "novel": precision.novel,
            "novel_share": precision.novel_share,
            # Occurrences of supported text emitted more often than the page prints it.
            # Separate from precision because a block emitted twice is an unchanged set.
            "duplication": precision.duplication,
            "excess": precision.excess,
            "occurrences": precision.occurrences,
            "control_precision": precision.control_precision,
            # As with recall's control: reported so a zero cannot be misread as passing.
            "control_emitted": precision.control_emitted,
            "discrimination": precision.precision - precision.control_precision,
        },
        # Whether a figure's caption reached the figure, as opposed to reaching the output.
        # Separate from `article_recall` because that instrument already scores these same
        # captions as text blocks and passes them at close to 100% -- which says nothing
        # about binding, and had been standing in for an answer nobody had measured.
        "figure_binding": {
            "binding_rate": binding.binding_rate,
            "bound": binding.bound,
            "scored": binding.scored,
            "too_short": binding.too_short,
            # The caption was found and written to alt text instead. A different defect from
            # not finding it, with a different fix, so it is counted apart rather than
            # folded into the failures.
            "misfiled_rate": binding.misfiled_rate,
            "misfiled": binding.misfiled,
            # Expected to stay high whatever the rest does. Present so a low binding rate
            # cannot be misread as the caption text having been lost.
            "caption_recall": binding.caption_recall,
            "present": binding.present,
            # Emitted images against ground-truth figures: the granularity gap. Multi-panel
            # and tiled figures emit several images under one caption, so these two are not
            # expected to be equal and a ratio of 1 would be the surprising reading.
            "images_emitted": binding.images_emitted,
            "captioned_emitted": binding.captioned_emitted,
            "control_binding_rate": binding.control_binding_rate,
            # As with recall and precision: reported so a zero control cannot be misread as
            # passing when it is really an absent denominator.
            "control_scored": binding.control_scored,
            "discrimination": binding.binding_rate - binding.control_binding_rate,
        },
        "dimensions": dimensions,
        "conversion_failures": failures,
        # Expected to be empty: this corpus was characterized as 0.0% scan-shaped. A
        # non-empty list means the corpus is not what the characterization says it is.
        "ocr_articles": ocr_articles,
        # Occurrences, not event objects, and broken down by the guard that fired. The
        # previous shape counted coalesced *events* -- one per (kind, reason) per article --
        # so an article rejecting twelve regions and one rejecting a single region
        # contributed identically, and the nine reasons behind `table_rejected` were
        # indistinguishable. Neither number could tell an improvement from a regression,
        # because some of those reasons are the parser correctly refusing to grid prose.
        "degraded_events": _degraded_summary(evaluations),
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
    # One sequence drives both instruments, so they cannot end up describing different runs.
    scored = [
        (result.article_id, result.truth_blocks, result.emitted_text, result.pdf_text)
        for result in evaluations
        if result.error is None
    ]
    recall = measure_recall(scored)
    precision = measure_precision(scored)
    binding = measure_binding(
        [
            (result.article_id, result.truth_captions, result.emitted_figures, result.emitted_text)
            for result in evaluations
            if result.error is None
        ]
    )
    return normalize_results(
        snapshot=snapshot,
        evaluations=evaluations,
        recall=recall,
        precision=precision,
        binding=binding,
        all2md_commit=all2md_commit,
        worktree_dirty=worktree_dirty,
        parser_runtime={
            "pymupdf": str(getattr(fitz, "__version__", "unknown")),
            "python": sys.version.split()[0],
        },
    )


def write_result(payload: Mapping[str, Any], path: Path) -> Path:
    """Write the evidence payload as strict JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return path
