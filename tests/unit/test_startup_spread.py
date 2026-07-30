"""Self-tests for the startup runner-variance aggregator.

``benchmarks/startup_spread.py`` is what will decide the threshold for the future
startup gate, so its arithmetic has to be right *and* has to be able to report
"no spread" when there genuinely isn't one - an instrument that always reports
noise would push the threshold up until the gate is meaningless, and one that
never reports noise would push it down until the gate flakes. Both directions are
exercised here.

The load-bearing test is ``test_ratio_cancels_a_uniformly_slower_runner``: the
whole argument for gating on ``ratio_over_baseline`` rather than milliseconds is
that a slower VM cancels out of it. If that stops being true, the metric choice
is wrong, not just the number.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks import startup_spread

pytestmark = pytest.mark.unit


def _payload(baseline_ms: float, scenarios: dict[str, float], *, median_factor: float = 1.0) -> dict:
    """Build a startup-benchmark payload the way ``startup.py --out`` writes one.

    ``over_baseline_ms`` is derived here exactly as the harness derives it, so the
    fixture can't drift into being self-consistent but unlike real input.
    """
    results = [
        {
            "name": "baseline",
            "command": "python -c pass",
            "repeat": 9,
            "min_ms": baseline_ms,
            "median_ms": baseline_ms * median_factor,
            "mean_ms": baseline_ms * median_factor,
            "over_baseline_ms": None,
            "returncodes": [0] * 9,
        }
    ]
    for name, min_ms in scenarios.items():
        results.append(
            {
                "name": name,
                "command": f"python -m all2md {name}",
                "repeat": 9,
                "min_ms": min_ms,
                "median_ms": min_ms * median_factor,
                "mean_ms": min_ms * median_factor,
                "over_baseline_ms": min_ms - baseline_ms,
                "returncodes": [0] * 9,
            }
        )
    return {"machine": {"python": "3.12.0"}, "results": results}


def _spreads_by_metric(runs: list[dict], scenario: str) -> dict[str, startup_spread.Spread]:
    labeled = [(f"run{i}", r) for i, r in enumerate(runs)]
    return {s.metric: s for s in startup_spread.compute_spreads(labeled) if s.scenario == scenario}


# --- the summary statistics themselves ----------------------------------------


def test_summarize_reports_median_bounds_and_worst_deviation() -> None:
    median, lo, hi, max_dev_pct, cv_pct = startup_spread.summarize([100.0, 100.0, 120.0])
    assert (median, lo, hi) == (100.0, 100.0, 120.0)
    assert max_dev_pct == pytest.approx(20.0)
    assert cv_pct > 0


def test_summarize_reports_no_spread_for_identical_values() -> None:
    # The control: an instrument that invents noise here would inflate every
    # threshold derived from it.
    _, _, _, max_dev_pct, cv_pct = startup_spread.summarize([250.0, 250.0, 250.0])
    assert max_dev_pct == 0.0
    assert cv_pct == 0.0


def test_summarize_survives_a_zero_median() -> None:
    # over_baseline_ms can legitimately land on 0.0; percentages are meaningless
    # then, but must not be infinite or a ZeroDivisionError.
    _, _, _, max_dev_pct, _ = startup_spread.summarize([0.0, 0.0, 5.0])
    assert max_dev_pct == 0.0


# --- per-run metric extraction -------------------------------------------------


def test_baseline_carries_no_derived_metrics() -> None:
    metrics = startup_spread.metrics_for_run(_payload(100.0, {"import": 500.0}))
    assert "over_baseline_ms" not in metrics["baseline"]
    assert "ratio_over_baseline" not in metrics["baseline"]
    assert metrics["import"]["over_baseline_ms"] == 400.0
    assert metrics["import"]["ratio_over_baseline"] == pytest.approx(4.0)


def test_within_run_noise_tracks_median_above_min() -> None:
    runs = [("a", _payload(100.0, {"import": 500.0}, median_factor=1.1))]
    assert startup_spread.within_run_noise(runs)["import"] == pytest.approx(10.0)


# --- the metric-choice claim ---------------------------------------------------


def test_ratio_cancels_a_uniformly_slower_runner() -> None:
    # Same code, one VM 1.5x slower across the board. Milliseconds move; the
    # dimensionless ratio must not - that is the entire case for gating on it.
    fast = _payload(100.0, {"import": 500.0})
    slow = _payload(150.0, {"import": 750.0})
    spreads = _spreads_by_metric([fast, slow], "import")

    assert spreads["min_ms"].max_dev_pct == pytest.approx(20.0)
    assert spreads["over_baseline_ms"].max_dev_pct == pytest.approx(20.0)
    assert spreads["ratio_over_baseline"].max_dev_pct == 0.0


def test_real_regression_shows_up_in_the_ratio() -> None:
    # The other half: a genuine slowdown on an identical VM must move the ratio,
    # or the metric would be stable by being blind.
    before = _payload(100.0, {"import": 500.0})
    after = _payload(100.0, {"import": 900.0})
    spreads = _spreads_by_metric([before, after], "import")
    assert spreads["ratio_over_baseline"].max_dev_pct > 0


# --- aggregation across scenarios ----------------------------------------------


def test_min_safe_tolerance_takes_the_worst_scenario() -> None:
    a = _payload(100.0, {"import": 500.0, "--help": 800.0})
    b = _payload(100.0, {"import": 505.0, "--help": 1200.0})
    labeled = [("a", a), ("b", b)]
    worst = startup_spread.min_safe_tolerance(startup_spread.compute_spreads(labeled))
    # --help moved far more than import; the floor must reflect the worse one.
    per_scenario = {(s.scenario, s.metric): s.max_dev_pct for s in startup_spread.compute_spreads(labeled)}
    assert worst["min_ms"] == pytest.approx(per_scenario[("--help", "min_ms")])
    assert worst["min_ms"] > per_scenario[("import", "min_ms")]


def test_a_noisy_ungated_scenario_does_not_set_the_floor() -> None:
    # Replays variance run 30180080149, which reported "min_ms > 12.2%" while every
    # gated scenario sat at 1.9-2.5%. The bare interpreter is a ~14ms measurement of
    # process spawn, so it is the noisiest row in the study and the one nothing
    # gates on. Letting it set the floor argued for a ~5x wider gate than the data
    # supports - and, worse, ranked min_ms *last* when it was in fact the steadiest.
    a = _payload(13.2, {"import": 162.0})
    b = _payload(15.2, {"import": 163.0})
    spreads = startup_spread.compute_spreads([("a", a), ("b", b)])

    per_scenario = {(s.scenario, s.metric): s.max_dev_pct for s in spreads}
    assert per_scenario[("baseline", "min_ms")] > 6.0, "the ungated scenario really is the noisy one"

    floor = startup_spread.min_safe_tolerance(spreads)
    assert floor["min_ms"] == pytest.approx(per_scenario[("import", "min_ms")])
    assert floor["min_ms"] < per_scenario[("baseline", "min_ms")]


def test_the_unfiltered_floor_is_still_available_and_still_worse() -> None:
    # The exclusion is a reporting decision, not a claim the noise is not there.
    a = _payload(13.2, {"import": 162.0})
    b = _payload(15.2, {"import": 163.0})
    spreads = startup_spread.compute_spreads([("a", a), ("b", b)])

    gated = startup_spread.min_safe_tolerance(spreads)
    everything = startup_spread.min_safe_tolerance(spreads, ungated=frozenset())
    assert everything["min_ms"] > gated["min_ms"]


def test_the_report_names_what_it_excluded() -> None:
    # A floor that quietly covers fewer rows than the table above it reads as
    # covering all of them. Whatever the number, the exclusion must be on the page.
    a = _payload(13.2, {"import": 162.0})
    b = _payload(15.2, {"import": 163.0})
    runs = [("a", a), ("b", b)]
    report = startup_spread.format_report(runs, startup_spread.compute_spreads(runs))

    assert "Excluded from the floors above" in report
    assert "baseline" in report.split("Excluded from the floors above")[1]


def test_scenarios_are_reported_in_pipeline_order() -> None:
    run = _payload(100.0, {"import": 500.0, "--version": 520.0, "--help": 800.0})
    order: list[str] = []
    for s in startup_spread.compute_spreads([("a", run), ("b", run)]):
        if s.scenario not in order:
            order.append(s.scenario)
    assert order == ["baseline", "import", "--version", "--help"]


# --- loading -------------------------------------------------------------------


def test_load_runs_reads_a_directory_tree_and_skips_foreign_json(tmp_path: Path) -> None:
    (tmp_path / "job1").mkdir()
    (tmp_path / "job2").mkdir()
    (tmp_path / "job1" / "startup-1.json").write_text(json.dumps(_payload(100.0, {"import": 500.0})), encoding="utf-8")
    (tmp_path / "job2" / "startup-2.json").write_text(json.dumps(_payload(110.0, {"import": 520.0})), encoding="utf-8")
    # An unrelated artifact sharing the directory must not be mistaken for a run.
    (tmp_path / "job2" / "coverage.json").write_text(json.dumps({"totals": {}}), encoding="utf-8")

    runs = startup_spread.load_runs([tmp_path])
    assert [label for label, _ in runs] == ["startup-1", "startup-2"]


def test_main_refuses_to_report_a_spread_from_one_run(tmp_path: Path) -> None:
    (tmp_path / "only.json").write_text(json.dumps(_payload(100.0, {"import": 500.0})), encoding="utf-8")
    assert startup_spread.main([str(tmp_path)]) == 2
