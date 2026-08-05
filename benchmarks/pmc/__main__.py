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
    build.add_argument("--max-candidates", type=int, default=60, help="give up on a seed after N candidates")
    build.add_argument("--quiet", action="store_true", help="suppress per-candidate progress")
    build.set_defaults(handler=_build)

    load = subparsers.add_parser("load", help="materialize and verify the committed corpus")
    load.add_argument("--manifest", default=None, help="manifest path (default: the committed one)")
    load.add_argument("--cache", default=str(DEFAULT_CACHE), help="cache directory")
    load.add_argument("--limit", type=int, default=None, help="evenly spaced subset size")
    load.add_argument("--workers", type=int, default=8, help="concurrent download workers")
    load.set_defaults(handler=_load)

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
