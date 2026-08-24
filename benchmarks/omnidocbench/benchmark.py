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

#: 3 adds ``strata``: per-data-source aggregates of every scored dimension. Under 2 the
#: payload averaged newspapers, handwritten notes, slides, textbooks and papers into one
#: number per dimension, which could not drive work because it could not say *where* a
#: score was earned or lost (#257). The strata are evidence, not identity: the gate does
#: not compare them, and ``emit_baseline`` does not copy them.
SCHEMA_VERSION = 3
#: 6 projects caption *attributes* (``Figure.caption``, ``Table.caption``,
#: ``Image.caption``) into the AST-side text stream as synthesized paragraphs. Under 5
#: the projection read children only, so a caption the parser correctly bound to its
#: figure vanished from measurement while an unbound one counted -- recall fell as
#: binding improved (#406). The annotation side always counted captions as text blocks,
#: so this removes an asymmetry rather than adding a credit.
#:
#: Still 6 after #443 widened ``_semantic_blocks`` to admit any container of inline text.
#: This gate ratchets against a recorded ``baseline.json``, and the version must equal the
#: one that baseline carries or the lane reports identity drift instead of a fidelity
#: result -- so the number may only move together with a re-recorded baseline, which costs
#: a 981-page OCR run. It is held back because the widening provably cannot reach this
#: lane: it projects the PDF parser's AST, which emits no definition lists and wraps every
#: list item in a ``Paragraph``, and 8 of 8 sampled corpus PDFs project byte-identically
#: across the change. Bump to 7 with the next baseline re-record, whatever prompts it.
ORACLE_SCHEMA_VERSION = 6


class DegradedConversionError(RuntimeError):
    """Requested PDF processing degraded to a fallback path."""


#: Traits describing what a corpus PDF actually contains. Recorded because this lane was
#: built, gated and baselined before anyone asked: every page turned out to be a single
#: full-page raster, so the scores grade OCR rather than the PDF text and table paths, and
#: nothing in the payload said so. Validating the annotation schema checks only one side of
#: the comparison. Characterize the inputs too.
_INPUT_TRAITS = ("text_layer", "vector_drawings", "one_full_page_image")


@dataclass(frozen=True, slots=True)
class InputTraits:
    """How many of a PDF's pages carry each input trait.

    Counted per page rather than sampled from page 1: OmniDocBench's PDFs are one page
    each, but an article PDF opens on a title page that is unrepresentative of the rest.
    """

    pages: int
    text_layer: int
    vector_drawings: int
    one_full_page_image: int


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
    #: What the *input* PDF contains, measured before conversion. ``None`` means the file
    #: could not be characterized at all, which is distinct from "has none of these traits"
    #: and must not be counted as either.
    traits: InputTraits | None = None
    #: Whether the parser actually ran OCR. ``None`` when the page never converted, so a
    #: failed page is not reported as one the parser chose not to OCR.
    ocr_applied: bool | None = None


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


#: Share of a page's area its largest image must cover to read as a scan rather than a
#: figure. Calibrated, not guessed: across 49 pages of scanned journal back-catalogue the
#: largest image covered exactly 100% of every page, while across 101 pages of modern
#: born-digital articles the largest figure reached 61% and the median was 12%.
_FULL_PAGE_IMAGE_COVERAGE = 0.8


def _covers_page(page: Any) -> bool:
    """Report whether any single image on the page covers most of it."""
    area = abs(page.rect.get_area())
    if area <= 0:
        return False
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            if abs(rect.get_area()) / area >= _FULL_PAGE_IMAGE_COVERAGE:
                return True
    return False


def _input_traits(pdf_path: Path) -> InputTraits | None:
    """Count how many of a PDF's pages carry each input trait, or ``None`` if unreadable.

    Deliberately independent of all2md: it reads the file with PyMuPDF directly, so a
    parser change can never quietly alter what the corpus is reported to contain.
    """
    try:
        import fitz
    except ImportError:
        return None
    try:
        with fitz.open(pdf_path) as document:
            pages = text_layer = vector_drawings = one_full_page_image = 0
            for page in document:
                pages += 1
                text_layer += bool(page.get_text().strip())
                vector_drawings += bool(page.get_drawings())
                # Measured by area, not by counting images and assuming: a scan is a raster
                # the size of the page. Requiring "exactly one image and no vector drawings"
                # instead both fired on born-digital pages carrying a single figure and
                # missed scans that ship a second small raster beside the page image.
                one_full_page_image += _covers_page(page)
            return InputTraits(
                pages=pages,
                text_layer=text_layer,
                vector_drawings=vector_drawings,
                one_full_page_image=one_full_page_image,
            )
    except Exception:  # noqa: BLE001 - characterization is evidence, never a reason to fail a page
        return None


def _ocr_applied(document: Any) -> bool:
    """Report whether the parser actually ran OCR, rather than inferring it from emptiness."""
    metadata = document.metadata if isinstance(document.metadata, Mapping) else {}
    confidence = metadata.get("confidence")
    signals = confidence.get("signals") if isinstance(confidence, Mapping) else None
    fraction = signals.get("ocr_page_fraction") if isinstance(signals, Mapping) else None
    return isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and fraction > 0


def _evaluate_page(
    page: CorpusPage,
    truth: GroundTruthPage,
    ocr_languages: str,
) -> PageEvaluation:
    from all2md import to_ast

    started = time.perf_counter()
    # Measured before conversion, so a page that fails to convert still reports what it was.
    traits = _input_traits(page.pdf_path)
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
            traits=traits,
            ocr_applied=_ocr_applied(document),
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
            traits=traits,
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


def _input_shape_clause(evaluations: list[PageEvaluation]) -> str:
    """Summarize what the inputs are, so an erased dimension carries its own counter-reading."""
    measured = [result.traits for result in evaluations if result.traits is not None]
    pages = sum(traits.pages for traits in measured)
    if pages == 0:
        return "; see provenance.corpus_characterization"
    rasters = sum(traits.one_full_page_image for traits in measured)
    return (
        f" ({rasters} of {pages} characterized page(s) are a full-page image); "
        f"see provenance.corpus_characterization"
    )


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
    # Naming only the parser reads as a parser gap, and on this corpus that reading is wrong:
    # every page is a full-page raster, so the PDF table path never runs at all. State both
    # sides and the input shape, and let the reader assign the cause.
    shape = _input_shape_clause(evaluations)
    if predicted_tables == 0:
        metric_names -= {"table_structure_similarity", "table_content_similarity"}
        unsupported["table_fidelity"] = (
            f"no Table nodes on any of the {converted} converted page(s); "
            f"{eligible_tables} page(s) carry table ground truth. This alone does not "
            f"separate a parser gap from the corpus's input shape{shape}"
        )
    if predicted_formulas == 0:
        metric_names -= {"formula_presence_accuracy", "formula_content_similarity"}
        unsupported["formula_fidelity"] = (
            f"no MathBlock or MathInline nodes on any of the {converted} converted page(s); "
            f"{eligible_formulas} page(s) carry formula ground truth. This alone does not "
            f"separate a parser gap from the corpus's input shape{shape}"
        )

    dimensions: dict[str, dict[str, Any]] = {}
    for name in sorted(metric_names):
        dimension = _dimension(evaluations, name)
        if dimension is not None:
            dimensions[name] = dimension

    # Per-stratum aggregates of the same dimensions. Evidence, not identity: the gate does
    # not compare these and `emit_baseline` does not copy them, so a stratum shifting does
    # not invalidate a baseline -- but a reader can finally see whether a mean moved on
    # newspapers or on handwritten notes (#257). `sample_scores` and `direction` are not
    # repeated per stratum; both live on the corresponding top-level dimension.
    strata: dict[str, dict[str, Any]] = {}
    for stratum in sorted({page.stratum for page in ground_truth.values()}):
        member_ids = {page_id for page_id, page in ground_truth.items() if page.stratum == stratum}
        members = [result for result in evaluations if result.page_id in member_ids]
        stratum_dimensions: dict[str, dict[str, Any]] = {}
        for name in sorted(metric_names):
            dimension = _dimension(members, name)
            if dimension is not None:
                stratum_dimensions[name] = {
                    "value": dimension["value"],
                    "eligible_items": dimension["eligible_items"],
                    "variance": dimension["variance"],
                }
        strata[stratum] = {"pages": len(members), "dimensions": stratum_dimensions}

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
    measured = [result.traits for result in evaluations if result.traits is not None]
    corpus_characterization = {
        # Both denominators, because they diverge the moment a corpus item is an article
        # rather than a page, and a page count over an unstated number of files says little.
        "documents_characterized": len(measured),
        "pages_characterized": sum(traits.pages for traits in measured),
        **{f"pages_with_{trait}": sum(getattr(traits, trait) for traits in measured) for trait in _INPUT_TRAITS},
        # Document-level: the parser reports OCR per conversion, not per page.
        "documents_ocr_applied": sum(1 for result in evaluations if result.ocr_applied),
    }
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
            # Evidence, not identity: the corpus is already pinned immutably by
            # dataset_revision and annotation_sha256, so these counts cannot drift without
            # those changing. Deliberately absent from the gate's _IDENTITY_FIELDS, which
            # is what lets them be added without invalidating a recorded baseline.
            "corpus_characterization": corpus_characterization,
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
        "strata": strata,
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
