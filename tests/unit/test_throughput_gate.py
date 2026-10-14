"""Self-tests for the per-format throughput gate (``benchmarks/throughput.py``).

These guard the *gate*, not all2md's speed. Every red path is pinned, and so is
every path that must stay green despite moving numbers, because the acceptance bar
on #183 has two halves: the gate has to go red on a deliberately slowed build, and
it has to stay green across a CPU-class change.

The ``REAL_*`` passes are the per-format minimum timings of actual CI runs on
``ubuntu-latest``, copied from their ``format-benchmarks-*`` artifacts, judged
against the committed baseline. They are the cases the gate was designed around:
the fastest CPU class the study saw, the slowest, and a contention burst.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from benchmarks.throughput import (
    gate_failed,
    judge,
    load_pass,
    machine_factor,
    main,
    metric_key,
    normalized_log_ratios,
    record_baseline,
)

pytestmark = pytest.mark.unit

BASELINE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "throughput_baseline.json"
BASELINE: dict[str, float] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["metrics_seconds"]
TOLERANCE = 30.0

# Run 1354 (main, 327549d9, 2026-10-02): the fast CPU class, ~0.55x the baseline.
REAL_FAST_CLASS = {
    "pdf:basic.pdf": 0.024118,
    "pdf:complex.pdf": 0.108211,
    "docx:basic.docx": 0.022754,
    "docx:complex.docx": 0.042024,
    "docx:footnotes-endnotes-comments.docx": 0.010548,
    "html:basic.html": 0.002187,
    "html:html_readability_article.html": 0.001034,
    "pptx:basic.pptx": 0.012179,
    "xlsx:basic.xlsx": 0.002742,
    "odt:basic.odt": 0.00945,
    "odt:complex.odt": 0.013079,
    "epub:epub-simple.epub": 0.002517,
    "ipynb:ipynb-simple.ipynb": 0.000403,
    "mhtml:mhtml-simple.mht": 0.001721,
    "csv:basic.csv": 0.000437,
    "rtf:basic-format.rtf": 0.014533,
    "md->docx->md:basic.md": 0.094841,
}

# Run 1351 (main, 627f01d8, 2026-10-02): the slowest runner in the window, ~1.16x.
REAL_SLOW_CLASS = {
    "pdf:basic.pdf": 0.047523,
    "pdf:complex.pdf": 0.2169,
    "docx:basic.docx": 0.053361,
    "docx:complex.docx": 0.09671,
    "docx:footnotes-endnotes-comments.docx": 0.0239,
    "html:basic.html": 0.004772,
    "html:html_readability_article.html": 0.002133,
    "pptx:basic.pptx": 0.028013,
    "xlsx:basic.xlsx": 0.005032,
    "odt:basic.odt": 0.020846,
    "odt:complex.odt": 0.026802,
    "epub:epub-simple.epub": 0.005064,
    "ipynb:ipynb-simple.ipynb": 0.000915,
    "mhtml:mhtml-simple.mht": 0.003775,
    "csv:basic.csv": 0.000957,
    "rtf:basic-format.rtf": 0.030776,
    "md->docx->md:basic.md": 0.198841,
}

# Run 1273 (main, e6159ea4, 2026-09-18): unchanged code, but a contention burst
# landed on the footnotes benchmark - all three iterations 3x slow - and spilled
# into html:basic. The worst single-run false alarm in the replay.
REAL_CONTENTION_BURST = {
    "pdf:basic.pdf": 0.023643,
    "pdf:complex.pdf": 0.109153,
    "docx:basic.docx": 0.023932,
    "docx:complex.docx": 0.043997,
    "docx:footnotes-endnotes-comments.docx": 0.037295,
    "html:basic.html": 0.003899,
    "html:html_readability_article.html": 0.0028,
    "pptx:basic.pptx": 0.012758,
    "xlsx:basic.xlsx": 0.005605,
    "odt:basic.odt": 0.024628,
    "odt:complex.odt": 0.019308,
    "epub:epub-simple.epub": 0.002487,
    "ipynb:ipynb-simple.ipynb": 0.000419,
    "mhtml:mhtml-simple.mht": 0.001713,
    "csv:basic.csv": 0.000445,
    "rtf:basic-format.rtf": 0.01435,
    "md->docx->md:basic.md": 0.093662,
}


def _slowed(run: dict[str, float], metric: str, factor: float) -> dict[str, float]:
    return {k: v * factor if k == metric else v for k, v in run.items()}


def _statuses(passes: list[dict[str, float]], baseline: dict[str, float] = BASELINE) -> dict[str, str]:
    return {v.metric: v.status for v in judge(passes, baseline, TOLERANCE)}


# --- the real runs: what must stay green ------------------------------------------


@pytest.mark.parametrize("run", [REAL_FAST_CLASS, REAL_SLOW_CLASS], ids=["fast-class", "slow-class"])
def test_real_cpu_classes_are_green(run: dict[str, float]) -> None:
    verdicts = judge([run, run], BASELINE, TOLERANCE)
    assert not gate_failed(verdicts), [v for v in verdicts if v.status != "ok"]


def test_the_two_real_cpu_classes_differ_by_more_than_any_raw_threshold_could_absorb() -> None:
    fast = machine_factor(REAL_FAST_CLASS, BASELINE)
    slow = machine_factor(REAL_SLOW_CLASS, BASELINE)
    assert fast is not None and slow is not None
    # Two runs of the same week's code, 2x apart in raw time: a raw threshold loose
    # enough to pass both could never see a 1.5x regression.
    assert slow / fast > 2.0


def test_contention_burst_in_one_pass_is_green() -> None:
    verdicts = judge([REAL_CONTENTION_BURST, REAL_FAST_CLASS], BASELINE, TOLERANCE)
    assert not gate_failed(verdicts)


def test_contention_burst_alone_would_have_been_a_false_red() -> None:
    # Why the gate takes two passes: on one, this real run of unchanged code is red.
    assert _statuses([REAL_CONTENTION_BURST])["docx:footnotes-endnotes-comments.docx"] == "SLOW"


# --- deliberately slowed builds: what must go red -----------------------------------


@pytest.mark.parametrize("factor", [1.5, 2.0])
@pytest.mark.parametrize("run", [REAL_FAST_CLASS, REAL_SLOW_CLASS], ids=["fast-class", "slow-class"])
def test_one_format_slowed_goes_red_on_either_cpu_class(run: dict[str, float], factor: float) -> None:
    slowed = _slowed(run, "docx:basic.docx", factor)
    statuses = _statuses([slowed, slowed])
    assert statuses["docx:basic.docx"] == "SLOW"
    assert [k for k, s in statuses.items() if s != "ok"] == ["docx:basic.docx"]


def test_slowed_format_on_a_fast_runner_is_red_although_raw_time_improved() -> None:
    # The case a raw (or raw-AND-normalized) rule misses: 1.5x slower code on a
    # 0.55x runner still reads faster than the baseline in milliseconds.
    slowed = _slowed(REAL_FAST_CLASS, "pdf:complex.pdf", 1.5)
    assert slowed["pdf:complex.pdf"] < BASELINE["pdf:complex.pdf"]
    assert _statuses([slowed, slowed])["pdf:complex.pdf"] == "SLOW"


def test_slowed_build_on_two_different_cpu_classes_is_red() -> None:
    a = _slowed(REAL_FAST_CLASS, "rtf:basic-format.rtf", 1.5)
    b = _slowed(REAL_SLOW_CLASS, "rtf:basic-format.rtf", 1.5)
    assert _statuses([a, b])["rtf:basic-format.rtf"] == "SLOW"


# --- synthetic: the arithmetic ------------------------------------------------------


def test_uniform_scaling_cancels_exactly() -> None:
    for factor in (0.5, 0.57, 0.73, 1.75, 4.0):
        scaled = {k: v * factor for k, v in BASELINE.items()}
        ratios = normalized_log_ratios(scaled, BASELINE)
        assert all(abs(r) < 1e-9 for r in ratios.values())
        assert not gate_failed(judge([scaled, scaled], BASELINE, TOLERANCE))


def test_leave_one_out_keeps_the_slowed_format_out_of_its_own_reference() -> None:
    ratios = normalized_log_ratios(_slowed(BASELINE, "csv:basic.csv", 2.0), BASELINE)
    assert math.exp(ratios["csv:basic.csv"]) == pytest.approx(2.0)


def test_just_under_tolerance_is_green_and_just_over_is_red() -> None:
    under = _slowed(BASELINE, "xlsx:basic.xlsx", 1.29)
    over = _slowed(BASELINE, "xlsx:basic.xlsx", 1.31)
    assert _statuses([under, under])["xlsx:basic.xlsx"] == "ok"
    assert _statuses([over, over])["xlsx:basic.xlsx"] == "SLOW"


def test_slow_in_only_one_of_two_passes_is_green() -> None:
    assert _statuses([_slowed(BASELINE, "odt:basic.odt", 3.0), BASELINE])["odt:basic.odt"] == "ok"


def test_faster_is_reported_but_not_red() -> None:
    fast = _slowed(BASELINE, "pdf:basic.pdf", 0.5)
    verdicts = judge([fast, fast], BASELINE, TOLERANCE)
    assert {v.metric: v.status for v in verdicts}["pdf:basic.pdf"] == "fast"
    assert not gate_failed(verdicts)


def test_missing_and_stale_are_red() -> None:
    run = dict(BASELINE)
    del run["csv:basic.csv"]
    run["new:fixture.xyz"] = 0.01
    statuses = _statuses([run, run])
    assert statuses["csv:basic.csv"] == "STALE"
    assert statuses["new:fixture.xyz"] == "MISSING"
    assert gate_failed(judge([run, run], BASELINE, TOLERANCE))


def test_too_few_formats_are_not_judged() -> None:
    few = {k: BASELINE[k] * 3 for k in list(BASELINE)[:4]}
    assert normalized_log_ratios(few, BASELINE) == {}
    assert not any(v.status == "SLOW" for v in judge([few], BASELINE, TOLERANCE))


# --- recording ----------------------------------------------------------------------


def test_record_baseline_is_insensitive_to_cpu_class_mix() -> None:
    # Two fast-class runs and one slow-class run of identical relative shape must
    # record the same relative shape, not a blend skewed toward either class.
    runs = [{k: v * 0.55 for k, v in BASELINE.items()}] * 2 + [{k: v * 1.16 for k, v in BASELINE.items()}]
    recorded = record_baseline(runs)
    ratios = normalized_log_ratios(recorded, BASELINE)
    assert all(abs(r) < 1e-9 for r in ratios.values())


# --- the file format and the CLI -----------------------------------------------------


def _write_pass(path: Path, run: dict[str, float]) -> Path:
    results = []
    for key, seconds in run.items():
        fmt, name = key.split(":", 1)
        results.append(
            {
                "format": fmt,
                "file_path": f"/home/runner/work/all2md/all2md/tests/fixtures/documents/{name}",
                "min_time": seconds,
                "median_time": seconds * 1.02,
                "timings": [seconds, seconds * 1.02, seconds * 1.05],
            }
        )
    path.write_text(json.dumps({"benchmark_run": {}, "results": results}), encoding="utf-8")
    return path


def test_metric_key_uses_the_fixture_filename() -> None:
    assert metric_key({"format": "pdf", "file_path": "/a/b/basic.pdf"}) == "pdf:basic.pdf"
    assert metric_key({"format": "pdf", "file_path": "C:\\a\\basic.pdf"}) == "pdf:basic.pdf"


def test_load_pass_reads_min_time(tmp_path: Path) -> None:
    assert load_pass(_write_pass(tmp_path / "p.json", REAL_FAST_CLASS)) == REAL_FAST_CLASS


def test_cli_green_on_real_cpu_classes(tmp_path: Path) -> None:
    a = _write_pass(tmp_path / "a.json", REAL_FAST_CLASS)
    b = _write_pass(tmp_path / "b.json", REAL_SLOW_CLASS)
    assert main([str(a), str(b), "--baseline", str(BASELINE_PATH)]) == 0


def test_cli_red_on_slowed_build(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    slowed = _slowed(REAL_FAST_CLASS, "pptx:basic.pptx", 1.5)
    a = _write_pass(tmp_path / "a.json", slowed)
    b = _write_pass(tmp_path / "b.json", slowed)
    assert main([str(a), str(b), "--baseline", str(BASELINE_PATH)]) == 1
    assert "SLOW: pptx:basic.pptx" in capsys.readouterr().err


def test_cli_record_round_trips(tmp_path: Path) -> None:
    a = _write_pass(tmp_path / "a.json", REAL_FAST_CLASS)
    b = _write_pass(tmp_path / "b.json", REAL_SLOW_CLASS)
    out = tmp_path / "baseline.json"
    assert main([str(a), str(b), "--record", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc["metrics_seconds"]) == set(REAL_FAST_CLASS)
    assert main([str(a), str(b), "--baseline", str(out)]) == 0
