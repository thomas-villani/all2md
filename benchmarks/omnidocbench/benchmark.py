"""Run all2md AST projections against pinned OmniDocBench annotations."""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .corpus import ANNOTATION_SHA256, CorpusPage, CorpusSnapshot
from .oracles import GroundTruthPage, PageProjection, project_annotation, project_ast, score_page

if TYPE_CHECKING:
    from all2md.options.pdf import PdfOptions

SCHEMA_VERSION = 2
ORACLE_SCHEMA_VERSION = 3


class DegradedConversionError(RuntimeError):
    """Requested PDF processing degraded to a fallback path."""


@dataclass(frozen=True, slots=True)
class PageEvaluation:
    """Direct external-ground-truth scores for one page."""

    page_id: str
    scores: Mapping[str, float]
    predicted_tables: int
    predicted_formulas: int
    duration_seconds: float
    degraded_events: tuple[str, ...] = ()
    error_type: str | None = None
    error: str | None = None


def _pdf_options(ocr_languages: str) -> PdfOptions:
    """Build the fixed PDF parser policy used by the external benchmark."""
    from all2md.options.common import OCROptions
    from all2md.options.pdf import PdfOptions

    return PdfOptions(
        layout_analysis_mode="enabled",
        ocr=OCROptions(
            enabled=True,
            mode="auto",
            engine="tesseract",
            languages=ocr_languages,
            dpi=200,
        ),
    )


def load_ground_truth(snapshot: CorpusSnapshot) -> dict[str, GroundTruthPage]:
    """Load supported annotation facts directly from the pinned JSON file."""
    try:
        records = json.loads(snapshot.annotation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read pinned annotation JSON: {exc}") from exc
    if not isinstance(records, list):
        raise ValueError("OmniDocBench annotation root must be an array")

    projected: dict[str, GroundTruthPage] = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError("OmniDocBench annotation contains a non-object page")
        page = project_annotation(raw)
        if page.page_id in projected:
            raise ValueError(f"duplicate annotation page ID: {page.page_id}")
        projected[page.page_id] = page

    selected_ids = {page.page_id for page in snapshot.pages}
    missing = sorted(selected_ids - projected.keys())
    if missing:
        raise ValueError(f"selected PDFs have no annotations: {missing[:5]}")
    return {page_id: projected[page_id] for page_id in sorted(selected_ids)}


# A deliberate non-tabular rejection is a correct parser decision, and the table and
# reading-order metrics already score its outcome. Zeroing every dimension on the page would
# turn correct behavior into a whole-page fidelity failure.
_MEASURABLE_DEGRADED_KINDS = frozenset({"table_rejected"})


def _degraded_conversion(document: Any) -> str | None:
    metadata = document.metadata if isinstance(document.metadata, Mapping) else {}
    confidence = metadata.get("confidence")
    events = confidence.get("degraded_events") if isinstance(confidence, Mapping) else None
    if not isinstance(events, list):
        return None
    blocking = [
        event
        for event in events
        if not (isinstance(event, Mapping) and event.get("kind") in _MEASURABLE_DEGRADED_KINDS)
    ]
    if not blocking:
        return None
    return json.dumps(blocking, sort_keys=True, ensure_ascii=False, default=str)


def _degraded_kinds(document: Any) -> tuple[str, ...]:
    """Return every degraded-event kind so an exempted degradation still leaves evidence."""
    metadata = document.metadata if isinstance(document.metadata, Mapping) else {}
    confidence = metadata.get("confidence")
    events = confidence.get("degraded_events") if isinstance(confidence, Mapping) else None
    if not isinstance(events, list):
        return ()
    return tuple(sorted(str(event["kind"]) for event in events if isinstance(event, Mapping) and "kind" in event))


def _evaluate_page(
    page: CorpusPage,
    truth: GroundTruthPage,
    ocr_languages: str,
) -> PageEvaluation:
    from all2md import to_ast

    started = time.perf_counter()
    try:
        document = to_ast(
            page.pdf_path,
            source_format="pdf",
            parser_options=_pdf_options(ocr_languages),
        )
        degraded = _degraded_conversion(document)
        if degraded is not None:
            raise DegradedConversionError(degraded)
        actual = project_ast(document)
        return PageEvaluation(
            page_id=page.page_id,
            scores=score_page(truth.projection, actual),
            predicted_tables=len(actual.tables),
            predicted_formulas=len(actual.formulas),
            duration_seconds=time.perf_counter() - started,
            degraded_events=_degraded_kinds(document),
        )
    except Exception as exc:  # noqa: BLE001 - failed pages stay in every applicable denominator
        empty = PageProjection((), (), (), ())
        failure_scores = dict.fromkeys(score_page(truth.projection, empty), 0.0)
        return PageEvaluation(
            page_id=page.page_id,
            scores=failure_scores,
            predicted_tables=0,
            predicted_formulas=0,
            duration_seconds=time.perf_counter() - started,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def evaluate_corpus(
    snapshot: CorpusSnapshot,
    ground_truth: Mapping[str, GroundTruthPage],
    *,
    ocr_languages: str = "eng+chi_sim",
) -> list[PageEvaluation]:
    """Call ``to_ast`` once per page and score its projection independently."""
    results = [_evaluate_page(page, ground_truth[page.page_id], ocr_languages) for page in snapshot.pages]
    results.sort(key=lambda result: result.page_id)
    if len({result.page_id for result in results}) != len(snapshot.pages):
        raise RuntimeError("evaluation did not produce one unique result per selected PDF")
    return results


def _dimension(
    evaluations: list[PageEvaluation],
    name: str,
) -> dict[str, Any] | None:
    samples = {result.page_id: float(result.scores[name]) for result in evaluations if name in result.scores}
    if not samples:
        return None
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in samples.values()):
        raise ValueError(f"oracle emitted an invalid score for {name}")
    values = list(samples.values())
    return {
        "value": statistics.fmean(values),
        "direction": "higher",
        "eligible_items": len(values),
        "variance": statistics.pvariance(values) if len(values) > 1 else 0.0,
        "sample_scores": dict(sorted(samples.items())),
    }


def normalize_results(
    *,
    snapshot: CorpusSnapshot,
    ground_truth: Mapping[str, GroundTruthPage],
    evaluations: list[PageEvaluation],
    all2md_commit: str,
    worktree_dirty: bool = False,
    parser_runtime: Mapping[str, str],
    ocr_languages: str = "eng+chi_sim",
) -> dict[str, Any]:
    """Build the deterministic fail-closed ratchet input."""
    metric_names = {name for evaluation in evaluations for name in evaluation.scores}
    predicted_tables = sum(result.predicted_tables for result in evaluations)
    predicted_formulas = sum(result.predicted_formulas for result in evaluations)
    converted = sum(1 for result in evaluations if result.error_type is None)
    unsupported: dict[str, str] = {}
    # Union-scoped scoring never awards a perfect score here: without the erasure these
    # dimensions would be uniformly 0.0 across every eligible page, which the ratchet reds as a
    # vacuous aggregate. The message names both sides, so the payload still shows how many pages
    # needed the erased dimension instead of only how many pages converted.
    eligible_tables = sum(1 for page in ground_truth.values() if page.projection.tables)
    eligible_formulas = sum(1 for page in ground_truth.values() if page.projection.formulas)
    if predicted_tables == 0:
        metric_names -= {"table_structure_similarity", "table_content_similarity"}
        unsupported["table_fidelity"] = (
            f"all2md emitted no Table nodes on {converted} converted page(s); "
            f"{eligible_tables} pages have table ground truth"
        )
    if predicted_formulas == 0:
        metric_names -= {"formula_presence_accuracy", "formula_content_similarity"}
        unsupported["formula_fidelity"] = (
            f"all2md emitted no MathBlock or MathInline nodes on {converted} converted page(s); "
            f"{eligible_formulas} pages have formula ground truth"
        )

    dimensions: dict[str, dict[str, Any]] = {}
    for name in sorted(metric_names):
        dimension = _dimension(evaluations, name)
        if dimension is not None:
            dimensions[name] = dimension

    failures = {
        result.page_id: f"{result.error_type}: {result.error}"
        for result in evaluations
        if result.error_type is not None
    }
    unscored: Counter[str] = Counter()
    explicitly_ignored = 0
    for page in ground_truth.values():
        unscored.update(page.unscored_categories)
        explicitly_ignored += page.explicitly_ignored

    successful = sum(result.error_type is None for result in evaluations)
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "dataset_revision": snapshot.revision,
            "annotation_sha256": ANNOTATION_SHA256,
            "oracle_schema_version": ORACLE_SCHEMA_VERSION,
            "all2md_commit": all2md_commit,
            "worktree_dirty": worktree_dirty,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "platform": sys.platform,
            "parser_runtime": dict(sorted(parser_runtime.items())),
            "parser_config": {
                "layout_analysis_mode": "enabled",
                "ocr": {
                    "enabled": True,
                    "engine": "tesseract",
                    "mode": "auto",
                    "languages": ocr_languages,
                    "dpi": 200,
                },
            },
        },
        "pages": {
            "expected": snapshot.expected_pages,
            "annotations": len(ground_truth),
            "pdfs": len(snapshot.pages),
            "converted": successful,
            "scored": len(evaluations),
            "unique_ids": len({result.page_id for result in evaluations}),
        },
        "dimensions": dimensions,
        "conversion_failures": failures,
        "unsupported_dimensions": unsupported,
        "unscored_annotation_categories": dict(sorted(unscored.items())),
        "degraded_events": dict(
            sorted(Counter(kind for result in evaluations for kind in result.degraded_events).items())
        ),
        "explicitly_ignored_annotations": explicitly_ignored,
    }


def write_result(payload: Mapping[str, Any], path: Path) -> Path:
    """Write normalized benchmark evidence as strict JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path
