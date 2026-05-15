"""CLI orchestrator for the all2md corpus benchmark.

Examples
--------
Run the whole pipeline (download, benchmark, report):

    python -m benchmarks.corpus.run

Just download (or refresh the cache):

    python -m benchmarks.corpus.run download

Benchmark only PDFs from arxiv and PMC, capping at 10 docs:

    python -m benchmarks.corpus.run --sources arxiv,pmc --max-docs 10

Re-render the report from the latest results JSON:

    python -m benchmarks.corpus.run report

"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .benchmark import latest_results, run_benchmark, write_results
from .download import fetch_all, load_cached, load_manifest
from .report import write_report

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "corpus.toml"
DEFAULT_CACHE = HERE / ".cache"
DEFAULT_RESULTS = HERE / "results"


def _split_csv(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.corpus.run", description=__doc__)
    p.add_argument(
        "mode",
        nargs="?",
        choices=("all", "download", "benchmark", "report"),
        default="all",
        help="Stage of the pipeline to run (default: all).",
    )
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to corpus.toml")
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="Where to cache downloaded docs")
    p.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS, help="Where to write JSON + report")
    p.add_argument("--sources", help="Comma-separated source names (default: all)")
    p.add_argument("--formats", help="Comma-separated formats to include (default: all)")
    p.add_argument("--max-docs", type=int, default=None, help="Cap total docs benchmarked")
    p.add_argument("--max-size-mb", type=float, default=None, help="Skip docs larger than this")
    p.add_argument(
        "--results-file",
        type=Path,
        default=None,
        help="(report mode) Specific results JSON to render. Defaults to the most recent.",
    )
    return p


def _do_download(args: argparse.Namespace) -> dict:
    manifest = load_manifest(args.manifest)
    return fetch_all(
        manifest,
        cache_root=args.cache_dir,
        source_filter=_split_csv(args.sources),
        format_filter=_split_csv(args.formats),
    )


def _do_benchmark(args: argparse.Namespace, items_by_source: dict) -> Path:
    results = run_benchmark(
        items_by_source,
        cache_root=args.cache_dir,
        max_size_mb=args.max_size_mb,
        max_docs=args.max_docs,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.results_dir / f"results_{timestamp}.json"
    write_results(results, out)
    print(f"Wrote {len(results)} result(s) to {out}", flush=True)
    return out


def _do_report(args: argparse.Namespace, results_path: Path | None = None) -> Path:
    if results_path is None:
        results_path = args.results_file or latest_results(args.results_dir)
    if results_path is None or not results_path.exists():
        print("No results JSON found. Run `benchmark` first.", file=sys.stderr)
        sys.exit(2)
    out = results_path.with_suffix(".md")
    write_report(results_path, out)
    print(f"Wrote report to {out}", flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    items: dict = {}
    if args.mode in ("download", "all"):
        items = _do_download(args)
    elif args.mode == "benchmark":
        manifest = load_manifest(args.manifest)
        items = load_cached(
            manifest,
            cache_root=args.cache_dir,
            source_filter=_split_csv(args.sources),
            format_filter=_split_csv(args.formats),
        )
        empty = [name for name, lst in items.items() if not lst]
        if empty:
            print(
                f"No cache for: {', '.join(empty)}. Run `download` first.",
                file=sys.stderr,
            )

    if args.mode == "download":
        return 0

    results_path: Path | None = None
    if args.mode in ("benchmark", "all"):
        results_path = _do_benchmark(args, items)

    if args.mode in ("report", "all"):
        _do_report(args, results_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
