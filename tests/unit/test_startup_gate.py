"""Self-tests for the cold-start timing gate.

These guard the *gate*, not all2md's startup. They exercise the comparison logic
directly instead of running the benchmark, which keeps them fast, deterministic,
and free of the runner variance the gate itself has to tolerate.

Per ``verify-the-judge-can-fail``, every red path is pinned here: a gate that
cannot go red launders "we didn't measure" into "we measured and it's fine". The
non-obvious one is ``FAST`` - an unrecorded *improvement* fails the build,
because a baseline nobody re-recorded has stopped describing the code it is
supposed to guard.
"""

from __future__ import annotations

import pytest

from benchmarks.startup import (
    Comparison,
    ScenarioResult,
    _runner_looks_slow,
    compare_to_baseline,
    gate_failed,
)

pytestmark = pytest.mark.unit


BASELINE = {
    "tolerance_pct": 20.0,
    "provenance": {"recorded": "2026-07-25"},
    "scenarios": {"baseline": 14.0, "import": 230.0, "--version": 246.0},
}


def _result(name: str, min_ms: float) -> ScenarioResult:
    return ScenarioResult(
        name=name,
        command=f"python -m all2md {name}",
        repeat=9,
        min_ms=min_ms,
        median_ms=min_ms * 1.02,
        mean_ms=min_ms * 1.03,
        over_baseline_ms=None,
        returncodes=[0] * 9,
    )


def _statuses(results: list[ScenarioResult], baseline: dict = BASELINE, tolerance: float = 20.0) -> dict[str, str]:
    return {c.scenario: c.status for c in compare_to_baseline(results, baseline, tolerance)}


# --- the green path ------------------------------------------------------------


def test_within_tolerance_is_green() -> None:
    results = [_result("baseline", 14.5), _result("import", 250.0), _result("--version", 260.0)]
    comparisons = compare_to_baseline(results, BASELINE, 20.0)
    assert _statuses(results) == {"baseline": "info", "import": "ok", "--version": "ok"}
    assert not gate_failed(comparisons)


def test_the_bare_interpreter_is_reported_but_never_gates() -> None:
    # A slow VM moves the bare interpreter too. Gating on it would fail builds
    # for being unlucky, so it is reported as a signal and nothing more.
    results = [_result("baseline", 40.0), _result("import", 230.0), _result("--version", 246.0)]
    comparisons = compare_to_baseline(results, BASELINE, 20.0)
    assert _statuses(results)["baseline"] == "info"
    assert not gate_failed(comparisons)


# --- every red path -------------------------------------------------------------


@pytest.mark.parametrize(
    ("results", "expect_status", "why"),
    [
        pytest.param(
            [_result("baseline", 14.0), _result("import", 300.0), _result("--version", 246.0)],
            "SLOW",
            "a 30% regression must fail, or the gate guards nothing",
            id="regression",
        ),
        pytest.param(
            [_result("baseline", 14.0), _result("import", 100.0), _result("--version", 246.0)],
            "FAST",
            "an unrecorded win leaves the gate judging against a number nobody stands behind",
            id="unrecorded-improvement",
        ),
        pytest.param(
            [
                _result("baseline", 14.0),
                _result("import", 230.0),
                _result("--version", 246.0),
                _result("convert", 400.0),
            ],
            "MISSING",
            "a scenario with no baseline entry is ungated and must not pass silently",
            id="ungated-scenario",
        ),
    ],
)
def test_gate_goes_red(results: list[ScenarioResult], expect_status: str, why: str) -> None:
    comparisons = compare_to_baseline(results, BASELINE, 20.0)
    assert expect_status in {c.status for c in comparisons}, why
    assert gate_failed(comparisons), why


def test_stale_baseline_entry_is_red() -> None:
    # The baseline names a scenario the harness no longer measures, so the file
    # has begun describing a benchmark that does not exist.
    results = [_result("baseline", 14.0), _result("import", 230.0)]
    comparisons = compare_to_baseline(results, BASELINE, 20.0)
    stale = [c for c in comparisons if c.status == "STALE"]
    assert [c.scenario for c in stale] == ["--version"]
    assert gate_failed(comparisons)


def test_every_red_status_actually_fails_the_gate() -> None:
    # Guards against a status being added to the table but forgotten in the
    # exit decision - the gate would then report a problem and exit 0.
    for status in ("SLOW", "FAST", "MISSING", "STALE"):
        assert gate_failed([Comparison("x", 1.0, 1.0, 0.0, status)]), f"{status} must fail the build"
    for status in ("ok", "info"):
        assert not gate_failed([Comparison("x", 1.0, 1.0, 0.0, status)]), f"{status} must not fail the build"


# --- tolerance handling ---------------------------------------------------------


def test_tolerance_is_applied_symmetrically() -> None:
    # 19% either way is inside a 20% tolerance; 21% either way is outside.
    assert _statuses([_result("import", 230.0 * 1.19)])["import"] == "ok"
    assert _statuses([_result("import", 230.0 * 0.81)])["import"] == "ok"
    assert _statuses([_result("import", 230.0 * 1.21)])["import"] == "SLOW"
    assert _statuses([_result("import", 230.0 * 0.79)])["import"] == "FAST"


def test_a_tighter_tolerance_catches_what_a_looser_one_allows() -> None:
    results = [_result("import", 230.0 * 1.15)]
    assert _statuses(results, tolerance=20.0)["import"] == "ok"
    assert _statuses(results, tolerance=10.0)["import"] == "SLOW"


# --- the slow-runner advisory ---------------------------------------------------


def test_slow_runner_advisory_fires_when_the_interpreter_also_drifted() -> None:
    # Everything up ~25%: more likely an unlucky VM than a real regression, and
    # saying so is the difference between "the gate is flaky" and "the gate is right".
    results = [_result("baseline", 17.5), _result("import", 287.0), _result("--version", 246.0)]
    assert _runner_looks_slow(compare_to_baseline(results, BASELINE, 20.0), 20.0)


def test_slow_runner_advisory_stays_quiet_for_a_real_regression() -> None:
    # Bare interpreter on target, all2md slow: that is our bug, and hinting at
    # the runner would send the reader down the wrong path.
    results = [_result("baseline", 14.0), _result("import", 300.0), _result("--version", 246.0)]
    assert not _runner_looks_slow(compare_to_baseline(results, BASELINE, 20.0), 20.0)
