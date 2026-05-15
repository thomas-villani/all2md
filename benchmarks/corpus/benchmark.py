"""Timing harness for the all2md corpus benchmark.

Iterates the cached items produced by ``download.py``, runs ``all2md.to_markdown``
once per file, and writes a result row per doc to a JSON file.

This is intentionally a single-pass timer (no warmup, no repetition per doc).
With ~250 docs the population is large enough for stratified statistics and the
runtime stays bounded. Per-doc timeout is not enforced - if you have a runaway
file, filter it out with ``--max-size-mb``.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .download import CorpusItem


@dataclass
class DocResult:
    """One conversion measurement."""

    source: str
    format: str
    source_id: str
    filename: str
    size_bytes: int
    duration_seconds: float | None
    output_chars: int | None
    error: str | None
    error_type: str | None


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parent,
        )
        return out.decode().strip()[:12]
    except Exception:
        return "unknown"


def _all2md_version() -> str:
    try:
        from all2md import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _machine_info() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor() or platform.machine(),
        "all2md_version": _all2md_version(),
        "git_commit": _git_commit(),
    }


def _flatten_items(by_source: dict[str, list[CorpusItem]]) -> list[CorpusItem]:
    return [item for items in by_source.values() for item in items]


def run_benchmark(
    items_by_source: dict[str, list[CorpusItem]],
    cache_root: Path,
    max_size_mb: float | None = None,
    max_docs: int | None = None,
) -> list[DocResult]:
    # Warm up: importing all2md + pymupdf is expensive and would skew the first doc.
    print("Warming up all2md...", flush=True)
    from all2md import to_markdown  # noqa: F401 - import for side effects (warmup)

    items = _flatten_items(items_by_source)
    if max_size_mb is not None:
        cutoff = int(max_size_mb * 1024 * 1024)
        before = len(items)
        items = [i for i in items if i.size_bytes <= cutoff]
        if before != len(items):
            print(f"Filtered {before - len(items)} doc(s) larger than {max_size_mb} MB", flush=True)
    if max_docs is not None and len(items) > max_docs:
        items = items[:max_docs]

    print(f"Benchmarking {len(items)} document(s)...", flush=True)
    results: list[DocResult] = []
    for i, item in enumerate(items, 1):
        path = item.resolve(cache_root)
        prefix = f"[{i}/{len(items)}] {item.source}/{item.filename}"
        print(f"{prefix} ({item.size_bytes / 1024:.0f} KB)", flush=True)
        if not path.exists():
            results.append(
                DocResult(
                    source=item.source,
                    format=item.format,
                    source_id=item.source_id,
                    filename=item.filename,
                    size_bytes=item.size_bytes,
                    duration_seconds=None,
                    output_chars=None,
                    error="file missing from cache",
                    error_type="MissingFile",
                )
            )
            continue
        results.append(_time_one(item, path))
    return results


def _time_one(item: CorpusItem, path: Path) -> DocResult:
    from all2md import to_markdown

    start = time.perf_counter()
    try:
        out = to_markdown(path)
        elapsed = time.perf_counter() - start
        chars = len(out) if isinstance(out, str) else None
        return DocResult(
            source=item.source,
            format=item.format,
            source_id=item.source_id,
            filename=item.filename,
            size_bytes=item.size_bytes,
            duration_seconds=elapsed,
            output_chars=chars,
            error=None,
            error_type=None,
        )
    except Exception as e:  # noqa: BLE001 - we want to capture every failure mode
        elapsed = time.perf_counter() - start
        tb = traceback.format_exc(limit=3)
        return DocResult(
            source=item.source,
            format=item.format,
            source_id=item.source_id,
            filename=item.filename,
            size_bytes=item.size_bytes,
            duration_seconds=elapsed,
            output_chars=None,
            error=tb.strip().splitlines()[-1] if tb else str(e),
            error_type=type(e).__name__,
        )


def write_results(results: Iterable[DocResult], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "machine": _machine_info(),
        },
        "results": [asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def latest_results(results_dir: Path) -> Path | None:
    if not results_dir.exists():
        return None
    candidates = sorted(results_dir.glob("results_*.json"))
    return candidates[-1] if candidates else None
