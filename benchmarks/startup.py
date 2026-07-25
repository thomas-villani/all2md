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

As a blocking gate, comparing against the committed baseline (this is what CI's
``Cold Start Gate`` job runs)::

    python -m benchmarks.startup --repeat 9 --baseline benchmarks/startup_baseline.json

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


@dataclass
class Comparison:
    """One scenario measured against its committed baseline."""

    scenario: str
    measured_ms: float
    baseline_ms: float | None
    delta_pct: float | None
    status: str
    note: str = ""


def load_baseline(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(results: list[ScenarioResult], baseline: dict, tolerance_pct: float) -> list[Comparison]:
    """Judge each scenario against the baseline.

    Statuses, and why each one is what it is:

    - ``ok``       - within tolerance.
    - ``SLOW``     - a regression; the thing this gate exists for.
    - ``FAST``     - faster than baseline by more than the tolerance. Red on
      purpose: an unrecorded win means the gate is now judging against a number
      nobody stands behind, so it has quietly stopped guarding. Re-record it in
      the commit that earned it. Same reasoning as an XPASS in the roundtrip gate.
    - ``MISSING``  - measured but absent from the baseline, so it is ungated.
    - ``STALE``    - in the baseline but no longer measured; the file has begun
      describing a benchmark that does not exist.
    - ``info``     - the bare-interpreter ``baseline`` scenario, reported but not
      gated. It measures the runner, not us; a VM slow enough to move it will
      have moved everything else too, which is the flake mode the tolerance
      already absorbs.
    """
    expected: dict[str, float] = baseline.get("scenarios", {})
    measured = {r.name: r for r in results}

    comparisons: list[Comparison] = []
    for r in results:
        ref = expected.get(r.name)
        if ref is None:
            comparisons.append(
                Comparison(r.name, r.min_ms, None, None, "MISSING", "not in the baseline, so nothing is gating it")
            )
            continue

        delta_pct = (r.min_ms - ref) / ref * 100.0
        if r.name == "baseline":
            status, note = "info", "bare interpreter; reported as a runner-speed signal, not gated"
        elif delta_pct > tolerance_pct:
            status, note = "SLOW", f"more than {tolerance_pct:.0f}% slower than baseline"
        elif delta_pct < -tolerance_pct:
            status, note = "FAST", f"more than {tolerance_pct:.0f}% faster; re-record the baseline in this commit"
        else:
            status, note = "ok", ""
        comparisons.append(Comparison(r.name, r.min_ms, ref, delta_pct, status, note))

    for name in expected:
        if name not in measured:
            comparisons.append(Comparison(name, 0.0, expected[name], None, "STALE", "in the baseline but not measured"))
    return comparisons


def gate_failed(comparisons: list[Comparison]) -> bool:
    """Whether this run should fail the build.

    Three red paths, so the baseline cannot rot in any direction: a genuine
    regression (``SLOW``), a win nobody recorded (``FAST``), and the baseline
    describing scenarios that no longer line up with the harness
    (``MISSING``/``STALE``).
    """
    return any(c.status in {"SLOW", "FAST", "MISSING", "STALE"} for c in comparisons)


def _runner_looks_slow(comparisons: list[Comparison], tolerance_pct: float) -> bool:
    """Report whether the bare interpreter itself drifted most of the way to the tolerance.

    If so, a ``SLOW`` verdict is more likely to be an unlucky VM than our code -
    worth saying in the failure output, because "the gate is flaky" and "the gate
    is right" look identical from a red X.
    """
    base = next((c for c in comparisons if c.scenario == "baseline"), None)
    return base is not None and base.delta_pct is not None and base.delta_pct > tolerance_pct / 2


def _format_comparison(comparisons: list[Comparison], tolerance_pct: float) -> str:
    header = f"{'scenario':<12} {'measured(ms)':>13} {'baseline(ms)':>13} {'delta':>8}  status"
    lines = [header, "-" * len(header)]
    for c in comparisons:
        base = "-" if c.baseline_ms is None else f"{c.baseline_ms:.1f}"
        delta = "-" if c.delta_pct is None else f"{c.delta_pct:+.1f}%"
        measured = "-" if c.status == "STALE" else f"{c.measured_ms:.1f}"
        suffix = f"  ({c.note})" if c.note else ""
        lines.append(f"{c.scenario:<12} {measured:>13} {base:>13} {delta:>8}  {c.status}{suffix}")
    lines.append("")
    lines.append(f"tolerance: +/-{tolerance_pct:.0f}%")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.startup", description=__doc__)
    p.add_argument("--repeat", type=int, default=5, help="Timed samples per scenario (default: 5)")
    p.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Compare against a committed baseline JSON and exit non-zero on regression",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="Percent deviation allowed either way (default: the baseline file's tolerance_pct)",
    )
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

    if any(rc != 0 for r in results for rc in r.returncodes):
        return 1

    if args.baseline is not None:
        baseline = load_baseline(args.baseline)
        tolerance = args.tolerance if args.tolerance is not None else baseline.get("tolerance_pct", 20.0)
        comparisons = compare_to_baseline(results, baseline, tolerance)

        print()
        print(_format_comparison(comparisons, tolerance))

        if gate_failed(comparisons):
            print("\nSTARTUP GATE FAILED", file=sys.stderr)
            for c in comparisons:
                if c.status in {"SLOW", "FAST", "MISSING", "STALE"}:
                    print(f"  {c.status}: {c.scenario} - {c.note}", file=sys.stderr)
            if _runner_looks_slow(comparisons, tolerance):
                print(
                    "\n  NOTE: the bare interpreter is also well above baseline, so this runner"
                    "\n  looks slow. Re-run before assuming the regression is in all2md - and if"
                    "\n  this recurs, the fix is a wider tolerance or a same-runner A/B against"
                    "\n  the merge base, not deleting the gate.",
                    file=sys.stderr,
                )
            print(
                f"\n  Baseline: {args.baseline} (recorded "
                f"{baseline.get('provenance', {}).get('recorded', 'unknown')}). Regenerate it from the"
                "\n  Startup Runner Variance workflow, never from a dev box.",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
