#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_layout.py
"""PDF document layout analysis utilities.

This private module wraps the optional pymupdf-layout model for
classifying text blocks by semantic role (title, section-header,
text, list-item, table, page-header, page-footer, caption, footnote,
picture, formula).

The model is a lightweight Graph Neural Network (GNN) that classifies
blocks based on spatial features (position, font size, spacing) and
relationships to neighboring blocks, running on CPU via ONNX runtime.

Requires: pip install all2md[pdf_layout]
License note: pymupdf-layout uses Polyform Noncommercial license.
Commercial use requires an Artifex license.

"""

from __future__ import annotations

import contextlib
import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from all2md.constants import DEFAULT_LAYOUT_FEATURE_SET

if TYPE_CHECKING:
    import pymupdf

__all__ = [
    "LayoutPrediction",
    "PageLayoutPredictions",
    "get_layout_model",
    "predict_page_layout",
    "match_predictions_to_blocks",
    "annotate_lines_with_layout",
    "is_layout_available",
    "native_find_tables",
]

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def native_find_tables() -> Iterator[None]:
    """Force PyMuPDF's native ``find_tables()`` within the block.

    Importing ``pymupdf.layout`` runs its module-level ``activate()``, which
    installs a *process-global* hook (``pymupdf._get_layout``). PyMuPDF's
    ``find_tables()`` consults that hook and, when present, reroutes table
    detection through the GNN layout model instead of its native ruling-line
    algorithm. On many real documents that model path is worse for our
    purposes: it overdetects tables (spurious sub-grids) and reconstructs cell
    text with dropped inter-word spaces and punctuation, because the model's
    predicted cell boundaries disagree with the ruling-line grid that
    ``Table.extract()`` then reads against.

    all2md drives layout analysis explicitly via :func:`predict_page_layout`
    and merges those predictions itself (header/footer trimming, list and
    table-region supplementation), so the implicit ``find_tables()`` hook is
    redundant and actively harmful. The whole table pipeline — and the corpus
    benchmark it was tuned against — assumes native ``find_tables()`` output.

    This context manager nulls the hook for the duration of the block and
    restores the prior value on exit, so it both guarantees native behavior
    for our ``find_tables()`` / ``Table.extract()`` calls and leaves global
    state untouched for any other consumer in the same process. It is a no-op
    when the hook was never installed (``pymupdf.layout`` not imported).

    The hook is read off the canonical ``pymupdf`` module, but ``fitz`` (the
    legacy alias) can be a distinct module object in some installs, so both are
    neutralized defensively.
    """
    sentinel = object()
    saved: list[tuple[Any, Any]] = []
    for name in ("pymupdf", "fitz"):
        mod: Any = sys.modules.get(name)
        if mod is None:
            continue
        saved.append((mod, getattr(mod, "_get_layout", sentinel)))
        mod._get_layout = None
    try:
        yield
    finally:
        for mod, prev in saved:
            if prev is sentinel:
                with contextlib.suppress(AttributeError):
                    delattr(mod, "_get_layout")
            else:
                mod._get_layout = prev


@dataclass(frozen=True)
class LayoutPrediction:
    """A single layout prediction for a region on a page.

    Attributes
    ----------
    x0 : float
        Left edge of the predicted region.
    y0 : float
        Top edge of the predicted region.
    x1 : float
        Right edge of the predicted region.
    y1 : float
        Bottom edge of the predicted region.
    label : str
        Semantic label: title, section-header, text, list-item, table,
        page-header, page-footer, caption, footnote, picture, formula.

    """

    x0: float
    y0: float
    x1: float
    y1: float
    label: str

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return bounding box as a tuple."""
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class PageLayoutPredictions:
    """All layout predictions for a single page, with block-level mapping.

    Attributes
    ----------
    predictions : list[LayoutPrediction]
        Raw predictions from the layout model.
    block_labels : dict[int, str]
        Mapping from block index to the matched semantic label.

    """

    predictions: list[LayoutPrediction] = field(default_factory=list)
    block_labels: dict[int, str] = field(default_factory=dict)

    def get_block_label(self, block_index: int) -> str | None:
        """Return the layout label for a given block index, or None."""
        return self.block_labels.get(block_index)

    def has_label(self, label: str) -> bool:
        """Check if any prediction has the given label."""
        return any(p.label == label for p in self.predictions)

    def get_predictions_by_label(self, label: str) -> list[LayoutPrediction]:
        """Return all predictions with the given label."""
        return [p for p in self.predictions if p.label == label]


#: Loaded models, keyed by feature set. Keyed rather than a singleton because the feature
#: set selects a *different* ONNX model, and a caller that switches sets mid-process -- the
#: optimizer searching this knob does exactly that -- would otherwise silently keep getting
#: whichever model was loaded first, making every arm of the search identical.
_layout_models: dict[str, Any] = {}


def is_layout_available() -> bool:
    """Check if pymupdf-layout is importable."""
    try:
        from pymupdf.layout import DocumentLayoutAnalyzer  # noqa: F401

        return True
    except ImportError:
        return False


def get_layout_model(feature_set: str = DEFAULT_LAYOUT_FEATURE_SET) -> Any:
    """Get or create the cached layout analysis model for a feature set.

    Models are cached per feature set and reused across pages and documents; loading one
    costs several MB of ONNX weights, and a search over this knob revisits each value many
    times.

    Parameters
    ----------
    feature_set : str
        Which classifier to load -- see `LayoutFeatureSet`.

    Returns
    -------
    Any
        The GNN layout model instance.

    Raises
    ------
    ImportError
        If pymupdf-layout is not installed.

    """
    if feature_set not in _layout_models:
        from pymupdf.layout import DocumentLayoutAnalyzer

        _layout_models[feature_set] = DocumentLayoutAnalyzer.get_model(feature_set_name=feature_set)
        logger.debug("Loaded pymupdf-layout GNN model (feature_set=%s)", feature_set)
    return _layout_models[feature_set]


def predict_page_layout(page: "pymupdf.Page", feature_set: str = DEFAULT_LAYOUT_FEATURE_SET) -> list[LayoutPrediction]:
    """Run layout prediction on a single page.

    Parameters
    ----------
    page : pymupdf.Page
        PDF page to analyze.
    feature_set : str
        Which classifier to run -- see `LayoutFeatureSet`.

    Returns
    -------
    list[LayoutPrediction]
        Predicted regions with semantic labels.

    """
    model = get_layout_model(feature_set)
    raw_predictions = model.predict(page)
    # raw_predictions: list of [x0, y0, x1, y1, label_str]

    predictions = [
        LayoutPrediction(
            x0=float(pred[0]),
            y0=float(pred[1]),
            x1=float(pred[2]),
            y1=float(pred[3]),
            label=str(pred[4]),
        )
        for pred in raw_predictions
    ]

    if predictions:
        labels = {p.label for p in predictions}
        logger.debug("Layout analysis: %d regions, labels=%s", len(predictions), labels)

    return predictions


def _compute_iou(
    box_a: tuple[float, float, float, float],
    box_b: tuple[float, float, float, float],
) -> float:
    """Compute Intersection over Union between two bounding boxes.

    Parameters
    ----------
    box_a : tuple of float
        First bounding box (x0, y0, x1, y1).
    box_b : tuple of float
        Second bounding box (x0, y0, x1, y1).

    Returns
    -------
    float
        IoU value in [0.0, 1.0].

    """
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])

    if x0 >= x1 or y0 >= y1:
        return 0.0

    intersection = (x1 - x0) * (y1 - y0)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def match_predictions_to_blocks(
    predictions: list[LayoutPrediction],
    blocks: list[dict],
    iou_threshold: float = 0.3,
) -> PageLayoutPredictions:
    """Match layout predictions to text blocks by IoU overlap.

    Each text block is assigned the label of the prediction with the
    highest IoU overlap, provided it exceeds ``iou_threshold``.

    Parameters
    ----------
    predictions : list[LayoutPrediction]
        Layout model predictions for the page.
    blocks : list[dict]
        Text blocks from ``page.get_text("dict")``.
    iou_threshold : float
        Minimum IoU to consider a match.

    Returns
    -------
    PageLayoutPredictions
        Predictions with block-level label mapping.

    """
    block_labels: dict[int, str] = {}

    for block_idx, block in enumerate(blocks):
        bbox = block.get("bbox")
        if not bbox:
            continue

        best_iou = 0.0
        best_label: str | None = None

        for pred in predictions:
            iou = _compute_iou(tuple(bbox), pred.bbox)
            if iou > best_iou:
                best_iou = iou
                best_label = pred.label

        if best_iou >= iou_threshold and best_label is not None:
            block_labels[block_idx] = best_label

    logger.debug("Matched %d/%d blocks to layout labels", len(block_labels), len(blocks))
    return PageLayoutPredictions(predictions=predictions, block_labels=block_labels)


def annotate_lines_with_layout(
    blocks: list[dict],
    predictions: list[LayoutPrediction],
    coverage_threshold: float = 0.5,
) -> int:
    """Stamp ``_layout_label`` onto each *line* a prediction covers.

    :func:`match_predictions_to_blocks` assigns labels per block, by IoU. That works when
    a block is one semantic unit, and fails whenever it is not: PyMuPDF returns a whole
    journal column as a single block, so a two-line section heading inside it has an IoU of
    roughly 0.03 against its own block and the label is discarded. Measured on the PMC
    corpus, 54% of ``section-header`` predictions never reached a block, the median offender
    being a block 38x the area of the prediction.

    Coverage of the *line* answers the question the matcher was really asking -- "did the
    model draw a box around this text" -- without depending on how PyMuPDF happened to group
    it. IoU is wrong at this granularity: a line inside a large correct region has a low IoU
    with it, so containment is the test, in the same direction the table-region filter uses.

    Parameters
    ----------
    blocks : list[dict]
        Text blocks from ``page.get_text("dict")``; their lines are mutated in place.
    predictions : list[LayoutPrediction]
        Layout model predictions for the page.
    coverage_threshold : float
        Share of the line's area a prediction must cover to claim it.

    Returns
    -------
    int
        Number of lines stamped, for logging.

    """
    import pymupdf

    if not predictions:
        return 0

    rects = [(pred, pymupdf.Rect(pred.bbox)) for pred in predictions]
    stamped = 0
    for block in blocks:
        for line in block.get("lines", ()):
            bbox = line.get("bbox")
            if bbox is None:
                continue
            rect = pymupdf.Rect(bbox)
            area = abs(rect)
            if area <= 0:
                continue
            best_label: str | None = None
            best_share = coverage_threshold
            for pred, pred_rect in rects:
                share = abs(rect & pred_rect) / area
                # Strict improvement, so the first prediction wins a tie -- predictions
                # arrive in the model's own order and a stable choice keeps the same page
                # producing the same output across runs.
                if share > best_share:
                    best_share = share
                    best_label = pred.label
            if best_label is not None:
                line["_layout_label"] = best_label
                stamped += 1

    logger.debug("Stamped %d line(s) with layout labels", stamped)
    return stamped


def annotate_blocks_with_layout(
    blocks: list[dict],
    layout: PageLayoutPredictions,
) -> None:
    """Stamp ``_layout_label`` onto each block dict that has a matched label.

    This allows the label to travel with the block through all downstream
    processing (column detection, filtering, etc.) without threading
    the ``PageLayoutPredictions`` object everywhere.

    Parameters
    ----------
    blocks : list[dict]
        Text blocks (mutated in place).
    layout : PageLayoutPredictions
        Predictions with block-level mapping.

    """
    for block_idx, label in layout.block_labels.items():
        if block_idx < len(blocks):
            blocks[block_idx]["_layout_label"] = label
