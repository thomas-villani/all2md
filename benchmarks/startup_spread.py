"""Runner-variance study for the cold-start benchmark.

**This is an instrument, not a gate.** It never fails a build on a threshold,
because its whole job is to tell us what threshold is even defensible. Before
``benchmarks/startup.py`` can become a blocking CI gate we have to know how much
its numbers move on identical code, on the runners the gate would actually run
on. Guessing here buys a flaky gate, and a flaky gate gets disabled, which leaves
the *appearance* of coverage - strictly worse than no gate.

Feed it several ``benchmarks.startup --out`` JSON files produced from unchanged
code (ideally one per runner VM, so it captures VM-to-VM variance and not just
sample noise within one machine) and it reports, per scenario:

- the spread of each candidate gate metric across runs, and
- ``max dev%`` - the largest deviation any run showed from the median, i.e. **the
  smallest tolerance that would not have flaked on this data**. A real threshold
  needs headroom on top of that, not equality with it.

The per-metric floors at the bottom cover only the scenarios a gate would actually
judge (see ``UNGATED_SCENARIOS``). A scenario that is measured but never gated
cannot flake a gate, so letting it set the floor overstates what the data supports -
which is what happened here before this was fixed. The report names any scenario it
excluded, and what the floor would have been with it included.

Three candidate metrics are tracked, because they trade off differently:

- ``min_ms`` - raw wall clock. Simple, but scales with runner speed, so a slower
  VM reads as a regression.
- ``over_baseline_ms`` - ``min_ms`` minus the bare-interpreter minimum. Removes
  interpreter startup, but is still in milliseconds, so it *also* scales with
  runner speed - just from a lower floor.
- ``ratio_over_baseline`` - ``over_baseline_ms / baseline_min_ms``. Dimensionless:
  "all2md costs N bare interpreter startups". A uniformly slower VM cancels out.
  The most stable in principle; whether that survives contact with real runners
  is exactly what this script measures.

``within-run%`` is a separate noise signal: how far each run's *median* sample sat
above its *minimum* sample. Large values mean the samples themselves are noisy and
``--repeat`` should go up; small values with a large ``max dev%`` mean the noise is
between machines, and more repeats would not help.

Usage::

    python -m benchmarks.startup_spread artifacts/          # any dir tree of JSONs
    python -m benchmarks.startup_spread a.json b.json c.json
    python -m benchmarks.startup_spread artifacts/ --json spread.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Candidate gate metrics, in the order they are reported.
METRICS = ("min_ms", "over_baseline_ms", "ratio_over_baseline")

# Scenarios the gate measures but never gates on, so their spread must not set the
# tolerance floor. ``baseline`` is the bare interpreter: it is reported as a
# runner-speed signal, and it is *by far* the noisiest scenario here, being a ~14 ms
# measurement of process spawn rather than of our code. Including it once produced a
# headline floor of 12.2% when every gated scenario sat at 1.9-2.5% - a ~5x
# overstatement, in the direction that argues for a uselessly wide gate.
UNGATED_SCENARIOS = frozenset({"baseline"})


@dataclass
class Spread:
    """How much one (scenario, metric) pair moved across runs of identical code."""

    scenario: str
    metric: str
    n: int
    median: float
    lo: float
    hi: float
    max_dev_pct: float
    cv_pct: float


def load_runs(paths: list[Path]) -> list[tuple[str, dict]]:
    """Load ``(label, payload)`` for every startup JSON under ``paths``.

    Directories are searched recursively, which is what the CI job needs: the
    artifact download produces one directory per matrix job.
    """
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.json")))
        else:
            files.append(p)

    runs: list[tuple[str, dict]] = []
    for f in files:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skipping {f}: {exc}", file=sys.stderr)
            continue
        if not isinstance(payload, dict) or "results" not in payload:
            print(f"skipping {f}: not a startup benchmark result", file=sys.stderr)
            continue
        runs.append((f.stem, payload))
    return runs


def metrics_for_run(payload: dict) -> dict[str, dict[str, float]]:
    """Map ``scenario -> metric -> value`` for a single run.

    ``baseline`` has no ``over_baseline_ms`` (it *is* the baseline), so it simply
    carries fewer metrics rather than being special-cased downstream.
    """
    by_name = {r["name"]: r for r in payload.get("results", [])}
    baseline_min = by_name.get("baseline", {}).get("min_ms")

    out: dict[str, dict[str, float]] = {}
    for name, r in by_name.items():
        min_ms = float(r["min_ms"])
        values: dict[str, float] = {"min_ms": min_ms}

        over = r.get("over_baseline_ms")
        if over is not None:
            values["over_baseline_ms"] = float(over)
            if baseline_min:
                values["ratio_over_baseline"] = float(over) / float(baseline_min)

        # Sample noise inside this one run, independent of the cross-run spread.
        if min_ms:
            values["within_run_spread_pct"] = (float(r["median_ms"]) - min_ms) / min_ms * 100.0
        out[name] = values
    return out


def summarize(values: list[float]) -> tuple[float, float, float, float, float]:
    """Return ``(median, lo, hi, max_dev_pct, cv_pct)`` for one metric's samples.

    ``max_dev_pct`` is the largest relative distance from the median - the
    smallest tolerance that would have survived this data. A zero median makes
    the percentages meaningless rather than infinite, so they report as 0.0.
    """
    median = statistics.median(values)
    lo, hi = min(values), max(values)
    if median:
        max_dev_pct = max(abs(v - median) / abs(median) for v in values) * 100.0
    else:
        max_dev_pct = 0.0
    if len(values) > 1:
        mean = statistics.fmean(values)
        cv_pct = (statistics.stdev(values) / mean * 100.0) if mean else 0.0
    else:
        cv_pct = 0.0
    return median, lo, hi, max_dev_pct, cv_pct


def compute_spreads(runs: list[tuple[str, dict]]) -> list[Spread]:
    """Cross-run spread for every (scenario, metric) present in at least one run.

    Scenario order follows the first run so the report reads in pipeline order
    (baseline, import, --version, ...) rather than alphabetically.
    """
    per_run = [metrics_for_run(payload) for _, payload in runs]

    order: list[str] = []
    for run in per_run:
        for name in run:
            if name not in order:
                order.append(name)

    spreads: list[Spread] = []
    for scenario in order:
        for metric in METRICS:
            values = [run[scenario][metric] for run in per_run if scenario in run and metric in run[scenario]]
            if not values:
                continue
            median, lo, hi, max_dev_pct, cv_pct = summarize(values)
            spreads.append(
                Spread(
                    scenario=scenario,
                    metric=metric,
                    n=len(values),
                    median=round(median, 3),
                    lo=round(lo, 3),
                    hi=round(hi, 3),
                    max_dev_pct=round(max_dev_pct, 1),
                    cv_pct=round(cv_pct, 1),
                )
            )
    return spreads


def within_run_noise(runs: list[tuple[str, dict]]) -> dict[str, float]:
    """Median ``(median_sample - min_sample) / min_sample`` per scenario, in percent."""
    per_run = [metrics_for_run(payload) for _, payload in runs]
    noise: dict[str, float] = {}
    for scenario in {s for run in per_run for s in run}:
        values = [
            run[scenario]["within_run_spread_pct"]
            for run in per_run
            if "within_run_spread_pct" in run.get(scenario, {})
        ]
        if values:
            noise[scenario] = round(statistics.median(values), 1)
    return noise


def min_safe_tolerance(spreads: list[Spread], ungated: frozenset[str] = UNGATED_SCENARIOS) -> dict[str, float]:
    """Per metric, the worst ``max_dev_pct`` across the scenarios a gate would judge.

    This is the floor for any tolerance built on that metric: set the gate below
    this and unchanged code would already have gone red somewhere in this data.

    Scenarios in ``ungated`` are excluded, because a scenario nobody gates on
    cannot flake a gate - and letting the noisiest measurement in the study set
    the floor for measurements it has no authority over is how a study argues for
    a tolerance five times wider than its own data supports. Pass an empty set to
    see the unfiltered figure; ``format_report`` names what was excluded either
    way, so the filtering is never silent.
    """
    worst: dict[str, float] = {}
    for s in spreads:
        if s.scenario in ungated:
            continue
        worst[s.metric] = max(worst.get(s.metric, 0.0), s.max_dev_pct)
    return worst


def format_report(runs: list[tuple[str, dict]], spreads: list[Spread]) -> str:
    noise = within_run_noise(runs)
    lines = [f"{len(runs)} run(s): {', '.join(label for label, _ in runs)}", ""]

    header = (
        f"{'scenario':<12} {'metric':<20} {'n':>2} {'median':>10} " f"{'lo':>10} {'hi':>10} {'max dev%':>9} {'cv%':>6}"
    )
    lines += [header, "-" * len(header)]
    last_scenario = None
    for s in spreads:
        if last_scenario is not None and s.scenario != last_scenario:
            lines.append("")
        last_scenario = s.scenario
        lines.append(
            f"{s.scenario:<12} {s.metric:<20} {s.n:>2} {s.median:>10.3f} "
            f"{s.lo:>10.3f} {s.hi:>10.3f} {s.max_dev_pct:>9.1f} {s.cv_pct:>6.1f}"
        )

    lines += ["", "Within-run sample noise (median sample vs min sample, %):"]
    for scenario, pct in sorted(noise.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {scenario:<12} {pct:>6.1f}")

    lines += ["", "Smallest tolerance that would NOT have flaked on this data:"]
    for metric, pct in sorted(min_safe_tolerance(spreads).items(), key=lambda kv: kv[1]):
        lines.append(f"  {metric:<20} > {pct:.1f}%")

    # Never let the exclusion be silent: a reader who does not know it happened
    # would read these floors as covering every row in the table above.
    excluded = sorted({s.scenario for s in spreads} & UNGATED_SCENARIOS)
    if excluded:
        gated = min_safe_tolerance(spreads)
        unfiltered = min_safe_tolerance(spreads, ungated=frozenset())
        # Per metric, not a single worst-of-all number: the excluded scenario
        # typically moves one metric and leaves the others alone, and collapsing
        # that into one figure misattributes the other metrics' own noise to it.
        raised = [(m, gated.get(m, 0.0), v) for m, v in unfiltered.items() if v > gated.get(m, 0.0)]
        lines += ["", f"Excluded from the floors above (measured, never gated): {', '.join(excluded)}."]
        if raised:
            lines.append("Including them would raise:")
            lines += [f"  {m:<20} {before:.1f}% -> {after:.1f}%" for m, before, after in sorted(raised)]
        else:
            lines.append("Including them would not change any floor above.")

    lines += [
        "",
        "Pick the metric with the smallest floor, then add headroom - these runs are a",
        "sample, not the worst case. Sensitivity matters too: a metric that carries a",
        "large constant offset dilutes real regressions even when it looks stable.",
    ]
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.startup_spread", description=__doc__)
    p.add_argument("paths", nargs="+", type=Path, help="startup JSON files, or directories to search recursively")
    p.add_argument("--json", type=Path, default=None, help="Write the computed spreads to this path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    runs = load_runs(args.paths)
    if len(runs) < 2:
        print(f"Need at least 2 runs to measure spread, found {len(runs)}.", file=sys.stderr)
        return 2

    spreads = compute_spreads(runs)
    print(format_report(runs, spreads))

    if args.json is not None:
        payload = {
            "runs": [{"label": label, "machine": r.get("machine", {})} for label, r in runs],
            "spreads": [asdict(s) for s in spreads],
            "within_run_noise_pct": within_run_noise(runs),
            "min_safe_tolerance_pct": min_safe_tolerance(spreads),
            # Carried explicitly so a consumer reading only this file sees the same
            # caveat the printed report shows, rather than reading the floor above
            # as covering every scenario in "spreads".
            "ungated_scenarios": sorted(UNGATED_SCENARIOS),
            "min_safe_tolerance_pct_including_ungated": min_safe_tolerance(spreads, ungated=frozenset()),
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote spreads to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
