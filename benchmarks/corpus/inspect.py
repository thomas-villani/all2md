"""Quality-review helper - convert a curated subset of corpus docs and save the markdown for human inspection.

Selection strategies
--------------------
- ``slowest``  pick the longest-running successful conversions from a results JSON.
                Use this to find docs that *converted but were slow* - candidates
                for performance investigation, often layout-heavy.
- ``largest``  pick by file size. Doesn't require a results JSON.
- ``random``   uniform sample from the cache. Doesn't require a results JSON.

For each picked doc, writes:
    benchmarks/corpus/inspect/<source>/<stem>.<ext>   (copy of the source)
    benchmarks/corpus/inspect/<source>/<stem>.md      (the converted markdown)
plus a top-level _summary.md indexing everything for easy browsing.

Examples
--------
    python -m benchmarks.corpus.inspect                       # 10 slowest from latest results
    python -m benchmarks.corpus.inspect --criteria largest --n 15
    python -m benchmarks.corpus.inspect --sources pmc --criteria random --n 5
    python -m benchmarks.corpus.inspect --formats pdf --n 8

"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
import traceback
from pathlib import Path

from .benchmark import latest_results
from .download import load_cached, load_manifest

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "corpus.toml"
DEFAULT_CACHE = HERE / ".cache"
DEFAULT_RESULTS = HERE / "results"
DEFAULT_INSPECT = HERE / "inspect"


def _split_csv(s: str | None) -> set[str] | None:
    if not s:
        return None
    return {x.strip() for x in s.split(",") if x.strip()}


def _format_size(b: int) -> str:
    if b >= 1 << 20:
        return f"{b / (1 << 20):.2f} MB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f} KB"
    return f"{b} B"


def _format_seconds(s: float | None) -> str:
    if s is None:
        return "-"
    if s >= 60:
        return f"{s / 60:.1f}m"
    if s >= 1:
        return f"{s:.2f}s"
    return f"{s * 1000:.0f}ms"


def _candidates_from_cache(
    cache_root: Path,
    manifest_path: Path,
    sources: set[str] | None,
    formats: set[str] | None,
) -> list[dict]:
    manifest = load_manifest(manifest_path)
    by_source = load_cached(manifest, cache_root, source_filter=sources, format_filter=formats)
    out: list[dict] = []
    for items in by_source.values():
        for item in items:
            out.append(
                {
                    "source": item.source,
                    "format": item.format,
                    "source_id": item.source_id,
                    "filename": item.filename,
                    "size_bytes": item.size_bytes,
                    "duration_seconds": None,
                }
            )
    return out


def _candidates_from_results(
    results_path: Path,
    sources: set[str] | None,
    formats: set[str] | None,
    require_success: bool,
) -> list[dict]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    rows: list[dict] = list(payload.get("results", []))
    if sources:
        rows = [r for r in rows if r.get("source") in sources]
    if formats:
        rows = [r for r in rows if r.get("format") in formats]
    if require_success:
        rows = [r for r in rows if r.get("error") is None and r.get("duration_seconds") is not None]
    return rows


def _pick(candidates: list[dict], criteria: str, n: int, seed: int | None) -> list[dict]:
    if criteria == "slowest":
        ranked = [c for c in candidates if c.get("duration_seconds") is not None]
        ranked.sort(key=lambda c: c["duration_seconds"], reverse=True)
        return ranked[:n]
    if criteria == "largest":
        ranked = sorted(candidates, key=lambda c: c["size_bytes"], reverse=True)
        return ranked[:n]
    if criteria == "random":
        rng = random.Random(seed) if seed is not None else random.Random()
        if n >= len(candidates):
            return list(candidates)
        return rng.sample(candidates, n)
    raise ValueError(f"unknown criteria {criteria!r}")


def _convert_and_save(picked: dict, cache_root: Path, out_root: Path) -> tuple[bool, float, str | None]:
    """Convert one doc, save markdown + copy source. Returns (ok, elapsed, error)."""
    from all2md import to_markdown

    source = picked["source"]
    filename = picked["filename"]
    src_path = cache_root / source / filename
    if not src_path.exists():
        return False, 0.0, f"missing from cache: {src_path}"

    out_dir = out_root / source
    out_dir.mkdir(parents=True, exist_ok=True)

    src_copy = out_dir / filename
    md_path = out_dir / (Path(filename).stem + ".md")

    if not src_copy.exists():
        shutil.copyfile(src_path, src_copy)

    start = time.perf_counter()
    try:
        text = to_markdown(src_path)
    except Exception as e:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        tb = traceback.format_exc(limit=3)
        md_path.write_text(
            f"# Conversion failed\n\n```\n{tb}\n```\n",
            encoding="utf-8",
        )
        return False, elapsed, f"{type(e).__name__}: {e}"
    elapsed = time.perf_counter() - start
    md_path.write_text(text if isinstance(text, str) else str(text), encoding="utf-8")
    return True, elapsed, None


def _write_summary(
    out_root: Path,
    picked: list[dict],
    inspections: list[dict],
    *,
    criteria: str,
    source_label: str,
) -> Path:
    lines = [
        "# Corpus inspection",
        "",
        f"_{len(picked)} docs picked by `{criteria}` from {source_label}_",
        "",
        "| # | source | format | size | benchmark time | inspect time | source | markdown |",
        "|---:|---|---|---:|---:|---:|---|---|",
    ]
    for i, info in enumerate(inspections, 1):
        rel_src = f"{info['source']}/{info['filename']}"
        rel_md = f"{info['source']}/{Path(info['filename']).stem}.md"
        bench = _format_seconds(info.get("duration_seconds"))
        ins = _format_seconds(info["inspect_seconds"]) if info["ok"] else "fail"
        lines.append(
            f"| {i} | {info['source']} | {info['format']} | {_format_size(info['size_bytes'])} "
            f"| {bench} | {ins} | [src]({rel_src}) | [md]({rel_md}) |"
        )
    lines.append("")
    failures = [i for i in inspections if not i["ok"]]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for f in failures:
            lines.append(f"- `{f['source']}/{f['filename']}`: {f['error']}")
        lines.append("")

    summary_path = out_root / "_summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.corpus.inspect", description=__doc__)
    p.add_argument(
        "--criteria",
        choices=("slowest", "largest", "random"),
        default="slowest",
        help="How to pick docs (default: slowest).",
    )
    p.add_argument("--n", type=int, default=10, help="Number of docs to inspect (default: 10).")
    p.add_argument("--sources", help="Comma-separated source names to filter to.")
    p.add_argument("--formats", help="Comma-separated formats to filter to.")
    p.add_argument(
        "--results-file",
        type=Path,
        default=None,
        help="Specific results JSON to use. Default: most recent in results/. Required for --criteria slowest.",
    )
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    p.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_INSPECT)
    p.add_argument("--seed", type=int, default=None, help="Seed for random selection (default: nondeterministic).")
    p.add_argument("--clean", action="store_true", help="Wipe output-dir before writing.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    sources = _split_csv(args.sources)
    formats = _split_csv(args.formats)

    results_path = args.results_file or latest_results(args.results_dir)
    source_label: str

    if args.criteria == "slowest":
        if results_path is None or not results_path.exists():
            print(
                "--criteria slowest requires a results JSON. Run `benchmark` first or pass --results-file.",
                file=sys.stderr,
            )
            return 2
        candidates = _candidates_from_results(results_path, sources, formats, require_success=True)
        source_label = f"`{results_path.name}`"
    else:
        if results_path and results_path.exists():
            # Prefer the results JSON when available so size/time fields are richer.
            candidates = _candidates_from_results(results_path, sources, formats, require_success=False)
            source_label = f"`{results_path.name}` (cache fallback)"
        else:
            candidates = _candidates_from_cache(args.cache_dir, args.manifest, sources, formats)
            source_label = "cache index"

    if not candidates:
        print("No candidates match the filters.", file=sys.stderr)
        return 1

    picked = _pick(candidates, args.criteria, args.n, args.seed)
    print(f"Picked {len(picked)} doc(s) by {args.criteria} from {source_label}", flush=True)

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Warming up all2md...", flush=True)
    from all2md import to_markdown  # noqa: F401

    inspections: list[dict] = []
    for i, doc in enumerate(picked, 1):
        print(
            f"[{i}/{len(picked)}] {doc['source']}/{doc['filename']} ({_format_size(doc['size_bytes'])})",
            flush=True,
        )
        ok, elapsed, err = _convert_and_save(doc, args.cache_dir, args.output_dir)
        inspections.append(
            {
                **doc,
                "ok": ok,
                "inspect_seconds": elapsed,
                "error": err,
            }
        )
        if not ok:
            print(f"    failed: {err}", flush=True)

    summary = _write_summary(args.output_dir, picked, inspections, criteria=args.criteria, source_label=source_label)
    print(f"Wrote {summary}", flush=True)
    print(f"Browse: {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
