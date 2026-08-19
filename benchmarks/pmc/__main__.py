"""Command line entry point for the PMC born-digital corpus.

``build`` walks the bucket and writes the manifest; it is run by hand and its output is
committed.  ``load`` and ``show`` operate on the committed manifest alone and never list
the bucket, so they are the reproducible half.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from benchmarks.pmc import corpus

DEFAULT_CACHE = Path(__file__).with_name(".cache")


def _build(args: argparse.Namespace) -> int:
    report = corpus.build_manifest(
        Path(args.out),
        workspace=Path(args.cache),
        seeds=corpus.seed_anchors(args.seed_offset),
        per_seed=args.per_seed,
        stride=args.stride,
        max_candidates_per_seed=args.max_candidates,
        progress=None if args.quiet else lambda line: print(line, flush=True),
    )
    print()
    print(f"manifest   : {report.manifest_path}")
    print(f"candidates : {report.candidates}")
    print(f"accepted   : {len(report.accepted)}")
    print("rejected   :")
    for reason, count in sorted(report.rejection_counts.items()):
        print(f"    {reason:20s} {count:4d}")
    # Reported separately from rejections because it is a property of the run, not of any
    # article: a network failure must never be readable as evidence about the corpus.
    print(f"unavailable: {len(report.unavailable)}")
    for article_id, error in sorted(report.unavailable.items()):
        print(f"    {article_id:20s} {error}")
    return 0


def _load(args: argparse.Namespace) -> int:
    snapshot = corpus.load_corpus(
        Path(args.cache),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        limit=args.limit,
        workers=args.workers,
    )
    print(f"manifest   : {snapshot.manifest_path}")
    print(f"pin        : {snapshot.manifest_sha256}")
    print(f"articles   : {len(snapshot.articles)} of {snapshot.expected_articles}")
    print(f"complete   : {snapshot.complete}")
    if snapshot.unavailable:
        print(f"unavailable: {len(snapshot.unavailable)} pinned article(s) the bucket no longer serves")
        for article_id, error in sorted(snapshot.unavailable.items()):
            print(f"    {article_id:20s} {error}")
    total = sum(article.pdf_size_bytes + article.xml_size_bytes for article in snapshot.articles)
    print(f"bytes      : {total:,}")
    return 0


def _show(args: argparse.Namespace) -> int:
    manifest = corpus.read_manifest(
        corpus.DEFAULT_MANIFEST if args.manifest is None else Path(args.manifest),
    )
    print(f"manifest   : {manifest.path}")
    print(f"pin        : {manifest.sha256}")
    print(f"bucket     : {manifest.bucket}")
    print(f"articles   : {len(manifest.articles)}")
    print(f"rejected   : {len(manifest.rejected)}")
    print("licences   :")
    for licence, count in sorted(Counter(a.licence for a in manifest.articles).items()):
        print(f"    {count:4d}  {licence}")
    print("rejections :")
    for reason, count in sorted(Counter(manifest.rejected.values()).items()):
        print(f"    {count:4d}  {reason}")
    return 0


def _characterize(args: argparse.Namespace) -> int:
    from benchmarks.pmc.characterize import characterize

    snapshot = corpus.load_corpus(
        Path(args.cache),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        limit=args.limit,
        workers=args.workers,
    )
    result = characterize(snapshot)
    print(f"articles                   : {len(result.articles)}")
    print(f"pages                      : {result.pages}")
    if result.unreadable:
        print(f"unreadable                 : {', '.join(result.unreadable)}")
    for label, pages in (
        ("text layer", result.text_layer_pages),
        ("vector drawings", result.vector_drawing_pages),
        ("one full-page image (scan)", result.scan_shape_pages),
    ):
        print(f"  {label:26s} {pages:5d} / {result.pages} = {result.share(pages):6.1%}")
    print(f"drawings per page (median) : {result.median_drawings_per_page:.1f}")
    for label, pages in sorted(result.pages_by_drawing_count.items()):
        print(f"  pages with {label:12s}    {pages:5d} = {result.share(pages):6.1%}")
    # One embedded font is the signature of an OCR dump re-typeset into a PDF, which no
    # geometric test can distinguish from a born-digital file.
    print(f"fewest fonts in an article : {result.min_font_count}")
    return 0


def _align(args: argparse.Namespace) -> int:
    from benchmarks.pmc.alignment import measure

    snapshot = corpus.load_corpus(
        Path(args.cache),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        limit=args.limit,
        workers=args.workers,
    )
    report = measure(snapshot.articles)
    print(f"articles   : {report.articles}")
    print(f"blocks     : {report.scored} scored ({report.verdicts['too_short']} too short to place)")
    print("placement  :")
    for verdict in ("clean", "spans", "split", "missing"):
        count = report.verdicts[verdict]
        print(f"    {verdict:9s} {count:6d}  {report.share(count):6.1%}")
    print(f"  placeable (clean + spans): {report.share(report.placeable):.1%}")
    print()
    # Ships with the tool rather than being remembered: a placement rate is meaningless
    # unless the same method fails on the wrong article.
    print("control    : same blocks against a DIFFERENT article's pages")
    print(f"    false placement rate    {report.control_false_placement:6.1%}  (want ~0%)")
    print()
    print("by kind    :")
    for kind, counts in report.by_kind.items():
        scored = sum(count for verdict, count in counts.items() if verdict != "too_short")
        if not scored:
            continue
        row = "  ".join(f"{v}={counts[v] / scored:5.1%}" for v in ("clean", "spans", "split", "missing"))
        print(f"    {kind:11s} n={scored:5d}  {row}")
    return 0


def _score(args: argparse.Namespace) -> int:
    from benchmarks.pmc.benchmark import run, write_result

    snapshot = corpus.load_corpus(
        Path(args.cache),
        manifest_path=None if args.manifest is None else Path(args.manifest),
        limit=args.limit,
        workers=args.workers,
    )
    payload = run(snapshot, all2md_commit=args.commit)
    if args.out:
        print(f"written    : {write_result(payload, Path(args.out))}")

    corpus_facts = payload["corpus"]
    projection = payload["projection"]
    print(f"pin        : {payload['provenance']['corpus_pin']}")
    print(f"articles   : {corpus_facts['articles_converted']} of {corpus_facts['articles_scored']} converted")
    if corpus_facts["articles_unavailable"]:
        # Beside the article count, not in a footer: every number below it is computed over
        # a smaller corpus than the pin names.
        print(
            f"  withdrawn: {len(corpus_facts['articles_unavailable'])} pinned article(s) no longer "
            f"served: {', '.join(corpus_facts['articles_unavailable'])}"
        )
    print(f"pages      : {corpus_facts['pages_scored']} scored")
    print(f"coverage   : {corpus_facts['coverage']['median']:.2f} median ground-truth words per PDF word")
    print(
        f"tables     : {corpus_facts['tables_emitted']} emitted against "
        f"{corpus_facts['tables_expected']} expected, on "
        f"{corpus_facts['pages_with_emitted_table']} of {corpus_facts['pages_with_expected_table']} page(s)"
    )
    print()
    print("projection : how each ground-truth block reached a page")
    for name, count in projection["assignments"].items():
        print(f"    {name:11s} {count:6d}")
    print(f"  error budget (excluded from every page score): {projection['error_budget']:.1%}")
    if projection["excluded_reasons"]:
        print(f"  excluded because: {projection['excluded_reasons']}")
    print()
    print("dimensions : own score, then the same truth against the WRONG page, then the gap")
    header = f"    {'dimension':34s} {'mean':>7s} {'median':>7s} {'wrong':>7s} {'gap':>7s}"
    print(f"{header}  {'reversed':>9s} {'halved':>7s}")
    for name, summary in payload["dimensions"].items():
        drop = summary.get("mutation_drop", {})
        flag = "  <- ungateable" if "ungateable" in summary else ""
        print(
            f"    {name:34s} {summary['mean']:7.3f} {summary['median']:7.3f} "
            f"{summary.get('control_mean', 0.0):7.3f} {summary.get('discrimination', 0.0):7.3f}  "
            f"{drop.get('reversed', 0.0):9.3f} {drop.get('halved', 0.0):7.3f}{flag}"
        )
    print()
    recall = payload["article_recall"]
    print("whole-article recall: did the text survive anywhere in the output")
    print(f"    raw recall        {recall['recall']:6.1%} of {recall['scored']} blocks")
    # Much of a JATS article cannot be recovered by any parser, because the markup records
    # words in an order the page never prints. Raw recall against that is unreadable.
    print(f"    attainable        {recall['ceiling']:6.1%}  (the PDF's own text layer reproduces this much)")
    print(f"    of what's attainable {recall['attainable_recall']:6.1%}  <- the number worth reading")
    if recall["control_scored"]:
        print(f"    wrong article     {recall['control_recall']:6.1%}  (want ~0%)")
    else:
        # A 0.0% with no denominator behind it would read exactly like a passing control.
        print("    wrong article        n/a  (needs more than one article to have a control)")
    for kind, counts in recall["by_kind"].items():
        print(
            f"      {kind:12s} attainable {counts['attainable']:5d}/{counts['scored']:<5d}"
            f"   recovered {counts['attainable_recall']:6.1%} of those"
        )
    print()
    precision = payload["article_precision"]
    # Printed next to recall, not in its own section: read alone, recall rewards emitting the
    # raw text layer and precision rewards emitting nothing.
    print("whole-article precision: did the output say anything the document does not")
    print(f"    supported         {precision['precision']:6.1%} of {precision['emitted']} emitted n-grams")
    # Most of the remainder is the document's own words in an adjacency the text layer does
    # not have, which is what ordering columns and joining blocks is *for*.
    print(
        f"    resequenced       {precision['resequenced'] / max(precision['emitted'], 1):6.1%}"
        "  (the document's words, new adjacency)"
    )
    print(f"    novel             {precision['novel_share']:6.1%}  <- the number worth reading")
    print(f"    duplication       {precision['duplication']:6.1%}  (supported text emitted more than once)")
    if precision["control_emitted"]:
        print(f"    wrong article     {precision['control_precision']:6.1%}  (want ~0%)")
    else:
        print("    wrong article        n/a  (needs more than one article to have a control)")
    if payload["ocr_articles"]:
        print()
        print(f"OCR fired on {len(payload['ocr_articles'])} article(s): {payload['ocr_articles']}")
    if payload["conversion_failures"]:
        print()
        print(f"failures   : {payload['conversion_failures']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the PMC corpus command line.

    Parameters
    ----------
    argv : list[str] or None, optional
        Argument vector, defaulting to ``sys.argv[1:]``.

    Returns
    -------
    int
        Process exit status.

    """
    parser = argparse.ArgumentParser(prog="benchmarks.pmc", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="walk the bucket and write a pinned manifest")
    build.add_argument("--out", default=str(corpus.DEFAULT_MANIFEST), help="manifest path to write")
    build.add_argument("--cache", default=str(DEFAULT_CACHE), help="workspace for candidate downloads")
    build.add_argument("--per-seed", type=int, default=3, help="articles to accept per ID-range seed")
    build.add_argument("--stride", type=int, default=corpus.DEFAULT_STRIDE, help="take every Nth listed prefix")
    build.add_argument(
        "--seed-offset",
        type=int,
        default=0,
        help=(
            "shift every seed anchor by N PMCIDs; a nonzero offset walks bucket regions "
            "the committed manifest never touched, which is how a held-out corpus is drawn"
        ),
    )
    build.add_argument("--max-candidates", type=int, default=60, help="give up on a seed after N candidates")
    build.add_argument("--quiet", action="store_true", help="suppress per-candidate progress")
    build.set_defaults(handler=_build)

    load = subparsers.add_parser("load", help="materialize and verify the committed corpus")
    load.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    load.add_argument("--cache", default=str(DEFAULT_CACHE), help="cache directory")
    load.add_argument("--limit", type=int, default=None, help="evenly spaced subset size")
    load.add_argument("--workers", type=int, default=8, help="concurrent download workers")
    load.set_defaults(handler=_load)

    characterize = subparsers.add_parser(
        "characterize",
        help="measure what the built corpus contains, independently of the selection filter",
    )
    characterize.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    characterize.add_argument("--cache", default=str(DEFAULT_CACHE), help="cache directory")
    characterize.add_argument("--limit", type=int, default=None, help="evenly spaced subset size")
    characterize.add_argument("--workers", type=int, default=8, help="concurrent download workers")
    characterize.set_defaults(handler=_characterize)

    align = subparsers.add_parser(
        "align",
        help="measure whether JATS blocks can be projected onto PDF pages, with its own control",
    )
    align.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    align.add_argument("--cache", default=str(DEFAULT_CACHE), help="cache directory")
    align.add_argument("--limit", type=int, default=None, help="evenly spaced subset size")
    align.add_argument("--workers", type=int, default=8, help="concurrent download workers")
    align.set_defaults(handler=_align)

    score = subparsers.add_parser(
        "score",
        help="score all2md against the corpus page by page, with the mismatch and mutation controls",
    )
    score.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    score.add_argument("--cache", default=str(DEFAULT_CACHE), help="cache directory")
    score.add_argument("--limit", type=int, default=None, help="evenly spaced subset size")
    score.add_argument("--workers", type=int, default=8, help="concurrent download workers")
    score.add_argument("--out", default=None, help="write the evidence payload here")
    score.add_argument("--commit", default="unknown", help="all2md commit being scored")
    score.set_defaults(handler=_score)

    show = subparsers.add_parser("show", help="summarize the committed manifest without any network access")
    show.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    show.set_defaults(handler=_show)

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except corpus.CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
