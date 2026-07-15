"""Cold-start latency benchmark for all2md.

Unlike the corpus benchmark (``benchmarks/corpus/``), which warms imports once and
then times *in-process* conversions, this harness measures **cold start**: every
sample spawns a fresh Python interpreter, so it captures interpreter startup +
``import all2md`` + CLI parser-build cost the way a user pays it on each CLI
invocation. That makes it the guard for the startup wins (short-circuiting
``--version``/``--about``, the options-import fix, and the ``get_type_hints``
cache) so they can't silently regress.

Scenarios
---------
- ``baseline`` - bare interpreter (``python -c pass``); the floor to subtract.
- ``import``   - ``python -c "import all2md"``; package import cost alone.
- ``--version``- ``python -m all2md --version``; should sit near ``import`` once
  the parser build is short-circuited.
- ``--help``   - ``python -m all2md --help``; legitimately builds the full parser.
- ``convert``  - ``python -m all2md <small.md>``; a tiny end-to-end conversion.

Usage
-----
Print a table (5 samples per scenario)::

    python -m benchmarks.startup

More samples for tighter numbers, and persist the raw JSON::

    python -m benchmarks.startup --repeat 9 --out benchmarks/startup_results/run.json

Each scenario runs one discarded warmup (to take OS file-cache cold reads out of
the numbers) followed by ``--repeat`` timed samples. The headline is the
**minimum** (least noisy, closest to true cost); median and mean are also shown.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# A small but non-trivial Markdown document: heading, emphasis, link, list. Enough
# to exercise the parse -> AST -> render round trip without the timing being
# dominated by document size.
_SAMPLE_MD = "# Title\n\nSome **bold** and _italic_ text with a [link](https://example.com).\n\n- one\n- two\n- three\n"


@dataclass
class ScenarioResult:
    """Timing summary for one cold-start scenario (all times in milliseconds)."""

    name: str
    command: str
    repeat: int
    min_ms: float
    median_ms: float
    mean_ms: float
    over_baseline_ms: float | None
    returncodes: list[int]


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=HERE,
        )
        return out.decode().strip()[:12]
    except Exception:
        return "unknown"


def _machine_info() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor() or platform.machine(),
        "git_commit": _git_commit(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _time_command(cmd: list[str], repeat: int, warmup: int = 1) -> tuple[list[float], list[int]]:
    """Run ``cmd`` in a fresh subprocess ``repeat`` times, returning (durations_s, returncodes).

    ``warmup`` discarded runs precede the timed samples so the numbers reflect a
    warm OS file cache (cold *interpreter*, warm *disk*) rather than one-off
    first-read latency. stdout/stderr are discarded so terminal I/O doesn't skew
    the measurement.
    """
    for _ in range(warmup):
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    durations: list[float] = []
    returncodes: list[int] = []
    for _ in range(repeat):
        start = time.perf_counter()
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        durations.append(time.perf_counter() - start)
        returncodes.append(proc.returncode)
    return durations, returncodes


def _scenarios(sample_md_path: Path) -> list[tuple[str, list[str]]]:
    """(name, command) pairs. ``baseline`` must be first so we can subtract it."""
    py = sys.executable
    return [
        ("baseline", [py, "-c", "pass"]),
        ("import", [py, "-c", "import all2md"]),
        ("--version", [py, "-m", "all2md", "--version"]),
        ("--help", [py, "-m", "all2md", "--help"]),
        ("convert", [py, "-m", "all2md", str(sample_md_path)]),
    ]


def run_startup_benchmark(repeat: int = 5, warmup: int = 1) -> list[ScenarioResult]:
    """Measure every scenario and return per-scenario summaries.

    The ``baseline`` (bare interpreter) minimum is subtracted from each other
    scenario's minimum to give ``over_baseline_ms`` - an estimate of the net cost
    above interpreter startup.
    """
    with tempfile.TemporaryDirectory() as tmp:
        sample_md = Path(tmp) / "sample.md"
        sample_md.write_text(_SAMPLE_MD, encoding="utf-8")

        results: list[ScenarioResult] = []
        baseline_min: float | None = None
        for name, cmd in _scenarios(sample_md):
            print(f"Timing {name} ({repeat} samples)...", flush=True)
            durations, returncodes = _time_command(cmd, repeat=repeat, warmup=warmup)
            durations_ms = [d * 1000.0 for d in durations]
            this_min = min(durations_ms)
            if name == "baseline":
                baseline_min = this_min
                over = None
            else:
                over = this_min - baseline_min if baseline_min is not None else None
            results.append(
                ScenarioResult(
                    name=name,
                    command=" ".join(cmd),
                    repeat=repeat,
                    min_ms=round(this_min, 1),
                    median_ms=round(statistics.median(durations_ms), 1),
                    mean_ms=round(statistics.fmean(durations_ms), 1),
                    over_baseline_ms=round(over, 1) if over is not None else None,
                    returncodes=returncodes,
                )
            )
    return results


def _format_table(results: list[ScenarioResult]) -> str:
    header = f"{'scenario':<12} {'min(ms)':>10} {'median(ms)':>12} {'mean(ms)':>10} {'over base(ms)':>14}"
    lines = [header, "-" * len(header)]
    for r in results:
        over = "-" if r.over_baseline_ms is None else f"{r.over_baseline_ms:.1f}"
        lines.append(f"{r.name:<12} {r.min_ms:>10.1f} {r.median_ms:>12.1f} {r.mean_ms:>10.1f} {over:>14}")
    failed = [r.name for r in results if any(rc != 0 for rc in r.returncodes)]
    if failed:
        lines.append("")
        lines.append(f"WARNING: nonzero exit in scenario(s): {', '.join(failed)}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.startup", description=__doc__)
    p.add_argument("--repeat", type=int, default=5, help="Timed samples per scenario (default: 5)")
    p.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Discarded warmup runs per scenario before timing (default: 1)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write raw results as JSON (machine info + per-scenario samples)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    results = run_startup_benchmark(repeat=args.repeat, warmup=args.warmup)

    print()
    print(_format_table(results))

    if args.out is not None:
        payload = {"machine": _machine_info(), "results": [asdict(r) for r in results]}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote results to {args.out}", flush=True)

    return 1 if any(rc != 0 for r in results for rc in r.returncodes) else 0


if __name__ == "__main__":
    sys.exit(main())
