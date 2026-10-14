"""Throughput gate for the per-format benchmarks in ``tests/performance``.

Judges the timings ``pytest tests/performance --benchmark --benchmark-save`` writes
against a committed baseline (``benchmarks/throughput_baseline.json``), and goes red
when one format has become markedly slower **relative to the other formats measured
on the same runner in the same job**.

Why relative, and not the raw milliseconds
------------------------------------------
The variance study on #183 read 1,003 ``format-benchmarks-*`` CI artifacts
(2026-07-26 to 2026-10-12). Three findings set the design:

- **One machine-wide factor explains 88% of the run-to-run variance.** Every format
  moves together; pairwise correlation of the per-run deviations is 0.87.
- **The ubuntu-latest pool has at least three CPU classes**, and they move every raw
  number at once: about 0.57x, 0.73x and 1.0x of the slowest class. A 1.75x swing
  on unchanged code rules out any threshold on raw time that could still see a
  1.5x regression.
- **Dividing each run by the median of its own formats collapses that factor.**
  Raw per-format spread (CV 18-24%, max/min 8-11x) drops to a robust sigma of
  1.5-4%, and the residual shift between CPU classes is at most 9% for any format.

So each format is expressed as its log ratio to the baseline *minus the median log
ratio of every other format in the same pass* (leave-one-out, so a regression in
the format under test cannot dilute its own reference). A uniformly faster or slower
VM cancels out; a format that got slower on its own does not.

Why two passes
--------------
What normalization does not remove is a burst of contention that lands on one
benchmark: the study found 0.5-1% of single runs with one format 1.4-3.4x slow while
the rest of the run was normal. Requiring the slowdown in **every** pass (the
per-format minimum across passes) removed every such false red in the historical
replay, while still catching an injected 1.5x slowdown 99% of the time and 2x every
time. CI therefore runs the suite twice in one job and passes both result files.

Why not the startup gate's agreement rule
-----------------------------------------
``benchmarks/startup.py`` requires the raw and the normalized delta to agree. Its
normalizer is a ~13 ms bare interpreter, whose jitter is what the raw signal guards
against. Here the normalizer is the median of sixteen other formats, which is far
steadier than any one of them. Requiring raw agreement would instead blind the gate
on the faster CPU classes: a 1.5x regression on a 0.57x runner reads 0.86x raw.

What it cannot see
------------------
A regression that slows **every** format by the same factor (the AST core, the
Markdown renderer, a shared dependency) moves the reference along with the format
and cancels, exactly as a CPU-class change does; the two are indistinguishable from
inside one job. The raw machine factor is printed for every pass so such a shift is
visible, but it is not gated. ``benchmarks/startup.py`` and the corpus gate are the
instruments for cross-cutting cost.

Statuses
--------
- ``ok``      - within tolerance in at least one pass.
- ``SLOW``    - slower than the tolerance, relative to the run, in every pass. Red.
- ``fast``    - faster than the tolerance in every pass. Reported, **not** red:
  even with two passes the replay produced false fast readings (0.1-0.3% of runs)
  where it produced no false slow ones, and an unrecorded win only blunts the gate
  for that one format. Re-record the
  baseline in the commit that earned it.
- ``MISSING`` - measured but absent from the baseline, so ungated. Red.
- ``STALE``   - in the baseline but no longer measured. Red.

Usage
-----
Gate two passes against the committed baseline (what CI's ``Throughput Gate`` job
runs)::

    python -m benchmarks.throughput tests/performance/results/*.json --baseline benchmarks/throughput_baseline.json

Record a baseline from CI artifacts (several runs, never a dev box)::

    python -m benchmarks.throughput run1.json run2.json ... --record out.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_TOLERANCE_PCT = 30.0

#: Fewer formats than this and the leave-one-out median is too thin to trust.
MIN_REFERENCE_FORMATS = 5

RED_STATUSES = frozenset({"SLOW", "MISSING", "STALE"})


def metric_key(entry: dict) -> str:
    """Name a benchmark result ``<format>:<fixture filename>``, the baseline's key."""
    name = str(entry["file_path"]).replace("\\", "/").rsplit("/", 1)[-1]
    return f"{entry['format']}:{name}"


def load_pass(path: Path) -> dict[str, float]:
    """Read one ``--benchmark-save`` JSON file into ``{metric: min seconds}``.

    The minimum over iterations is used, as in the startup gate: it is the reading
    least disturbed by whatever else the VM was doing. A second result for the same
    key gets a ``#2`` suffix rather than silently overwriting the first.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for entry in data.get("results", []):
        key = metric_key(entry)
        while key in out:
            key += "#2"
        out[key] = float(entry["min_time"])
    return out


def normalized_log_ratios(measured: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    """Each metric's log ratio to baseline, minus the median of the *other* metrics'.

    Only metrics present on both sides and positive take part. Returns an empty
    dict when there are too few to form a reference.
    """
    common = [k for k in measured if k in baseline and measured[k] > 0 and baseline[k] > 0]
    if len(common) < MIN_REFERENCE_FORMATS + 1:
        return {}
    logs = {k: math.log(measured[k] / baseline[k]) for k in common}
    return {k: v - statistics.median(logs[o] for o in common if o != k) for k, v in logs.items()}


def machine_factor(measured: dict[str, float], baseline: dict[str, float]) -> float | None:
    """Return the median raw ratio to baseline across metrics: how fast this runner was."""
    ratios = [measured[k] / baseline[k] for k in measured if k in baseline and measured[k] > 0 and baseline[k] > 0]
    return statistics.median(ratios) if ratios else None


@dataclass
class Verdict:
    """The gate's judgement of one metric across all passes."""

    metric: str
    status: str
    #: Relative-to-run ratio per pass (1.0 = same share of the run as the baseline).
    ratios: list[float]
    note: str = ""

    @property
    def worst_slow(self) -> float | None:
        return min(self.ratios) if self.ratios else None


def judge(passes: list[dict[str, float]], baseline: dict[str, float], tolerance_pct: float) -> list[Verdict]:
    """Judge every metric over one or more passes against the baseline."""
    limit = math.log1p(tolerance_pct / 100.0)
    per_pass = [normalized_log_ratios(p, baseline) for p in passes]
    measured_keys = sorted(set().union(*passes)) if passes else []

    verdicts: list[Verdict] = []
    for key in measured_keys:
        if key not in baseline:
            verdicts.append(Verdict(key, "MISSING", [], "not in the baseline, so nothing is gating it"))
            continue
        logs = [r[key] for r in per_pass if key in r]
        ratios = [math.exp(v) for v in logs]
        if not logs:
            verdicts.append(Verdict(key, "ok", [], "too few formats measured to form a reference; not judged"))
        elif min(logs) > limit:
            verdicts.append(
                Verdict(
                    key,
                    "SLOW",
                    ratios,
                    f"more than {tolerance_pct:.0f}% slower than baseline relative to the rest of the run, "
                    f"in all {len(logs)} pass(es)",
                )
            )
        elif max(logs) < -limit:
            verdicts.append(Verdict(key, "fast", ratios, "faster than tolerance in every pass; re-record the baseline"))
        else:
            verdicts.append(Verdict(key, "ok", ratios))
    for key in sorted(baseline):
        if not any(key in p for p in passes):
            verdicts.append(Verdict(key, "STALE", [], "in the baseline but not measured"))
    return verdicts


def gate_failed(verdicts: list[Verdict]) -> bool:
    return any(v.status in RED_STATUSES for v in verdicts)


def format_report(
    verdicts: list[Verdict], passes: list[dict[str, float]], baseline: dict[str, float], tolerance_pct: float
) -> str:
    lines = []
    for i, p in enumerate(passes, 1):
        mf = machine_factor(p, baseline)
        shown = "-" if mf is None else f"{mf:.2f}x"
        lines.append(f"pass {i}: runner speed {shown} of baseline (median raw ratio; informational, not gated)")
    lines.append("")
    header = f"{'metric':<45} {'relative to run, per pass':<28} status"
    lines.append(header)
    lines.append("-" * len(header))
    for v in verdicts:
        rel = " ".join(f"{r:.2f}x" for r in v.ratios) or "-"
        suffix = f"  ({v.note})" if v.note else ""
        lines.append(f"{v.metric:<45} {rel:<28} {v.status}{suffix}")
    lines.append("")
    lines.append(f"tolerance: +{tolerance_pct:.0f}% relative to the run, required in every pass")
    return "\n".join(lines)


def record_baseline(passes: list[dict[str, float]]) -> dict[str, float]:
    """Build baseline values from several runs, insensitive to which CPU class each ran on.

    Each run is first divided by its own median ratio to a provisional reference
    (the per-metric median over runs), so a fast-class run and a slow-class run
    contribute on the same scale; the per-metric median of the rescaled values is
    the baseline. Only metrics measured in every run are kept.
    """
    keys = sorted(set.intersection(*(set(p) for p in passes)))
    provisional = {k: statistics.median(p[k] for p in passes) for k in keys}
    rescaled: dict[str, list[float]] = {k: [] for k in keys}
    for p in passes:
        factor = statistics.median(p[k] / provisional[k] for k in keys)
        for k in keys:
            rescaled[k].append(p[k] / factor)
    return {k: statistics.median(v) for k, v in rescaled.items()}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="benchmarks.throughput", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("results", nargs="+", type=Path, help="--benchmark-save JSON files, one per pass")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--baseline", type=Path, help="Gate against this baseline JSON; exit non-zero on red")
    mode.add_argument("--record", type=Path, help="Write a baseline built from the given results to this path")
    p.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help=f"Percent slowdown relative to the run that goes red (default: the baseline's, else "
        f"{DEFAULT_TOLERANCE_PCT:.0f})",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    passes = [load_pass(path) for path in args.results]

    if args.record is not None:
        values = record_baseline(passes)
        payload = {
            "tolerance_pct": args.tolerance if args.tolerance is not None else DEFAULT_TOLERANCE_PCT,
            "provenance": {"recorded": date.today().isoformat(), "runs": len(passes)},
            "metrics_seconds": {k: round(v, 6) for k, v in values.items()},
        }
        args.record.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(values)} metrics from {len(passes)} run(s) to {args.record}")
        return 0

    doc = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline: dict[str, float] = doc["metrics_seconds"]
    tolerance = args.tolerance if args.tolerance is not None else float(doc.get("tolerance_pct", DEFAULT_TOLERANCE_PCT))
    verdicts = judge(passes, baseline, tolerance)
    print(format_report(verdicts, passes, baseline, tolerance))

    if gate_failed(verdicts):
        print("\nTHROUGHPUT GATE FAILED", file=sys.stderr)
        for v in verdicts:
            if v.status in RED_STATUSES:
                print(f"  {v.status}: {v.metric} - {v.note}", file=sys.stderr)
        print(
            f"\n  Baseline: {args.baseline} (recorded {doc.get('provenance', {}).get('recorded', 'unknown')})."
            "\n  A SLOW verdict means this format lost ground against every other format on the"
            "\n  same runner, in every pass - a CPU-class change cannot do that. If the slowdown is"
            "\n  intended, re-record the baseline from CI artifacts in the same commit, never from"
            "\n  a dev box.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
