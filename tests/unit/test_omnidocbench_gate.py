#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Synthetic contract tests for the external-fidelity OmniDocBench gate."""

from __future__ import annotations

import copy
import json

import pytest

from benchmarks.omnidocbench import gate

pytestmark = pytest.mark.unit


RESULTS = {
    "schema_version": 3,
    "provenance": {
        "dataset_revision": "f5f559bddf50e36f7f9899d842d0006f13ce8afc",
        "annotation_sha256": "2fafe9329dc92fc426b30036aee51c716b3fcdcc1d20cb964dc7670579533817",
        "oracle_schema_version": 6,
        "parser_config": {
            "layout_analysis_mode": "auto",
            "ocr": {
                "enabled": True,
                "engine": "tesseract",
                "mode": "auto",
                "languages": "eng+chi_sim",
                "dpi": 200,
            },
        },
        "parser_runtime": {
            "pymupdf": "1.26.3",
            "tesseract": "5.3.0",
        },
        "worktree_dirty": False,
    },
    "pages": {
        "expected": 3,
        "annotations": 3,
        "pdfs": 3,
        "converted": 2,
        "scored": 3,
        "unique_ids": 3,
    },
    "dimensions": {
        "edit_distance": {
            "value": 0.2,
            "direction": "lower",
            "eligible_items": 3,
            "variance": 0.006666666666666666,
            "sample_scores": {
                "page-001": 0.1,
                "page-002": 0.2,
                "page-003": 0.3,
            },
        },
        "text_similarity": {
            "value": 0.8,
            "direction": "higher",
            "eligible_items": 3,
            "variance": 0.006666666666666668,
            "sample_scores": {
                "page-001": 0.7,
                "page-002": 0.8,
                "page-003": 0.9,
            },
        },
    },
    "conversion_failures": {"page-003": "Encrypted PDF"},
}
BASELINE = gate.emit_baseline(
    RESULTS,
    {"edit_distance": 0.01, "text_similarity": 0.01},
)


def _results() -> dict:
    return copy.deepcopy(RESULTS)


def _baseline() -> dict:
    return copy.deepcopy(BASELINE)


def _set_metric_value(results: dict, metric: str, value: float) -> None:
    dimension = results["dimensions"][metric]
    delta = value - dimension["value"]
    dimension["value"] = value
    dimension["sample_scores"] = {page_id: score + delta for page_id, score in dimension["sample_scores"].items()}


def _finding(status: str, subject: str, detail: str) -> list[gate.Finding]:
    return [gate.Finding(status, subject, detail)]


def test_an_exact_normalized_run_is_green() -> None:
    """An unchanged, fully accounted run must be the gate's exact green path."""
    verdict = gate.compare(_results(), _baseline())
    assert verdict.findings == []
    assert verdict.failed is False
    assert gate.format_verdict(verdict).splitlines()[0] == "OMNIDOCBENCH GATE PASS"


# ---------------------------------------------------------------------------
# Dimensions recorded but not gated
# ---------------------------------------------------------------------------

_UNGATED = next(iter(gate.UNGATEABLE))
#: The trailer `format_verdict` appends to every verdict, red or green.
_NOT_GATED_LINE = f"NOT GATED dimensions.{_UNGATED}: {gate.UNGATEABLE[_UNGATED].split(';')[0]}"


def _with_ungated(value: float = 0.5) -> tuple[dict, dict]:
    """Return a results/baseline pair carrying one ungateable dimension at ``value``."""
    results = _results()
    results["dimensions"][_UNGATED] = {
        "value": value,
        "direction": "higher",
        "eligible_items": 3,
        "variance": 0.0,
        "sample_scores": {"page-001": value, "page-002": value, "page-003": value},
    }
    baseline = gate.emit_baseline(
        results,
        {"edit_distance": 0.01, "text_similarity": 0.01, _UNGATED: 0.01},
    )
    return results, baseline


def test_a_dimension_declared_ungateable_does_not_fail_on_drift() -> None:
    """It moves the wrong way under damage, so a drift in it is not evidence either way."""
    results, baseline = _with_ungated()
    _set_metric_value(results, _UNGATED, 0.05)  # far outside the 0.01 tolerance
    verdict = gate.compare(results, baseline)
    assert verdict.findings == []
    assert verdict.failed is False


def test_the_same_drift_on_a_gated_dimension_is_still_red() -> None:
    """The control for the test above: without it, a broken gate would look identical."""
    results, baseline = _with_ungated()
    _set_metric_value(results, "text_similarity", 0.5)
    verdict = gate.compare(results, baseline)
    assert [finding.status for finding in verdict.findings] == ["REGRESSION"]


def test_an_ungateable_dimension_is_still_held_to_its_own_sample_scores() -> None:
    """Not gated is not unchecked: shape, range and self-consistency all still apply."""
    results, baseline = _with_ungated()
    results["dimensions"][_UNGATED]["value"] = 0.9  # sample_scores still average 0.5
    verdict = gate.compare(results, baseline)
    assert [finding.status for finding in verdict.findings] == ["IDENTITY_DRIFT"]


def test_an_ungateable_dimension_missing_from_the_run_is_still_red() -> None:
    """A dimension nobody gates on is still evidence, and evidence cannot go quietly absent."""
    results, baseline = _with_ungated()
    del results["dimensions"][_UNGATED]
    verdict = gate.compare(results, baseline)
    assert [finding.status for finding in verdict.findings] == ["MISSING_METRIC"]


def test_the_verdict_names_what_it_did_not_gate() -> None:
    """A gate that quietly stops comparing reads exactly like one that compared and passed."""
    verdict = gate.compare(*_with_ungated())
    assert verdict.failed is False
    report = gate.format_verdict(verdict)
    assert f"NOT GATED dimensions.{_UNGATED}" in report
    assert "#256" in report


def test_failed_conversion_stays_in_the_scored_denominator() -> None:
    """One failed AST conversion must still contribute a zero-score page."""
    results = _results()
    results["pages"] = {
        "expected": 2,
        "annotations": 2,
        "pdfs": 2,
        "converted": 1,
        "scored": 2,
        "unique_ids": 2,
    }
    # The sample scores have to shrink with the manifest: page-003 is the failed conversion that
    # still scores, and a third page would claim a score no manifest entry could have produced.
    for metric, scores in (
        ("edit_distance", {"page-001": 0.1, "page-003": 0.3}),
        ("text_similarity", {"page-001": 0.7, "page-003": 0.9}),
    ):
        dimension = results["dimensions"][metric]
        dimension["sample_scores"] = scores
        dimension["eligible_items"] = 2
        dimension["variance"] = 0.01
    baseline = gate.emit_baseline(
        results,
        {"edit_distance": 0.01, "text_similarity": 0.01},
    )
    verdict = gate.compare(results, baseline)
    assert verdict.findings == []
    assert verdict.failed is False


@pytest.mark.parametrize(
    ("metric", "value", "status", "detail"),
    [
        (
            "text_similarity",
            0.78,
            "REGRESSION",
            "higher is better: baseline 0.8, result 0.78, tolerance 0.01",
        ),
        (
            "text_similarity",
            0.82,
            "UNRECORDED_IMPROVEMENT",
            "higher is better: baseline 0.8, result 0.82, tolerance 0.01",
        ),
        (
            "edit_distance",
            0.22,
            "REGRESSION",
            "lower is better: baseline 0.2, result 0.22, tolerance 0.01",
        ),
        (
            "edit_distance",
            0.18,
            "UNRECORDED_IMPROVEMENT",
            "lower is better: baseline 0.2, result 0.18, tolerance 0.01",
        ),
    ],
)
def test_metric_mutations_are_red_in_both_directions(
    metric: str,
    value: float,
    status: str,
    detail: str,
) -> None:
    """Both metric directions must reject regressions and unrecorded improvements."""
    results = _results()
    _set_metric_value(results, metric, value)
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(status, f"dimensions.{metric}", detail)
    assert verdict.failed is True


def test_a_change_inside_the_recorded_tolerance_is_green() -> None:
    """The inclusive per-metric tolerance must absorb only deliberately recorded noise."""
    results = _results()
    _set_metric_value(results, "text_similarity", 0.81)
    _set_metric_value(results, "edit_distance", 0.19)
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == []
    assert verdict.failed is False


def test_a_missing_metric_is_red() -> None:
    """Dropping a baseline dimension must not shrink coverage into a vacuous pass."""
    results = _results()
    del results["dimensions"]["text_similarity"]
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "MISSING_METRIC",
        "dimensions.text_similarity",
        "baseline metric is missing from result",
    )
    assert verdict.failed is True


def test_an_untracked_stale_metric_is_red() -> None:
    """A result dimension absent from the baseline must force an explicit baseline decision."""
    baseline = _baseline()
    del baseline["dimensions"]["text_similarity"]
    verdict = gate.compare(_results(), baseline)
    assert verdict.findings == _finding(
        "STALE_METRIC",
        "dimensions.text_similarity",
        "result metric is not recorded in baseline",
    )
    assert verdict.failed is True


def test_identity_drift_is_red() -> None:
    """Changing pinned corpus identity must never compare scores from different truth sets."""
    results = _results()
    results["provenance"]["annotation_sha256"] = "0" * 64
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "IDENTITY_DRIFT",
        "provenance.annotation_sha256",
        'expected "2fafe9329dc92fc426b30036aee51c716b3fcdcc1d20cb964dc7670579533817", ' f'got "{"0" * 64}"',
    )
    assert verdict.failed is True


def test_parser_policy_drift_is_red() -> None:
    """A changed OCR policy must not compare scores produced by different parsers."""
    results = _results()
    results["provenance"]["parser_config"]["ocr"]["dpi"] = 300
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "IDENTITY_DRIFT",
        "provenance.parser_config",
        'expected {"layout_analysis_mode": "auto", "ocr": {"dpi": 200, "enabled": true, '
        '"engine": "tesseract", "languages": "eng+chi_sim", "mode": "auto"}}, got '
        '{"layout_analysis_mode": "auto", "ocr": {"dpi": 300, "enabled": true, '
        '"engine": "tesseract", "languages": "eng+chi_sim", "mode": "auto"}}',
    )
    assert verdict.failed is True


def test_a_missing_required_identity_field_is_red() -> None:
    """A missing schema version must fail closed rather than bypass identity comparison."""
    results = _results()
    del results["schema_version"]
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "IDENTITY_DRIFT",
        "schema_version",
        "required identity field is missing from result",
    )
    assert verdict.failed is True


def test_a_missing_page_count_is_red() -> None:
    """Every pipeline-stage count is required so omitted pages cannot disappear silently."""
    results = _results()
    del results["pages"]["pdfs"]
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "MISSING_PAGES",
        "pages.pdfs",
        "required page count is missing",
    )
    assert verdict.failed is True


def test_missing_scored_pages_are_red() -> None:
    """Fewer scored pages than expected must expose a truncated denominator."""
    results = _results()
    results["pages"]["scored"] = 2
    results["pages"]["unique_ids"] = 2
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "MISSING_PAGES",
        "pages.scored",
        "expected 3 scored pages (including conversion failures), got 2",
    )
    assert verdict.failed is True


def test_duplicate_page_ids_are_red() -> None:
    """Repeated scored page IDs must not satisfy the total by raw row count."""
    results = _results()
    results["pages"]["unique_ids"] = 2
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "DUPLICATE_PAGES",
        "pages.unique_ids",
        "3 scored pages contain only 2 unique page IDs",
    )
    assert verdict.failed is True


def test_a_zero_page_run_is_red() -> None:
    """A zero-page result has no evidence and must never be reported as fidelity success."""
    results = _results()
    results["pages"] = dict.fromkeys(results["pages"], 0)
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "ZERO_PAGES",
        "pages.expected",
        "a zero-page run cannot establish fidelity",
    )
    assert verdict.failed is True


def test_a_truncated_page_selection_is_red() -> None:
    """Lowering the run's declared expected count must expose a truncated corpus run."""
    results = _results()
    results["pages"] = {
        "expected": 2,
        "annotations": 2,
        "pdfs": 2,
        "converted": 1,
        "scored": 2,
        "unique_ids": 2,
    }
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "TRUNCATED_PAGES",
        "pages.expected",
        "expected 3 pages from baseline, got 2",
    )
    assert verdict.failed is True


@pytest.mark.parametrize(
    ("value", "status", "detail"),
    [
        (float("nan"), "NONFINITE_VALUE", "got NaN"),
        (1.2, "OUT_OF_RANGE_VALUE", "expected a value in [0, 1], got 1.2"),
    ],
)
def test_nonfinite_and_out_of_range_metric_values_are_red(
    value: float,
    status: str,
    detail: str,
) -> None:
    """Invalid bounded metric values must fail instead of poisoning or flattering comparison."""
    results = _results()
    results["dimensions"]["text_similarity"]["value"] = value
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(status, "dimensions.text_similarity.value", detail)
    assert verdict.failed is True


def test_a_missing_metric_member_is_red() -> None:
    """Omitting a required dimension member must fail before score comparison."""
    results = _results()
    del results["dimensions"]["text_similarity"]["variance"]
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "MISSING_METRIC",
        "dimensions.text_similarity",
        "missing required fields: variance",
    )
    assert verdict.failed is True


def test_an_invalid_metric_direction_is_red() -> None:
    """A direction outside the normalized higher/lower vocabulary must fail closed."""
    results = _results()
    results["dimensions"]["text_similarity"]["direction"] = "sideways"
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "INVALID_DIRECTION",
        "dimensions.text_similarity.direction",
        "direction must be 'higher' or 'lower'",
    )
    assert verdict.failed is True


def test_zero_eligible_items_are_red() -> None:
    """A metric with no scored items must not retain a reassuring aggregate value."""
    results = _results()
    results["dimensions"]["text_similarity"]["eligible_items"] = 0
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "ZERO_ELIGIBLE_ITEMS",
        "dimensions.text_similarity.eligible_items",
        "metric has no eligible items",
    )
    assert verdict.failed is True


def test_zero_variance_is_red() -> None:
    """A zero-variance aggregate must be treated as vacuous oracle output."""
    results = _results()
    results["dimensions"]["text_similarity"]["sample_scores"] = dict.fromkeys(
        results["dimensions"]["text_similarity"]["sample_scores"],
        0.8,
    )
    results["dimensions"]["text_similarity"]["variance"] = 0.0
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "ZERO_VARIANCE",
        "dimensions.text_similarity.variance",
        "zero variance makes the aggregate vacuous",
    )
    assert verdict.failed is True


def test_unreviewed_drift_into_unanimity_stays_red() -> None:
    """Losing all spread against a baseline that recorded spread must still fail.

    Unanimity is the classic vacuous pass: an oracle that stops discriminating reports a
    stable aggregate. Accepting it is a reviewer decision recorded in the baseline, never
    something a run may award itself.
    """
    results = _results()
    scores = results["dimensions"]["text_similarity"]["sample_scores"]
    results["dimensions"]["text_similarity"]["sample_scores"] = dict.fromkeys(scores, 0.8)
    results["dimensions"]["text_similarity"]["value"] = 0.8
    results["dimensions"]["text_similarity"]["variance"] = 0.0
    baseline = _baseline()
    baseline["dimensions"]["text_similarity"]["value"] = 0.8

    statuses = [finding.status for finding in gate.compare(results, baseline).findings]
    assert "ZERO_VARIANCE" in statuses


def test_reviewed_unanimity_recorded_in_the_baseline_is_green() -> None:
    """A genuinely 0/1-per-page metric must have a path through baseline review.

    ``formula_presence_accuracy`` scores one bit per eligible page, so unanimous agreement is
    a real outcome. Firing ZERO_VARIANCE unconditionally made that outcome permanently red
    with no way to accept it, which turns a working gate into one maintainers must disable.
    """
    results = _results()
    scores = results["dimensions"]["text_similarity"]["sample_scores"]
    results["dimensions"]["text_similarity"]["sample_scores"] = dict.fromkeys(scores, 1.0)
    results["dimensions"]["text_similarity"]["value"] = 1.0
    results["dimensions"]["text_similarity"]["variance"] = 0.0
    baseline = _baseline()
    baseline["dimensions"]["text_similarity"]["value"] = 1.0
    baseline["dimensions"]["text_similarity"]["variance"] = 0.0

    verdict = gate.compare(results, baseline)
    assert verdict.findings == []
    assert verdict.failed is False


def test_unanimity_at_the_worst_score_can_never_be_accepted() -> None:
    """A metric that is unanimous at its floor must stay red even if a baseline records it.

    ``baseline.json`` is bootstrapped from a single dispatched run. If that run is degenerate --
    missing OCR models, an empty-text parser path -- every page scores 0.0 with zero variance.
    Letting the baseline accept that unanimity mints a permanently green gate over a broken
    parser and then reports the first working run as ``UNRECORDED_IMPROVEMENT``: the ratchet
    installed upside down. Recording unanimity cannot make a floor score discriminating,
    because nothing can move it further down.
    """
    results = _results()
    scores = results["dimensions"]["text_similarity"]["sample_scores"]
    results["dimensions"]["text_similarity"]["sample_scores"] = dict.fromkeys(scores, 0.0)
    results["dimensions"]["text_similarity"]["value"] = 0.0
    results["dimensions"]["text_similarity"]["variance"] = 0.0
    baseline = _baseline()
    baseline["dimensions"]["text_similarity"]["value"] = 0.0
    baseline["dimensions"]["text_similarity"]["variance"] = 0.0

    verdict = gate.compare(results, baseline)
    assert [finding.status for finding in verdict.findings] == ["ZERO_VARIANCE"]

    with pytest.raises(ValueError, match="ZERO_VARIANCE"):
        gate.emit_baseline(results, default_tolerance=0.005)


def test_zero_metrics_are_red() -> None:
    """Mutually empty dimension mappings must not pass merely because they match."""
    results = _results()
    baseline = _baseline()
    results["dimensions"] = {}
    baseline["dimensions"] = {}
    verdict = gate.compare(results, baseline)
    assert verdict.findings == _finding(
        "ZERO_METRICS",
        "dimensions",
        "a run with no metrics cannot establish fidelity",
    )
    assert verdict.failed is True


def test_an_unexpected_conversion_failure_is_red() -> None:
    """A new failed page must be ratcheted even when total page accounting remains valid."""
    results = _results()
    results["conversion_failures"]["page-002"] = "Parser crashed"
    results["pages"]["converted"] = 1
    results["pages"]["scored"] = 3
    results["pages"]["unique_ids"] = 3
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "UNEXPECTED_CONVERSION_FAILURE",
        "page-002",
        "Parser crashed",
    )
    assert verdict.failed is True


def test_a_fixed_conversion_failure_is_red() -> None:
    """A formerly failing page that converts must require removing its stale allowance."""
    results = _results()
    results["conversion_failures"] = {}
    results["pages"]["converted"] = 3
    results["pages"]["scored"] = 3
    results["pages"]["unique_ids"] = 3
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "FIXED_CONVERSION_FAILURE",
        "page-003",
        "expected 'Encrypted PDF', but page now converts",
    )
    assert verdict.failed is True


def test_a_stale_conversion_failure_reason_is_red() -> None:
    """A changed failure mode must not hide behind an allowance for a different error."""
    results = _results()
    results["conversion_failures"]["page-003"] = "Timeout"
    verdict = gate.compare(results, _baseline())
    assert verdict.findings == _finding(
        "STALE_CONVERSION_FAILURE",
        "page-003",
        "expected 'Encrypted PDF', got 'Timeout'",
    )
    assert verdict.failed is True


def test_an_absent_baseline_is_red() -> None:
    """The first run without a reviewed comparison point must fail rather than self-bless."""
    verdict = gate.compare(_results(), None)
    assert verdict.findings == _finding(
        "ABSENT_BASELINE",
        "baseline",
        "a committed baseline is required",
    )
    assert verdict.failed is True


def test_baseline_emission_copies_identity_metrics_tolerances_and_failures() -> None:
    """Emission must preserve the complete ratchet identity and produce its own green baseline."""
    emitted = gate.emit_baseline(_results(), {"text_similarity": 0.02}, default_tolerance=0.005)
    assert emitted == {
        "schema_version": 3,
        "provenance": RESULTS["provenance"],
        "pages": RESULTS["pages"],
        "dimensions": {
            "edit_distance": {
                "value": 0.2,
                "direction": "lower",
                "eligible_items": 3,
                "variance": 0.006666666666666666,
                "tolerance": 0.005,
            },
            "text_similarity": {
                "value": 0.8,
                "direction": "higher",
                "eligible_items": 3,
                "variance": 0.006666666666666668,
                "tolerance": 0.02,
            },
        },
        "expected_conversion_failures": {"page-003": "Encrypted PDF"},
    }
    assert gate.compare(_results(), emitted).findings == []


def test_cli_formats_findings_concisely_and_returns_failure(tmp_path, capsys) -> None:
    """The CLI must expose an exact one-line red finding and a failing exit status."""
    results = _results()
    _set_metric_value(results, "text_similarity", 0.78)
    results_path = tmp_path / "results.json"
    baseline_path = tmp_path / "baseline.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")
    baseline_path.write_text(json.dumps(_baseline()), encoding="utf-8")
    rc = gate.main([str(results_path), "--baseline", str(baseline_path)])
    assert rc == 1
    assert capsys.readouterr().out == (
        "OMNIDOCBENCH GATE FAIL (1 finding(s))\n"
        "REGRESSION dimensions.text_similarity: higher is better: baseline 0.8, result 0.78, tolerance 0.01\n"
        f"{_NOT_GATED_LINE}\n"
    )


def test_cli_reports_a_missing_baseline_as_a_red_verdict(tmp_path, capsys) -> None:
    """A missing baseline is the documented pre-bootstrap state: red (1), not an error (2).

    Exit 1 means a fidelity verdict and exit 2 means a broken environment. The CLI used to
    print the ABSENT_BASELINE verdict and then return 2, contradicting both the production
    entrypoint and its own behavior for a baseline file containing ``{}``.
    """
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(_results()), encoding="utf-8")
    rc = gate.main([str(results_path), "--baseline", str(tmp_path / "absent.json")])
    assert rc == 1
    assert capsys.readouterr().out == (
        "OMNIDOCBENCH GATE FAIL (1 finding(s))\n"
        "ABSENT_BASELINE baseline: a committed baseline is required\n"
        f"{_NOT_GATED_LINE}\n"
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), None),
        (("provenance", "dataset_revision"), ""),
        (("provenance", "annotation_sha256"), "bad"),
        (("provenance", "oracle_schema_version"), None),
        (("provenance", "parser_config"), []),
        (("provenance", "parser_runtime"), {}),
    ],
)
def test_matching_malformed_baseline_identity_is_red(path: tuple[str, ...], value: object) -> None:
    """Matching malformed identities must not let a result self-authorize."""
    results = _results()
    baseline = _baseline()
    result_target = results
    baseline_target = baseline
    for part in path[:-1]:
        result_target = result_target[part]
        baseline_target = baseline_target[part]
    result_target[path[-1]] = value
    baseline_target[path[-1]] = value

    verdict = gate.compare(results, baseline)

    assert verdict.findings == [
        gate.Finding(
            "INVALID_BASELINE",
            ".".join(path),
            {
                ("schema_version",): "must be integer 3",
                ("provenance", "dataset_revision"): "must be a 40-character lowercase hexadecimal revision",
                ("provenance", "annotation_sha256"): "must be a 64-character lowercase hexadecimal digest",
                ("provenance", "oracle_schema_version"): "must be integer 6",
                ("provenance", "parser_config"): "must be a mapping",
                ("provenance", "parser_runtime"): "must be a non-empty mapping",
            }[path],
        )
    ]


def test_missing_parser_runtime_is_red() -> None:
    """Parser runtime identity is required independently of parser options."""
    results = _results()
    del results["provenance"]["parser_runtime"]

    assert gate.compare(results, _baseline()).findings == _finding(
        "IDENTITY_DRIFT",
        "provenance.parser_runtime",
        "required identity field is missing from result",
    )


def test_malformed_parser_runtime_is_red() -> None:
    """Runtime names and versions must both be non-empty strings."""
    results = _results()
    results["provenance"]["parser_runtime"] = {"tesseract": ""}

    assert gate.compare(results, _baseline()).findings == _finding(
        "IDENTITY_DRIFT",
        "provenance.parser_runtime",
        "names and versions must be non-empty strings",
    )


def test_parser_runtime_drift_is_red() -> None:
    """A parser dependency version change requires a baseline decision."""
    results = _results()
    results["provenance"]["parser_runtime"]["tesseract"] = "5.4.0"

    assert gate.compare(results, _baseline()).findings == _finding(
        "IDENTITY_DRIFT",
        "provenance.parser_runtime",
        'expected {"pymupdf": "1.26.3", "tesseract": "5.3.0"}, ' 'got {"pymupdf": "1.26.3", "tesseract": "5.4.0"}',
    )


@pytest.mark.parametrize("field", ("annotations", "pdfs", "converted", "scored", "unique_ids"))
def test_a_missing_baseline_page_count_is_red(field: str) -> None:
    """Every baseline page-stage count is independently required."""
    baseline = _baseline()
    del baseline["pages"][field]

    assert gate.compare(_results(), baseline).findings == _finding(
        "INVALID_BASELINE",
        f"pages.{field}",
        "required page count is missing from baseline",
    )


@pytest.mark.parametrize("field", ("expected", "annotations", "pdfs", "converted", "scored", "unique_ids"))
def test_a_malformed_baseline_page_count_is_red(field: str) -> None:
    """Baseline counts must remain non-negative integers."""
    baseline = _baseline()
    baseline["pages"][field] = "three"

    assert gate.compare(_results(), baseline).findings == _finding(
        "INVALID_BASELINE",
        f"pages.{field}",
        'expected a non-negative integer, got "three"',
    )


def test_internally_inconsistent_baseline_pages_are_red() -> None:
    """Baseline conversion accounting must include every expected failure."""
    baseline = _baseline()
    baseline["pages"]["converted"] = 1

    assert gate.compare(_results(), baseline).findings == _finding(
        "INVALID_BASELINE",
        "pages.converted",
        "1 converted + 1 expected failures accounts for 2 of 3 pages",
    )


@pytest.mark.parametrize("direction", ([], {}))
def test_unhashable_result_direction_is_red(direction: object) -> None:
    """JSON arrays and objects must become findings rather than TypeError."""
    results = _results()
    results["dimensions"]["text_similarity"]["direction"] = direction

    assert gate.compare(results, _baseline()).findings == _finding(
        "INVALID_DIRECTION",
        "dimensions.text_similarity.direction",
        "direction must be 'higher' or 'lower'",
    )


@pytest.mark.parametrize("direction", ([], {}))
def test_unhashable_baseline_direction_is_red(direction: object) -> None:
    """Malformed baseline directions must return deterministic findings."""
    baseline = _baseline()
    baseline["dimensions"]["text_similarity"]["direction"] = direction

    assert gate.compare(_results(), baseline).findings == _finding(
        "INVALID_BASELINE",
        "dimensions.text_similarity.direction",
        "direction must be 'higher' or 'lower'",
    )


def test_missing_sample_scores_are_red() -> None:
    """An aggregate without exact page evidence must not pass."""
    results = _results()
    del results["dimensions"]["text_similarity"]["sample_scores"]

    assert gate.compare(results, _baseline()).findings == _finding(
        "MISSING_METRIC",
        "dimensions.text_similarity",
        "missing required fields: sample_scores",
    )


def test_declared_aggregate_and_variance_must_match_samples() -> None:
    """Declared metric summaries must be recomputed from exact page scores."""
    results = _results()
    results["dimensions"]["text_similarity"]["sample_scores"] = {
        "page-001": 0.5,
        "page-002": 0.5,
        "page-003": 0.5,
    }
    results["dimensions"]["text_similarity"]["value"] = 0.8
    results["dimensions"]["text_similarity"]["variance"] = 0.1

    assert gate.compare(results, _baseline()).findings == [
        gate.Finding(
            "IDENTITY_DRIFT",
            "dimensions.text_similarity.variance",
            "declared 0.1, recomputed 0.0 from sample_scores",
        ),
        gate.Finding(
            "ZERO_VARIANCE",
            "dimensions.text_similarity.variance",
            "zero variance makes the aggregate vacuous",
        ),
        gate.Finding(
            "IDENTITY_DRIFT",
            "dimensions.text_similarity.value",
            "declared 0.8, recomputed 0.5 from sample_scores",
        ),
        gate.Finding(
            "REGRESSION",
            "dimensions.text_similarity",
            "higher is better: baseline 0.8, result 0.5, tolerance 0.01",
        ),
    ]


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("text_similarity", 0.79),
        ("edit_distance", 0.21),
    ],
)
def test_regression_at_the_tolerance_boundary_is_green(metric: str, value: float) -> None:
    """The recorded tolerance is inclusive on the regression side."""
    results = _results()
    _set_metric_value(results, metric, value)

    assert gate.compare(results, _baseline()).findings == []


def test_cli_rejects_duplicate_json_keys(tmp_path, capsys) -> None:
    """Ambiguous JSON objects must fail before comparison."""
    results_path = tmp_path / "results.json"
    results_path.write_text('{"schema_version": null, "schema_version": 3}', encoding="utf-8")

    assert gate.main([str(results_path), "--emit-baseline"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"OMNIDOCBENCH GATE ERROR: cannot read strict JSON from {results_path}: "
        "duplicate JSON key 'schema_version'\n"
    )


def test_cli_rejects_nonfinite_json_numbers(tmp_path, capsys) -> None:
    """Non-standard NaN tokens must fail strict result loading."""
    results_path = tmp_path / "results.json"
    results_path.write_text('{"score": NaN}', encoding="utf-8")

    assert gate.main([str(results_path), "--emit-baseline"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"OMNIDOCBENCH GATE ERROR: cannot read strict JSON from {results_path}: " "non-finite JSON number NaN\n"
    )


def test_emit_baseline_rejects_invalid_identity() -> None:
    """Baseline emission must not self-bless malformed identity."""
    results = _results()
    results["schema_version"] = None

    with pytest.raises(ValueError, match="INVALID_BASELINE schema_version: must be integer 3"):
        gate.emit_baseline(results)


def test_a_tolerance_of_one_is_rejected_because_no_score_could_ever_breach_it() -> None:
    """Guards the vacuous-tolerance escape.

    Scores live in [0, 1], so a tolerance of 1 or more makes a dimension unable to fail: the worst
    imaginable run still lands inside the band and the gate reports a clean pass. That is the same
    defect ZERO_VARIANCE exists to catch, so the bound must be enforced when the baseline is read,
    not just when it is emitted.
    """
    baseline = _baseline()
    baseline["dimensions"]["text_similarity"]["tolerance"] = 1.0
    results = _results()
    _set_metric_value(results, "text_similarity", 0.0)

    verdict = gate.compare(results, baseline)

    assert verdict.failed
    assert (
        gate.Finding(
            "INVALID_BASELINE",
            "dimensions.text_similarity.tolerance",
            "tolerance must be finite and in [0, 1)",
        )
        in verdict.findings
    )


def test_emit_baseline_refuses_a_tolerance_of_one() -> None:
    """The emitter must reject the same vacuous band the comparator rejects.

    Otherwise `--emit-baseline --default-tolerance 1` would mint a baseline that `compare` then
    refuses, splitting the two halves of the contract.
    """
    with pytest.raises(ValueError, match=r"default tolerance must be finite and in \[0, 1\)"):
        gate.emit_baseline(_results(), default_tolerance=1.0)
    with pytest.raises(ValueError, match=r"tolerance for text_similarity must be finite and in \[0, 1\)"):
        gate.emit_baseline(_results(), {"text_similarity": 1.5})


def test_an_aggregate_within_tolerance_of_the_worst_score_is_vacuous() -> None:
    """Guards the near-floor unanimity escape.

    Exact-floor unanimity was already refused, but a single page scoring one part in a billion made
    the variance non-zero and slipped past. Such a baseline is still permanently green, because no
    later decline can exceed the tolerance from a value already at the floor. The rule therefore
    has to measure distance to the floor against the recorded tolerance.
    """
    results = _results()
    dimension = results["dimensions"]["text_similarity"]
    dimension["sample_scores"] = {"page-001": 0.0, "page-002": 0.0, "page-003": 1e-9}
    dimension["value"] = 1e-9 / 3
    dimension["variance"] = 2.2222222222222224e-19

    verdict = gate.compare(results, _baseline())

    assert verdict.failed
    assert [finding for finding in verdict.findings if finding.status == "ZERO_VARIANCE"] == [
        gate.Finding(
            "ZERO_VARIANCE",
            "dimensions.text_similarity.value",
            f"aggregate {1e-9 / 3} is within the recorded tolerance of the worst score 0.0",
        )
    ]


def test_more_eligible_items_than_manifest_pages_is_a_finding() -> None:
    """Each dimension scores a page at most once, so eligible items cannot exceed the manifest.

    Without this sibling invariant a producer could inflate a weak aggregate by padding
    `sample_scores` with page IDs no manifest entry could have produced, and every other declared
    number would still be self-consistent.
    """
    results = _results()
    baseline = _baseline()
    for payload in (results, baseline):
        payload["dimensions"]["text_similarity"]["eligible_items"] = 4
    results["dimensions"]["text_similarity"]["sample_scores"]["page-004"] = 0.8

    verdict = gate.compare(results, baseline)

    assert verdict.failed
    assert (
        gate.Finding(
            "INVALID_PAGE_COUNT",
            "dimensions.text_similarity.eligible_items",
            "declared 4 eligible items but the manifest holds only 3 pages",
        )
        in verdict.findings
    )


def test_an_integer_too_large_for_a_float_is_a_finding_not_a_traceback() -> None:
    """`math.isfinite` raises OverflowError on a huge int, which JSON permits without notation.

    A hostile or corrupt result file must yield an ordinary finding and exit 1, never an uncaught
    traceback that leaves the run with no verdict at all.
    """
    results = _results()
    results["dimensions"]["text_similarity"]["sample_scores"]["page-001"] = 10**400

    verdict = gate.compare(results, _baseline())

    assert verdict.failed
    assert [finding.status for finding in verdict.findings] == ["OUT_OF_RANGE_VALUE"]


def test_a_dirty_worktree_cannot_match_a_baseline_recorded_from_a_clean_one() -> None:
    """`worktree_dirty` was recorded on both sides but never compared, making it dead evidence.

    The field exists to prove the measurement came from the committed tree, so it has to be an
    identity field like every other provenance entry rather than decoration in the JSON.
    """
    results = _results()
    results["provenance"]["worktree_dirty"] = True

    verdict = gate.compare(results, _baseline())

    assert verdict.failed
    assert (
        gate.Finding(
            "IDENTITY_DRIFT",
            "provenance.worktree_dirty",
            "expected false, got true",
        )
        in verdict.findings
    )


def test_a_baseline_omitting_worktree_dirty_is_invalid() -> None:
    """A baseline predating the field must fail closed rather than silently skip the comparison."""
    baseline = _baseline()
    del baseline["provenance"]["worktree_dirty"]

    verdict = gate.compare(_results(), baseline)

    assert verdict.failed
    assert (
        gate.Finding(
            "INVALID_BASELINE",
            "provenance.worktree_dirty",
            "required identity field is missing from baseline",
        )
        in verdict.findings
    )


def test_new_provenance_evidence_does_not_invalidate_a_recorded_baseline() -> None:
    """Informational provenance must be addable without paying for a new baseline run.

    Corpus characterization is evidence, not identity: the corpus is already pinned by
    ``dataset_revision`` and ``annotation_sha256``, so these counts cannot drift without
    those changing first. The gate compares an explicit allowlist of identity paths, and
    this test pins that property -- adding a field to ``_IDENTITY_FIELDS`` would force an
    ~80-minute re-record of every recorded baseline, which should be a deliberate choice
    rather than a side effect.
    """
    results = _results()
    baseline = _baseline()
    results["provenance"]["corpus_characterization"] = {
        "documents_characterized": 2,
        "pages_characterized": 2,
        "pages_with_text_layer": 0,
        "pages_with_vector_drawings": 0,
        "pages_with_one_full_page_image": 2,
        "documents_ocr_applied": 2,
    }

    assert not gate.compare(results, baseline).failed
    assert "provenance.corpus_characterization" not in gate._IDENTITY_FIELDS
