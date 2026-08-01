"""Fail-closed ratchet for normalized OmniDocBench fidelity results."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, cast

HERE = Path(__file__).resolve().parent
DEFAULT_BASELINE = HERE / "baseline.json"
_DATASET_REVISION_RE = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED_SCHEMA_VERSION = 2
_SUPPORTED_ORACLE_SCHEMA_VERSION = 4

_IDENTITY_FIELDS = (
    "schema_version",
    "provenance.dataset_revision",
    "provenance.annotation_sha256",
    "provenance.oracle_schema_version",
    "provenance.parser_config",
    "provenance.parser_runtime",
    "provenance.worktree_dirty",
)
_PAGE_FIELDS = ("expected", "annotations", "pdfs", "converted", "scored", "unique_ids")
_DIMENSION_FIELDS = ("value", "direction", "eligible_items", "variance")
_RESULT_DIMENSION_FIELDS = (*_DIMENSION_FIELDS, "sample_scores")


@dataclass(frozen=True)
class Finding:
    """One fail-closed result from comparing a run with its baseline."""

    status: str
    subject: str
    detail: str


@dataclass
class Verdict:
    """The complete, deterministically ordered gate verdict."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        """Return whether any finding was recorded.

        Every status this module emits is red, so membership in a status allow-list would
        only create a way for a newly added status to pass silently.
        """
        return bool(self.findings)


def _nested(payload: Mapping[str, Any], dotted_path: str) -> tuple[bool, Any]:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return False, None
        value = value[part]
    return True, value


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(value: Any) -> bool:
    if not _number(value):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # A JSON integer literal too large for a float must become a finding, not a traceback.
        return False


def _page_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _repr(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _add(verdict: Verdict, status: str, subject: str, detail: str) -> None:
    verdict.findings.append(Finding(status, subject, detail))


def _identity_error(path: str, value: Any) -> str | None:
    if path == "schema_version":
        if not isinstance(value, int) or isinstance(value, bool) or value != _SUPPORTED_SCHEMA_VERSION:
            return f"must be integer {_SUPPORTED_SCHEMA_VERSION}"
    elif path == "provenance.dataset_revision":
        if not isinstance(value, str) or _DATASET_REVISION_RE.fullmatch(value) is None:
            return "must be a 40-character lowercase hexadecimal revision"
    elif path == "provenance.annotation_sha256":
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            return "must be a 64-character lowercase hexadecimal digest"
    elif path == "provenance.oracle_schema_version":
        if not isinstance(value, int) or isinstance(value, bool) or value != _SUPPORTED_ORACLE_SCHEMA_VERSION:
            return f"must be integer {_SUPPORTED_ORACLE_SCHEMA_VERSION}"
    elif path == "provenance.parser_config":
        if not isinstance(value, Mapping):
            return "must be a mapping"
        if set(value) != {"layout_analysis_mode", "ocr"}:
            return "must contain exactly layout_analysis_mode and ocr"
        if not isinstance(value["layout_analysis_mode"], str) or not value["layout_analysis_mode"]:
            return "layout_analysis_mode must be a non-empty string"
        ocr = value["ocr"]
        if not isinstance(ocr, Mapping):
            return "ocr must be a mapping"
        if set(ocr) != {"enabled", "engine", "mode", "languages", "dpi"}:
            return "ocr must contain exactly enabled, engine, mode, languages, and dpi"
        if not isinstance(ocr["enabled"], bool):
            return "ocr.enabled must be a boolean"
        for field in ("engine", "mode", "languages"):
            if not isinstance(ocr[field], str) or not ocr[field]:
                return f"ocr.{field} must be a non-empty string"
        if not isinstance(ocr["dpi"], int) or isinstance(ocr["dpi"], bool) or ocr["dpi"] <= 0:
            return "ocr.dpi must be a positive integer"
    elif path == "provenance.parser_runtime":
        if not isinstance(value, Mapping) or not value:
            return "must be a non-empty mapping"
        if any(
            not isinstance(name, str) or not name or not isinstance(version, str) or not version
            for name, version in value.items()
        ):
            return "names and versions must be non-empty strings"
    elif path == "provenance.worktree_dirty":
        # Recorded on both sides and compared for equality like every other identity field, so a
        # measurement taken from an unclean tree can never match a baseline recorded from a clean
        # one. Requiring False outright would make the field unusable in a baseline candidate.
        if not isinstance(value, bool):
            return "must be a boolean"
    return None


def _baseline_page_values(
    baseline: Mapping[str, Any],
    expected_failure_count: int | None,
    verdict: Verdict,
) -> dict[str, int]:
    pages = baseline.get("pages")
    if not isinstance(pages, Mapping):
        _add(verdict, "INVALID_BASELINE", "pages", "required pages mapping is missing")
        return {}

    values: dict[str, int] = {}
    for name in _PAGE_FIELDS:
        if name not in pages:
            _add(
                verdict,
                "INVALID_BASELINE",
                f"pages.{name}",
                "required page count is missing from baseline",
            )
        elif not _page_count(pages[name]):
            _add(
                verdict,
                "INVALID_BASELINE",
                f"pages.{name}",
                f"expected a non-negative integer, got {_repr(pages[name])}",
            )
        else:
            values[name] = pages[name]

    expected = values.get("expected")
    if expected is None:
        return values
    if expected == 0:
        _add(
            verdict,
            "INVALID_BASELINE",
            "pages.expected",
            "baseline must record a positive expected page count",
        )
        return values
    for name in ("annotations", "pdfs", "scored", "unique_ids"):
        value = values.get(name)
        if value is not None and value != expected:
            _add(
                verdict,
                "INVALID_BASELINE",
                f"pages.{name}",
                f"must equal pages.expected {expected}, got {value}",
            )
    converted = values.get("converted")
    if converted is not None and expected_failure_count is not None:
        accounted = converted + expected_failure_count
        if accounted != expected:
            _add(
                verdict,
                "INVALID_BASELINE",
                "pages.converted",
                f"{converted} converted + {expected_failure_count} expected failures "
                f"accounts for {accounted} of {expected} pages",
            )
    return values


def _check_identity(results: Mapping[str, Any], baseline: Mapping[str, Any], verdict: Verdict) -> None:
    for path in _IDENTITY_FIELDS:
        result_present, actual = _nested(results, path)
        baseline_present, expected = _nested(baseline, path)
        if not baseline_present:
            _add(verdict, "INVALID_BASELINE", path, "required identity field is missing from baseline")
            continue
        baseline_error = _identity_error(path, expected)
        if baseline_error is not None:
            _add(verdict, "INVALID_BASELINE", path, baseline_error)
            continue
        if not result_present:
            _add(verdict, "IDENTITY_DRIFT", path, "required identity field is missing from result")
            continue
        result_error = _identity_error(path, actual)
        if result_error is not None:
            _add(verdict, "IDENTITY_DRIFT", path, result_error)
        elif actual != expected:
            _add(
                verdict,
                "IDENTITY_DRIFT",
                path,
                f"expected {_repr(expected)}, got {_repr(actual)}",
            )


def _check_pages(
    results: Mapping[str, Any],
    baseline: Mapping[str, Any],
    failure_count: int | None,
    expected_failure_count: int | None,
    verdict: Verdict,
) -> None:
    baseline_values = _baseline_page_values(baseline, expected_failure_count, verdict)
    pages = results.get("pages")
    if not isinstance(pages, Mapping):
        _add(verdict, "MISSING_PAGES", "pages", "required pages mapping is missing")
        return

    values: dict[str, int] = {}
    for name in _PAGE_FIELDS:
        if name not in pages:
            _add(verdict, "MISSING_PAGES", f"pages.{name}", "required page count is missing")
        elif not _page_count(pages[name]):
            _add(
                verdict,
                "INVALID_PAGE_COUNT",
                f"pages.{name}",
                f"expected a non-negative integer, got {_repr(pages[name])}",
            )
        else:
            values[name] = pages[name]

    expected = values.get("expected")
    if expected == 0:
        _add(verdict, "ZERO_PAGES", "pages.expected", "a zero-page run cannot establish fidelity")
        return

    baseline_expected = baseline_values.get("expected")
    if expected is not None and baseline_expected is not None:
        if expected < baseline_expected:
            _add(
                verdict,
                "TRUNCATED_PAGES",
                "pages.expected",
                f"expected {baseline_expected} pages from baseline, got {expected}",
            )
        elif expected > baseline_expected:
            _add(
                verdict,
                "IDENTITY_DRIFT",
                "pages.expected",
                f"expected {baseline_expected}, got {expected}",
            )

    if expected is None:
        return

    for name in ("annotations", "pdfs"):
        actual = values.get(name)
        if actual == 0:
            _add(verdict, "ZERO_PAGES", f"pages.{name}", f"no {name} were available")
        elif actual is not None and actual < expected:
            _add(
                verdict,
                "MISSING_PAGES",
                f"pages.{name}",
                f"expected {expected}, got {actual}",
            )
        elif actual is not None and actual > expected:
            _add(
                verdict,
                "INVALID_PAGE_COUNT",
                f"pages.{name}",
                f"count {actual} exceeds pages.expected {expected}",
            )

    converted = values.get("converted")
    if converted == 0:
        _add(verdict, "ZERO_PAGES", "pages.converted", "no pages converted successfully")
    elif converted is not None and failure_count is not None:
        accounted = converted + failure_count
        if accounted < expected:
            _add(
                verdict,
                "MISSING_PAGES",
                "pages.converted",
                f"{converted} converted + {failure_count} failures accounts for {accounted} of {expected} pages",
            )
        elif accounted > expected:
            _add(
                verdict,
                "INVALID_PAGE_COUNT",
                "pages.converted",
                f"{converted} converted + {failure_count} failures exceeds {expected} pages",
            )

    scored = values.get("scored")
    if scored == 0:
        _add(verdict, "ZERO_PAGES", "pages.scored", "no page projections were scored")
    elif scored is not None:
        if scored < expected:
            _add(
                verdict,
                "MISSING_PAGES",
                "pages.scored",
                f"expected {expected} scored pages (including conversion failures), got {scored}",
            )
        elif scored > expected:
            _add(
                verdict,
                "INVALID_PAGE_COUNT",
                "pages.scored",
                f"scored pages {scored} exceeds pages.expected {expected}",
            )

    unique_ids = values.get("unique_ids")
    if unique_ids == 0:
        _add(verdict, "ZERO_PAGES", "pages.unique_ids", "no unique scored page IDs were recorded")
    elif unique_ids is not None and scored is not None:
        if unique_ids < scored:
            _add(
                verdict,
                "DUPLICATE_PAGES",
                "pages.unique_ids",
                f"{scored} scored pages contain only {unique_ids} unique page IDs",
            )
        elif unique_ids > scored:
            _add(
                verdict,
                "INVALID_PAGE_COUNT",
                "pages.unique_ids",
                f"unique IDs {unique_ids} exceeds scored pages {scored}",
            )


def _valid_baseline_dimension(name: str, dimension: Any, verdict: Verdict) -> bool:
    subject = f"dimensions.{name}"
    if not isinstance(dimension, Mapping):
        _add(verdict, "INVALID_BASELINE", subject, "baseline metric must be a mapping")
        return False
    missing = [field for field in (*_DIMENSION_FIELDS, "tolerance") if field not in dimension]
    if missing:
        _add(
            verdict,
            "INVALID_BASELINE",
            subject,
            f"missing required fields: {', '.join(missing)}",
        )
        return False
    direction = dimension["direction"]
    if not isinstance(direction, str) or direction not in {"higher", "lower"}:
        _add(verdict, "INVALID_BASELINE", f"{subject}.direction", "direction must be 'higher' or 'lower'")
        return False
    if not _finite(dimension["value"]) or not 0 <= dimension["value"] <= 1:
        _add(verdict, "INVALID_BASELINE", f"{subject}.value", "value must be finite and in [0, 1]")
        return False
    tolerance = dimension["tolerance"]
    if not _finite(tolerance) or not 0 <= tolerance < 1:
        # A tolerance of 1 or more is vacuous for the same reason a zero-variance aggregate is: no
        # score in [0, 1] can ever breach it, so the dimension stops being able to fail.
        _add(verdict, "INVALID_BASELINE", f"{subject}.tolerance", "tolerance must be finite and in [0, 1)")
        return False
    if (
        not isinstance(dimension["eligible_items"], int)
        or isinstance(dimension["eligible_items"], bool)
        or dimension["eligible_items"] <= 0
    ):
        _add(verdict, "INVALID_BASELINE", f"{subject}.eligible_items", "eligible_items must be a positive integer")
        return False
    # A metric may legitimately be unanimous (formula presence is 0/1 per page). Accepting
    # that requires recording it, so drifting into unanimity is still red.
    if not _finite(dimension["variance"]) or dimension["variance"] < 0:
        _add(verdict, "INVALID_BASELINE", f"{subject}.variance", "variance must be finite and non-negative")
        return False
    return True


def _check_dimension_direction(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    subject: str,
    verdict: Verdict,
) -> tuple[Any, bool]:
    direction = actual["direction"]
    valid = isinstance(direction, str) and direction in {"higher", "lower"}
    if not valid:
        _add(verdict, "INVALID_DIRECTION", f"{subject}.direction", "direction must be 'higher' or 'lower'")
    elif direction != expected["direction"]:
        _add(
            verdict,
            "IDENTITY_DRIFT",
            f"{subject}.direction",
            f"expected {_repr(expected['direction'])}, got {_repr(direction)}",
        )
    return direction, valid


def _check_dimension_eligible_items(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    subject: str,
    verdict: Verdict,
) -> tuple[Any, bool]:
    eligible = actual["eligible_items"]
    valid = isinstance(eligible, int) and not isinstance(eligible, bool) and eligible >= 0
    if not valid:
        _add(
            verdict,
            "OUT_OF_RANGE_VALUE",
            f"{subject}.eligible_items",
            f"expected a non-negative integer, got {_repr(eligible)}",
        )
    elif eligible == 0:
        _add(verdict, "ZERO_ELIGIBLE_ITEMS", f"{subject}.eligible_items", "metric has no eligible items")
    elif eligible != expected["eligible_items"]:
        _add(
            verdict,
            "IDENTITY_DRIFT",
            f"{subject}.eligible_items",
            f"expected {expected['eligible_items']}, got {eligible}",
        )
    return eligible, valid


def _dimension_sample_values(
    actual: Mapping[str, Any],
    subject: str,
    verdict: Verdict,
) -> list[float] | None:
    samples = actual["sample_scores"]
    if not isinstance(samples, Mapping):
        _add(verdict, "MISSING_METRIC", f"{subject}.sample_scores", "sample_scores must be a mapping")
        return None
    if not samples:
        _add(verdict, "ZERO_ELIGIBLE_ITEMS", f"{subject}.sample_scores", "metric has no sample scores")
        return None
    invalid_samples = sorted(
        str(page_id)
        for page_id, sample in samples.items()
        if not isinstance(page_id, str) or not page_id or not _finite(sample) or not 0 <= sample <= 1
    )
    if invalid_samples:
        _add(
            verdict,
            "OUT_OF_RANGE_VALUE",
            f"{subject}.sample_scores",
            f"page IDs must be non-empty strings and scores finite in [0, 1]: {', '.join(invalid_samples)}",
        )
        return None
    return [float(samples[page_id]) for page_id in sorted(samples)]


def _check_dimension_summary(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    subject: str,
    direction: Any,
    direction_valid: bool,
    computed_value: float,
    computed_variance: float,
    verdict: Verdict,
) -> None:
    variance = actual["variance"]
    variance_valid = _finite(variance) and variance >= 0
    if not _finite(variance):
        _add(verdict, "NONFINITE_VALUE", f"{subject}.variance", f"got {_repr(variance)}")
    elif variance < 0:
        _add(verdict, "OUT_OF_RANGE_VALUE", f"{subject}.variance", f"expected a non-negative value, got {variance}")
    elif not math.isclose(variance, computed_variance, rel_tol=1e-12, abs_tol=1e-15):
        _add(
            verdict,
            "IDENTITY_DRIFT",
            f"{subject}.variance",
            f"declared {variance}, recomputed {computed_variance} from sample_scores",
        )
    # A metric whose recorded aggregate sits within its own tolerance of its worst possible score
    # is vacuous by construction: recording it cannot make it discriminating, because no further
    # decline can exceed the tolerance. Accepting that would let one degenerate bootstrap run mint
    # a permanently green baseline and then report the first working run as an improvement. The
    # test is against the tolerance rather than exact equality with the floor, because a single
    # page scoring one part in a billion is enough to make the variance non-zero.
    worst = 0.0 if direction == "higher" else 1.0
    floor_bound = expected.get("tolerance")
    at_the_floor = _finite(floor_bound) and abs(computed_value - worst) <= float(cast(float, floor_bound))
    if computed_variance == 0 and (expected.get("variance") != 0 or computed_value == worst):
        _add(verdict, "ZERO_VARIANCE", f"{subject}.variance", "zero variance makes the aggregate vacuous")
    elif at_the_floor:
        _add(
            verdict,
            "ZERO_VARIANCE",
            f"{subject}.value",
            f"aggregate {computed_value} is within the recorded tolerance of the worst score {worst}",
        )

    value = actual["value"]
    value_valid = _finite(value) and 0 <= value <= 1
    value_matches_samples = value_valid and math.isclose(
        value,
        computed_value,
        rel_tol=1e-12,
        abs_tol=1e-15,
    )
    if not _finite(value):
        _add(verdict, "NONFINITE_VALUE", f"{subject}.value", f"got {_repr(value)}")
    elif not 0 <= value <= 1:
        _add(verdict, "OUT_OF_RANGE_VALUE", f"{subject}.value", f"expected a value in [0, 1], got {value}")
    elif not value_matches_samples:
        _add(
            verdict,
            "IDENTITY_DRIFT",
            f"{subject}.value",
            f"declared {value}, recomputed {computed_value} from sample_scores",
        )

    if not direction_valid or not value_valid or not variance_valid:
        return
    baseline_value = expected["value"]
    tolerance = expected["tolerance"]
    signed_change = computed_value - baseline_value
    displayed_value = value if value_matches_samples else computed_value
    quality_change = signed_change if direction == "higher" else -signed_change
    if quality_change < -tolerance and not math.isclose(
        quality_change,
        -tolerance,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        _add(
            verdict,
            "REGRESSION",
            subject,
            f"{direction} is better: baseline {baseline_value}, result {displayed_value}, tolerance {tolerance}",
        )
    elif quality_change > tolerance and not math.isclose(
        quality_change,
        tolerance,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        _add(
            verdict,
            "UNRECORDED_IMPROVEMENT",
            subject,
            f"{direction} is better: baseline {baseline_value}, result {displayed_value}, tolerance {tolerance}",
        )


def _check_result_dimension(
    name: str,
    actual: Any,
    expected: Mapping[str, Any],
    verdict: Verdict,
    page_bound: int | None,
) -> None:
    subject = f"dimensions.{name}"
    if not isinstance(actual, Mapping):
        _add(verdict, "MISSING_METRIC", subject, "metric must be a mapping")
        return
    missing = [field for field in _RESULT_DIMENSION_FIELDS if field not in actual]
    if missing:
        _add(verdict, "MISSING_METRIC", subject, f"missing required fields: {', '.join(missing)}")
        return

    direction, direction_valid = _check_dimension_direction(actual, expected, subject, verdict)
    eligible, eligible_valid = _check_dimension_eligible_items(actual, expected, subject, verdict)
    sample_values = _dimension_sample_values(actual, subject, verdict)
    if sample_values is None:
        return
    if eligible_valid and eligible > 0 and eligible != len(sample_values):
        _add(
            verdict,
            "IDENTITY_DRIFT",
            f"{subject}.eligible_items",
            f"declared {eligible}, but sample_scores contains {len(sample_values)} items",
        )
    if eligible_valid and page_bound is not None and eligible > page_bound:
        # Each dimension scores a page at most once, so more eligible items than pages in the
        # manifest means the aggregate was padded with entries no page could have produced.
        _add(
            verdict,
            "INVALID_PAGE_COUNT",
            f"{subject}.eligible_items",
            f"declared {eligible} eligible items but the manifest holds only {page_bound} pages",
        )

    computed_value = statistics.fmean(sample_values)
    computed_variance = statistics.pvariance(sample_values) if len(sample_values) > 1 else 0.0
    _check_dimension_summary(
        actual,
        expected,
        subject,
        direction,
        direction_valid,
        computed_value,
        computed_variance,
        verdict,
    )


def _check_dimensions(
    results: Mapping[str, Any],
    baseline: Mapping[str, Any],
    verdict: Verdict,
    *,
    pages_coherent: bool = True,
) -> None:
    actual_dimensions = results.get("dimensions")
    baseline_dimensions = baseline.get("dimensions")
    pages = results.get("pages")
    # Bound eligibility against the manifest size, which is the largest number of pages any single
    # dimension could have scored.
    page_bound = pages.get("expected") if isinstance(pages, Mapping) else None
    if not pages_coherent or not _page_count(page_bound):
        page_bound = None
    if not isinstance(baseline_dimensions, Mapping):
        _add(verdict, "INVALID_BASELINE", "dimensions", "required dimensions mapping is missing")
        return
    if not isinstance(actual_dimensions, Mapping):
        _add(verdict, "MISSING_METRIC", "dimensions", "required dimensions mapping is missing")
        return
    if not baseline_dimensions and not actual_dimensions:
        _add(verdict, "ZERO_METRICS", "dimensions", "a run with no metrics cannot establish fidelity")
        return

    baseline_names = set(baseline_dimensions)
    actual_names = set(actual_dimensions)
    for name in sorted(baseline_names - actual_names):
        _add(verdict, "MISSING_METRIC", f"dimensions.{name}", "baseline metric is missing from result")
    for name in sorted(actual_names - baseline_names):
        _add(verdict, "STALE_METRIC", f"dimensions.{name}", "result metric is not recorded in baseline")
    for name in sorted(baseline_names & actual_names):
        expected = baseline_dimensions[name]
        if _valid_baseline_dimension(name, expected, verdict):
            _check_result_dimension(name, actual_dimensions[name], expected, verdict, page_bound)


def _failure_mapping(
    payload: Mapping[str, Any], field: str, verdict: Verdict, baseline: bool = False
) -> Mapping[str, str] | None:
    value = payload.get(field)
    status = "INVALID_BASELINE" if baseline else "MISSING_PAGES"
    if not isinstance(value, Mapping):
        _add(verdict, status, field, "required page-ID-to-error mapping is missing")
        return None
    bad = sorted(
        str(page_id)
        for page_id, error in value.items()
        if not isinstance(page_id, str) or not page_id or not isinstance(error, str) or not error
    )
    if bad:
        _add(verdict, status, field, f"page IDs and errors must be non-empty strings: {', '.join(bad)}")
        return None
    return value


def _check_failures(
    actual: Mapping[str, str] | None,
    expected: Mapping[str, str] | None,
    verdict: Verdict,
) -> None:
    if actual is None or expected is None:
        return
    actual_ids = set(actual)
    expected_ids = set(expected)
    for page_id in sorted(actual_ids - expected_ids):
        _add(
            verdict,
            "UNEXPECTED_CONVERSION_FAILURE",
            page_id,
            actual[page_id],
        )
    for page_id in sorted(expected_ids - actual_ids):
        _add(
            verdict,
            "FIXED_CONVERSION_FAILURE",
            page_id,
            f"expected {expected[page_id]!r}, but page now converts",
        )
    for page_id in sorted(actual_ids & expected_ids):
        if actual[page_id] != expected[page_id]:
            _add(
                verdict,
                "STALE_CONVERSION_FAILURE",
                page_id,
                f"expected {expected[page_id]!r}, got {actual[page_id]!r}",
            )


def compare(results: Any, baseline: Any) -> Verdict:
    """Compare normalized results with a baseline, returning every red finding."""
    verdict = Verdict()
    if not baseline:
        _add(verdict, "ABSENT_BASELINE", "baseline", "a committed baseline is required")
        return verdict
    if not isinstance(baseline, Mapping):
        _add(verdict, "INVALID_BASELINE", "baseline", "baseline must be a mapping")
        return verdict
    if not isinstance(results, Mapping):
        _add(verdict, "IDENTITY_DRIFT", "result", "normalized result must be a mapping")
        return verdict

    _check_identity(results, baseline, verdict)
    actual_failures = _failure_mapping(results, "conversion_failures", verdict)
    expected_failures = _failure_mapping(baseline, "expected_conversion_failures", verdict, baseline=True)
    pages_before = len(verdict.findings)
    _check_pages(
        results,
        baseline,
        len(actual_failures) if actual_failures is not None else None,
        len(expected_failures) if expected_failures is not None else None,
        verdict,
    )
    # The per-dimension eligibility bound is only meaningful once the page counts agree with the
    # baseline. When they do not, the deficit is already reported against `pages` and repeating it
    # for every dimension would bury that finding.
    _check_dimensions(results, baseline, verdict, pages_coherent=len(verdict.findings) == pages_before)
    _check_failures(actual_failures, expected_failures, verdict)
    return verdict


def emit_baseline(
    results: Mapping[str, Any],
    tolerances: Mapping[str, float] | None = None,
    *,
    default_tolerance: float = 0.0,
) -> dict[str, Any]:
    """Create a reviewable baseline which makes an unchanged valid run green."""
    if not _finite(default_tolerance) or not 0 <= default_tolerance < 1:
        raise ValueError("default tolerance must be finite and in [0, 1)")
    tolerances = tolerances or {}
    if not isinstance(results, Mapping):
        raise TypeError("benchmark results must be a JSON object")
    result_dimensions = results.get("dimensions", {})
    if not isinstance(result_dimensions, Mapping):
        raise TypeError("benchmark results dimensions must be a JSON object")
    unknown = set(tolerances) - set(result_dimensions)
    if unknown:
        raise ValueError(f"tolerances provided for unknown metrics: {', '.join(sorted(unknown))}")

    dimensions: dict[str, dict[str, Any]] = {}
    for name, metric in sorted(result_dimensions.items()):
        tolerance = tolerances.get(name, default_tolerance)
        if not _finite(tolerance) or not 0 <= tolerance < 1:
            raise ValueError(f"tolerance for {name} must be finite and in [0, 1)")
        dimensions[name] = {
            "value": metric["value"],
            "direction": metric["direction"],
            "eligible_items": metric["eligible_items"],
            "variance": metric["variance"],
            "tolerance": tolerance,
        }

    candidate = {
        "schema_version": results["schema_version"],
        "provenance": dict(results["provenance"]),
        "pages": dict(results["pages"]),
        "dimensions": dimensions,
        "expected_conversion_failures": dict(sorted(results["conversion_failures"].items())),
    }
    verdict = compare(results, candidate)
    if verdict.failed:
        raise ValueError("refusing to emit an invalid baseline:\n" + format_verdict(verdict))
    return candidate


def format_verdict(verdict: Verdict) -> str:
    """Render a concise one-line-per-finding CLI verdict."""
    if not verdict.findings:
        return "OMNIDOCBENCH GATE PASS"
    lines = [f"OMNIDOCBENCH GATE FAIL ({len(verdict.findings)} finding(s))"]
    lines.extend(f"{finding.status} {finding.subject}: {finding.detail}" for finding in verdict.findings)
    return "\n".join(lines)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key {key!r}")
        payload[key] = value
    return payload


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_json,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read strict JSON from {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmarks.omnidocbench.gate", description=__doc__)
    parser.add_argument("results", type=Path, help="normalized result JSON")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="committed ratchet baseline")
    parser.add_argument("--emit-baseline", action="store_true", help="emit a baseline instead of comparing")
    parser.add_argument("--tolerance", type=float, default=0.0, help="default tolerance for emitted metrics")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line gate."""
    args = _build_parser().parse_args(argv)
    try:
        results = _load_json(args.results)
        if args.emit_baseline:
            emitted = emit_baseline(results, default_tolerance=args.tolerance)
            print(json.dumps(emitted, indent=2, sort_keys=True))
            return 0
        # A missing baseline is the documented pre-bootstrap state: a red verdict, not a broken
        # environment. compare() reports ABSENT_BASELINE for a falsy baseline.
        baseline = _load_json(args.baseline) if args.baseline.is_file() else {}
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        print(f"OMNIDOCBENCH GATE ERROR: {exc}", file=sys.stderr)
        return 2
    verdict = compare(results, baseline)
    print(format_verdict(verdict))
    return 1 if verdict.failed else 0


if __name__ == "__main__":
    sys.exit(main())
